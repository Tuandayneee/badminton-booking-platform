from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from booking.models import Booking
from partner.models import BadmintonCenter, Court
from users.models import CustomerProfile, PartnerProfile, StaffProfile, User


class UserAuthProfileAndResetTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            username='cust_u',
            email='cust_u@test.com',
            password='Password@123',
            role=User.Role.CUSTOMER,
        )
        self.partner_user = User.objects.create_user(
            username='partner_u',
            email='partner_u@test.com',
            password='Password@123',
            role=User.Role.PARTNER,
        )
        self.staff_user = User.objects.create_user(
            username='staff_u',
            email='staff_u@test.com',
            password='Password@123',
            role=User.Role.STAFF,
        )
        self.admin_user = User.objects.create_superuser(
            username='admin_u',
            email='admin_u@test.com',
            password='Password@123',
            role=User.Role.ADMIN,
        )

    def test_profile_signals_and_rank_progression(self):
        self.assertTrue(CustomerProfile.objects.filter(user=self.customer).exists())
        self.assertTrue(StaffProfile.objects.filter(user=self.staff_user).exists())

        profile = self.customer.customer_profile
        profile.points = 120
        profile.update_rank()
        self.assertEqual(profile.rank, CustomerProfile.Ranking.SILVER)

        profile.points = 250
        profile.update_rank()
        self.assertEqual(profile.rank, CustomerProfile.Ranking.GOLD)

        profile.points = 500
        profile.update_rank()
        self.assertEqual(profile.rank, CustomerProfile.Ranking.DIAMOND)

    def test_login_role_redirects_and_missing_partner_profile_safety(self):
        # Customer -> home
        resp_cust = self.client.post(reverse('login'), {
            'username': 'cust_u',
            'password': 'Password@123',
        })
        self.assertRedirects(resp_cust, reverse('home'))

        # Partner without PartnerProfile does not crash
        resp_no_profile = self.client.post(reverse('login'), {
            'username': 'partner_u',
            'password': 'Password@123',
        })
        self.assertRedirects(resp_no_profile, reverse('login'))

        # Unverified partner blocked
        profile = PartnerProfile.objects.create(user=self.partner_user, is_verified=False)
        resp_unverified = self.client.post(reverse('login'), {
            'username': 'partner_u',
            'password': 'Password@123',
        })
        self.assertRedirects(resp_unverified, reverse('login'))

        # Verified partner -> partner_dashboard
        profile.is_verified = True
        profile.save()
        resp_verified = self.client.post(reverse('login'), {
            'username': 'partner_u',
            'password': 'Password@123',
        })
        self.assertRedirects(resp_verified, reverse('partner_dashboard'))

        # Staff -> pos_sales (fetch_redirect_response=False since staff has no center yet)
        resp_staff = self.client.post(reverse('login'), {
            'username': 'staff_u',
            'password': 'Password@123',
        })
        self.assertRedirects(resp_staff, reverse('pos_sales'), fetch_redirect_response=False)

        # Admin -> /admin/
        resp_admin = self.client.post(reverse('login'), {
            'username': 'admin_u',
            'password': 'Password@123',
        })
        self.assertRedirects(resp_admin, '/admin/', fetch_redirect_response=False)

    def test_customer_profile_excludes_cancelled_and_pending_from_total_spent(self):
        partner_profile = PartnerProfile.objects.create(user=self.partner_user, is_verified=True)
        center = BadmintonCenter.objects.create(name='Sân U', partner=partner_profile, address='HN')
        court = Court.objects.create(name='Sân 1', center=center, base_price_per_hour=Decimal('100000'))
        tomorrow = timezone.localdate() + timedelta(days=1)

        Booking.objects.create(
            booking_code='BK-U-1',
            group_code='BK-U1',
            user=self.customer,
            court=court,
            date=tomorrow,
            start_time=time(8, 0),
            end_time=time(9, 0),
            total_price=Decimal('100000'),
            status=Booking.Status.CONFIRMED,
        )
        Booking.objects.create(
            booking_code='BK-U-2',
            group_code='BK-U2',
            user=self.customer,
            court=court,
            date=tomorrow,
            start_time=time(10, 0),
            end_time=time(11, 0),
            total_price=Decimal('200000'),
            status=Booking.Status.ADMIN_CANCELLED,
        )
        Booking.objects.create(
            booking_code='BK-U-3',
            group_code='BK-U3',
            user=self.customer,
            court=court,
            date=tomorrow,
            start_time=time(12, 0),
            end_time=time(13, 0),
            total_price=Decimal('150000'),
            status=Booking.Status.PENDING,
        )

        self.client.force_login(self.customer)
        resp = self.client.get(reverse('customer_profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_spent'], Decimal('100000'))

    @patch('users.views.send_password_reset_email.delay')
    def test_forgot_and_reset_password_flow(self, mock_reset_delay):
        resp = self.client.post(reverse('forgot_password'), {'email': 'cust_u@test.com'})
        self.assertRedirects(resp, reverse('login'))
        mock_reset_delay.assert_called_once()

        uid = urlsafe_base64_encode(force_bytes(self.customer.pk))
        token = default_token_generator.make_token(self.customer)
        reset_url = reverse('reset_password', args=[uid, token])

        # Weak password rejected
        resp_weak = self.client.post(reset_url, {
            'new_password': '123',
            'confirm_password': '123',
        })
        self.assertEqual(resp_weak.status_code, 200)

        # Valid strong password updates account
        resp_ok = self.client.post(reset_url, {
            'new_password': 'NewPassword@123',
            'confirm_password': 'NewPassword@123',
        })
        self.assertRedirects(resp_ok, reverse('login'))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password('NewPassword@123'))

        # Token cannot be reused after password change
        resp_reuse = self.client.get(reset_url)
        self.assertRedirects(resp_reuse, reverse('forgot_password'))
