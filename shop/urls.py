# shop/urls.py
from django.urls import path
from . import views
urlpatterns = [
    path("", views.index, name="index_shop"),
    path("about/", views.about, name="AboutUs"),
    path("contact/", views.contact, name="ContactUs"),
    path("tracker/", views.tracker, name="TrackingStatus"),
    path("search/", views.search, name="Search"),
    path("products/<int:myid>", views.productview, name="ProductView"),
    path("checkout/", views.checkout, name="Checkout"),
    path("handlerequest/", views.handlerequest, name="HandleRequest"),
    path("paymenthandler/", views.handlerequest, name="PaymentHandler"),
    path("create_order/", views.create_order, name="CreateOrder"),
    path("verify_payment/", views.verify_payment, name="VerifyPayment"),
    path("paymentsuccess/", views.paymentsuccess, name="PaymentSuccess"),
    path("paymentfail/", views.paymentfail, name="PaymentFail"),
    # OTP
    path("send_otp/", views.send_otp, name="SendOTP"),
    path("verify_otp/", views.verify_otp, name="VerifyOTP"),
    # Merchant Auth
    path("merchant/register/", views.merchant_register, name="MerchantRegister"),
    path("merchant/register/verify/", views.merchant_register_verify_otp, name="MerchantRegisterVerify"),
    path("merchant/login/", views.merchant_login_view, name="MerchantLogin"),
    path("merchant/login/verify/", views.merchant_verify_otp, name="MerchantVerifyOTP"),
    path("merchant/logout/", views.merchant_logout_view, name="MerchantLogout"),
    # Merchant Dashboard
    path("merchant/", views.merchant_dashboard, name="MerchantDashboard"),
    path("merchant/update_status/", views.update_item_status, name="UpdateStatus"),
    path("merchant/add/", views.add_product, name="AddProduct"),
    path("merchant/edit/<int:product_id>/", views.edit_product, name="EditProduct"),
    path("merchant/delete/<int:product_id>/", views.delete_product, name="DeleteProduct"),
    # Customer
    path("my_orders/", views.my_orders, name="MyOrders"),
]
