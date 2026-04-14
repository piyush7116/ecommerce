from django import forms
from django.contrib.auth.models import User
from .models import Product, MerchantProfile


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_name', 'category', 'subcategory', 'price', 'desc', 'image']
        widgets = {
            'product_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product Name'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Electronics'}),
            'subcategory': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Phones'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Price in ₹'}),
            'desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Product description...'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class MerchantRegistrationForm(forms.Form):
    # Account details
    username     = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Choose a username'}))
    email        = forms.EmailField(widget=forms.EmailInput(attrs={'class':'form-control','placeholder':'Business email'}))
    password     = forms.CharField(widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Create password'}))
    password2    = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Repeat password'}))
    # Shop details
    shop_name    = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Your shop / brand name'}))
    shop_location= forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Shop address / city'}))
    phone        = forms.CharField(max_length=15, widget=forms.TextInput(attrs={'class':'form-control','placeholder':'10-digit mobile number'}))
    gst_number   = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class':'form-control','placeholder':'GST Number (optional)'}))
    description  = forms.CharField(required=False, widget=forms.Textarea(attrs={'class':'form-control','rows':3,'placeholder':'Brief description of your shop (optional)'}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password2'):
            raise forms.ValidationError('Passwords do not match.')
        if User.objects.filter(username=cleaned.get('username')).exists():
            raise forms.ValidationError('Username already taken. Please choose another.')
        if User.objects.filter(email=cleaned.get('email')).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return cleaned


class MerchantLoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Password'}))
