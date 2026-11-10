import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


@shared_task
def send_register_confirmation_email(
    username,
    email,
    phone_number,
    bank_name,
    bank_account_number,
    bank_account_owner,
    contact_person,
):
    """Gửi email HTML xác nhận đăng ký đối tác."""
    subject = f'[BadmintonPro] Xác nhận đăng kí thành công - {username}'
    context = {
        'username': username,
        'email': email,
        'phone_number': phone_number,
        'bank_name': bank_name,
        'bank_account_number': bank_account_number,
        'bank_account_owner': bank_account_owner,
        'contact_person': contact_person,
        'support_phone': settings.SUPPORT_PHONE,
    }
    html_content = render_to_string('emails/register_partner_success.html', context)
    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return f"SUCCESS: Đã gửi email chào mừng đến {email}"
    except Exception as exc:
        logger.exception("Failed sending partner registration email to %s", email)
        return f"Thất bại: {exc}"


@shared_task
def send_password_reset_email(user_id, reset_url):
    """Gửi email HTML chứa link đặt lại mật khẩu."""
    from .models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return f"FAILED: User ID {user_id} không tồn tại"

    subject = '[BadmintonPro] Yêu cầu đặt lại mật khẩu'
    context = {
        'username': user.username,
        'full_name': user.full_name or user.username,
        'reset_url': reset_url,
        'support_phone': settings.SUPPORT_PHONE,
    }
    html_content = render_to_string('emails/password_reset.html', context)
    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return f"SUCCESS: Đã gửi email reset mật khẩu đến {user.email}"
    except Exception as exc:
        logger.exception("Failed sending password reset email to %s", user.email)
        return f"Thất bại: {exc}"
