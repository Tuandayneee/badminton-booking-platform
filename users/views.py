from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from users.models import PartnerProfile, User, CustomerProfile
from users.forms import PartnerRegistrationForm, RegistrationForm
from users.forms import LoginForm
from django.db import transaction
def login_view(request):
    login_form = LoginForm()
    register_form = RegistrationForm()
    if request.method == 'POST':
        login_form = LoginForm(request.POST)
        if login_form.is_valid():
            user = login_form.cleaned_data.get('user_obj')
            if user.role == User.Role.CUSTOMER:
       
                login(request, user)
                messages.success(request, f"Chào mừng {user.username} quay lại!")
                return redirect('home')
            elif user.role == User.Role.PARTNER:
                login(request, user)
                messages.success(request, f"Chào mừng Đối tác {user.username} quay lại!")
                return redirect('partner_dashboard')
        else:
            messages.warning(request, "Tài khoản hoặc mật khẩu không đúng.")
    context = {
        'login_form': login_form,
        'register_form': register_form
    }
    return render(request, 'user/login_register.html', context)

def logout_view(request):
    logout(request)
    return redirect('login')


def register_view(request):
    
    register_form = RegistrationForm(request.POST or None)
    login_form = LoginForm() 

    if request.method == 'POST':
        
        if 'btn_register' in request.POST:
            if register_form.is_valid():
                data = register_form.cleaned_data
                try:
                    
                    with transaction.atomic():
                        
                        user = User.objects.create_user(
                            username=data['username'],
                            email=data['email'],
                            password=data['password'],
                            full_name=data['full_name'],
                            phone_number=data['phone_number'],
                            role=User.Role.CUSTOMER
                        )
                        
                        
                        
                    messages.success(request, "Đăng ký thành công! Vui lòng đăng nhập.")
                    return redirect('login') 

                except Exception as e:
                    messages.error(request, f"Lỗi hệ thống: {str(e)}")
            else:
                messages.error(request, "Vui lòng kiểm tra lại thông tin nhập liệu.")

    context = {
        'register_form': register_form,
        'login_form': login_form
    }
    return render(request, 'user/login_register.html', context)

def register_partner(request):
    if request.method == 'POST':
        
        partner_form = PartnerRegistrationForm(request.POST)
        
        if partner_form.is_valid():
            data = partner_form.cleaned_data
            
            try:
               
                with transaction.atomic():
                    
                    user = User.objects.create_user(
                        username=data['username'],
                        full_name=data['username'],
                        email=data['email'],
                        password=data['password'],
                        phone_number=data['phone_number'],
                        role=User.Role.PARTNER 
                    )
                    
                    PartnerProfile.objects.create(
                        user=user,
                        business_name=data['name_company'],      
                        business_address=data['address_company'], 
                        contact_person=data['contact_person'],
                        
                        
                        bank_name=data.get('bank_name', ''),
                        bank_account_number=data.get('bank_account_number', ''),
                        bank_account_owner=data.get('bank_account_owner', '')
                    )

                messages.success(request, "Đăng ký đối tác thành công! Vui lòng đăng nhập.")
                return redirect('login') 
            
            except Exception as e:
                messages.error(request, f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
        else:
            messages.error(request, "Vui lòng kiểm tra lại thông tin nhập liệu.")
    else:
        partner_form = PartnerRegistrationForm()

    
    return render(request, 'partner/register_partner.html', {'partner_form': partner_form})


def login_social_account(request):
    
    return redirect('home')
