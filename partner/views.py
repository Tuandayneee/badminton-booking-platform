from datetime import timedelta
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from booking.models import Booking, Transaction
from booking.services import process_approve_transaction
from partner.excel_utils import create_excel_response
from partner.utils import redirect_back
from users.decorators import role_required
from users.models import StaffProfile, User
from .forms import BadmintonCenterForm, CourtForm, CustomerForm, StaffForm
from .models import BadmintonCenter, Court, Customer, ServiceOrder
from .utils import generate_random_password

logger = logging.getLogger(__name__)


def _center_group_codes(center):
    return (
        Booking.objects.filter(court__center=center)
        .exclude(group_code__isnull=True)
        .exclude(group_code='')
        .values_list('group_code', flat=True)
        .distinct()
    )


def _centers_group_codes(centers):
    return (
        Booking.objects.filter(court__center__in=centers)
        .exclude(group_code__isnull=True)
        .exclude(group_code='')
        .values_list('group_code', flat=True)
        .distinct()
    )


@role_required('partner')
def partner_dashboard(request):
    try:
        partner = request.user.partner_profile
    except AttributeError:
        messages.error(request, "Bạn không có quyền truy cập trang này.")
        return redirect('home')

    centers = BadmintonCenter.objects.filter(partner=partner)
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    today_revenue = (
        Booking.objects.filter(
            court__center__in=centers,
            date=today,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        ).aggregate(total=Sum('total_price'))['total']
        or 0
    )

    yesterday_revenue = (
        Booking.objects.filter(
            court__center__in=centers,
            date=yesterday,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        ).aggregate(total=Sum('total_price'))['total']
        or 0
    )

    today_service_revenue = (
        ServiceOrder.objects.filter(
            center__in=centers,
            created_at__date=today,
        ).aggregate(total=Sum('total_amount'))['total']
        or 0
    )

    total_today_revenue = today_revenue + today_service_revenue

    if yesterday_revenue > 0:
        revenue_change = round(((today_revenue - yesterday_revenue) / yesterday_revenue) * 100, 1)
    else:
        revenue_change = 100 if today_revenue > 0 else 0

    today_bookings_count = (
        Booking.objects.filter(court__center__in=centers, date=today)
        .exclude(status=Booking.Status.ADMIN_CANCELLED)
        .count()
    )

    total_courts = Court.objects.filter(center__in=centers, is_active=True).count()

    pending_transactions = Transaction.objects.filter(
        booking_group_code__in=_centers_group_codes(centers),
        is_verified=False,
    ).count()

    seven_days_ago = today - timedelta(days=6)
    daily_revs = (
        Booking.objects.filter(
            court__center__in=centers,
            date__gte=seven_days_ago,
            date__lte=today,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        )
        .values('date')
        .annotate(total=Sum('total_price'))
    )
    rev_by_date = {row['date']: int(row['total'] or 0) for row in daily_revs}

    chart_labels = []
    chart_data = []
    day_names = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(day_names[d.weekday()])
        chart_data.append(rev_by_date.get(d, 0))

    upcoming_bookings = (
        Booking.objects.filter(
            court__center__in=centers,
            date=today,
            status__in=[
                Booking.Status.CONFIRMED,
                Booking.Status.COMPLETED,
                Booking.Status.PENDING,
                Booking.Status.WAITING_VERIFY,
            ],
        )
        .select_related('court', 'court__center', 'user', 'customer')
        .order_by('start_time')[:5]
    )

    start_of_month = today.replace(day=1)

    booking_cash = (
        Booking.objects.filter(
            court__center__in=centers,
            date__gte=start_of_month,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
            payment_method=Booking.PaymentMethod.CASH,
        ).aggregate(total=Sum('total_price'))['total']
        or 0
    )

    booking_transfer = (
        Booking.objects.filter(
            court__center__in=centers,
            date__gte=start_of_month,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
            payment_method=Booking.PaymentMethod.TRANSFER,
        ).aggregate(total=Sum('total_price'))['total']
        or 0
    )

    service_cash = (
        ServiceOrder.objects.filter(
            center__in=centers,
            created_at__date__gte=start_of_month,
            payment_method=ServiceOrder.PaymentMethod.CASH,
        ).aggregate(total=Sum('total_amount'))['total']
        or 0
    )

    service_transfer = (
        ServiceOrder.objects.filter(
            center__in=centers,
            created_at__date__gte=start_of_month,
            payment_method=ServiceOrder.PaymentMethod.TRANSFER,
        ).aggregate(total=Sum('total_amount'))['total']
        or 0
    )

    total_cash_month = int(booking_cash + service_cash)
    total_transfer_month = int(booking_transfer + service_transfer)

    context = {
        'centers': centers,
        'total_today_revenue': total_today_revenue,
        'revenue_change': revenue_change,
        'today_bookings_count': today_bookings_count,
        'total_courts': total_courts,
        'pending_transactions': pending_transactions,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'total_cash_month': total_cash_month,
        'total_transfer_month': total_transfer_month,
        'upcoming_bookings': upcoming_bookings,
        'today': today,
    }
    return render(request, 'partner/dashboard.html', context)


@role_required('partner')
def manage_staff(request, center_id):
    """Trang quản lý nhân viên của 1 center."""
    center = get_object_or_404(BadmintonCenter, id=center_id, partner=request.user.partner_profile)
    staff_list = StaffProfile.objects.filter(center=center).select_related('user').order_by('-created_at')
    staff_form = StaffForm()

    return render(request, 'partner/manage_staff.html', {
        'center': center,
        'staff_list': staff_list,
        'staff_form': staff_form,
    })


@role_required('partner')
def add_staff_to_center(request, center_id):
    """Thêm nhân viên mới vào center."""
    center = get_object_or_404(BadmintonCenter, id=center_id, partner=request.user.partner_profile)

    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            phone_number = data['phone_number']

            if User.objects.filter(username=phone_number).exists():
                messages.error(request, f"Số điện thoại '{phone_number}' đã được đăng ký!")
                return redirect('manage_staff', center_id=center_id)
            if User.objects.filter(email=data['email']).exists():
                messages.error(request, f"Email '{data['email']}' đã được đăng ký!")
                return redirect('manage_staff', center_id=center_id)

            try:
                password = generate_random_password(8)

                with transaction.atomic():
                    user = User.objects.create_user(
                        username=phone_number,
                        email=data['email'],
                        password=password,
                        full_name=data['full_name'],
                        phone_number=phone_number,
                        role=User.Role.STAFF,
                    )

                    staff_profile, _ = StaffProfile.objects.get_or_create(user=user)
                    staff_profile.center = center
                    staff_profile.position = data.get('position', 'Nhân viên')
                    staff_profile.is_active = True
                    staff_profile.save()

                try:
                    email_context = {
                        'full_name': user.full_name or user.username,
                        'username': user.username,
                        'password': password,
                        'email': user.email,
                        'phone_number': phone_number,
                        'position': data.get('position', 'Nhân viên'),
                        'center_name': center.name,
                        'support_phone': settings.SUPPORT_PHONE,
                    }
                    html_content = render_to_string('emails/add_staff_success.html', email_context)

                    email_msg = EmailMessage(
                        subject=f'[BadmintonPro] Thông tin tài khoản nhân viên - {center.name}',
                        body=html_content,
                        to=[user.email],
                    )
                    email_msg.content_subtype = 'html'
                    email_msg.send(fail_silently=True)
                except Exception as exc:
                    logger.warning("Failed sending welcome email to staff %s: %s", user.email, exc)

                messages.success(
                    request,
                    f"Đã thêm nhân viên '{user.full_name or user.username}' thành công! Thông tin tài khoản đã gửi về email.",
                )
            except Exception as exc:
                logger.exception("Error creating staff member for center %s", center_id)
                messages.error(request, f"Lỗi hệ thống: {exc}")
        else:
            messages.error(request, "Vui lòng kiểm tra lại thông tin nhập liệu.")

    return redirect('manage_staff', center_id=center_id)


@role_required('partner')
def edit_staff_member(request, staff_id):
    """Sửa thông tin nhân viên."""
    staff_profile = get_object_or_404(
        StaffProfile,
        id=staff_id,
        center__partner=request.user.partner_profile,
    )
    center = staff_profile.center

    if request.method == 'POST':
        user = staff_profile.user
        user.full_name = request.POST.get('full_name', user.full_name)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        user.email = request.POST.get('email', user.email)
        user.save()

        staff_profile.position = request.POST.get('position', staff_profile.position)
        is_active = request.POST.get('is_active')
        staff_profile.is_active = is_active in ('on', 'true', 'True', '1')
        staff_profile.save()

        messages.success(request, f"Đã cập nhật thông tin nhân viên '{user.full_name or user.username}'!")

    return redirect('manage_staff', center_id=center.id)


@role_required('partner')
@require_POST
def delete_staff_member(request, staff_id):
    """Xóa (vô hiệu hóa) nhân viên."""
    staff_profile = get_object_or_404(
        StaffProfile,
        id=staff_id,
        center__partner=request.user.partner_profile,
    )
    center = staff_profile.center
    staff_name = staff_profile.user.full_name or staff_profile.user.username

    staff_profile.is_active = False
    staff_profile.user.is_active = False
    staff_profile.user.save(update_fields=['is_active'])
    staff_profile.save(update_fields=['is_active'])

    messages.success(request, f"Đã xóa nhân viên '{staff_name}'!")
    return redirect('manage_staff', center_id=center.id)


@role_required('partner')
def revenue_management(request):
    """Trang tổng quan - hiển thị danh sách center với doanh thu mini."""
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)

    today = timezone.localdate()
    start_of_month = today.replace(day=1)
    centers_with_revenue = []
    total_all_revenue = 0

    for center in centers:
        group_codes = _center_group_codes(center)

        revenue_data = Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=True,
            verified_at__date__gte=start_of_month,
        ).aggregate(total_rev=Sum('amount'))
        month_revenue = revenue_data['total_rev'] or 0

        pending_count = Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=False,
        ).count()

        centers_with_revenue.append({
            'center': center,
            'month_revenue': month_revenue,
            'pending_count': pending_count,
        })
        total_all_revenue += month_revenue

    context = {
        'centers_data': centers_with_revenue,
        'total_all_revenue': total_all_revenue,
        'current_month': today.strftime('%m/%Y'),
    }
    return render(request, 'partner/revenue.html', context)


@role_required('partner')
def revenue_center_detail(request, center_id):
    """Chi tiết doanh thu của 1 center cụ thể."""
    center = get_object_or_404(BadmintonCenter, pk=center_id, partner=request.user.partner_profile)
    group_codes = _center_group_codes(center)

    today = timezone.localdate()
    period = request.GET.get('period', 'month')

    if period == 'day':
        start_date = today
    elif period == 'week':
        start_date = today - timedelta(days=7)
    elif period == 'month':
        start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=30)

    transactions = (
        Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=True,
            verified_at__date__gte=start_date,
        )
        .select_related('user', 'verified_by')
        .order_by('-verified_at')[:20]
    )

    all_verified = Transaction.objects.filter(
        booking_group_code__in=group_codes,
        is_verified=True,
        verified_at__date__gte=start_date,
    )
    total_revenue = all_verified.aggregate(total=Sum('amount'))['total'] or 0
    total_revenue_int = int(total_revenue)

    booking_cash = (
        Booking.objects.filter(
            court__center=center,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
            date__gte=start_date,
            payment_method=Booking.PaymentMethod.CASH,
        ).aggregate(total=Sum('total_price'))['total']
        or 0
    )

    service_cash = (
        ServiceOrder.objects.filter(
            center=center,
            created_at__date__gte=start_date,
            payment_method=ServiceOrder.PaymentMethod.CASH,
        ).aggregate(total=Sum('total_amount'))['total']
        or 0
    )

    booking_transfer = (
        Booking.objects.filter(
            court__center=center,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
            date__gte=start_date,
            payment_method=Booking.PaymentMethod.TRANSFER,
        ).aggregate(total=Sum('total_price'))['total']
        or 0
    )

    service_transfer = (
        ServiceOrder.objects.filter(
            center=center,
            created_at__date__gte=start_date,
            payment_method=ServiceOrder.PaymentMethod.TRANSFER,
        ).aggregate(total=Sum('total_amount'))['total']
        or 0
    )

    cash_revenue = int(booking_cash + service_cash)
    online_revenue = int(booking_transfer + service_transfer)

    seven_days_ago = today - timedelta(days=6)
    daily_revs = (
        Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=True,
            verified_at__date__gte=seven_days_ago,
            verified_at__date__lte=today,
        )
        .annotate(day=TruncDate('verified_at'))
        .values('day')
        .annotate(total=Sum('amount'))
    )
    rev_by_day = {row['day']: float(row['total'] or 0) for row in daily_revs}

    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%d/%m'))
        chart_data.append(rev_by_day.get(day, 0.0))

    context = {
        'center': center,
        'transactions': transactions,
        'total_revenue': total_revenue_int,
        'cash_revenue': cash_revenue,
        'online_revenue': online_revenue,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'selected_period': period,
    }
    return render(request, 'partner/revenue_detail.html', context)


@role_required('partner')
def export_revenue_csv(request):
    """Xuất tổng quan doanh thu tất cả cơ sở ra Excel."""
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    today = timezone.localdate()
    start_of_month = today.replace(day=1)

    headers = ['Tên Cơ Sở', 'Địa chỉ', 'Số đơn chờ duyệt', 'Doanh thu tháng (VND)']
    rows = []

    for center in centers:
        group_codes = _center_group_codes(center)

        revenue_data = Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=True,
            verified_at__date__gte=start_of_month,
        ).aggregate(total_rev=Sum('amount'))
        month_revenue = revenue_data['total_rev'] or 0

        pending_count = Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=False,
        ).count()

        rows.append([
            center.name,
            center.address,
            pending_count,
            int(month_revenue),
        ])

    return create_excel_response('bao_cao_tong_doanh_thu.xlsx', headers, rows, 'Tổng quan doanh thu')


@role_required('partner')
def export_revenue_detail_csv(request, center_id):
    """Xuất chi tiết doanh thu giao dịch của 1 cơ sở ra Excel."""
    center = get_object_or_404(BadmintonCenter, pk=center_id, partner=request.user.partner_profile)
    group_codes = _center_group_codes(center)

    today = timezone.localdate()
    period = request.GET.get('period', 'month')

    if period == 'day':
        start_date = today
    elif period == 'week':
        start_date = today - timedelta(days=7)
    else:
        start_date = today - timedelta(days=30)

    transactions = (
        Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=True,
            verified_at__date__gte=start_date,
        )
        .select_related('user', 'verified_by')
        .order_by('-verified_at')
    )

    headers = ['Mã GD (Hệ thống)', 'Nội dung Đặt sân', 'Khách hàng', 'Số tiền (VND)', 'Thời gian duyệt', 'Người duyệt']
    rows = []

    for trans in transactions:
        rows.append([
            f"#{trans.id}",
            trans.booking_group_code,
            trans.user.full_name or trans.user.username,
            int(trans.amount) if trans.amount else 0,
            trans.verified_at.strftime('%H:%M %d/%m/%Y') if trans.verified_at else '',
            trans.verified_by.username if trans.verified_by else '',
        ])

    return create_excel_response('bao_cao_chi_tiet_doanh_thu.xlsx', headers, rows, 'Chi tiết doanh thu')


@role_required('partner')
def schedule_management(request, center_id):
    center = get_object_or_404(BadmintonCenter, pk=center_id, partner=request.user.partner_profile)
    courts = Court.objects.filter(center=center, is_active=True)

    today = timezone.localdate()
    selected_date_str = request.GET.get('date')
    try:
        filter_date = (
            timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            if selected_date_str
            else today
        )
    except ValueError:
        filter_date = today

    center_bookings = (
        Booking.objects.filter(court__center=center, date=filter_date)
        .select_related('user', 'court')
        .order_by('start_time')
    )

    selected_court_id = request.GET.get('court_id')
    if selected_court_id:
        center_bookings = center_bookings.filter(court_id=selected_court_id)

    group_map = {}
    for b in center_bookings:
        key = b.group_code or b.booking_code
        group_map.setdefault(key, []).append(b)

    valid_group_codes = list(group_map.keys())
    transactions = (
        Transaction.objects.filter(booking_group_code__in=valid_group_codes)
        .select_related('user', 'verified_by')
        .order_by('-timestamp')
    )

    status = request.GET.get('status')
    keyword = request.GET.get('keyword')
    if status == 'verified':
        transactions = transactions.filter(is_verified=True)
    elif status == 'unverified':
        transactions = transactions.filter(is_verified=False)

    if keyword:
        transactions = transactions.filter(
            Q(transaction_reference__icontains=keyword)
            | Q(booking_group_code__icontains=keyword)
            | Q(amount__icontains=keyword)
        )

    for trans in transactions:
        trans.related_bookings = group_map.get(trans.booking_group_code, [])

    total_revenue = (
        transactions.filter(is_verified=True).aggregate(doanh_thu=Sum('amount'))['doanh_thu'] or 0
    )

    context = {
        'center': center,
        'courts': courts,
        'transactions': transactions,
        'total_revenue': total_revenue,
        'today_date': today.strftime("%Y-%m-%d"),
        'filter_date': filter_date,
    }
    return render(request, 'partner/schedule.html', context)


@role_required('partner')
def customer_management(request, center_id):
    center = get_object_or_404(BadmintonCenter, pk=center_id, partner=request.user.partner_profile)

    customers = Customer.objects.filter(center=center).order_by('-total_spent')
    keyword = request.GET.get('keyword', '')
    if keyword:
        customers = customers.filter(
            Q(name__icontains=keyword)
            | Q(phone__icontains=keyword)
            | Q(email__icontains=keyword)
        )

    sort_by = request.GET.get('sort', 'spent')
    if sort_by == 'spent':
        customers = customers.order_by('-total_spent')
    elif sort_by == 'recent':
        customers = customers.order_by('-last_booking')
    elif sort_by == 'name':
        customers = customers.order_by('name')

    total_customers = customers.count()
    vip_customers = customers.filter(total_spent__gt=5000000).count()
    avg_spent = customers.aggregate(avg=Avg('total_spent'))['avg'] or 0

    context = {
        'center': center,
        'customers': customers,
        'total_customers': total_customers,
        'vip_customers': vip_customers,
        'avg_spent': avg_spent,
        'keyword': keyword,
        'sort_by': sort_by,
        'form': CustomerForm(),
    }
    return render(request, 'partner/customers.html', context)


@role_required('partner')
@require_POST
def partner_add_customer(request, center_id):
    center = get_object_or_404(BadmintonCenter, pk=center_id, partner=request.user.partner_profile)
    form = CustomerForm(request.POST)

    if form.is_valid():
        customer = form.save(commit=False)
        customer.center = center
        customer.save()
        messages.success(request, f"Đã thêm khách hàng {customer.name} thành công.")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"Lỗi ở trường {field}: {error}")

    return redirect('customer_management', center_id=center_id)


@role_required('partner')
def partner_customer_history(request, customer_id):
    customer = get_object_or_404(
        Customer,
        pk=customer_id,
        center__partner=request.user.partner_profile,
    )

    bookings = Booking.objects.filter(
        customer=customer,
        court__center=customer.center,
    ).order_by('-date', '-start_time')

    context = {
        'customer': customer,
        'bookings': bookings,
        'center': customer.center,
    }
    return render(request, 'partner/customer_history.html', context)


@role_required('partner')
def centers_management(request):
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    center_form = BadmintonCenterForm()
    return render(request, 'partner/manage_centers.html', {'centers': centers, 'center_form': center_form})


@role_required('partner')
def partner_add_center(request):
    if request.method == 'POST':
        form = BadmintonCenterForm(request.POST, request.FILES)
        if form.is_valid():
            center = form.save(commit=False)
            center.partner = request.user.partner_profile
            center.save()
            form.save_m2m()
            messages.success(request, "Đã thêm trung tâm thành công!")
            return redirect('centers_management')
        messages.error(request, "Có lỗi xảy ra!")

    return redirect('centers_management')


@role_required('partner')
def export_centers_csv(request):
    """Xuất danh sách cơ sở ra file Excel."""
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)

    headers = ['Tên cơ sở', 'Địa chỉ', 'Giờ mở cửa', 'Giờ đóng cửa', 'Số lượng sân', 'Trạng thái']
    rows = []
    for center in centers:
        rows.append([
            center.name,
            center.address,
            center.open_time.strftime('%H:%M') if center.open_time else '',
            center.close_time.strftime('%H:%M') if center.close_time else '',
            center.courts.count(),
            'Hoạt động' if center.is_active else 'Tạm dừng',
        ])

    return create_excel_response('danh_sach_co_so.xlsx', headers, rows, 'Danh sách cơ sở')


@role_required('partner')
def partner_edit_center(request, center_id):
    center = get_object_or_404(BadmintonCenter, id=center_id, partner=request.user.partner_profile)
    if request.method == 'POST':
        form = BadmintonCenterForm(request.POST, request.FILES, instance=center)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật thông tin!")
        else:
            messages.error(request, "Có lỗi xảy ra!")
    return redirect('centers_management')


@role_required('partner')
@require_POST
def partner_delete_center(request, center_id):
    center = get_object_or_404(BadmintonCenter, id=center_id, partner=request.user.partner_profile)
    center.delete()
    messages.success(request, f"Đã xóa cơ sở '{center.name}' thành công!")
    return redirect('centers_management')


@role_required('partner')
def manage_courts(request, center_id):
    center = get_object_or_404(BadmintonCenter, id=center_id, partner=request.user.partner_profile)
    courts = center.courts.all()
    court_form = CourtForm()
    return render(request, 'partner/manage_courts.html', {
        'center': center,
        'courts': courts,
        'court_form': court_form,
    })


@role_required('partner')
def add_court(request, center_id):
    center = get_object_or_404(BadmintonCenter, id=center_id, partner=request.user.partner_profile)
    if request.method == 'POST':
        form = CourtForm(request.POST)
        if form.is_valid():
            court = form.save(commit=False)
            court.center = center
            court.save()
            form.save_m2m()
            messages.success(request, "Đã thêm sân!")
        else:
            messages.error(request, "Có lỗi xảy ra!")
    return redirect('manage_courts', center_id=center_id)


@role_required('partner')
def edit_court(request, court_id):
    court = get_object_or_404(Court, id=court_id, center__partner=request.user.partner_profile)
    center_id = court.center.id
    if request.method == 'POST':
        form = CourtForm(request.POST, instance=court)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật thông tin!")
        else:
            messages.error(request, "Có lỗi xảy ra!")
    return redirect('manage_courts', center_id=center_id)


@role_required('partner')
@require_POST
def delete_court(request, court_id):
    court = get_object_or_404(Court, id=court_id, center__partner=request.user.partner_profile)
    center_id = court.center.id
    court.delete()
    messages.success(request, "Đã xóa sân!")
    return redirect('manage_courts', center_id=center_id)


@role_required('partner')
def transactions_management(request):
    """Danh sách giao dịch chờ xác nhận của Partner."""
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    group_codes = _centers_group_codes(centers)

    transactions = (
        Transaction.objects.filter(booking_group_code__in=group_codes)
        .select_related('user', 'verified_by')
        .order_by('-timestamp')
    )

    filter_status = request.GET.get('status', 'pending')
    if filter_status == 'pending':
        transactions = transactions.filter(is_verified=False)
    elif filter_status == 'verified':
        transactions = transactions.filter(is_verified=True)

    context = {
        'transactions': transactions,
        'filter_status': filter_status,
    }
    return render(request, 'partner/transactions.html', context)


@role_required('partner')
def export_transactions_csv(request):
    """Xuất danh sách giao dịch ra file Excel."""
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    group_codes = _centers_group_codes(centers)

    transactions = (
        Transaction.objects.filter(booking_group_code__in=group_codes)
        .select_related('user', 'verified_by')
        .order_by('-timestamp')
    )

    filter_status = request.GET.get('status', 'all')
    if filter_status == 'pending':
        transactions = transactions.filter(is_verified=False)
    elif filter_status == 'verified':
        transactions = transactions.filter(is_verified=True)

    headers = ['Mã đơn hàng', 'Khách hàng', 'Số điện thoại', 'Số tiền (VND)', 'Mã giao dịch', 'Thời gian', 'Trạng thái', 'Người duyệt']
    rows = []

    for trans in transactions:
        rows.append([
            trans.booking_group_code,
            trans.user.full_name or trans.user.username,
            trans.user.phone_number or '',
            int(trans.amount) if trans.amount else 0,
            trans.transaction_reference,
            trans.timestamp.strftime('%H:%M %d/%m/%Y') if trans.timestamp else '',
            'Đã duyệt' if trans.is_verified else 'Chờ duyệt',
            trans.verified_by.username if trans.is_verified and trans.verified_by else '',
        ])

    return create_excel_response('danh_sach_giao_dich.xlsx', headers, rows, 'Danh sách giao dịch')


@role_required('partner')
@require_POST
def approve_transaction(request, transaction_id):
    """Duyệt giao dịch + cộng doanh thu & điểm loyalty."""
    trans = get_object_or_404(Transaction, id=transaction_id)
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    has_access = Booking.objects.filter(
        group_code=trans.booking_group_code,
        court__center__in=centers,
    ).exists()

    if not has_access:
        messages.error(request, "Bạn không có quyền duyệt giao dịch này!")
        return redirect_back(request, fallback='partner_transactions')

    if trans.is_verified:
        messages.warning(request, "Giao dịch này đã được duyệt trước đó!")
        return redirect_back(request, fallback='partner_transactions')

    success = process_approve_transaction(trans, request.user)
    if success:
        messages.success(request, f"Đã duyệt giao dịch {trans.transaction_reference}!")
    else:
        messages.warning(request, "Giao dịch này đã được duyệt trước đó!")

    return redirect_back(request, fallback='partner_transactions')


@role_required('partner')
def service_orders_management(request):
    """Danh sách hóa đơn dịch vụ của Partner."""
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)

    selected_center_id = request.GET.get('center_id')
    if selected_center_id:
        orders = ServiceOrder.objects.filter(center_id=selected_center_id, center__in=centers)
    else:
        orders = ServiceOrder.objects.filter(center__in=centers)

    today = timezone.localdate()
    selected_date_str = request.GET.get('date')
    try:
        selected_date = (
            timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            if selected_date_str
            else today
        )
    except ValueError:
        selected_date = today

    orders = (
        orders.filter(created_at__date=selected_date)
        .prefetch_related('items__product')
        .select_related('center')
        .order_by('-created_at')
    )

    stats = orders.aggregate(
        total_revenue=Sum('total_amount'),
        total_orders=Count('id'),
    )

    orders_with_items = [
        {'order': order, 'items': order.items.all()}
        for order in orders
    ]

    context = {
        'centers': centers,
        'selected_center_id': selected_center_id,
        'selected_date': selected_date,
        'today': today,
        'total_revenue': stats['total_revenue'] or 0,
        'total_orders': stats['total_orders'] or 0,
        'orders_with_items': orders_with_items,
    }
    return render(request, 'partner/service_orders.html', context)
