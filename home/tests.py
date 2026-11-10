import json

from django.test import Client, TestCase
from django.urls import reverse

from home.chatbot_engine import get_chatbot_response, normalize_text
from users.models import PartnerProfile, User


class HomeAndChatbotTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner = User.objects.create_user(
            username='partner_h',
            email='partner_h@test.com',
            password='Password@123',
            role=User.Role.PARTNER,
        )
        PartnerProfile.objects.create(user=self.partner, is_verified=True)
        self.staff = User.objects.create_user(
            username='staff_h',
            email='staff_h@test.com',
            password='Password@123',
            role=User.Role.STAFF,
        )

    def test_home_and_static_pages(self):
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        for name in ['about', 'terms', 'privacy', 'booking_guide', 'contact_partner', 'partner_info', 'faq']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

        self.client.force_login(self.partner)
        self.assertRedirects(self.client.get(reverse('home')), reverse('partner_dashboard'))

        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get(reverse('home')), reverse('pos_sales'), fetch_redirect_response=False)

    def test_chatbot_engine_matching_and_fallback(self):
        self.assertEqual(normalize_text('  Xin chào!!!  '), 'xin chào')
        self.assertIn('Hướng dẫn đặt sân', get_chatbot_response('Cách đặt sân thế nào?'))
        self.assertIn('Thông tin thanh toán', get_chatbot_response('Thanh toán chuyển khoản'))
        self.assertIn('chưa hiểu rõ', get_chatbot_response('xyzabcdef12345'))

    def test_chatbot_api_validation_and_csrf(self):
        self.assertEqual(self.client.get(reverse('chatbot_api')).status_code, 405)

        csrf_client = Client(enforce_csrf_checks=True)
        resp_no_csrf = csrf_client.post(
            reverse('chatbot_api'),
            data=json.dumps({'message': 'xin chào'}),
            content_type='application/json',
        )
        self.assertEqual(resp_no_csrf.status_code, 403)

        resp_empty = self.client.post(
            reverse('chatbot_api'),
            data=json.dumps({'message': '   '}),
            content_type='application/json',
        )
        self.assertEqual(resp_empty.status_code, 400)

        resp_ok = self.client.post(
            reverse('chatbot_api'),
            data=json.dumps({'message': 'hướng dẫn đặt sân'}),
            content_type='application/json',
        )
        self.assertEqual(resp_ok.status_code, 200)
        self.assertIn('reply', resp_ok.json())
