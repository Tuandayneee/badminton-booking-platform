from django.shortcuts import render,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .forms import BadmintonCenterForm, CourtForm
from django.contrib import messages
from .models import BadmintonCenter,Court
from booking.services import process_approve_transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
from booking.models import Booking, Transaction
@login_required 
def partner_dashboard(request):
    
    return render(request, 'partner/dashboard.html')


@login_required
def revenue_management(request):
    return render(request, 'partner/revenue.html')
@login_required
def schedule_management(request,center_id):
    center = get_object_or_404(BadmintonCenter, pk=center_id)
    courts = Court.objects.filter(center=center, is_active=True)
    
    # 1. Xử lý ngày lọc
    today = timezone.now().date()
    selected_date_str = request.GET.get('date')
    try:
        filter_date = timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date() if selected_date_str else today
    except ValueError:
        filter_date = today

    # 2. Lấy các slot lẻ (Raw Bookings)
    raw_bookings = Booking.objects.filter(
        court__center=center,
        date=filter_date
    ).select_related('user', 'court').order_by('start_time')

    # Lọc theo sân nếu có
    selected_court_id = request.GET.get('court_id')
    if selected_court_id:
        raw_bookings = raw_bookings.filter(court_id=selected_court_id)

    # 3. THUẬT TOÁN GOM NHÓM (Grouping Algorithm)
    grouped_schedule = {}
    
    for b in raw_bookings:
        # Lấy mã nhóm: BK-2026...-1 -> BK-2026...
        # Nếu là booking lẻ không có dấu gạch ngang, fallback về booking_code gốc
        group_code = b.booking_code.rsplit('-', 1)[0] if '-' in b.booking_code else b.booking_code
        
        if group_code not in grouped_schedule:
            grouped_schedule[group_code] = {
                'group_code': group_code,
                'user': b.user,
                'court_names': {b.court.name}, # Dùng Set để không bị trùng tên sân
                'start_time': b.start_time,
                'end_time': b.end_time,
                'total_price': 0,
                'status': b.status,
                'is_paid': False, # Logic check thanh toán
                'slots_count': 0
            }
        
        # Cộng dồn thông tin
        item = grouped_schedule[group_code]
        item['total_price'] += b.total_price
        item['slots_count'] += 1
        item['court_names'].add(b.court.name)
        
        # Cập nhật thời gian Min - Max
        if b.start_time < item['start_time']: item['start_time'] = b.start_time
        if b.end_time > item['end_time']: item['end_time'] = b.end_time
        
        # Kiểm tra trạng thái thanh toán (Logic tạm: confirmed = đã cọc/thanh toán)
        if b.status in ['confirmed', 'checked_in']:
            item['is_paid'] = True

    # Chuyển Dict thành List để gửi sang Template
    schedule_list = list(grouped_schedule.values())
    
    # Sắp xếp lại danh sách theo giờ bắt đầu
    schedule_list.sort(key=lambda x: x['start_time'])

    context = {
        'center': center,
        'courts': courts,
        'schedule_list': schedule_list, # Dùng biến mới này thay vì 'bookings'
        'today_date': today.strftime("%Y-%m-%d"),
        'filter_date': filter_date,
    }
    
    return render(request, 'partner/schedule.html', context)


@login_required
def customer_management(request,center_id):
    return render(request, 'partner/customers.html')

@login_required
def centers_management(request):
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    center_form = BadmintonCenterForm()
    return render(request ,'partner/manage_centers.html', {'centers': centers, 'center_form': center_form})
@login_required
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


@login_required
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

@login_required
def partner_delete_center(request,center_id):

    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    if request.method == 'POST':

        center.delete()
        messages.success(request, f"Đã xóa cơ sở '{center.name}' thành công!")
    return redirect('centers_management')


@login_required
def manage_courts(request,center_id):
    center = get_object_or_404(BadmintonCenter,id = center_id, partner=request.user.partner_profile)
    courts = center.courts.all()
    court_form = CourtForm()
    return render(request, 'partner/manage_courts.html', {
        'center': center,
        'courts': courts,
        'court_form': court_form
    })


@login_required
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

@login_required
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

@login_required
def delete_court(request,court_id):
    court = get_object_or_404(Court,id = court_id)
    center_id = court.center.id
    if request.method == 'POST':
        court.delete()
        messages.success(request, "Đã xóa sân!")
    return redirect('manage_courts', center_id=center_id)


@login_required
def transactions_management(request):
    """Danh sách giao dịch chờ xác nhận của Partner"""
    # Lấy tất cả center thuộc partner
    centers = BadmintonCenter.objects.filter(partner=request.user.partner_profile)
    
    # Lấy tất cả booking_code prefix của các center này
    booking_codes = Booking.objects.filter(
        court__center__in=centers
    ).values_list('booking_code', flat=True)
    
    # Extract group codes (BK-YYYYMMDD-HHMMSS format, lấy phần trước số cuối)
    group_codes = set()
    for code in booking_codes:
        # VD: BK-20260124-163000-1 -> BK-20260124-163000
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


@login_required
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