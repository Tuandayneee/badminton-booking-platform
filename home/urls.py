
from django.urls import path
from .views import home, partner_info, about_page, terms_page, privacy_page, booking_guide, contact_partner, faq, chatbot_api
urlpatterns = [
    path('', home ,name='home'),
    path('api/chatbot/', chatbot_api, name='chatbot_api'),

    path('partner-info/', partner_info, name='partner_info'),
    path('about/', about_page, name='about'),
    path('terms/', terms_page, name='terms'),
    path('privacy/', privacy_page, name='privacy'),
    path('booking-guide/', booking_guide, name='booking_guide'),
    path('contact-partner/', contact_partner, name='contact_partner'),
    path('faq/', faq, name='faq'),
]
