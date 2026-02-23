from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from users.models import PartnerProfile, User
import re
from django.contrib.auth import get_user_model
from users.utils import get_bank
User = get_user_model()
class RegistrationForm(forms.Form):
    username = forms.CharField(
        min_length=8, max_length=150, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập username'})
    )
    full_name = forms.CharField(
        max_length=150, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ và tên'})
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
            'title': 'Mật khẩu tối thiểu 8 ký tự, gồm chữ hoa, số và ký tự đặc biệt'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'})
    )

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
    
    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name')
        if re.search(r'\d', full_name): 
             raise ValidationError("Họ tên không được chứa số.")
        invalid_chars = set('!@#$%^&*()+=[]{}|\\;:"<>,.?/')
        if any(char in invalid_chars for char in full_name):
            raise ValidationError("Họ tên chứa ký tự không hợp lệ.")
            
        return full_name.strip()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email này đã được đăng ký.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.strip()
            
        if not re.match(r'^0\d{9}$', phone_number):
            raise ValidationError("Số điện thoại phải gồm 10 số và bắt đầu bằng số 0.")
            
        if User.objects.filter(phone_number=phone_number).exists():
            raise ValidationError("Số điện thoại này đã được sử dụng.")
        return phone_number

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password: return password
        
        if len(password) < 8:
            raise ValidationError("Mật khẩu quá ngắn.")
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Thiếu chữ cái viết hoa.")
        if not re.search(r'\d', password):
            raise ValidationError("Thiếu chữ số.")
        if not re.search(r'[@$!%*?&#^+=_\-]', password):
            raise ValidationError("Thiếu ký tự đặc biệt.")
            
        return password


class PartnerRegistrationForm(RegistrationForm):

    bank_bin = forms.CharField(widget=forms.HiddenInput(), required=False)
    bank_name = forms.ChoiceField(
        choices=[], 
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'select_bank_name'})
    )
    bank_account_number = forms.CharField(
        max_length=255, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số tài khoản ngân hàng'})
    )
    bank_account_owner = forms.CharField(
        max_length=100, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên chủ tài khoản ngân hàng'})
    )
    contact_person = forms.CharField(
        max_length=100, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Người đại diện liên hệ'})
    )
    
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        
        if 'full_name' in self.fields:
            del self.fields['full_name']
        banks = get_bank()
        try:
            bank_choices = [('', '--- Chọn ngân hàng thụ hưởng ---')] + \
                           [(b['shortName'], f"{b['shortName']} - {b['name']}") for b in banks]
        except TypeError:
            bank_choices = [('', 'Lỗi tải danh sách ngân hàng')]

        self.fields['bank_name'].choices = bank_choices
   
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('bank_name')
        number = cleaned_data.get('bank_account_number')
        owner = cleaned_data.get('bank_account_owner')
        if name and number and owner:
            if PartnerProfile.objects.filter(
                bank_name=name, 
                bank_account_number=number, 
                bank_account_owner=owner
            ).exists():
                self.add_error('bank_account_number', "Tài khoản ngân hàng này đã được đăng ký bởi đối tác khác.")
        
        return cleaned_data


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
                try:
                    staff_user = User.objects.get(phone_number=username, role='staff')
                    user = authenticate(username=staff_user.username, password=password)
                except User.DoesNotExist:
                    pass
            
            if not user:
                self.add_error(None, "Tài khoản hoặc mật khẩu không đúng.")
            else:
                cleaned_data['user_obj'] = user
        return cleaned_data