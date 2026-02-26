from django.shortcuts import render,get_object_or_404
from users.decorators import role_required
from django.shortcuts import redirect
from datetime import timedelta
from partner.utils import redirect_back
from .forms import BadmintonCenterForm, CourtForm, StaffForm, CustomerForm
from django.contrib import messages
from .models import BadmintonCenter, Court, Product, ServiceOrder, ServiceOrderItem
from booking.services import process_approve_transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
from booking.models import Booking, Transaction
from django.db.models import Q, Sum
from django.db import transaction
from partner.models import Customer
from django.db.models import Avg, Count
import json
from .utils import generate_random_password
from users.models import User, StaffProfile
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
@role_required('partner')
def partner_dashboard(request):
    try:
        partner = request.user.partner_profile
    except AttributeError:
        messages.error(request, "Bạn không có quyền truy cập trang này.")
        return redirect('home')
    
    centers = BadmintonCenter.objects.filter(partner=partner)
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    # Doanh thu booking
    today_revenue = Booking.objects.filter(
        court__center__in=centers,
        date=today,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
    ).aggregate(total=Sum('total_price'))['total'] or 0

    yesterday_revenue = Booking.objects.filter(
        court__center__in=centers,
        date=yesterday,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
    ).aggregate(total=Sum('total_price'))['total'] or 0

    # Doanh thu dịch vụ hôm nay
    today_service_revenue = ServiceOrder.objects.filter(
        center__in=centers,
        created_at__date=today
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    total_today_revenue = today_revenue + today_service_revenue

    # % thay đổi
    if yesterday_revenue > 0:
        revenue_change = round(((today_revenue - yesterday_revenue) / yesterday_revenue) * 100, 1)
    else:
        revenue_change = 100 if today_revenue > 0 else 0

    # Lịch đặt hôm nay
    today_bookings_count = Booking.objects.filter(
        court__center__in=centers,
        date=today
    ).exclude(status=Booking.Status.ADMIN_CANCELLED).count()

    total_courts = Court.objects.filter(center__in=centers, is_active=True).count()

    pending_transactions = Transaction.objects.filter(
        booking_group_code__in=Booking.objects.filter(
            court__center__in=centers
        ).values_list('group_code', flat=True),
        is_verified=False
    ).count()

    # Biểu đồ 7 ngày 
    chart_labels = []
    chart_data = []
    day_names = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(day_names[d.weekday()])
        day_rev = Booking.objects.filter(
            court__center__in=centers,
            date=d,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
        ).aggregate(total=Sum('total_price'))['total'] or 0
        chart_data.append(int(day_rev))

    #  Lịch sắp tới 
    upcoming_bookings = Booking.objects.filter(
        court__center__in=centers,
        date=today,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED, Booking.Status.PENDING, Booking.Status.WAITING_VERIFY]
    ).select_related('court', 'court__center', 'user', 'customer').order_by('start_time')[:5]

    # Doanh thu theo phương thức thanh toán trong tháng
    start_of_month = today.replace(day=1)
    
    booking_cash = Booking.objects.filter(
        court__center__in=centers,
        date__gte=start_of_month,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        payment_method=Booking.PaymentMethod.CASH
    ).aggregate(total=Sum('total_price'))['total'] or 0

    booking_transfer = Booking.objects.filter(
        court__center__in=centers,
        date__gte=start_of_month,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        payment_method=Booking.PaymentMethod.TRANSFER
    ).aggregate(total=Sum('total_price'))['total'] or 0

    service_cash = ServiceOrder.objects.filter(
        center__in=centers,
        created_at__date__gte=start_of_month,
        payment_method=ServiceOrder.PaymentMethod.CASH
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    service_transfer = ServiceOrder.objects.filter(
        center__in=centers,
        created_at__date__gte=start_of_month,
        payment_method=ServiceOrder.PaymentMethod.TRANSFER
    ).aggregate(total=Sum('total_amount'))['total'] or 0

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
    """Trang quản lý nhân viên của 1 center"""
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
    """Thêm nhân viên mới vào center"""
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
                    
                    
                    staff_profile, created = StaffProfile.objects.get_or_create(user=user)
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
                        'support_phone': '0123 456 789',
                    }
                    html_content = render_to_string('emails/add_staff_success.html', email_context)
                    
                    email_msg = EmailMessage(
                        subject=f'[BadmintonPro] Thông tin tài khoản nhân viên - {center.name}',
                        body=html_content,
                        to=[user.email],
                    )
                    email_msg.content_subtype = 'html'
                    email_msg.send(fail_silently=True)
                except Exception:
                    pass  
                
                messages.success(request, f"Đã thêm nhân viên '{user.full_name or user.username}' thành công! Thông tin tài khoản đã gửi về email.")
            except Exception as e:
                messages.error(request, f"Lỗi hệ thống: {str(e)}")
        else:
            messages.error(request, "Vui lòng kiểm tra lại thông tin nhập liệu.")
    
    return redirect('manage_staff', center_id=center_id)


@role_required('partner')
def edit_staff_member(request, staff_id):
    """Sửa thông tin nhân viên"""
    staff_profile = get_object_or_404(StaffProfile, id=staff_id)
    center = staff_profile.center
    
    if center.partner != request.user.partner_profile:
        messages.error(request, "Bạn không có quyền chỉnh sửa nhân viên này!")
        return redirect('centers_management')
    
    if request.method == 'POST':
        user = staff_profile.user
        user.full_name = request.POST.get('full_name', user.full_name)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        user.email = request.POST.get('email', user.email)
        user.save()
        
        staff_profile.position = request.POST.get('position', staff_profile.position)
        is_active = request.POST.get('is_active')
        staff_profile.is_active = is_active == 'on' or is_active == 'true'
        staff_profile.save()
        
        messages.success(request, f"Đã cập nhật thông tin nhân viên '{user.full_name or user.username}'!")
    
    return redirect('manage_staff', center_id=center.id)


@role_required('partner')
@require_POST
def delete_staff_member(request, staff_id):
    """Xóa (vô hiệu hóa) nhân viên"""
    staff_profile = get_object_or_404(StaffProfile, id=staff_id)
    center = staff_profile.center
    
    if center.partner != request.user.partner_profile:
        messages.error(request, "Bạn không có quyền xóa nhân viên này!")
        return redirect('centers_management')
    
    staff_name = staff_profile.user.full_name or staff_profile.user.username
    
    staff_profile.is_active = False
    staff_profile.user.is_active = False
    staff_profile.user.save()
    staff_profile.save()
    
    messages.success(request, f"Đã xóa nhân viên '{staff_name}'!")
    return redirect('manage_staff', center_id=center.id)


@role_required('partner')
def revenue_management(request):

    """Trang tổng quan - hiển thị danh sách center với doanh thu mini"""
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)

    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    centers_with_revenue = []
    total_all_revenue = 0
    for center in centers:
        group_codes = Booking.objects.filter(
            court__center=center
        ).values_list('group_code', flat=True).distinct()

        revenue_data = Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=True,
            verified_at__date__gte=start_of_month
        ).aggregate(
            total_rev=Sum('amount'),
        )
        month_revenue = revenue_data['total_rev'] or 0
        pending_count = Transaction.objects.filter(
            booking_group_code__in=group_codes,
            is_verified=False
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
    """Chi tiết doanh thu của 1 center cụ thể"""
    center = get_object_or_404(BadmintonCenter, pk=center_id, partner=request.user.partner_profile)
    group_codes = set()
    booking_codes = Booking.objects.filter(
        court__center=center
    ).values_list('booking_code', flat=True)
    for code in booking_codes:
        parts = code.rsplit('-', 1)
        if len(parts) > 1:
            group_codes.add(parts[0])
    today = timezone.now().date()
    period = request.GET.get('period', 'month')

    if period == 'day':
        start_date = today
    elif period == 'week':
        start_date = today - timedelta(days= 7)
    elif period == 'month':
        start_date = today - timedelta(days=30)

    transactions = Transaction.objects.filter(
        booking_group_code__in=group_codes,
        is_verified=True,
        verified_at__date__gte=start_date
    ).select_related('user','verified_by').order_by('-verified_at')[:20]


    all_verified = Transaction.objects.filter(
        booking_group_code__in=group_codes,
        is_verified=True,
        verified_at__date__gte=start_date
    )
    total_revenue = all_verified.aggregate(total=Sum('amount'))['total'] or 0
    total_revenue_int = int(total_revenue) if total_revenue else 0

    # Tính doanh thu Tiền Mặt (Booking cash + POS cash)
    booking_cash = Booking.objects.filter(
        court__center=center,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        date__gte=start_date,
        payment_method=Booking.PaymentMethod.CASH
    ).aggregate(total=Sum('total_price'))['total'] or 0

    service_cash = ServiceOrder.objects.filter(
        center=center,
        created_at__date__gte=start_date,
        payment_method=ServiceOrder.PaymentMethod.CASH
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Tính doanh thu Chuyển khoản (Booking transfer + POS transfer)
    booking_transfer = Booking.objects.filter(
        court__center=center,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        date__gte=start_date,
        payment_method=Booking.PaymentMethod.TRANSFER
    ).aggregate(total=Sum('total_price'))['total'] or 0

    service_transfer = ServiceOrder.objects.filter(
        center=center,
        created_at__date__gte=start_date,
        payment_method=ServiceOrder.PaymentMethod.TRANSFER
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    cash_revenue = int(booking_cash + service_cash)
    online_revenue = int(booking_transfer + service_transfer)

    chart_labels = []
    chart_data = []
    for i in range(6,-1,1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%d/%m'))
        day_revenue = Transaction.objects.filter(

            booking_group_code__in=group_codes,

            is_verified=True,

            verified_at__date=day

        ).aggregate(total=Sum('amount'))['total'] or 0

        chart_data.append(float(day_revenue))
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
def schedule_management(request,center_id):
    center = get_object_or_404(BadmintonCenter, pk=center_id)
    courts = Court.objects.filter(center=center, is_active=True)
    
    # Lấy ngày lọc
    today = timezone.now().date()
    selected_date_str = request.GET.get('date')
    try:
        filter_date = timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date() if selected_date_str else today
    except ValueError:
        filter_date = today

    # Lấy các slot lẻ 
    raw_bookings = Booking.objects.filter(
        court__center=center,
        date=filter_date
    ).select_related('user', 'court').order_by('start_time')

    selected_court_id = request.GET.get('court_id')
    if selected_court_id:
        raw_bookings = raw_bookings.filter(court_id=selected_court_id)

    grouped_schedule = {}
    
    for b in raw_bookings:
        # Lấy mã nhóm: BK-2026...-1 -> BK-2026...
        # Nếu là booking lẻ không có dấu gạch ngang, fallback về booking_code gốc
        group_code = b.booking_code.rsplit('-', 1)[0] if '-' in b.booking_code else b.booking_code
        
        if group_code not in grouped_schedule:
            grouped_schedule[group_code] = {
                'group_code': group_code,
                'user': b.user,
                'court_names': {b.court.name}, 
                'start_time': b.start_time,
                'end_time': b.end_time,
                'total_price': 0,
                'status': b.status,
                'is_paid': False,
                'slots_count': 0
            }
        
        
        item = grouped_schedule[group_code]
        item['total_price'] += b.total_price
        item['slots_count'] += 1
        item['court_names'].add(b.court.name)
        
        
        if b.start_time < item['start_time']: item['start_time'] = b.start_time
        if b.end_time > item['end_time']: item['end_time'] = b.end_time
        
        
        if b.status in ['confirmed', 'checked_in']:
            item['is_paid'] = True

    # Chuyển Dict thành List để gửi sang Template
    schedule_list = list(grouped_schedule.values())
    
    
    schedule_list.sort(key=lambda x: x['start_time'])

    context = {
        'center': center,
        'courts': courts,
        'schedule_list': schedule_list, 
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
            Q(name__icontains=keyword) | 
            Q(phone__icontains=keyword) |
            Q(email__icontains=keyword)
        )
    
    # Xử lý sắp xếp
    sort_by = request.GET.get('sort', 'spent')
    if sort_by == 'spent':
        customers = customers.order_by('-total_spent')
    elif sort_by == 'recent':
        customers = customers.order_by('-last_booking')
    elif sort_by == 'name':
        customers = customers.order_by('name')
    
    # Thống kê
    total_customers = customers.count()
    vip_customers = customers.filter(total_spent__gt=5000000).count()
    avg_spent = customers.aggregate(avg=Avg('total_spent'))['avg'] or 0
    
    # Form thêm khách hàng mới
    form = CustomerForm()

    context = {
        'center': center,
        'customers': customers,
        'total_customers': total_customers,
        'vip_customers': vip_customers,
        'avg_spent': avg_spent,
        'keyword': keyword,
        'sort_by': sort_by,
        'form': form,
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
    customer = get_object_or_404(Customer, pk=customer_id, center__partner=request.user.partner_profile)
    
    # Lấy lịch sử giao dịch/đặt sân của khách tại trung tâm này
    bookings = Booking.objects.filter(
        customer=customer, 
        court__center=customer.center
    ).order_by('-date', '-start_time')
    
    context = {
        'customer': customer,
        'bookings': bookings,
        'center': customer.center
    }
    return render(request, 'partner/customer_history.html', context)

@role_required('partner')
def centers_management(request):
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    center_form = BadmintonCenterForm()
    return render(request ,'partner/manage_centers.html', {'centers': centers, 'center_form': center_form})
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
        else:
            messages.error(request, "có lỗi xảy ra!")
            
    return redirect('centers_management')


@role_required('partner')
def partner_edit_center(request,center_id):
    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    if request.method == 'POST':
        
        form = BadmintonCenterForm(request.POST, request.FILES,instance=center)
        if form.is_valid():
            center = form.save()
            
            
            messages.success(request, "Đã cập nhập thông tin!")
            return redirect('centers_management')
        else:
            messages.error(request, "có lỗi xảy ra!")
            return redirect('partner_centers')
    return redirect('partner_centers')

@role_required('partner')
def partner_delete_center(request,center_id):

    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    if request.method == 'POST':

        center.delete()
        messages.success(request, f"Đã xóa cơ sở '{center.name}' thành công!")
    return redirect('centers_management')


@role_required('partner')
def manage_courts(request,center_id):
    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    courts = center.courts.all()
    court_form = CourtForm()
    return render(request, 'partner/manage_courts.html', {
        'center': center,
        'courts': courts,
        'court_form': court_form
    })


@role_required('partner')
def add_court(request,center_id):
    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    if request.method == 'POST':
        form = CourtForm(request.POST)
        if form.is_valid():
            court = form.save(commit=False)
            court.center = center
            court.save()
            form.save_m2m()
            messages.success(request, "Đã thêm sân!")
            return redirect('manage_courts', center_id=center_id)
        else:
            messages.error(request, "có lỗi xảy ra!")
    return redirect('manage_courts', center_id=center_id)          

@role_required('partner')
def edit_court(request,court_id):
    court = get_object_or_404(Court,id = court_id)
    center_id = court.center.id
    if request.method == 'POST':
        form = CourtForm(request.POST,instance=court)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhập thông tin!")
            return redirect('manage_courts', center_id=center_id)
        else:
            messages.error(request, "có lỗi xảy ra!")
    return redirect('manage_courts', center_id=center_id)

@role_required('partner')
def delete_court(request,court_id):
    court = get_object_or_404(Court,id = court_id)
    center_id = court.center.id
    if request.method == 'POST':
        court.delete()
        messages.success(request, "Đã xóa sân!")
    return redirect('manage_courts', center_id=center_id)


@role_required('partner')
def transactions_management(request):
    """Danh sách giao dịch chờ xác nhận của Partner"""
    
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    
    
    booking_codes = Booking.objects.filter(
        court__center__in=centers
    ).values_list('booking_code', flat=True)
    
    # Extract group codes 
    group_codes = set()
    for code in booking_codes:
        
        parts = code.rsplit('-', 1)
        if len(parts) > 1:
            group_codes.add(parts[0])
    
    # Lấy transactions có group_code thuộc partner
    transactions = Transaction.objects.filter(
        booking_group_code__in=group_codes
    ).select_related('user', 'verified_by').order_by('-timestamp')
    
    
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
@require_POST
def approve_transaction(request, transaction_id):
    """Duyệt giao dịch + cộng điểm"""
    trans = get_object_or_404(Transaction, id=transaction_id)
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    bookings = Booking.objects.filter(
        booking_code__startswith=trans.booking_group_code,
        court__center__in=centers
    )       
    
    if not bookings.exists():
        messages.error(request, "Bạn không có quyền duyệt giao dịch này!")
        return redirect('partner_transactions')
    
    if trans.is_verified:
        messages.warning(request, "Giao dịch này đã được duyệt trước đó!")
        return redirect('partner_transactions')
    
    success = process_approve_transaction(trans, request.user)
    
    if success:
        messages.success(request, f"Đã duyệt giao dịch {trans.transaction_reference}!")
    else:
        messages.warning(request, "Giao dịch này đã được duyệt trước đó!")
        
    return redirect('partner_transactions')


@role_required('partner')
def booking_court_history(request,center_id):
    center = get_object_or_404(BadmintonCenter, pk=center_id)
    if center.partner.user != request.user:
        messages.error(request, "Bạn không có quyền truy cập sân này.")
        return redirect('home')

    center_bookings = Booking.objects.filter(court__center=center)
    group_codes = center_bookings.values_list('booking_code', flat=True)

    bookings = center_bookings.select_related('user', 'court').order_by('-created_at')

    group_map = {}
    for b in bookings:
        group_code = b.booking_code.rsplit('-', 1)[0]
        if group_code not in group_map:
            group_map[group_code] = []
        group_map[group_code].append(b)

    valid_group_codes = list(group_map.keys())
    transactions = Transaction.objects.filter(
        booking_group_code__in=valid_group_codes
    ).select_related('user').order_by('-timestamp')

    status = request.GET.get('status') 
    keyword = request.GET.get('keyword')
    if status == 'verified':
        transactions = transactions.filter(is_verified=True)
    elif status == 'unverified':
        transactions = transactions.filter(is_verified=False)

    if keyword:
        transactions = transactions.filter(
            Q(transaction_reference__icontains=keyword) |
            Q(booking_group_code__icontains=keyword) |
            Q(amount__icontains=keyword)
        )


    for trans in transactions:
        trans.related_bookings = group_map.get(trans.booking_group_code, [])
    total_revenue = transactions.filter(is_verified=True).aggregate(doanh_thu=Sum('amount'))['doanh_thu'] or 0
    context = {
        'center': center,
        'transactions': transactions,
        'total_revenue': total_revenue,
    }
    return render(request, 'partner/schedule.html', context)  


@role_required('partner')
@require_POST
def partner_approve_transaction(request, transaction_id):
    trans = get_object_or_404(Transaction, id=transaction_id)
    related_booking = Booking.objects.filter(booking_code__startswith = trans.booking_group_code).select_related('court__center__partner__user').first()
    if not related_booking:
        messages.error(request, "Lỗi dữ liệu: Không tìm thấy đơn đặt sân tương ứng với giao dịch này.")
        return redirect_back(request, transaction_id)
    
    is_owner = (related_booking.court.center.partner.user == request.user)
    if not is_owner:
        messages.error(request, "Bạn không có quyền duyệt giao dịch của cơ sở khác!")
        return redirect('home')
    
    try:
        success = process_approve_transaction(trans, request.user)
        if success:
            messages.success(request, f"Đã duyệt giao dịch {trans.transaction_reference}!")
        else:
            messages.warning(request, "Giao dịch này đã được duyệt trước đó hoặc đang được xử lý.")
    except Exception as e:
        print(f"CRITICAL ERROR in partner_approve_transaction: {e}")
        messages.error(request, "Đã xảy ra lỗi hệ thống khi duyệt đơn. Vui lòng liên hệ Admin.")
    return redirect_back(request, transaction_id)


@role_required('partner')
def service_orders_management(request):
    """Danh sách hóa đơn dịch vụ của Partner"""
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)

    selected_center_id = request.GET.get('center_id')
    if selected_center_id:
        orders = ServiceOrder.objects.filter(center_id=selected_center_id, center__in=centers)
    else:
        orders = ServiceOrder.objects.filter(center__in=centers)

    today = timezone.now().date()
    selected_date_str = request.GET.get('date')
    try:
        selected_date = timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date() if selected_date_str else today
    except ValueError:
        selected_date = today

    orders = orders.filter(created_at__date=selected_date).order_by('-created_at')

    # Tổng hợp
    stats = orders.aggregate(
        total_revenue=Sum('total_amount'),
        total_orders=Count('id'),
    )

    
    orders_with_items = []
    for order in orders.prefetch_related('items__product').select_related('center'):
        items = order.items.all()
        orders_with_items.append({
            'order': order,
            'items': items,
        })

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