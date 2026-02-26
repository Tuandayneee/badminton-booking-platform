from django.db import transaction
from django.utils import timezone
from .models import Booking, Transaction
from .tasks import send_booking_confirmation_email
from users.models import CustomerProfile
@transaction.atomic
def process_approve_transaction(transaction_obj, approved_by_user):
    # Lock và kiểm tra
    try:
        transaction_obj = Transaction.objects.select_for_update().get(id=transaction_obj.id)
    except Transaction.DoesNotExist:
        return False

    if transaction_obj.is_verified:
        return False 

    # Update Transaction
    transaction_obj.is_verified = True
    transaction_obj.verified_at = timezone.now()
    transaction_obj.verified_by = approved_by_user
    transaction_obj.save()
    
    # lay list booking
    booking_list = list(Booking.objects.filter(
        booking_code__startswith=transaction_obj.booking_group_code
    ).select_related('court', 'court__center', 'customer', 'user', 'user__customer_profile'))
    
    if not booking_list:
        return True

    # Update status
    Booking.objects.filter(id__in=[b.id for b in booking_list]).update(status='confirmed')
    
    first_booking = booking_list[0]
    total_grp_price = sum(b.total_price for b in booking_list)

    # cong doanh thu
    if first_booking.customer:
        customer = first_booking.customer
        customer.total_spent = (customer.total_spent or 0) + total_grp_price
        customer.total_visits = (customer.total_visits or 0) + 1
        customer.last_booking = timezone.now()
        customer.save()

    # cong diem
    try:
        user = first_booking.user
        if user and hasattr(user, 'customer_profile'):
            profile = user.customer_profile
            points_earned = int(total_grp_price / 1000)
            if points_earned > 0:
                profile.points += points_earned
                profile.update_rank()
                profile.save()
    except Exception as e:
        print(f"ERROR Loyalty Update: {e}")

    # gui email xac nhan dat san
    if first_booking.user and first_booking.user.email:
        details_list = [
            f"{b.court.name} ({b.start_time.strftime('%H:%M')}-{b.end_time.strftime('%H:%M')})"
            for b in booking_list
        ]
        
        # Dùng on_commit để đảm bảo email chỉ gửi khi DB đã commit
        transaction.on_commit(lambda: send_booking_confirmation_email.delay(
            user_email=first_booking.user.email,
            booking_code=transaction_obj.booking_group_code,
            center_name=first_booking.court.center.name,
            court_name="; ".join(details_list),
            time_slots_str="",
            total_price=float(total_grp_price)
        ))

    return True