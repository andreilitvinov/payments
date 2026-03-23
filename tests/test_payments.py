import unittest

from payments.models import OrderPaymentStatus, PaymentType
from payments.money import MoneyError
from payments.service import PaymentService


class PaymentsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.svc = PaymentService()
        self.order = self.svc.add_order(total_amount="100.00")

    def test_new_order_is_unpaid(self) -> None:
        self.assertEqual(self.order.payment_status, OrderPaymentStatus.UNPAID)
        self.assertEqual(str(self.order.net_paid_amount), "0.00")

    def test_partial_and_full_payments_update_status(self) -> None:
        p1 = self.svc.create_payment(self.order.id, PaymentType.CASH)
        p2 = self.svc.create_payment(self.order.id, PaymentType.ACQUIRING)

        p1.deposit("30")
        self.assertEqual(self.order.payment_status, OrderPaymentStatus.PARTIALLY_PAID)
        self.assertEqual(str(self.order.net_paid_amount), "30.00")

        p2.deposit("70.00")
        self.assertEqual(self.order.payment_status, OrderPaymentStatus.PAID)
        self.assertEqual(str(self.order.net_paid_amount), "100.00")

    def test_overpay_is_forbidden(self) -> None:
        p1 = self.svc.create_payment(self.order.id, PaymentType.CASH)
        p1.deposit("100.00")
        with self.assertRaises(MoneyError):
            p1.deposit("0.01")

    def test_refund_changes_status_and_allows_repay(self) -> None:
        p1 = self.svc.create_payment(self.order.id, PaymentType.CASH)
        p1.deposit("100.00")
        self.assertEqual(self.order.payment_status, OrderPaymentStatus.PAID)

        p1.refund("10.00")
        self.assertEqual(self.order.payment_status, OrderPaymentStatus.PARTIALLY_PAID)
        self.assertEqual(str(self.order.net_paid_amount), "90.00")

        p2 = self.svc.create_payment(self.order.id, PaymentType.ACQUIRING)
        p2.deposit("10.00")
        self.assertEqual(self.order.payment_status, OrderPaymentStatus.PAID)
        self.assertEqual(str(self.order.net_paid_amount), "100.00")

    def test_refund_more_than_payment_net_is_forbidden(self) -> None:
        p1 = self.svc.create_payment(self.order.id, PaymentType.CASH)
        p1.deposit("5.00")
        with self.assertRaises(MoneyError):
            p1.refund("5.01")

    def test_zero_or_negative_amounts_forbidden(self) -> None:
        p1 = self.svc.create_payment(self.order.id, PaymentType.CASH)
        with self.assertRaises(MoneyError):
            p1.deposit("0")
        with self.assertRaises(MoneyError):
            p1.deposit("-1")
        with self.assertRaises(MoneyError):
            p1.refund("0")


if __name__ == "__main__":
    unittest.main()

