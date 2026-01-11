from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from users.models import PartnerProfile, User
import re
class RegistrationForm(forms.Form):
    username = forms.CharField(
        min_length=8, max_length=150, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập username'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'})
    )
    phone_number = forms.CharField(
        max_length=10, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': '0912...',
            'pattern': '0[0-9]{9}', 
            'title': 'Số điện thoại phải gồm 10 số và bắt đầu bằng số 0'
        }),
    )
    password = forms.CharField(
        min_length=8, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': '••••••••',
           
            'pattern': '(?=.*\\d)(?=.*[A-Z])(?=.*[@$!%*?&])[A-Za-z\\d@$!%*?&]{8,}',
            'title': 'Mật khẩu phải có ít nhất 8 ký tự, gồm: 1 chữ hoa, 1 số và 1 ký tự đặc biệt'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'})
    )

    # --- CÁC HÀM VALIDATION DÙNG CHUNG ---
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
               self.add_error('confirm_password', "Mật khẩu nhập lại không khớp!")
        return cleaned_data

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Tên tài khoản đã tồn tại.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email đã được sử dụng.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.strip()
        if not re.match(r'^0\d{9}$', phone_number):
            raise ValidationError("Số điện thoại không hợp lệ (10 số, bắt đầu bằng 0).")
        if User.objects.filter(phone_number=phone_number).exists():
            raise ValidationError("Số điện thoại đã được sử dụng.")
        return phone_number

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password: return password
        # Logic check độ mạnh mật khẩu (Backend)
        if len(password) < 8:
            raise ValidationError("Mật khẩu phải có ít nhất 8 ký tự.")
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Mật khẩu phải chứa ít nhất 1 chữ viết hoa.")
        if not re.search(r'\d', password):
            raise ValidationError("Mật khẩu phải chứa ít nhất 1 chữ số.")
        if not re.search(r'[@$!%*?&#^+=_\-]', password):
            raise ValidationError("Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt.")
        return password


class PartnerRegistrationForm(RegistrationForm):
    
    
    name_company = forms.CharField(
        max_length=200, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đơn vị kinh doanh'})
    )
    address_company = forms.CharField(
        max_length=255, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Địa chỉ kinh doanh'})
    )
    contact_person = forms.CharField(
        max_length=100, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ và tên người đại diện'})
    )
    
    
    
   
    def clean_name_company(self):
        name = self.cleaned_data.get('name_company')
        
        if PartnerProfile.objects.filter(business_name=name).exists():
            raise ValidationError("Tên đơn vị kinh doanh này đã được đăng ký.")
        return name


class LoginForm(forms.Form):
    username = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'})
    )

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                self.add_error(None, "Tài khoản hoặc mật khẩu không đúng.")
            else:
                cleaned_data['user_obj'] = user
        return cleaned_data