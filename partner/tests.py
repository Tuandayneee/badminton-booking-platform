from datetime import time, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from booking.models import Booking, Transaction
from booking.services import process_approve_transaction
from partner.models import BadmintonCenter, Court, Customer
from partner.utils import redirect_back
from users.models import PartnerProfile, User


class PartnerRBACAndWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner_a = User.objects.create_user(
            username='partner_a',
            email='partner_a@test.com',
            password='Password@123',
            role=User.Role.PARTNER,
        )
        self.profile_a = PartnerProfile.objects.create(
            user=self.partner_a,
            is_verified=True,
        )
        self.center_a = BadmintonCenter.objects.create(
            name='Center A',
            partner=self.profile_a,
            address='Hà Nội',
        )
        self.court_a = Court.objects.create(
            name='Court A1',
            center=self.center_a,
            base_price_per_hour=Decimal('100000'),
            golden_price_per_hour=Decimal('150000'),
            golden_start_time=time(17, 0),
            golden_end_time=time(21, 0),
        )

        self.partner_b = User.objects.create_user(
            username='partner_b2',
            email='partner_b2@test.com',
            password='Password@123',
            role=User.Role.PARTNER,
        )
        self.profile_b = PartnerProfile.objects.create(
            user=self.partner_b,
            is_verified=True,
        )
        self.center_b = BadmintonCenter.objects.create(
            name='Center B',
            partner=self.profile_b,
            address='TP HCM',
        )
        self.court_b = Court.objects.create(
            name='Court B1',
            center=self.center_b,
            base_price_per_hour=Decimal('120000'),
        )

        self.customer_user = User.objects.create_user(
            username='cust_p',
            email='cust_p@test.com',
            password='Password@123',
            role=User.Role.CUSTOMER,
        )

    def test_court_get_price_at_time(self):
        self.assertEqual(self.court_a.get_price_at_time('10:00'), Decimal('100000'))
        self.assertEqual(self.court_a.get_price_at_time('18:00'), Decimal('150000'))
        self.assertEqual(self.court_b.get_price_at_time('18:00'), Decimal('120000'))

    def test_customer_cannot_access_partner_dashboard(self):
        self.client.force_login(self.customer_user)
        resp = self.client.get(reverse('partner_dashboard'))
        self.assertRedirects(resp, reverse('home'))

    def test_partner_idor_protection_on_centers_courts_schedule_and_staff(self):
        staff_b_user = User.objects.create_user(
            username='0988776655',
            email='staff_b@test.com',
            password='Password@123',
            role=User.Role.STAFF,
        )
        staff_b = staff_b_user.staff_profile
        staff_b.center = self.center_b
        staff_b.save()

        self.client.force_login(self.partner_a)

        # Partner A cannot view/edit/delete Partner B's center, court, schedule, or staff
        self.assertEqual(
            self.client.get(reverse('schedule_management', args=[self.center_b.id])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('edit_court', args=[self.court_b.id]), {'name': 'Hacked'}).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('delete_court', args=[self.court_b.id])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('partner_delete_center', args=[self.center_b.id])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('delete_staff_member', args=[staff_b.id])).status_code,
            404,
        )
        self.assertTrue(Court.objects.filter(pk=self.court_b.pk).exists())
        self.assertTrue(BadmintonCenter.objects.filter(pk=self.center_b.pk).exists())

    def test_destructive_endpoints_require_post(self):
        self.client.force_login(self.partner_a)
        self.assertEqual(
            self.client.get(reverse('delete_court', args=[self.court_a.id])).status_code,
            405,
        )
        self.assertEqual(
            self.client.get(reverse('partner_delete_center', args=[self.center_a.id])).status_code,
            405,
        )

    def test_partner_edit_center_redirects_to_centers_management_without_error(self):
        self.client.force_login(self.partner_a)
        resp_get = self.client.get(reverse('partner_edit_center', args=[self.center_a.id]))
        self.assertRedirects(resp_get, reverse('centers_management'))

        resp_invalid = self.client.post(reverse('partner_edit_center', args=[self.center_a.id]), {
            'name': '',
        })
        self.assertRedirects(resp_invalid, reverse('centers_management'))

    def test_revenue_center_detail_handles_invalid_period_and_returns_7_day_chart(self):
        self.client.force_login(self.partner_a)
        resp = self.client.get(
            reverse('revenue_center', args=[self.center_a.id]),
            {'period': 'unknown_period'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['chart_labels']), 7)
        self.assertEqual(len(resp.context['chart_data']), 7)

    @patch('booking.services.send_booking_confirmation_email.delay')
    def test_approve_transaction_updates_revenue_loyalty_and_is_idempotent(self, mock_email_delay):
        customer_record = Customer.objects.create(
            center=self.center_a,
            user=self.customer_user,
            name='Customer P',
            email='cust_p@test.com',
            phone='0909998888',
        )
        booking = Booking.objects.create(
            booking_code='BK-LOYAL-1',
            group_code='BK-LOYAL',
            user=self.customer_user,
            court=self.court_a,
            customer=customer_record,
            date=timezone.localdate() + timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 0),
            total_price=Decimal('150000'),
            status=Booking.Status.WAITING_VERIFY,
        )
        trans = Transaction.objects.create(
            booking_group_code='BK-LOYAL',
            user=self.customer_user,
            amount=Decimal('150000'),
            transaction_reference='FT-LOYAL-1',
            is_verified=False,
        )

        # Partner B cannot approve Partner A's transaction
        self.client.force_login(self.partner_b)
        self.client.post(reverse('partner_approve_transaction', args=[trans.id]))
        trans.refresh_from_db()
        self.assertFalse(trans.is_verified)

        # Partner A approves transaction
        self.client.force_login(self.partner_a)
        resp = self.client.post(reverse('partner_approve_transaction', args=[trans.id]))
        self.assertRedirects(resp, reverse('partner_transactions'))

        trans.refresh_from_db()
        booking.refresh_from_db()
        customer_record.refresh_from_db()
        self.customer_user.customer_profile.refresh_from_db()

        self.assertTrue(trans.is_verified)
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(customer_record.total_spent, Decimal('150000'))
        self.assertEqual(customer_record.total_visits, 1)
        # 150000 / 1000 = 150 points -> Silver rank (>= 120)
        self.assertEqual(self.customer_user.customer_profile.points, 150)
        self.assertEqual(self.customer_user.customer_profile.rank, 'silver')

        # Second call is idempotent and does not double-count
        self.assertFalse(process_approve_transaction(trans, self.partner_a))
        customer_record.refresh_from_db()
        self.assertEqual(customer_record.total_spent, Decimal('150000'))

    def test_excel_exports_return_valid_xlsx_workbooks(self):
        self.client.force_login(self.partner_a)
        for url_name, args in [
            ('partner_export_revenue', []),
            ('partner_export_revenue_detail', [self.center_a.id]),
            ('partner_export_centers', []),
            ('partner_export_transactions', []),
        ]:
            resp = self.client.get(reverse(url_name, args=args))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(
                resp['Content-Type'],
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            wb = load_workbook(BytesIO(resp.content))
            self.assertGreaterEqual(len(wb.sheetnames), 1)

    def test_redirect_back_blocks_open_redirect(self):
        req = RequestFactory().get('/partner/transactions/?next=https://evil.example/phish')
        resp = redirect_back(req, fallback='partner_transactions')
        self.assertEqual(resp.url, reverse('partner_transactions'))
