from django.utils import timezone
from .models import Booking, Transaction
from partner.models import Customer
from .tasks import send_booking_confirmation_email
from django.db.models import Sum
def process_approve_transaction(transaction, approved_by_user):
    """
    Xử lý logic duyệt giao dịch:
    1. Update Transaction
    2. Update Booking status
    3. Cộng điểm thưởng
    """
    if transaction.is_verified:
        return False # Đã duyệt rồi thì bỏ qua

    # 1. Update Transaction
    transaction.is_verified = True
    transaction.verified_at = timezone.now()
    transaction.verified_by = approved_by_user
    transaction.save()
   
    bookings = Booking.objects.filter(booking_code__startswith=transaction.booking_group_code)
    rows_updated = bookings.update(status='confirmed')
    if rows_updated == 0:
        return True
    first_booking = bookings.first()
    
    total_price = bookings.aggregate(Sum('total_price'))['total_price__sum'] or 0
    # a. Cộng doanh thu cho Customer (CRM)
    if first_booking and first_booking.customer:
        customer = first_booking.customer
        total_grp_price = sum(b.total_price for b in bookings)
        customer.total_spent = (customer.total_spent or 0) + total_grp_price
        customer.total_visits = (customer.total_visits or 0) + 1
        customer.last_booking = timezone.now()
        customer.save()
    

    # b. Cộng điểm Loyalty
    user = first_booking.user
    if user and hasattr(user, 'customer_profile'):
        try:
            profile = user.customer_profile
            total_money = sum(b.total_price for b in bookings)
            points_earned = int(total_money / 1000)
            profile.points += points_earned
            profile.update_rank() 
            profile.save()
        except Exception as e:
            print(f"Lỗi cộng điểm Loyalty: {e}")
            pass
    if first_booking and first_booking.user.email:
        try:
            
            # Celery chỉ nhận JSON serializable (str, int, list), không nhận Object DateTime
            time_slots_list = [
                f"{b.start_time.strftime('%H:%M')}-{b.end_time.strftime('%H:%M')}" 
                for b in bookings
            ]
            time_slots_str = ", ".join(time_slots_list)
            
            
            send_booking_confirmation_email.delay(
                user_email=first_booking.user.email,
                booking_code=transaction.booking_group_code,
                center_name=first_booking.court.center.name,
                court_name=first_booking.court.name,
                time_slots_str=time_slots_str,
                total_price=float(total_price) 
            )
        except Exception as e:
            print(f"Lỗi gọi task gửi mail: {e}")
    return True