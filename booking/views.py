from django.shortcuts import render,get_object_or_404,redirect
from partner.models import Court,BadmintonCenter
from datetime import date, timedelta,datetime as dt
import json
from .models import Booking
from django.shortcuts import render, get_object_or_404
from datetime import date, timedelta, datetime as dt

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
        status__in=['cancelled', 'admin_cancelled']
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

def booking_confirm(request):
    if request.method == 'POST':
        booking_data_str = request.POST.get('booking_data')
        selected_date = request.POST.get('selected_date')
        try:
            booking_items = json.loads(booking_data_str)
        except:
            booking_items = []
        total_price = sum(item['price'] for item in booking_items)  
        context = {
            'booking_items': booking_items,
            'selected_date': selected_date,
            'total_price': total_price

        }
        return render(request, 'booking/booking_confirm.html', context)
    return redirect('home')