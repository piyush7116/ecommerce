import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecom.settings')
django.setup()

from shop.models import Product

print("\n--- Verifying Product Image URLs ---")
for p in Product.objects.all():
    try:
        url = p.image.url
        print(f"Product: {p.product_name}")
        print(f"Image URL: {url}")
        print("-" * 20)
    except Exception as e:
        print(f"Product: {p.product_name} - Error: {e}")
