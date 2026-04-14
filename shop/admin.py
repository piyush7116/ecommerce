from django.contrib import admin
from .models import Contact, Product, Orders, OrderUpdate, Payment, MerchantProfile

admin.site.register(Product)
admin.site.register(Contact)
admin.site.register(Orders)
admin.site.register(OrderUpdate)
admin.site.register(Payment)

@admin.register(MerchantProfile)
class MerchantProfileAdmin(admin.ModelAdmin):
    list_display  = ('shop_name', 'user', 'phone', 'shop_location', 'is_approved', 'created_at')
    list_filter   = ('is_approved',)
    search_fields = ('shop_name', 'user__username', 'user__email', 'phone')
    list_editable = ('is_approved',)   # ← approve directly from the list page
    ordering      = ('-created_at',)