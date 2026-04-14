from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Product(models.Model):
    product_id=models.AutoField
    product_name=models.CharField(max_length=30)
    category=models.CharField(max_length=50,default="")
    subcategory=models.CharField(max_length=50,default="")
    price=models.IntegerField(default=0)
    desc= models.CharField(max_length=3000)
    pub_date=models.DateField()
    image=models.ImageField(upload_to="shop/images",default="")
    seller = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return self.product_name


class MerchantProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='merchant_profile')
    shop_name = models.CharField(max_length=100)
    shop_location = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    gst_number = models.CharField(max_length=20, blank=True, default='')
    description = models.TextField(blank=True, default='')
    is_approved = models.BooleanField(default=False)  # Admin must approve
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.shop_name} ({self.user.username})"

class Contact(models.Model):
    contact_id=models.AutoField(primary_key=True)
    name=models.CharField(max_length=30)
    email=models.CharField(max_length=70,default="")
    phone=models.CharField(max_length=15, default="")  # ✅ Correct phone=models.IntegerField(default=0)
    desc= models.CharField(max_length=500)
    
    def __str__(self):
        return self.name

class Orders(models.Model):
    order_id=models.AutoField(primary_key=True)
    item_Json=models.CharField(max_length=5000)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    name=models.CharField(max_length=90)
    email=models.CharField(max_length=110)
    address=models.CharField(max_length=110)
    city=models.CharField(max_length=110)
    state=models.CharField(max_length=110)
    phone=models.CharField(max_length=15, default="")
    zip_code=models.CharField(max_length=10, default="")
    payment_status = models.CharField(max_length=20, default="Pending") # Pending, Success, Failed
    created_at = models.DateTimeField(auto_now_add=True, null=True)

class OrderUpdate(models.Model):
    update_id=models.AutoField(primary_key=True)
    order_id=models.IntegerField(default=0)
    update_desc=models.CharField(max_length=5000)
    timestamp=models.DateField(auto_now_add=True)
    
    def __str__(self):
        return self.update_desc[0:7]+"..."

class OrderItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Orders, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    vendor_status = models.CharField(max_length=50, default="Processing") # Processing, Shipped, Delivered
    
    def __str__(self):
        return f"{self.product.product_name} ({self.quantity})"

class Payment(models.Model):
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    # Link to Orders.order_id (stored as integer) so we can record updates against the order
    order_id = models.IntegerField(blank=True, null=True)
    amount = models.IntegerField()
    status = models.CharField(max_length=50, default='Created')  # Created, Success, Failed
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.razorpay_order_id} - {self.status}"


class OTPRecord(models.Model):
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    email_otp = models.CharField(max_length=6)
    phone_otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    session_key = models.CharField(max_length=100, blank=True)  # links OTP to browser session

    def is_expired(self):
        from django.utils import timezone
        import datetime
        return (timezone.now() - self.created_at) > datetime.timedelta(minutes=10)

    def __str__(self):
        return f"OTP for {self.email} / {self.phone}"