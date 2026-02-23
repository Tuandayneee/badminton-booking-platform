from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import PartnerProfile



@shared_task
def send_register_confirmation_email(username, email, phone_number, bank_name, bank_account_number, bank_account_owner, contact_person):
    """
    Gửi email HTML xác nhận đăng kí.
    """
    subject = f'[BadmintonPro] Xác nhận đăng kí thành công - {username}'
    context = {
        'username': username,
        'email': email,
        'phone_number': phone_number,
        'bank_name': bank_name, 
        'bank_account_number': bank_account_number,
        'bank_account_owner': bank_account_owner,
        'contact_person': contact_person,
        'support_phone': '034.608.3728',
    }
    html_content = render_to_string('emails/register_partner_success.html', context)
    
    text_content = strip_tags(html_content)

    try:
     
       
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content, 
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email]
        )
        
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        return f"SUCCESS: Đã gửi email chào mừng đến {email}"
        
    except Exception as e:
        print(f"Lỗi gửi email: {e}")
        return f"Thất bại: {str(e)}"