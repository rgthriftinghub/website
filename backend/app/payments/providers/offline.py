"""Fully implemented providers that need no external API.

Both settle offline: money changes hands in the physical world (cash at the door)
or through the customer's own bank, and a human confirms it. There is no gateway
to call, so these are complete, working integrations rather than boundaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models.enums import PaymentProvider, PaymentStatus
from app.core.config import get_settings
from app.models.shipping import BankAccount
from app.payments.base import BasePaymentProvider, PaymentIntent, ProviderNotConfigured

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.order import Order
    from app.models.payment import Payment


class CashOnDeliveryProvider(BasePaymentProvider):
    """Cash collected by the courier.

    The payment stays PENDING at order creation and only a staff action marks it
    PAID, because nothing has been collected until the parcel is handed over.
    """

    code = PaymentProvider.COD
    display_name = "Cash on Delivery"
    settles_offline = True

    @property
    def is_configured(self) -> bool:
        return True

    def create_payment(self, db: Session, payment: Payment, order: Order) -> PaymentIntent:
        return PaymentIntent(
            payment_id=str(payment.id),
            provider=self.code,
            status=PaymentStatus.PENDING,
            requires_redirect=False,
            instructions=(
                "Please have the exact amount ready for the courier when your parcel "
                "arrives. Nothing is charged online."
            ),
            reference=order.order_number,
        )


class BankTransferProvider(BasePaymentProvider):
    """Manual bank transfer.

    The customer is shown the store's receiving details, transfers the amount
    themselves, then submits the reference. Staff reconcile it against the bank
    statement and verify or reject. No customer banking data is ever stored — only
    the reference string they quote.
    """

    code = PaymentProvider.BANK_TRANSFER
    display_name = "Bank Transfer"
    settles_offline = True

    @property
    def is_configured(self) -> bool:
        return True

    def create_payment(self, db: Session, payment: Payment, order: Order) -> PaymentIntent:
        accounts = (
            db.execute(
                select(BankAccount)
                .where(BankAccount.is_active.is_(True))
                .order_by(BankAccount.sort_order, BankAccount.bank_name)
            )
            .scalars()
            .all()
        )

        if accounts:
            lines = [
                f"{account.bank_name} — {account.account_title} — {account.account_number}"
                + (f" (IBAN {account.iban})" if account.iban else "")
                for account in accounts
            ]
            instructions = (
                "Transfer the total to one of the accounts below, then submit your "
                "transaction reference on the order page so we can match it:\n"
                + "\n".join(lines)
            )
        else:
            # Honest fallback: never invent account numbers.
            instructions = (
                "Our team will contact you with bank account details. Quote your order "
                "number with the transfer so we can match it quickly."
            )

        return PaymentIntent(
            payment_id=str(payment.id),
            provider=self.code,
            status=PaymentStatus.PENDING,
            requires_redirect=False,
            instructions=instructions,
            reference=order.order_number,
        )


class ManualWalletProvider(BasePaymentProvider):
    """Mobile wallet transfer confirmed manually by staff; no gateway call."""

    number_setting: str

    @property
    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(getattr(settings, self.number_setting) and settings.payment_whatsapp_number)

    def create_payment(self, db: Session, payment: Payment, order: Order) -> PaymentIntent:
        number = getattr(get_settings(), self.number_setting)
        if not number or not get_settings().payment_whatsapp_number:
            raise ProviderNotConfigured(
                f"{self.display_name} number and WhatsApp contact must be configured"
            )
        return PaymentIntent(
            payment_id=str(payment.id), provider=self.code, status=PaymentStatus.PENDING,
            requires_redirect=False,
            instructions=f"Send PKR {payment.amount} to {self.display_name} number {number}. Then send your payment screenshot on WhatsApp and include order {order.order_number}.",
            reference=order.order_number,
        )


class JazzCashManualProvider(ManualWalletProvider):
    code = PaymentProvider.JAZZCASH
    display_name = "JazzCash"
    number_setting = "jazzcash_number"


class EasypaisaManualProvider(ManualWalletProvider):
    code = PaymentProvider.EASYPAISA
    display_name = "Easypaisa"
    number_setting = "easypaisa_number"
