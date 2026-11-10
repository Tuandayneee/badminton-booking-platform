import logging

from django.db import transaction
from django.utils import timezone

from .models import Booking, Transaction
from .tasks import send_booking_confirmation_email

logger = logging.getLogger(__name__)


@transaction.atomic
def process_approve_transaction(transaction_obj, approved_by_user):
    try:
        transaction_obj = Transaction.objects.select_for_update().get(id=transaction_obj.id)
    except Transaction.DoesNotExist:
        return False

    if transaction_obj.is_verified:
        return False

    transaction_obj.is_verified = True
    transaction_obj.verified_at = timezone.now()
    transaction_obj.verified_by = approved_by_user
    transaction_obj.save()

    booking_list = list(
        Booking.objects.filter(
            group_code=transaction_obj.booking_group_code
        ).select_related('court', 'court__center', 'customer', 'user', 'user__customer_profile')
    )

    if not booking_list:
        return True

    Booking.objects.filter(id__in=[b.id for b in booking_list]).update(status=Booking.Status.CONFIRMED)

    first_booking = booking_list[0]
    total_grp_price = sum(b.total_price for b in booking_list)

    if first_booking.customer:
        customer = first_booking.customer
        customer.total_spent = (customer.total_spent or 0) + total_grp_price
        customer.total_visits = (customer.total_visits or 0) + 1
        customer.last_booking = timezone.now()
        customer.save()

    try:
        user = first_booking.user
        if user and hasattr(user, 'customer_profile'):
            profile = user.customer_profile
            points_earned = int(total_grp_price / 1000)
            if points_earned > 0:
                profile.points += points_earned
                profile.update_rank()
    except Exception:
        logger.exception("Failed updating loyalty profile for booking group %s", transaction_obj.booking_group_code)

    if first_booking.user and first_booking.user.email:
        details_list = [
            f"{b.court.name} ({b.start_time.strftime('%H:%M')}-{b.end_time.strftime('%H:%M')})"
            for b in booking_list
        ]

        transaction.on_commit(lambda: send_booking_confirmation_email.delay(
            user_email=first_booking.user.email,
            booking_code=transaction_obj.booking_group_code,
            center_name=first_booking.court.center.name,
            court_name="; ".join(details_list),
            time_slots_str="",
            total_price=float(total_grp_price),
        ))

    return True
