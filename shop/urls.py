# shop/urls.py
from django.urls import path
from . import views
urlpatterns = [
    path("",views.index,name="index_shop" ),
    path("about/",views.about,name="AboutUs"),
    path("contact/",views.contact,name="ContactUs"),
    path("tracker/",views.tracker,name="TrackingStatus"),
    path("search/",views.search,name="Search"),
    path("products/<int:myid>",views.productview,name="ProductView"),
    path("checkout/",views.checkout,name="Checkout"),
    path("handlerequest/",views.handlerequest,name="HandleRequest"),
    path("paymenthandler/", views.handlerequest, name="PaymentHandler"),
    path("create_order/", views.create_order, name="CreateOrder"),
    path("verify_payment/", views.verify_payment, name="VerifyPayment"),
    path("paymentsuccess/", views.paymentsuccess, name="PaymentSuccess"),
    path("paymentfail/", views.paymentfail, name="PaymentFail"),
]
