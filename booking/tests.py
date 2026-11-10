from datetime import time, timedelta
from decimal import Decimal
import json
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from booking.admin import TransactionAdmin
from booking.models import Booking, Transaction
from booking.tasks import cancel_expired_bookings
from booking.views import build_internal_lock_token
from fastapi_service.routers.booking import HTTPException, verify_internal_token
from fastapi_service.routers.search import _generate_half_hour_slots
from partner.models import BadmintonCenter, Court, Customer
from users.models import PartnerProfile, User


class BookingFlowAndSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner_user = User.objects.create_user(
            username='partner_b',
            email='partner_b@test.com',
            password='Password@123',
            role=User.Role.PARTNER,
        )
        self.partner_profile = PartnerProfile.objects.create(
            user=self.partner_user,
            bank_bin='970422',
            bank_account_number='123456789',
            bank_account_owner='PARTNER B',
            is_verified=True,
        )
        self.center = BadmintonCenter.objects.create(
            name='Sân Test Pro',
            partner=self.partner_profile,
            address='Cầu Giấy, Hà Nội',
            open_time=time(6, 0),
            close_time=time(23, 0),
        )
        self.court = Court.objects.create(
            name='Sân 1',
            center=self.center,
            base_price_per_hour=Decimal('100000'),
            golden_price_per_hour=Decimal('160000'),
            golden_start_time=time(17, 0),
            golden_end_time=time(21, 0),
        )
        self.customer_user = User.objects.create_user(
            username='customer_b',
            email='customer_b@test.com',
            password='Password@123',
            full_name='Nguyen Van A',
            phone_number='0901112222',
            role=User.Role.CUSTOMER,
        )
        self.other_user = User.objects.create_user(
            username='other_b',
            email='other_b@test.com',
            password='Password@123',
            role=User.Role.CUSTOMER,
        )
        self.future_date = timezone.localdate() + timedelta(days=2)
        self.future_date_str = self.future_date.strftime('%Y-%m-%d')

    def test_booking_confirm_ignores_tampered_price_and_blocks_past_date(self):
        self.client.force_login(self.customer_user)

        # Past date must be rejected
        past_date_str = (timezone.localdate() - timedelta(days=1)).strftime('%Y-%m-%d')
        resp_past = self.client.post(reverse('booking_confirm'), {
            'center_id': str(self.center.id),
            'selected_date': past_date_str,
            'booking_data': json.dumps([{'court_id': self.court.id, 'time': '18:00', 'price': 0}]),
        })
        self.assertRedirects(resp_past, reverse('booking_timeline', args=[self.center.id]))

        # Tampered client price (0) must be overridden by server golden hour price (160000/2 = 80000)
        resp_ok = self.client.post(reverse('booking_confirm'), {
            'center_id': str(self.center.id),
            'selected_date': self.future_date_str,
            'booking_data': json.dumps([{'court_id': self.court.id, 'time': '18:00', 'price': 0}]),
        })
        self.assertEqual(resp_ok.status_code, 200)
        self.assertEqual(resp_ok.context['total_price'], 80000)

    @patch('booking.views.get_redis')
    def test_booking_save_enforces_server_price_and_prevents_double_booking(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.get.return_value = str(self.customer_user.id).encode('utf-8')
        mock_get_redis.return_value = mock_redis

        self.client.force_login(self.customer_user)
        # Client tries to tamper price=0 at base-price hour (10:00 -> 100000/2 = 50000)
        payload = json.dumps([{'court_id': self.court.id, 'time': '10:00', 'price': 0}])
        resp = self.client.post(reverse('booking_save'), {
            'center_id': str(self.center.id),
            'selected_date': self.future_date_str,
            'booking_data': payload,
            'full_name': 'Nguyen Van A',
            'phone_number': '0901112222',
        })
        self.assertEqual(Booking.objects.count(), 1)
        booking = Booking.objects.first()
        self.assertEqual(booking.total_price, Decimal('50000'))
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertTrue(bool(booking.group_code))
        self.assertRedirects(resp, reverse('booking_payment', args=[booking.group_code]))
        mock_redis.delete.assert_called()

        # Second user attempting to book the exact same slot is blocked
        mock_redis.get.return_value = str(self.other_user.id).encode('utf-8')
        self.client.force_login(self.other_user)
        resp_dup = self.client.post(reverse('booking_save'), {
            'center_id': str(self.center.id),
            'selected_date': self.future_date_str,
            'booking_data': payload,
            'full_name': 'Other User',
            'phone_number': '0903334444',
        })
        self.assertRedirects(resp_dup, reverse('booking_timeline', args=[self.center.id]))
        self.assertEqual(Booking.objects.count(), 1)

    @patch('booking.views.get_redis')
    def test_booking_save_rejects_missing_or_foreign_redis_lock(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        self.client.force_login(self.customer_user)
        payload = json.dumps([{'court_id': self.court.id, 'time': '10:00', 'price': 50000}])
        resp = self.client.post(reverse('booking_save'), {
            'center_id': str(self.center.id),
            'selected_date': self.future_date_str,
            'booking_data': payload,
        })
        self.assertRedirects(resp, reverse('booking_timeline', args=[self.center.id]))
        self.assertEqual(Booking.objects.count(), 0)

        # Lock held by another user
        mock_redis.get.return_value = str(self.other_user.id).encode('utf-8')
        resp2 = self.client.post(reverse('booking_save'), {
            'center_id': str(self.center.id),
            'selected_date': self.future_date_str,
            'booking_data': payload,
        })
        self.assertRedirects(resp2, reverse('booking_timeline', args=[self.center.id]))
        self.assertEqual(Booking.objects.count(), 0)

    def test_unique_constraint_allows_rebooking_after_admin_cancelled(self):
        Booking.objects.create(
            booking_code='BK-OLD-1',
            group_code='BK-OLD',
            user=self.customer_user,
            court=self.court,
            date=self.future_date,
            start_time=time(14, 0),
            end_time=time(14, 30),
            total_price=Decimal('50000'),
            status=Booking.Status.ADMIN_CANCELLED,
        )
        new_booking = Booking.objects.create(
            booking_code='BK-NEW-1',
            group_code='BK-NEW',
            user=self.other_user,
            court=self.court,
            date=self.future_date,
            start_time=time(14, 0),
            end_time=time(14, 30),
            total_price=Decimal('50000'),
            status=Booking.Status.PENDING,
        )
        self.assertEqual(new_booking.court, self.court)

    @patch('booking.views.get_redis')
    def test_booking_timeline_uses_batch_mget_for_locks(self, mock_get_redis):
        mock_redis = MagicMock()
        # Return foreign user lock for first free slot only
        mock_redis.mget.side_effect = lambda keys: [str(self.other_user.id).encode('utf-8')] + [None] * (len(keys) - 1)
        mock_get_redis.return_value = mock_redis

        self.client.force_login(self.customer_user)
        resp = self.client.get(reverse('booking_timeline', args=[self.center.id]), {'date': self.future_date_str})
        self.assertEqual(resp.status_code, 200)
        mock_redis.mget.assert_called_once()
        slots = resp.context['courts_data'][0]['slots']
        self.assertEqual(slots[0]['status'], 'booked')
        self.assertEqual(slots[1]['status'], 'free')

    @patch('booking.views.requests.post')
    def test_proxy_lock_slot_signs_session_user_and_verifies_token(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'success', 'message': 'Đã khóa sân'}
        mock_post.return_value = mock_resp

        self.client.force_login(self.customer_user)
        resp = self.client.post(
            reverse('proxy_lock_slot'),
            data=json.dumps({
                'court_id': self.court.id,
                'date': self.future_date_str,
                'start_time': '19:00',
                'end_time': '19:00',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        sent_headers = mock_post.call_args.kwargs['headers']
        verified_uid = verify_internal_token(sent_headers['X-Internal-Token'])
        self.assertEqual(verified_uid, str(self.customer_user.id))

    def test_fastapi_helpers_token_verification_and_half_hour_slots(self):
        valid_token = build_internal_lock_token(42)
        self.assertEqual(verify_internal_token(valid_token), '42')

        with self.assertRaises(HTTPException):
            verify_internal_token(None)
        with self.assertRaises(HTTPException):
            verify_internal_token('123456:42:tamperedsignature')

        slots = _generate_half_hour_slots(time(17, 0), time(18, 0))
        self.assertEqual(slots, ['17:00', '17:30'])

    def test_booking_success_confirm_prevents_duplicate_transaction_submission(self):
        booking = Booking.objects.create(
            booking_code='BK-GRP1-1',
            group_code='BK-GRP1',
            user=self.customer_user,
            court=self.court,
            date=self.future_date,
            start_time=time(9, 0),
            end_time=time(9, 30),
            total_price=Decimal('50000'),
            status=Booking.Status.PENDING,
        )
        self.client.force_login(self.customer_user)
        resp1 = self.client.post(reverse('booking_success_confirm', args=['BK-GRP1']), {
            'transaction_code': 'FT123456',
        })
        self.assertRedirects(resp1, reverse('home'))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.WAITING_VERIFY)
        self.assertEqual(Transaction.objects.count(), 1)

        # Submitting again must not create a second Transaction
        resp2 = self.client.post(reverse('booking_success_confirm', args=['BK-GRP1']), {
            'transaction_code': 'FT999999',
        })
        self.assertRedirects(resp2, reverse('customer_booking_history'))
        self.assertEqual(Transaction.objects.count(), 1)

    @patch('booking.views.get_redis')
    def test_cancel_booking_enforces_csrf_and_owner(self, mock_get_redis):
        mock_get_redis.return_value = MagicMock()
        booking = Booking.objects.create(
            booking_code='BK-CANC-1',
            group_code='BK-CANC',
            user=self.customer_user,
            court=self.court,
            date=self.future_date,
            start_time=time(11, 0),
            end_time=time(11, 30),
            total_price=Decimal('50000'),
            status=Booking.Status.PENDING,
        )

        # Unauthenticated gets 401
        resp_unauth = self.client.post(reverse('cancel_booking_on_leave', args=['BK-CANC']))
        self.assertEqual(resp_unauth.status_code, 401)

        # CSRF check enforced
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.customer_user)
        resp_no_csrf = csrf_client.post(reverse('cancel_booking_on_leave', args=['BK-CANC']))
        self.assertEqual(resp_no_csrf.status_code, 403)

        # Owner can cancel with standard client
        self.client.force_login(self.customer_user)
        resp_ok = self.client.post(reverse('cancel_booking_on_leave', args=['BK-CANC']))
        self.assertEqual(resp_ok.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.ADMIN_CANCELLED)

    def test_cancel_expired_bookings_task_only_cancels_stale_pending(self):
        stale = Booking.objects.create(
            booking_code='BK-EXP-1',
            group_code='BK-EXP',
            user=self.customer_user,
            court=self.court,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(12, 30),
            total_price=Decimal('50000'),
            status=Booking.Status.PENDING,
        )
        Booking.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(minutes=15))

        fresh = Booking.objects.create(
            booking_code='BK-FRESH-1',
            group_code='BK-FRESH',
            user=self.customer_user,
            court=self.court,
            date=self.future_date,
            start_time=time(12, 30),
            end_time=time(13, 0),
            total_price=Decimal('50000'),
            status=Booking.Status.PENDING,
        )

        result = cancel_expired_bookings()
        self.assertIn('1', result)
        stale.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(stale.status, Booking.Status.ADMIN_CANCELLED)
        self.assertEqual(fresh.status, Booking.Status.PENDING)

    @patch('booking.services.send_booking_confirmation_email.delay')
    def test_transaction_admin_save_model_preserves_verification_metadata(self, mock_email_delay):
        admin_user = User.objects.create_superuser(
            username='admin_b',
            email='admin_b@test.com',
            password='Password@123',
            role=User.Role.ADMIN,
        )
        customer_record = Customer.objects.create(
            center=self.center,
            user=self.customer_user,
            name='Nguyen Van A',
            email='customer_b@test.com',
            phone='0901112222',
        )
        booking = Booking.objects.create(
            booking_code='BK-ADM-1',
            group_code='BK-ADM',
            user=self.customer_user,
            court=self.court,
            customer=customer_record,
            date=self.future_date,
            start_time=time(15, 0),
            end_time=time(15, 30),
            total_price=Decimal('150000'),
            status=Booking.Status.WAITING_VERIFY,
        )
        trans = Transaction.objects.create(
            booking_group_code='BK-ADM',
            user=self.customer_user,
            amount=Decimal('150000'),
            transaction_reference='FT-ADMIN-1',
            is_verified=False,
        )

        admin_site = AdminSite()
        tx_admin = TransactionAdmin(Transaction, admin_site)
        request = RequestFactory().post('/admin/')
        request.user = admin_user

        form = MagicMock()
        form.changed_data = ['is_verified']
        trans.is_verified = True
        tx_admin.save_model(request, trans, form, change=True)

        trans.refresh_from_db()
        booking.refresh_from_db()
        self.assertTrue(trans.is_verified)
        self.assertIsNotNone(trans.verified_at)
        self.assertEqual(trans.verified_by, admin_user)
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
