"""Phase 4 seed data: shipping methods and store bank accounts.

The bank details are obviously fictional placeholders. Real receiving accounts
must be entered by the client — seeding a plausible-looking account number would
be worse than leaving it clearly fake, because a customer could actually send
money to it.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import DeliveryMethod


@dataclass(frozen=True, slots=True)
class ShippingMethodSeed:
    code: DeliveryMethod
    name: str
    description: str
    price: Decimal
    free_threshold: Decimal | None
    estimated_days_min: int
    estimated_days_max: int
    sort_order: int


SHIPPING_METHODS: tuple[ShippingMethodSeed, ...] = (
    ShippingMethodSeed(
        code=DeliveryMethod.STANDARD,
        name="Standard Delivery",
        description="Delivered by our courier partner across Pakistan.",
        price=Decimal("250.00"),
        free_threshold=Decimal("4000.00"),
        estimated_days_min=3,
        estimated_days_max=5,
        sort_order=0,
    ),
)


@dataclass(frozen=True, slots=True)
class BankAccountSeed:
    bank_name: str
    account_title: str
    account_number: str
    iban: str | None
    branch: str | None
    instructions: str
    sort_order: int


# Marked DEMO in every field so no one can mistake these for live details.
BANK_ACCOUNTS: tuple[BankAccountSeed, ...] = (
    BankAccountSeed(
        bank_name="DEMO Bank (replace before go-live)",
        account_title="RG Thrifting Hub — DEMO ACCOUNT",
        account_number="DEMO-0000-0000-0000",
        iban="PK00DEMO0000000000000000",
        branch="DEMO Branch, Lahore",
        instructions=(
            "These are placeholder details for development only. Replace them with the "
            "store's real receiving account before accepting live payments. Always quote "
            "your order number as the transfer reference."
        ),
        sort_order=0,
    ),
)
