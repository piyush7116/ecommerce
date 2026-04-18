from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import Product, Contact, Orders, OrderUpdate, Payment, OrderItem, OTPRecord, MerchantProfile
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from math import ceil
import json
import random
import requests as req_lib
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse
from django.core.mail import send_mail
from .forms import ProductForm, MerchantRegistrationForm, MerchantLoginForm
import datetime


from django.http import HttpResponseBadRequest
import razorpay
from .models import Payment

# Initialize Razorpay client - will be recreated per request
razorpay_client = razorpay.Client(auth=(settings.RAZOR_KEY_ID, settings.RAZOR_KEY_SECRET))

def get_razorpay_client():
    """Create a fresh Razorpay client instance with current settings."""
    try:
        client = razorpay.Client(auth=(settings.RAZOR_KEY_ID, settings.RAZOR_KEY_SECRET))
        return client
    except Exception as e:
        print(f"Failed to create Razorpay client: {e}")
        raise

def index(request):
    allProds=[]
    catprods=Product.objects.values('category','id')
    cats={item['category'] for item in catprods}
    for cat in cats:
        prod=Product.objects.filter(category=cat)
        n=len(prod)
        nslides=n//4+ceil((n/4)-n//4)
        allProds.append([prod,range(1,nslides),nslides])
    params={'allProds':allProds}
    return render(request,'shop/index.html',params)

# def searchMatch(query,item):
#     if query in item.desc.lower() or query in item.product_name.lower() or query in item.category.lower():
#         return True    
#     else:
#         return False
def searchMatch(query, item):
    query = query.lower()
    return (
        query in item.desc.lower() or
        query in item.product_name.lower() or
        query in item.category.lower()
    )
#universal sentence encoder  
#scit learn (ML)
# wrod to vec
# how to convert string to vector


def search(request):
    query = request.GET.get('search', '').strip()
    allProds = []

    # ✅ FIRST validation (important)
    if len(query) < 4:
        return render(request, 'shop/search.html', {
            'msg': 'Please enter a relevant search query (min 4 characters)'
        })

    catprods = Product.objects.values('category', 'id')
    cats = {item['category'] for item in catprods}

    for cat in cats:
        prodtemp = Product.objects.filter(category=cat)
        prod = [item for item in prodtemp if searchMatch(query, item)]

        if prod:
            n = len(prod)
            nslides = n // 4 + ceil((n / 4) - n // 4)
            allProds.append([prod, range(1, nslides), nslides])

    # ✅ NO results found
    if not allProds:
        return render(request, 'shop/search.html', {
            'msg': 'No products found for your search'
        })

    return render(request, 'shop/search.html', {
        'allProds': allProds,
        'query': query
    })


def about(request):
    return render(request,'shop/about.html')

def contact(request):
    thank=False
    if request.method=="POST":
        name=request.POST.get('name','')
        email=request.POST.get('email','')
        phone=request.POST.get('phone','')
        desc=request.POST.get('message','')
        contact=Contact(name=name, email=email, phone=phone, desc=desc)
        contact.save()
        thank=True
    return render(request,'shop/contact.html',{'thank':thank})

def tracker(request):
    if request.method=="POST":
        orderID=request.POST.get('inputOrderID','')
        email=request.POST.get('inputEmail4','')
        try:
            order=Orders.objects.filter(order_id=orderID,email=email)
            if len(order)>0:
                update=OrderUpdate.objects.filter(order_id=orderID)
                updates=[]
                for item in update:
                    updates.append({'text':item.update_desc,'time':item.timestamp})
                response=json.dumps({ "status":"success","updates":updates,"itemJson":order[0].item_Json},default=str)
                return HttpResponse(response)
            else:
                return HttpResponse('{"status":"noitem"}')
        except Exception as e:
                return HttpResponse('{"status":"error"}')
    return render(request,'shop/tracker.html')


def productview(request, myid):
    # Fetch the specific product
    product = Product.objects.get(id=myid)
    # Send it to the template
    return render(request, 'shop/productView.html', {'product': product})


def checkout(request):
    thank=False
    id=None
    razorpay_order_id = None
    razorpay_merchant_key = None
    
    if request.method=="POST":
        itemJson=request.POST.get('itemJson','')
        name=request.POST.get('inputname','')
        amount_str = request.POST.get("amount", "0")
        
        try:
            amount = Decimal(amount_str)
        except (InvalidOperation, ValueError):
            amount = Decimal('0')

        email=request.POST.get('inputEmail4','')
        address1=request.POST.get('inputAddress','')
        address2=request.POST.get('inputAddress2','')
        city=request.POST.get('inputCity','')
        state=request.POST.get('inputState','')
        zip=request.POST.get('inputZip','')
        phone=request.POST.get('phone','')
        
        # Save email in session so we can show orders later
        request.session['customer_email'] = email
        
        # Save order first
        # Save order first with Pending status
        order=Orders(name=name, amount=amount, item_Json=itemJson, email=email, address=address1+", "+address2, city=city, state=state, zip_code=zip, phone=phone, payment_status="Pending")
        order.save()

        # We delay "Order Placed Successfully" update until payment is verified (unless COD)
        # update=OrderUpdate(order_id=order.order_id, update_desc="Order Placed Successfully")
        # update.save()

        id=order.order_id
        if not request.POST.get('pay_with_razorpay'):
            order.payment_status = "Success" # COD/Other
            order.save()
            OrderUpdate(order_id=order.order_id, update_desc="Order Placed Successfully (COD)").save()
            # For COD, we still want to create OrderItems
            create_order_items(order)
            thank = True
        
        # Only create a Razorpay order when the user explicitly chose to pay now
        razorpay_order_id = None
        razorpay_merchant_key = None
        if request.POST.get('pay_with_razorpay'):
            # Create Razorpay order
            amount_in_paise = int(amount * 100)  # Convert to paise
            currency = 'INR'
            try:
                razorpay_order = razorpay_client.order.create(
                    dict(amount=amount_in_paise, currency=currency, payment_capture=1)
                )

                # Save payment record (store amount in paise as integer)
                Payment.objects.create(
                    razorpay_order_id=razorpay_order['id'],
                    amount=amount_in_paise,
                    order_id=order.order_id,
                    status='Created'
                )

                razorpay_order_id = razorpay_order['id']
                razorpay_merchant_key = settings.RAZOR_KEY_ID
            except Exception as e:
                print(f"Razorpay Order Creation Error: {e}")
    
    # Always pass these to template, include submitted values so form doesn't clear
    context = {
        'thank': thank,
        'id': id,
        'razorpay_order_id': razorpay_order_id,
        'razorpay_merchant_key': settings.RAZOR_KEY_ID,
        'inputname': name if 'name' in locals() else '',
        'inputEmail4': email if 'email' in locals() else '',
        'phone': phone if 'phone' in locals() else '',
        'inputAddress': address1 if 'address1' in locals() else '',
        'inputAddress2': address2 if 'address2' in locals() else '',
        'inputCity': city if 'city' in locals() else '',
        'inputState': state if 'state' in locals() else '',
        'inputZip': zip if 'zip' in locals() else '',
        'itemJson': itemJson if 'itemJson' in locals() else '',
        'amount': str(amount) if 'amount' in locals() else '',
        'razorpay_amount': amount_in_paise if 'amount_in_paise' in locals() else None,
    }
    
    return render(request, 'shop/checkout.html', context)






# from django.http import HttpResponseBadRequest
# import razorpay
# from .models import Payment

# # Initialize Razorpay client
# razorpay_client = razorpay.Client(auth=(settings.RAZOR_KEY_ID, settings.RAZOR_KEY_SECRET))

# def homepage(request):
#     amount = 20000  # Rs. 200 in paise
#     currency = 'INR'

#     # Create Razorpay order
#     razorpay_order = razorpay_client.order.create(
#         dict(amount=amount, currency=currency, payment_capture='0')
#     )
    
#     # Save order in database
#     Payment.objects.create(
#         razorpay_order_id=razorpay_order['id'],
#         amount=amount,
#         status='Created'
#     )

#     context = {
#         'razorpay_order_id': razorpay_order['id'],
#         'razorpay_merchant_key': settings.RAZOR_KEY_ID,
#         'razorpay_amount': amount,
#         'currency': currency,
#         'callback_url': '/paymenthandler/'
#     }
#     return render(request, 'index.html', context)


@csrf_exempt
def handlerequest(request):
    if request.method == "POST":
        payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_order_id = request.POST.get('razorpay_order_id', '')
        signature = request.POST.get('razorpay_signature', '')

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }

        try:
            # Verify payment signature
            razorpay_client = get_razorpay_client()
            razorpay_client.utility.verify_payment_signature(params_dict)
            
            # Capture payment
            payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
            razorpay_client.payment.capture(payment_id, payment.amount)

            # Update payment record
            payment.razorpay_payment_id = payment_id
            payment.razorpay_signature = signature
            payment.status = 'Success'
            payment.save()
            # Record an order update for tracker
            try:
                if payment.order_id:
                    OrderUpdate(order_id=payment.order_id, update_desc="Payment received via Razorpay.").save()
            except Exception as e:
                print(f"DEBUG: Failed to create OrderUpdate in handlerequest: {e}")

            return render(request, 'shop/paymentsuccess.html')
        except razorpay.errors.SignatureVerificationError:
            # Update payment as failed
            Payment.objects.filter(razorpay_order_id=razorpay_order_id).update(status='Failed')
            return render(request, 'shop/paymentfail.html')
        except Exception as e:
            return HttpResponseBadRequest(str(e))
    else:
        return HttpResponseBadRequest("Invalid request method")


@csrf_exempt
def create_order(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'invalid json'}, status=400)

    # Extract fields
    name = payload.get('name', '')
    email = payload.get('email', '')
    phone = payload.get('phone', '')
    address1 = payload.get('address1', '')
    address2 = payload.get('address2', '')
    city = payload.get('city', '')
    state = payload.get('state', '')
    zip_code = payload.get('zip', '')
    itemJson = payload.get('itemJson', '{}')
    amount_str = payload.get('amount', '0')
    try:
        amount = Decimal(str(amount_str))
    except Exception:
        amount = Decimal('0')

    # Save order
    order = Orders(name=name, amount=amount, item_Json=itemJson, email=email,
                   address=address1 + ", " + address2, city=city, state=state,
                   zip_code=zip_code, phone=phone)
    order.save()

    # Save order update status
    OrderUpdate(order_id=order.order_id, update_desc="Order Placed Successfully").save()

    # Create razorpay order
    amount_in_paise = int(amount * 100)
    currency = 'INR'
    try:
        razorpay_client = get_razorpay_client()
        print(f"DEBUG: Creating Razorpay order with amount {amount_in_paise} paise using key {settings.RAZOR_KEY_ID[:10]}...")
        razorpay_order = razorpay_client.order.create(
            dict(amount=amount_in_paise, currency=currency, payment_capture=1) # 1 for auto-capture
        )
        print(f"DEBUG: Razorpay order created: {razorpay_order['id']}")
        # Save payment record
        Payment.objects.create(
            razorpay_order_id=razorpay_order['id'],
            amount=amount_in_paise,
            order_id=order.order_id,
            status='Created'
        )
    except Exception as e:
        return JsonResponse({'error': 'razorpay_create_failed', 'details': str(e)}, status=500)

    return JsonResponse({
        'order_id': razorpay_order['id'],
        'amount': amount_in_paise,
        'key': settings.RAZOR_KEY_ID,
        'order_db_id': order.order_id,
    })


@csrf_exempt
def verify_payment(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("POST required")
    
    # Handle both JSON (AJAX) and Form data (Redirect)
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({'error': 'invalid json'}, status=400)
    else:
        data = request.POST.dict()

    payment_id = data.get('razorpay_payment_id')
    razorpay_order_id = data.get('razorpay_order_id')
    signature = data.get('razorpay_signature')

    if not (payment_id and razorpay_order_id and signature):
        if request.content_type == 'application/json':
            return JsonResponse({'error': 'missing fields'}, status=400)
        else:
            return render(request, 'shop/paymentfail.html', {'reason': 'Missing payment fields'})

    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    }

    try:
        razorpay_client = get_razorpay_client()
        razorpay_client.utility.verify_payment_signature(params_dict)
    except Exception as e:
        # mark failed
        print(f"DEBUG: Signature verification failed: {e}")
        Payment.objects.filter(razorpay_order_id=razorpay_order_id).update(status='Failed')
        return JsonResponse({'status': 'failed', 'reason': 'signature_verification_failed', 'details': str(e)})

    try:
        razorpay_client = get_razorpay_client()
        payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
        order = Orders.objects.get(order_id=payment.order_id)
        
        # In auto-capture mode (payment_capture=1), we skip the explicit capture call
        # but we still verify the signature
        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.status = 'Success'
        payment.save()

        # Update order status
        order.payment_status = "Success"
        order.save()
        
        print(f"DEBUG: Payment verified for order {order.order_id}")

        # Record an order update so tracker shows payment confirmation
        OrderUpdate(order_id=order.order_id, update_desc="Payment received via Razorpay. Order Placed Successfully.").save()
        
        # Create individual OrderItem records for merchants
        create_order_items(order)
        
        print(f"DEBUG: Payment {payment_id} captured successfully")
        
        if request.content_type == 'application/json':
            return JsonResponse({'status': 'success'})
        else:
            return render(request, 'shop/paymentsuccess.html', {'order': order})
            
    except Exception as e:
        print(f"DEBUG: Payment capture failed: {e}")
        Payment.objects.filter(razorpay_order_id=razorpay_order_id).update(status='Failed')
        if request.content_type == 'application/json':
            return JsonResponse({'status': 'failed', 'reason': 'capture_failed', 'details': str(e)}, status=500)
        else:
            return render(request, 'shop/paymentfail.html', {'reason': f"Capture failed: {str(e)}"})

def create_order_items(order):
    """Helper to parse item_Json and create OrderItem records"""
    try:
        items = json.loads(order.item_Json)
        for key, value in items.items():
            # item_Json format: {"pr4": [1, "Product Name", 500, "img_url"]}
            prod_id = int(key.replace("pr", ""))
            qty = value[0]
            price = value[2]
            product = Product.objects.get(id=prod_id)
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                price=price
            )
    except Exception as e:
        print(f"Error creating order items: {e}")

# --- Merchant Auth Views ---

def merchant_register(request):
    """Step 1: Fill details, send OTP to entered email."""
    if request.method == 'POST':
        form = MerchantRegistrationForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            # Store all form data in session
            request.session['merchant_reg_data'] = {
                'username':      d['username'],
                'email':         d['email'],
                'password':      d['password'],
                'shop_name':     d['shop_name'],
                'shop_location': d['shop_location'],
                'phone':         d['phone'],
                'gst_number':    d.get('gst_number', ''),
                'description':   d.get('description', ''),
            }
            # Send OTP to the provided email
            otp = _generate_otp()
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key
            OTPRecord.objects.filter(session_key=session_key).delete()
            OTPRecord.objects.create(
                email=d['email'], phone='',
                email_otp='000000', phone_otp=otp,
                session_key=session_key,
            )
            sent = _send_email_otp_gmail(d['email'], otp)
            print(f"MERCHANT REGISTER OTP — {otp}")
            return redirect('MerchantRegisterVerify')
    else:
        form = MerchantRegistrationForm()
    return render(request, 'shop/merchant_register.html', {'form': form})


def merchant_register_verify_otp(request):
    """Step 2: Verify OTP, then create account."""
    reg_data = request.session.get('merchant_reg_data')
    if not reg_data:
        return redirect('MerchantRegister')

    error = None
    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()
        session_key = request.session.session_key
        try:
            record = OTPRecord.objects.filter(
                session_key=session_key, is_verified=False
            ).latest('created_at')
            if record.is_expired():
                error = 'OTP has expired. Please go back and register again.'
            elif record.phone_otp != entered:
                error = 'Invalid OTP. Please try again.'
            else:
                record.is_verified = True
                record.save()
                # Create user and merchant profile
                user = User.objects.create_user(
                    username=reg_data['username'],
                    email=reg_data['email'],
                    password=reg_data['password'],
                    first_name=reg_data['shop_name'],
                )
                MerchantProfile.objects.create(
                    user=user,
                    shop_name=reg_data['shop_name'],
                    shop_location=reg_data['shop_location'],
                    phone=reg_data['phone'],
                    gst_number=reg_data.get('gst_number', ''),
                    description=reg_data.get('description', ''),
                    is_approved=False,
                )
                del request.session['merchant_reg_data']
                messages.success(request, 'Email verified! Your account is under review. We will notify you once approved.')
                return redirect('MerchantLogin')
        except OTPRecord.DoesNotExist:
            error = 'No OTP found. Please register again.'

    # Mask email for display
    email = reg_data.get('email', '')
    try:
        at = email.index('@')
        masked = email[:2] + '****' + email[at:]
    except Exception:
        masked = '****'

    return render(request, 'shop/merchant_register_verify_otp.html', {
        'masked_email': masked,
        'error': error,
    })


def merchant_login_view(request):
    """Step 1: Verify credentials, then send OTP to merchant email."""
    if request.user.is_authenticated:
        try:
            request.user.merchant_profile
            return redirect('MerchantDashboard')
        except MerchantProfile.DoesNotExist:
            pass

    error = None
    if request.method == 'POST':
        form = MerchantLoginForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            user = authenticate(request, username=d['username'], password=d['password'])
            if user:
                try:
                    profile = user.merchant_profile
                    if not profile.is_approved:
                        error = 'Your account is pending admin approval. Please wait.'
                    else:
                        # Credentials OK — generate & send OTP to merchant email
                        otp = _generate_otp()
                        if not request.session.session_key:
                            request.session.create()
                        session_key = request.session.session_key
                        OTPRecord.objects.filter(session_key=session_key).delete()
                        OTPRecord.objects.create(
                            email=user.email, phone='',
                            email_otp='000000', phone_otp=otp,
                            session_key=session_key,
                        )
                        # Store pending user id in session (not logged in yet)
                        request.session['merchant_pending_uid'] = user.pk
                        sent = _send_email_otp_gmail(user.email, otp)
                        print(f"MERCHANT LOGIN OTP — {otp}")
                        return redirect('MerchantVerifyOTP')
                except MerchantProfile.DoesNotExist:
                    error = 'No merchant account found. Please register first.'
            else:
                error = 'Invalid username or password.'
    else:
        form = MerchantLoginForm()
    return render(request, 'shop/merchant_login.html', {'form': form, 'error': error})


def merchant_verify_otp(request):
    """Step 2: Verify OTP emailed to merchant, then log them in."""
    uid = request.session.get('merchant_pending_uid')
    if not uid:
        return redirect('MerchantLogin')

    error = None
    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()
        session_key = request.session.session_key
        try:
            record = OTPRecord.objects.filter(
                session_key=session_key, is_verified=False
            ).latest('created_at')
            if record.is_expired():
                error = 'OTP has expired. Please login again.'
            elif record.phone_otp != entered:
                error = 'Invalid OTP. Please try again.'
            else:
                record.is_verified = True
                record.save()
                from django.contrib.auth.models import User as AuthUser
                user = AuthUser.objects.get(pk=uid)
                request.session.pop('merchant_pending_uid', None)
                login(request, user)
                return redirect('MerchantDashboard')
        except OTPRecord.DoesNotExist:
            error = 'No OTP found. Please login again.'

    try:
        from django.contrib.auth.models import User as AuthUser
        merchant_email = AuthUser.objects.get(pk=uid).email
        # Mask email: pi****@gmail.com
        at = merchant_email.index('@')
        masked = merchant_email[:2] + '****' + merchant_email[at:]
    except Exception:
        masked = '****'

    return render(request, 'shop/merchant_verify_otp.html', {
        'masked_email': masked,
        'error': error,
    })


def merchant_logout_view(request):
    logout(request)
    return redirect('MerchantLogin')


# --- Merchant Views ---

def _is_approved_merchant(user):
    if not user.is_authenticated:
        return False
    try:
        return user.merchant_profile.is_approved
    except MerchantProfile.DoesNotExist:
        return False

@login_required(login_url='/shop/merchant/login/')
def merchant_dashboard(request):
    if not _is_approved_merchant(request.user):
        return render(request, 'shop/merchant_pending.html')
    profile = request.user.merchant_profile
    my_products = Product.objects.filter(seller=request.user)
    my_sales = OrderItem.objects.filter(product__seller=request.user).select_related('order', 'product').order_by('-item_id')
    total_revenue = sum(s.price * s.quantity for s in my_sales)
    context = {
        'products': my_products,
        'sales': my_sales,
        'total_revenue': total_revenue,
        'total_orders': my_sales.count(),
        'profile': profile,
    }
    return render(request, 'shop/merchant_dashboard.html', context)

@login_required(login_url='/shop/merchant/login/')
def add_product(request):
    if not _is_approved_merchant(request.user):
        return render(request, 'shop/merchant_pending.html')
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.pub_date = datetime.date.today()
            product.save()
            messages.success(request, f"Product '{product.product_name}' added!")
            return redirect('MerchantDashboard')
    else:
        form = ProductForm()
    return render(request, 'shop/add_product.html', {'form': form, 'action': 'Add'})

@login_required(login_url='/shop/merchant/login/')
def edit_product(request, product_id):
    if not _is_approved_merchant(request.user):
        return render(request, 'shop/merchant_pending.html')
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.product_name}' updated!")
            return redirect('MerchantDashboard')
    else:
        form = ProductForm(instance=product)
    return render(request, 'shop/add_product.html', {'form': form, 'action': 'Edit', 'product': product})

@login_required(login_url='/shop/merchant/login/')
def delete_product(request, product_id):
    if not _is_approved_merchant(request.user):
        return render(request, 'shop/merchant_pending.html')
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    if request.method == 'POST':
        name = product.product_name
        product.delete()
        messages.success(request, f"Product '{name}' deleted.")
        return redirect('MerchantDashboard')
    return render(request, 'shop/delete_product_confirm.html', {'product': product})

@login_required(login_url='/shop/merchant/login/')
def update_item_status(request):
    if request.method == "POST":
        item_id = request.POST.get('item_id')
        new_status = request.POST.get('status')
        item = get_object_or_404(OrderItem, item_id=item_id, product__seller=request.user)
        item.vendor_status = new_status
        item.save()
        OrderUpdate(order_id=item.order.order_id,
                    update_desc=f"Update for {item.product.product_name}: {new_status}").save()
        messages.success(request, f"Status updated for {item.product.product_name}")
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "failed"}, status=400)


# --- OTP Views ---

def _generate_otp():
    return str(random.randint(100000, 999999))

def _send_email_otp_gmail(to_email, otp):
    """Send OTP via Gmail SMTP."""
    try:
        from_email = getattr(settings, 'EMAIL_HOST_USER', '')
        if not from_email or from_email == 'your-email@gmail.com':
            print(f"Email not configured in settings. OTP for {to_email}: {otp}")
            return False
        send_mail(
            subject="Your Verification OTP - My Awesome Cart",
            message=(
                f"Your OTP is: {otp}\n\n"
                f"Valid for 10 minutes. Do not share it with anyone.\n\n"
                f"- My Awesome Cart"
            ),
            from_email=from_email,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email OTP (Gmail) failed: {e}")
        return False

@csrf_exempt
def send_otp(request):
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=400)
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({'error': 'invalid json'}, status=400)

        email = data.get('email', '').strip()
        if not email:
            return JsonResponse({'error': 'Email is required'}, status=400)

        otp = _generate_otp()

        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        OTPRecord.objects.filter(session_key=session_key).delete()
        OTPRecord.objects.create(
            email=email, phone='',
            email_otp='000000', phone_otp=otp,
            session_key=session_key,
        )

        sent = _send_email_otp_gmail(email, otp)
        print(f"DEBUG OTP — {otp}")

        return JsonResponse({'success': True, 'message': 'OTP sent to your email.'})
    except Exception as e:
        import traceback
        return JsonResponse({'success': False, 'error': f'CRASH: {str(e)} | {traceback.format_exc()}'})

@csrf_exempt
def verify_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'invalid json'}, status=400)

    phone_otp_input = data.get('phone_otp', '').strip()
    session_key = request.session.session_key

    try:
        otp_record = OTPRecord.objects.filter(session_key=session_key, is_verified=False).latest('created_at')
    except OTPRecord.DoesNotExist:
        return JsonResponse({'error': 'No OTP found. Please request a new OTP.'}, status=400)

    if otp_record.is_expired():
        return JsonResponse({'error': 'OTP has expired. Please request a new one.'}, status=400)

    if otp_record.phone_otp != phone_otp_input:
        return JsonResponse({'error': 'Invalid OTP. Please try again.'}, status=400)

    # Mark verified
    otp_record.is_verified = True
    otp_record.save()
    request.session['otp_verified'] = True

    return JsonResponse({'success': True, 'message': 'Phone verified successfully!'})


# --- Customer Views ---

def my_orders(request):
    """
    Shows orders for the current customer.
    If the customer just checked out, their email is in the session.
    Otherwise, we prompt them to enter their email to view orders.
    """
    email = request.session.get('customer_email')
    if request.GET.get('clear') == '1' and 'customer_email' in request.session:
        del request.session['customer_email']
        email = None
    
    if request.method == 'POST':
        submitted_email = request.POST.get('email')
        if submitted_email:
            if request.session.get('otp_verified'):
                email = submitted_email
                request.session['customer_email'] = email
                request.session.pop('otp_verified', None)  # Consume the verification
            else:
                from django.contrib import messages
                messages.error(request, 'Please verify your email via OTP.')

    if email:
        orders = Orders.objects.filter(email=email).order_by('-created_at')
    else:
        orders = None
        
    return render(request, 'shop/my_orders.html', {'orders': orders, 'email_entered': bool(email)})


def paymentsuccess(request):
    """Display payment success page with order details"""
    order_id = request.GET.get('order_id', '')
    try:
        order = Orders.objects.get(order_id=order_id)
        context = {'order': order}
        return render(request, 'shop/paymentsuccess.html', context)
    except Orders.DoesNotExist:
        context = {'error': 'Order not found'}
        return render(request, 'shop/paymentsuccess.html', context)


def paymentfail(request):
    """Display payment failure page with reason"""
    reason = request.GET.get('reason', 'unknown')
    context = {'reason': reason}
    return render(request, 'shop/paymentfail.html', context)