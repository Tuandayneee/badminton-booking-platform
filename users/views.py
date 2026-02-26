from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from users.models import PartnerProfile, User, CustomerProfile
from users.forms import PartnerRegistrationForm, RegistrationForm
from users.forms import LoginForm
from booking.models import Booking
from django.db.models import Sum, Count

from django.db import transaction

from users.utils import get_bank
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
                PartnerProfile.objects.get(user=user)
                if not user.partner_profile.is_verified:
                    messages.warning(request, "Tài khoản của bạn chưa được xác minh. Vui lòng chờ quản trị viên liên hệ.")
                    return redirect('login')
                login(request, user)
                messages.success(request, f"Chào mừng Đối tác {user.username} quay lại!")
                return redirect('partner_dashboard')
            elif user.role == User.Role.STAFF:
                login(request, user)
                messages.success(request, f"Chào mừng Nhân viên {user.full_name or user.username}!")
                return redirect('pos_sales')
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
    bank_list = get_bank()  
    
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
                        bank_name = data['bank_name'] ,
                        bank_bin = data['bank_bin'],
                        bank_account_number=data.get('bank_account_number'),
                        bank_account_owner=data.get('bank_account_owner'),
                        contact_person = data.get('contact_person') 
                    )

                messages.success(request, "Yêu cầu của bạn đã được gửi. Vui lòng đợi admin liên hệ.")
                return redirect('login') 
            
            except Exception as e:
                messages.error(request, f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
        else:
            messages.error(request, "Vui lòng kiểm tra lại thông tin nhập liệu.")
    else:
        partner_form = PartnerRegistrationForm()

    
    return render(request, 'partner/register_partner.html', {'partner_form': partner_form, 'bank_list': bank_list})


def login_social_account(request):
    
    return redirect('home')


@login_required
def change_password(request):
    """Đổi mật khẩu cho tất cả role"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Đổi mật khẩu thành công!")
            if user.role == User.Role.PARTNER:
                return redirect('partner_dashboard')
            elif user.role == User.Role.STAFF:
                return redirect('pos_sales')
            else:
                return redirect('home')
        else:
            messages.error(request, "Vui lòng kiểm tra lại thông tin.")
    else:
        form = PasswordChangeForm(request.user)

    
    if request.user.role == User.Role.PARTNER:
        template = 'partner/change_password.html'
    else:
        template = 'user/change_password.html'

    return render(request, template, {'form': form})


@login_required
def customer_profile(request):
    """Hồ sơ cá nhân của customer"""
    user = request.user
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        
        if full_name:
            user.full_name = full_name
        if email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, "Email này đã được sử dụng.")
            else:
                user.email = email
        if phone_number:
            user.phone_number = phone_number
        
        user.save()
        messages.success(request, "Cập nhật hồ sơ thành công!")
        return redirect('customer_profile')
    
    bookings = Booking.objects.filter(user=user)
    stats = bookings.aggregate(
        total_bookings=Count('id'),
        total_spent=Sum('total_price'),
    )
    completed_count = bookings.filter(status=Booking.Status.COMPLETED).count()
    
    try:
        profile = user.customer_profile
    except CustomerProfile.DoesNotExist:
        profile = CustomerProfile.objects.create(user=user)
    
    context = {
        'profile': profile,
        'total_bookings': stats['total_bookings'] or 0,
        'total_spent': stats['total_spent'] or 0,
        'completed_count': completed_count,
    }
    return render(request, 'user/profile.html', context)


@login_required
def customer_booking_history(request):
    """Lịch sử đặt sân của customer"""
    user = request.user
    tab = request.GET.get('tab', 'all')
    
    bookings = Booking.objects.filter(user=user).select_related(
        'court', 'court__center'
    ).order_by('-date', '-start_time')
    
    if tab == 'upcoming':
        bookings = bookings.filter(status__in=[
            Booking.Status.PENDING, 
            Booking.Status.WAITING_VERIFY,
            Booking.Status.CONFIRMED
        ])
    elif tab == 'completed':
        bookings = bookings.filter(status=Booking.Status.COMPLETED)
    elif tab == 'cancelled':
        bookings = bookings.filter(status=Booking.Status.ADMIN_CANCELLED)
    
    all_bookings = Booking.objects.filter(user=user)
    tab_counts = {
        'all': all_bookings.count(),
        'upcoming': all_bookings.filter(status__in=[
            Booking.Status.PENDING, Booking.Status.WAITING_VERIFY, Booking.Status.CONFIRMED
        ]).count(),
        'completed': all_bookings.filter(status=Booking.Status.COMPLETED).count(),
        'cancelled': all_bookings.filter(status=Booking.Status.ADMIN_CANCELLED).count(),
    }
    
    context = {
        'bookings': bookings,
        'current_tab': tab,
        'tab_counts': tab_counts,
    }
    return render(request, 'user/booking_history.html', context)
