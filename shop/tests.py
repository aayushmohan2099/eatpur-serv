from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from .models import Coupon, CouponStatus
from .views import _get_auto_applied_free_shipping_coupon


class FreeShippingAutoApplyTests(TestCase):
    def setUp(self):
        self.ongoing = CouponStatus.objects.create(status_name="ONGOING")
        now = timezone.now()
        self.free_shipping = Coupon.objects.create(
            coupon_code="FREESHIP",
            status=self.ongoing,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
            coupon_type="FREE_SHIPPING",
            discount_value=Decimal("0.00"),
            min_order_value=Decimal("500.00"),
        )
        self.flat = Coupon.objects.create(
            coupon_code="FLAT100",
            status=self.ongoing,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
            coupon_type="FLAT",
            discount_value=Decimal("100.00"),
            min_order_value=Decimal("0.00"),
        )

    def test_only_free_shipping_coupon_is_auto_applied(self):
        coupon = _get_auto_applied_free_shipping_coupon(Decimal("500.00"))

        self.assertEqual(coupon, self.free_shipping)
        self.assertFalse(self.flat.is_auto_apply)
        self.assertTrue(self.free_shipping.is_auto_apply)

    def test_free_shipping_coupon_requires_minimum_order_value(self):
        coupon = _get_auto_applied_free_shipping_coupon(Decimal("499.99"))

        self.assertIsNone(coupon)
