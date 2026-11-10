from decimal import Decimal
import json

from django.test import Client, TestCase
from django.urls import reverse

from partner.models import BadmintonCenter, Product, ServiceOrder, ServiceOrderItem
from users.models import PartnerProfile, User


class StaffPOSAndReportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner_user = User.objects.create_user(
            username='partner_s',
            email='partner_s@test.com',
            password='Password@123',
            role=User.Role.PARTNER,
        )
        self.partner_profile = PartnerProfile.objects.create(
            user=self.partner_user,
            is_verified=True,
        )
        self.center = BadmintonCenter.objects.create(
            name='Sân POS',
            partner=self.partner_profile,
            address='Đống Đa, HN',
        )
        self.other_center = BadmintonCenter.objects.create(
            name='Sân Khác',
            partner=self.partner_profile,
            address='Ba Đình, HN',
        )
        self.product = Product.objects.create(
            center=self.center,
            name='Nước khoáng Revive',
            price=Decimal('15000'),
            stock_quantity=10,
            is_active=True,
        )
        self.other_product = Product.objects.create(
            center=self.other_center,
            name='Ống cầu Yonex',
            price=Decimal('250000'),
            stock_quantity=5,
            is_active=True,
        )
        self.staff_user = User.objects.create_user(
            username='staff_s',
            email='staff_s@test.com',
            password='Password@123',
            full_name='Nhân viên A',
            role=User.Role.STAFF,
        )
        self.staff_user.staff_profile.center = self.center
        self.staff_user.staff_profile.save()

        self.customer_user = User.objects.create_user(
            username='cust_s',
            email='cust_s@test.com',
            password='Password@123',
            role=User.Role.CUSTOMER,
        )

    def test_customer_cannot_access_pos(self):
        self.client.force_login(self.customer_user)
        resp = self.client.get(reverse('pos_sales'))
        self.assertRedirects(resp, reverse('home'))

    def test_pos_sales_ignores_tampered_price_and_decrements_stock(self):
        self.client.force_login(self.staff_user)
        resp = self.client.post(reverse('pos_sales'), {
            'staff_name': 'Nhân viên A',
            'payment_method': 'transfer',
            # Tampered price=0 in client payload must be ignored
            'cart_data': json.dumps([{'product_id': self.product.id, 'quantity': 3, 'price': 0}]),
        })
        self.assertRedirects(resp, reverse('pos_sales'))
        self.assertEqual(ServiceOrder.objects.count(), 1)
        order = ServiceOrder.objects.first()
        self.assertEqual(order.total_amount, Decimal('45000'))
        self.assertEqual(order.payment_method, ServiceOrder.PaymentMethod.TRANSFER)
        self.assertEqual(ServiceOrderItem.objects.filter(order=order).count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)

    def test_pos_sales_rejects_excess_quantity_negative_quantity_and_foreign_product(self):
        self.client.force_login(self.staff_user)

        # Insufficient stock
        self.client.post(reverse('pos_sales'), {
            'cart_data': json.dumps([{'product_id': self.product.id, 'quantity': 50}]),
        })
        self.assertEqual(ServiceOrder.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

        # Negative / zero quantity
        self.client.post(reverse('pos_sales'), {
            'cart_data': json.dumps([{'product_id': self.product.id, 'quantity': -2}]),
        })
        self.assertEqual(ServiceOrder.objects.count(), 0)

        # Product belonging to a different center
        self.client.post(reverse('pos_sales'), {
            'cart_data': json.dumps([{'product_id': self.other_product.id, 'quantity': 1}]),
        })
        self.assertEqual(ServiceOrder.objects.count(), 0)

    def test_staff_sales_report_and_service_orders(self):
        ServiceOrder.objects.create(
            center=self.center,
            staff_name='Nhân viên A',
            total_amount=Decimal('60000'),
            payment_method=ServiceOrder.PaymentMethod.CASH,
        )
        self.client.force_login(self.staff_user)

        report_resp = self.client.get(reverse('staff_sales_report'))
        self.assertEqual(report_resp.status_code, 200)
        self.assertEqual(report_resp.context['total_revenue'], Decimal('60000'))
        self.assertEqual(report_resp.context['total_orders'], 1)
        self.assertEqual(len(json.loads(report_resp.context['chart_labels'])), 7)

        orders_resp = self.client.get(reverse('staff_service_orders'))
        self.assertEqual(orders_resp.status_code, 200)
        self.assertEqual(orders_resp.context['total_orders'], 1)
