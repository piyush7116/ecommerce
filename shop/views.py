# shop/views.py
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from .models import Product, Contact,Orders,OrderUpdate, Payment
from math import ceil
import json
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from paytmchecksum import generateSignature, verifySignature
from django.http import JsonResponse


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
        
        # Save order first
        order=Orders(name=name, amount=amount, item_Json=itemJson, email=email, address=address1+", "+address2, city=city, state=state, zip_code=zip, phone=phone)
        order.save()

        update=OrderUpdate(order_id=order.order_id, update_desc="The Order has been placed.")
        update.save()

        id=order.order_id
        # If user submitted the form to pay with Razorpay, don't mark thank=True here
        # because we want to open the Razorpay popup for payment. For COD (no flag), show thank you.
        if not request.POST.get('pay_with_razorpay'):
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

# @csrf_exempt
# def handlerequest(request):
#     form=request.POST 
#     response_dict={}
#     for i in form.keys():
#         response_dict[i]=form[i]
#         if i=='CHECKSUMHASH':
#             checksum=form[i]
#     verify=verifySignature(response_dict, settings.PAYTM_MERCHANT_KEY,checksum)
#     if verify:
#         if response_dict['RESPCODE']=='01':
#             print('order placed')
#         else:
#             print('order was nto successful'+response_dict['RESPONSE'])
#     return render(request, 'shop/paymentstatus.html',{'response_dict':response_dict})


# @csrf_exempt
# def handlerequest(request):
#     if request.method != "POST":
#         return HttpResponse("Invalid request")

#     response_dict = request.POST.dict()
#     print("PAYTM RESPONSE:", response_dict)

#     checksum = response_dict.pop('CHECKSUMHASH', None)

#     if not checksum:
#         return HttpResponse("CHECKSUM MISSING")

#     verify = verifySignature(
#         response_dict,
#         settings.PAYTM_MERCHANT_KEY,
#         checksum
#     )

#     if verify:
#         if response_dict.get('RESPCODE') == '01':
#             print("✅ PAYMENT SUCCESS")
#         else:
#             print("❌ PAYMENT FAILED:", response_dict.get('RESPMSG'))
#     else:
#         print("❌ CHECKSUM VERIFICATION FAILED")

#     return render(request, 'shop/paymentstatus.html', {
#         'response_dict': response_dict
#     })




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

    # Create razorpay order
    amount_in_paise = int(amount * 100)
    currency = 'INR'
    try:
        razorpay_client = get_razorpay_client()
        print(f"DEBUG: Creating Razorpay order with amount {amount_in_paise} paise using key {settings.RAZOR_KEY_ID[:10]}...")
        razorpay_order = razorpay_client.order.create(
            dict(amount=amount_in_paise, currency=currency, payment_capture='0')
        )
        print(f"DEBUG: Razorpay order created: {razorpay_order['id']}")
        # Save payment record
        Payment.objects.create(
            razorpay_order_id=razorpay_order['id'],
            amount=amount_in_paise,
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
        return JsonResponse({'error': 'POST required'}, status=400)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'invalid json'}, status=400)

    payment_id = data.get('razorpay_payment_id')
    razorpay_order_id = data.get('razorpay_order_id')
    signature = data.get('razorpay_signature')

    if not (payment_id and razorpay_order_id and signature):
        return JsonResponse({'error': 'missing fields'}, status=400)

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
        # capture
        razorpay_client.payment.capture(payment_id, payment.amount)
        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.status = 'Success'
        payment.save()
        print(f"DEBUG: Payment {payment_id} captured successfully")
        return JsonResponse({'status': 'success'})
    except Exception as e:
        print(f"DEBUG: Payment capture failed: {e}")
        Payment.objects.filter(razorpay_order_id=razorpay_order_id).update(status='Failed')
        return JsonResponse({'status': 'failed', 'reason': 'capture_failed', 'details': str(e)}, status=500)


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