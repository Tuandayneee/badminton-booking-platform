import json
import logging

from django.db.models import Min
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from home.chatbot_engine import get_chatbot_response
from partner.models import BadmintonCenter

logger = logging.getLogger(__name__)


@require_POST
def chatbot_api(request):
    """API endpoint cho chatbot - Rule-based, không cần API bên ngoài."""
    try:
        body = json.loads(request.body)
        user_message = body.get('message', '').strip()

        if not user_message:
            return JsonResponse({'error': 'Tin nhắn trống'}, status=400)

        reply = get_chatbot_response(user_message)
        return JsonResponse({'reply': reply})

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Dữ liệu JSON không hợp lệ'}, status=400)
    except Exception:
        logger.exception("Chatbot unexpected error")
        return JsonResponse({
            'reply': 'Xin lỗi, tôi đang gặp sự cố kỹ thuật. Vui lòng thử lại sau hoặc liên hệ hotline hỗ trợ 🙏'
        })


def home(request):
    if request.user.is_authenticated:
        if request.user.role == 'partner':
            return redirect('partner_dashboard')
        if request.user.role == 'staff':
            return redirect('pos_sales')

    centers = BadmintonCenter.objects.annotate(
        min_price=Min('courts__base_price_per_hour')
    )
    return render(request, 'home/home.html', {'centers': centers})


def partner_info(request):
    return render(request, 'home/partner_info.html')


def about_page(request):
    return render(request, 'home/about.html')


def terms_page(request):
    return render(request, 'home/terms.html')


def privacy_page(request):
    return render(request, 'home/privacy.html')


def booking_guide(request):
    return render(request, 'home/booking_guide.html')


def contact_partner(request):
    return render(request, 'home/contact_partner.html')


def faq(request):
    return render(request, 'home/faq.html')
