from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Booking
from django.utils import timezone
from datetime import timedelta
@shared_task
def send_booking_confirmation_email(user_email, booking_code, center_name, court_name, time_slots_str, total_price):
    """
    Gửi email HTML xác nhận đặt sân.
    """
    subject = f'[BadmintonPro] Xác nhận đặt sân thành công - {booking_code}'
    formatted_price = "{:,.0f}".format(total_price).replace(",", ".")
    context = {
        'booking_code': booking_code,
        'center_name': center_name,
        'court_name': court_name,
        'time_slots': time_slots_str,
        'total_price': formatted_price,
        'support_phone': '0988.888.888', # Ví dụ
    }
    html_content = render_to_string('emails/booking_success.html', context)
    
    text_content = strip_tags(html_content)

    try:
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content, 
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email]
        )
        
        
        email.attach_alternative(html_content, "text/html")
        
        email.send()
        return f"Email sent to {user_email}"
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return f"Failed: {str(e)}"
    
@shared_task
def cancel_expired_bookings():
    """
    Hủy các booking đã quá hạn thanh toán (ví dụ: quá 10 phút).
    """
    

    expiration_time = timezone.now() - timedelta(minutes=1)
    expired_bookings = Booking.objects.filter(
        status=Booking.Status.PENDING,
        created_at__lt=expiration_time
    )

    count = expired_bookings.count()
    if count > 0:
        expired_bookings.update(status=Booking.Status.ADMIN_CANCELLED)  
    return f"Cleaned {count} bookings"