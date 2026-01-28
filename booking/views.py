from django.shortcuts import render,get_object_or_404,redirect
from partner.models import Court, BadmintonCenter, Customer
import json
from .models import Booking, Transaction
from django.shortcuts import render, get_object_or_404
from datetime import date, timedelta, datetime as dt
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction,IntegrityError
from django.contrib import messages
import redis



r = redis.Redis(host='redis', port=6379, db=0)
@login_required
def booking_timeline(request, center_id):
    center = get_object_or_404(BadmintonCenter, pk=center_id)
    courts = Court.objects.filter(center=center, is_active=True)
    
    time_labels = []
    
    # 1. Xử lý ngày tháng (Giữ nguyên logic của bạn)
    today = date.today()
    end_of_year = date(today.year, 12, 31)
    now = dt.now()
    current_real_time = now.time()


    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            current_date = dt.strptime(selected_date_str, "%Y-%m-%d").date()
            if current_date < today:
                current_date = today
        except ValueError:
            current_date = today
    else:
        current_date = today
    is_today = (current_date == today)


    # 2. Lấy danh sách lịch đã đặt trong ngày đó
    booked_slots = Booking.objects.filter(
        court__center=center,
        date=current_date,
    ).exclude(
        status__in=['cancelled', 'admin_cancelled','failed']
    )

    # 3. Tạo khung giờ (Giữ nguyên logic của bạn)
    if center.open_time:
        start_datetime = dt.combine(current_date, center.open_time)
    else:
        start_datetime = dt.combine(current_date, dt.strptime("05:00", "%H:%M").time())

    if center.close_time:
        end_datetime = dt.combine(current_date, center.close_time)
    else:
        end_datetime = dt.combine(current_date, dt.strptime("22:00", "%H:%M").time())

    current = start_datetime
    while current <= end_datetime:
        time_labels.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)

    # 4. Xử lý dữ liệu từng sân (LOGIC QUAN TRỌNG NHẤT)
    courts_data = []
    for court in courts:
        slots_info = []

        # Lọc booking của riêng sân này
        court_specific_bookings = booked_slots.filter(court=court)
        
        for time_str in time_labels:
            price = court.get_price_at_time(time_str)
            current_slot_time = dt.strptime(time_str, "%H:%M").time()
            
            if current_date < today:
                status = 'expired'
            elif is_today and current_slot_time < current_real_time:
                status = 'expired'
            else:
                status = 'free'

            
            for booking in court_specific_bookings:
               
                if booking.start_time <= current_slot_time < booking.end_time:
                    print(f"DEBUG: Sân {court.name} lúc {time_str} bị chiếm bởi Booking ID: {booking.id} - Status: {booking.status}")
                    if status == 'expired':
                        status = 'completed' 
                    else:
                        status = 'booked' 
                    break
            

            
            
            is_golden = False
            # Chỉ check giờ vàng nếu status đang là 'free' (tối ưu hiệu năng)
            if status == 'free' and court.golden_start_time and court.golden_end_time:
                if court.golden_start_time <= current_slot_time < court.golden_end_time:
                    is_golden = True
            
        
            slots_info.append({
                'time': time_str,
                'price': price,
                'is_golden': is_golden,
                'status': status, 
            })
            
        courts_data.append({
            'court_obj': court,
            'slots': slots_info
        })

    context = {
        'center': center,
        'time_labels': time_labels,
        'courts_data': courts_data, 
        'selected_date': current_date.strftime('%Y-%m-%d'),
        'min_date': today.strftime('%Y-%m-%d'),             
        'max_date': end_of_year.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'booking/booking_timeline.html', context)

@login_required
@require_POST
def booking_confirm(request):
    booking_data_str = request.POST.get('booking_data')
    selected_date_str = request.POST.get('selected_date')
    center_id = request.POST.get('center_id')
    center = get_object_or_404(BadmintonCenter, pk=center_id)

    try:
        booking_items = json.loads(booking_data_str)
        selected_date = dt.strptime(selected_date_str, "%Y-%m-%d").date()
    except:
        booking_items = []
        selected_date = None
    total_price = sum(item['price'] for item in booking_items)  
    context = {
        'center': center,  
        'booking_items': booking_items,
        'booking_data_json': booking_data_str, 
        'selected_date': selected_date,
        'total_price': total_price

    }
    return render(request, 'booking/booking_confirm.html', context)

@login_required
@require_POST
def booking_save(request):
    
    if request.method == 'POST':
        acquired_locks = []
        try:
            booking_data_str = request.POST.get('booking_data')
            selected_date_str = request.POST.get('selected_date')
            center_id = request.POST.get('center_id')
            center = get_object_or_404(BadmintonCenter, pk=center_id)

            full_name = request.POST.get('full_name') or request.user.full_name
            phone_number = request.POST.get('phone_number') or request.user.phone_number
            email = request.user.email or ''
            note = request.POST.get('note', '')

            booking_items = json.loads(booking_data_str)
            booking_date = dt.strptime(selected_date_str, "%Y-%m-%d").date()
        
            
            
            
            for item in booking_items:
                court_id = item['court_id']
                start_time_str = item['time']
                lock_key = f"lock:court_{court_id}_{booking_date}_{start_time_str}"
                is_locked = r.set(lock_key, "holding", nx=True, ex=20)
                if not is_locked:
                    for key in acquired_locks:
                        r.delete(key)
                    messages.error(request, f"Rất tiếc! Khung giờ {start_time_str} vừa có người khác bấm đặt trước bạn 1 giây.")
                    return redirect('booking_timeline', center_id=center_id)
                acquired_locks.append(lock_key)

            timestamp = dt.now().strftime('%Y%m%d-%H%M%S')
            group_code = f"BK-{timestamp}"
            saved_count = 0
            total_order_price = 0
            with transaction.atomic():
                # Tìm hoặc tạo Customer dựa trên phone (unique per center)
                customer, created = Customer.objects.get_or_create(
                    center=center,
                    phone=phone_number,
                    defaults={
                        'name': full_name,
                        'email': email,
                    }
                )
                # Nếu khách đã tồn tại, cập nhật tên nếu có thay đổi
                if not created and full_name:
                    customer.name = full_name
                    customer.save()
                
                for item in booking_items:

                    start_time = dt.strptime(item['time'], "%H:%M").time()
                    end_time_dt = dt.combine(date.today(), start_time) + timedelta(minutes=30)
                    end_time = end_time_dt.time()
                    unique_code = f"BK-{timestamp}-{saved_count + 1}"
                    Booking.objects.create(
                        booking_code=unique_code,
                        user=request.user,
                        court_id=item['court_id'],
                        customer=customer,
                        date=booking_date,
                        start_time=start_time,
                        end_time=end_time,  
                        total_price=item['price'],
                        status='pending',
                        note=note
                    )
                    total_order_price += item['price']
                    saved_count += 1
                
                customer.save()
            for key in acquired_locks:
                r.delete(key)       
            messages.success(request, "Đã giữ sân thành công! Vui lòng thanh toán.")
            return redirect('booking_payment', group_code=group_code)
        except IntegrityError :
            for key in acquired_locks: r.delete(key)
            messages.error(request, "Lỗi dữ liệu: Khung giờ này đã tồn tại trong hệ thống.")
            return redirect('home')
        except Exception as e:
            for key in acquired_locks: r.delete(key)
            messages.warning(request, str(e))
            return redirect('booking_timeline', center_id=request.POST.get('center_id'))
    return redirect('home')
@login_required
def booking_payment(request,group_code):
    bookings = Booking.objects.filter(booking_code__startswith=group_code, user=request.user)
    if not bookings.exists():
        messages.error(request, "Đơn hàng không tồn tại!")
        return redirect('home')
    
    first_booking = bookings.first()
    center = first_booking.court.center
    total_price = sum(b.total_price for b in bookings)
    bank_id = "MB" 
    account_no = "0346083728" 
    account_name = "LE ANH TUAN"
    content = f"THANHTOAN {group_code}"
    qr_url = f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact.png?amount={int(total_price)}&addInfo={content}&accountName={account_name}"
    
    timeout_minutes = 1
    create_at = first_booking.created_at
    expire_time = create_at + timedelta(minutes=timeout_minutes)
    remaining_seconds = (expire_time - timezone.now()).total_seconds()
    if remaining_seconds <= 0:
        for b in bookings:
            time_str = b.start_time.strftime("%H:%M")
            lock_key = f"lock:court_{b.court.id}_{b.date}_{time_str}"
            try:
                r.delete(lock_key)
            except:
                pass
        bookings.update(status='admin_cancelled')
        messages.error(request, "Đơn hàng đã hết hạn thanh toán!")
        return redirect('home')
    context = {
        'bookings': bookings,
        'first_booking': first_booking,
        'total_price': total_price,
        'group_code': group_code,
        'qr_url': qr_url,
        'bank_info': {
            'bank_name': "MB Bank",
            'account_no': account_no,
            'account_name': account_name
        },
        'time_left': int(remaining_seconds),
    }
    return render(request, 'booking/booking_payment.html', context)


@login_required
@require_POST
def booking_success_confirm(request, group_code):
    bookings = Booking.objects.filter(booking_code__startswith=group_code, user=request.user)
    if not bookings.exists():
        messages.error(request, "Không tìm thấy đơn hàng!")
        return redirect('home')
    total_price = sum(b.total_price for b in bookings)  
    user_trans_code = request.POST.get('transaction_code', '')
    if not user_trans_code:
        messages.error(request, "Vui lòng nhập mã giao dịch!")
        return redirect('booking_payment', group_code=group_code)
    try:

        Transaction.objects.create(
            booking_group_code=group_code,
            user=request.user,
            amount=total_price,
            transaction_reference=user_trans_code,
            is_verified=False
        )           
        bookings.update(status='waiting_verify')
        messages.success(request, "Đã gửi xác nhận thanh toán! Vui lòng chờ Admin duyệt trong ít phút.")
        return redirect('home')
    except IntegrityError:
        messages.error(request, f"Mã giao dịch '{user_trans_code}' đã tồn tại trên hệ thống. Vui lòng kiểm tra lại!")
        return redirect('booking_payment', group_code=group_code)
    
def generate_bookings_from_fixed_schedule(fixed_schedule):
    current_date = fixed_schedule.start_date
    booking_to_create = []
    while current_date <= fixed_schedule.end_date:
        if current_date.weekday() in fixed_schedule.days_of_week:
            bookinng = Booking(booking_code=generate_booking_code(),
                user=fixed_schedule.user,
                court=fixed_schedule.court,
                fixed_schedule=fixed_schedule,
                date=current_date,
                start_time=fixed_schedule.start_time,
                end_time=fixed_schedule.end_time,
                total_price=fixed_schedule.price,
                status='confirmed'
            )
            booking_to_create.append(bookinng)
        current_date += timedelta(days=1)
    Booking.objects.bulk_create(booking_to_create)  

