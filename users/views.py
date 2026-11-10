from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from booking.models import Booking
from users.forms import (
    ForgotPasswordForm,
    LoginForm,
    PartnerRegistrationForm,
    RegistrationForm,
    ResetPasswordForm,
)
from users.models import CustomerProfile, PartnerProfile, User
from users.tasks import send_password_reset_email
from users.utils import get_bank


def login_view(request):
    login_form = LoginForm()
    register_form = RegistrationForm()
    if request.method == 'POST':
        login_form = LoginForm(request.POST)
        if login_form.is_valid():
            user = login_form.cleaned_data.get('user_obj')
            if user.is_superuser or user.role == User.Role.ADMIN:
                login(request, user)
                return redirect('/admin/')
            if user.role == User.Role.CUSTOMER:
                login(request, user)
                messages.success(request, f"Chào mừng {user.username} quay lại!")
                return redirect('home')
            if user.role == User.Role.PARTNER:
                try:
                    partner_profile = user.partner_profile
                except PartnerProfile.DoesNotExist:
                    messages.warning(request, "Tài khoản đối tác chưa có hồ sơ hợp lệ. Vui lòng liên hệ quản trị viên.")
                    return redirect('login')
                if not partner_profile.is_verified:
                    messages.warning(request, "Tài khoản của bạn chưa được xác minh. Vui lòng chờ quản trị viên liên hệ.")
                    return redirect('login')
                login(request, user)
                messages.success(request, f"Chào mừng Đối tác {user.username} quay lại!")
                return redirect('partner_dashboard')
            if user.role == User.Role.STAFF:
                login(request, user)
                messages.success(request, f"Chào mừng Nhân viên {user.full_name or user.username}!")
                return redirect('pos_sales')
        else:
            messages.warning(request, "Tài khoản hoặc mật khẩu không đúng.")
    context = {
        'login_form': login_form,
        'register_form': register_form,
    }
    return render(request, 'user/login_register.html', context)


def logout_view(request):
    logout(request)
    return redirect('login')


def register_view(request):
    register_form = RegistrationForm(request.POST or None)
    login_form = LoginForm()

    if request.method == 'POST' and 'btn_register' in request.POST:
        if register_form.is_valid():
            data = register_form.cleaned_data
            try:
                with transaction.atomic():
                    User.objects.create_user(
                        username=data['username'],
                        email=data['email'],
                        password=data['password'],
                        full_name=data['full_name'],
                        phone_number=data['phone_number'],
                        role=User.Role.CUSTOMER,
                    )
                messages.success(request, "Đăng ký thành công! Vui lòng đăng nhập.")
                return redirect('login')
            except Exception as exc:
                messages.error(request, f"Lỗi hệ thống: {exc}")
        else:
            messages.error(request, "Vui lòng kiểm tra lại thông tin nhập liệu.")

    context = {
        'register_form': register_form,
        'login_form': login_form,
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
                        role=User.Role.PARTNER,
                    )
                    PartnerProfile.objects.create(
                        user=user,
                        bank_name=data['bank_name'],
                        bank_bin=data['bank_bin'],
                        bank_account_number=data.get('bank_account_number'),
                        bank_account_owner=data.get('bank_account_owner'),
                        contact_person=data.get('contact_person'),
                    )

                messages.success(request, "Yêu cầu của bạn đã được gửi. Vui lòng đợi admin liên hệ.")
                return redirect('login')
            except Exception as exc:
                messages.error(request, f"Đã xảy ra lỗi trong quá trình xử lý: {exc}")
        else:
            messages.error(request, "Vui lòng kiểm tra lại thông tin nhập liệu.")
    else:
        partner_form = PartnerRegistrationForm()

    return render(request, 'partner/register_partner.html', {'partner_form': partner_form, 'bank_list': bank_list})


def login_social_account(request):
    return redirect('home')


@login_required
def change_password(request):
    """Đổi mật khẩu cho tất cả role."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Đổi mật khẩu thành công!")
            if user.role == User.Role.PARTNER:
                return redirect('partner_dashboard')
            if user.role == User.Role.STAFF:
                return redirect('pos_sales')
            return redirect('home')
        messages.error(request, "Vui lòng kiểm tra lại thông tin.")
    else:
        form = PasswordChangeForm(request.user)

    template = 'partner/change_password.html' if request.user.role == User.Role.PARTNER else 'user/change_password.html'
    return render(request, template, {'form': form})


@login_required
def customer_profile(request):
    """Hồ sơ cá nhân của customer."""
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
    paid_bookings = bookings.filter(
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
    )
    total_bookings = bookings.count()
    total_spent = paid_bookings.aggregate(total=Sum('total_price'))['total'] or 0
    completed_count = bookings.filter(status=Booking.Status.COMPLETED).count()

    try:
        profile = user.customer_profile
    except CustomerProfile.DoesNotExist:
        profile = CustomerProfile.objects.create(user=user)

    context = {
        'profile': profile,
        'total_bookings': total_bookings,
        'total_spent': total_spent,
        'completed_count': completed_count,
    }
    return render(request, 'user/profile.html', context)


@login_required
def customer_booking_history(request):
    """Lịch sử đặt sân của customer."""
    user = request.user
    tab = request.GET.get('tab', 'all')

    bookings = Booking.objects.filter(user=user).select_related(
        'court', 'court__center'
    ).order_by('-date', '-start_time')

    if tab == 'upcoming':
        bookings = bookings.filter(status__in=[
            Booking.Status.PENDING,
            Booking.Status.WAITING_VERIFY,
            Booking.Status.CONFIRMED,
        ])
    elif tab == 'completed':
        bookings = bookings.filter(status=Booking.Status.COMPLETED)
    elif tab == 'cancelled':
        bookings = bookings.filter(status=Booking.Status.ADMIN_CANCELLED)

    all_bookings = Booking.objects.filter(user=user)
    tab_counts = {
        'all': all_bookings.count(),
        'upcoming': all_bookings.filter(status__in=[
            Booking.Status.PENDING,
            Booking.Status.WAITING_VERIFY,
            Booking.Status.CONFIRMED,
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


def forgot_password(request):
    """Xử lý yêu cầu quên mật khẩu - gửi email reset."""
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.get(email=email)

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = request.build_absolute_uri(f'/users/reset-password/{uid}/{token}/')

            send_password_reset_email.delay(user.id, reset_url)

            messages.success(
                request,
                f'Chúng tôi đã gửi email hướng dẫn đặt lại mật khẩu đến {email}. '
                'Vui lòng kiểm tra hộp thư (bao gồm thư mục Spam).',
            )
            return redirect('login')
        messages.error(request, 'Vui lòng kiểm tra lại thông tin.')
    else:
        form = ForgotPasswordForm()

    return render(request, 'user/forgot_password.html', {'form': form})


def reset_password(request, uidb64, token):
    """Xử lý đặt lại mật khẩu mới từ link email."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(
            request,
            'Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn. Vui lòng yêu cầu lại.',
        )
        return redirect('forgot_password')

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password']
            user.set_password(new_password)
            user.save()
            messages.success(
                request,
                'Đặt lại mật khẩu thành công! Vui lòng đăng nhập với mật khẩu mới.',
            )
            return redirect('login')
        messages.error(request, 'Vui lòng kiểm tra lại thông tin.')
    else:
        form = ResetPasswordForm()

    return render(request, 'user/reset_password.html', {
        'form': form,
        'uidb64': uidb64,
        'token': token,
    })
