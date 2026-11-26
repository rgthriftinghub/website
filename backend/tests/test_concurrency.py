"""Overselling protection under genuine concurrency.

Unlike the rest of the suite, these tests cannot run inside a rolled-back
transaction: proving that `SELECT ... FOR UPDATE` serialises two checkouts
requires two real connections that actually commit. Each test therefore creates
its own data, commits it, and deletes it again in a `finally` block so the shared
test database is left exactly as it was found.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.address import CustomerAddress
from app.models.cart import Cart, CartItem
from app.models.category import Category
from app.models.enums import InventoryTransactionType, UserRole
from app.models.inventory import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.models.variant import ProductVariant
from app.schemas.order import CheckoutRequest
from app.services import orders as order_service
from app.services.exceptions import ServiceError


class _Fixture:
    """Ids of everything a concurrency test created, so it can all be removed."""

    def __init__(self) -> None:
        self.user_ids: list[uuid.UUID] = []
        self.address_ids: list[uuid.UUID] = []
        self.product_id: uuid.UUID | None = None
        self.category_id: uuid.UUID | None = None
        self.variant_id: uuid.UUID | None = None


def _build(engine, *, stock: int, buyers: int, quantity: int = 1) -> _Fixture:
    """Commit a product with a fixed stock plus N buyers who each have it in their bag."""
    state = __state = _Fixture()
    suffix = uuid.uuid4().hex[:8]

    with Session(engine) as db:
        category = Category(name="Concurrency", slug=f"concurrency-{suffix}", is_active=True)
        db.add(category)
        db.flush()
        state.category_id = category.id

        product = Product(
            name="Last Unit Jeans",
            slug=f"last-unit-{suffix}",
            sku=f"CONC-{suffix}",
            category_id=category.id,
            regular_price=Decimal("4000.00"),
            condition="THRIFT",
            gender="MEN",
            product_type="JEANS",
            is_active=True,
        )
        variant = ProductVariant(sku=f"CONC-{suffix}-W32", waist=32, is_active=True)
        variant.inventory = InventoryItem(quantity=stock, low_stock_threshold=1)
        product.variants.append(variant)
        db.add(product)
        db.flush()
        state.product_id = product.id
        state.variant_id = variant.id

        from app.core.security import hash_password

        for index in range(buyers):
            user = User(
                email=f"conc-{suffix}-{index}@example.com",
                password_hash=hash_password("ConcurrencyPass!2026"),
                first_name="Race",
                last_name=f"Buyer{index}",
                role=UserRole.CUSTOMER,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.flush()
            state.user_ids.append(user.id)

            address = CustomerAddress(
                user_id=user.id,
                full_name=f"Race Buyer{index}",
                phone="+92 300 1234567",
                address_line_1="1 Race Street",
                city="Lahore",
                province="Punjab",
                country="Pakistan",
                is_default=True,
            )
            db.add(address)
            db.flush()
            state.address_ids.append(address.id)

            cart = Cart(user_id=user.id)
            db.add(cart)
            db.flush()
            db.add(
                CartItem(
                    cart_id=cart.id,
                    product_variant_id=variant.id,
                    quantity=quantity,
                    unit_price=Decimal("4000.00"),
                )
            )

        db.commit()
    return state


def _teardown(engine, state: _Fixture) -> None:
    """Remove everything, in dependency order. Runs even if the test failed."""
    with Session(engine) as db:
        if state.user_ids:
            # Orders reference users with RESTRICT, so they go first.
            db.execute(delete(Order).where(Order.user_id.in_(state.user_ids)))
            db.execute(
                delete(CartItem).where(
                    CartItem.cart_id.in_(select(Cart.id).where(Cart.user_id.in_(state.user_ids)))
                )
            )
            db.execute(delete(Cart).where(Cart.user_id.in_(state.user_ids)))
            db.execute(
                delete(CustomerAddress).where(CustomerAddress.user_id.in_(state.user_ids))
            )
        if state.variant_id:
            db.execute(
                delete(InventoryTransaction).where(
                    InventoryTransaction.product_variant_id == state.variant_id
                )
            )
        if state.product_id:
            # Cascades to variants, inventory, and images.
            db.execute(delete(Product).where(Product.id == state.product_id))
        if state.category_id:
            db.execute(delete(Category).where(Category.id == state.category_id))
        if state.user_ids:
            db.execute(delete(User).where(User.id.in_(state.user_ids)))
        db.commit()


def _checkout(engine, user_id: uuid.UUID, address_id: uuid.UUID, barrier) -> str | Exception:
    """Run one checkout on its own connection, released from the barrier together."""
    with Session(engine) as db:
        user = db.get(User, user_id)
        payload = CheckoutRequest(address_id=address_id, payment_method="COD")
        # Both threads reach the lock at as close to the same moment as possible.
        barrier.wait(timeout=20)
        try:
            order = order_service.place_order(db, user, payload)
            return order.order_number
        except ServiceError as exc:
            db.rollback()
            return exc


def test_only_one_of_two_buyers_gets_the_last_unit(engine):
    """Variant stock is 1. Two customers check out simultaneously."""
    state = _build(engine, stock=1, buyers=2)
    try:
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(_checkout, engine, user_id, address_id, barrier)
                for user_id, address_id in zip(state.user_ids, state.address_ids, strict=True)
            ]
            results = [future.result(timeout=60) for future in futures]

        succeeded = [r for r in results if isinstance(r, str)]
        failed = [r for r in results if isinstance(r, Exception)]

        assert len(succeeded) == 1, f"expected exactly one winner, got {results}"
        assert len(failed) == 1
        assert "left" in str(failed[0]).lower() or "stock" in str(failed[0]).lower()

        with Session(engine) as db:
            stock = db.execute(
                select(InventoryItem.quantity).where(
                    InventoryItem.product_variant_id == state.variant_id
                )
            ).scalar_one()
            # Never negative: the loser was blocked, not merely overwritten.
            assert stock == 0

            sales = db.execute(
                select(func.count())
                .select_from(InventoryTransaction)
                .where(
                    InventoryTransaction.product_variant_id == state.variant_id,
                    InventoryTransaction.type == InventoryTransactionType.SALE,
                )
            ).scalar_one()
            assert sales == 1

            orders = db.execute(
                select(func.count()).select_from(Order).where(Order.user_id.in_(state.user_ids))
            ).scalar_one()
            assert orders == 1
    finally:
        _teardown(engine, state)


def test_five_buyers_contend_for_three_units(engine):
    """Three units, five simultaneous checkouts: exactly three orders, stock 0."""
    state = _build(engine, stock=3, buyers=5)
    try:
        barrier = threading.Barrier(5)
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [
                pool.submit(_checkout, engine, user_id, address_id, barrier)
                for user_id, address_id in zip(state.user_ids, state.address_ids, strict=True)
            ]
            results = [future.result(timeout=90) for future in futures]

        succeeded = [r for r in results if isinstance(r, str)]
        assert len(succeeded) == 3, f"expected three winners, got {results}"
        # Order numbers stay unique under contention.
        assert len(set(succeeded)) == 3

        with Session(engine) as db:
            stock = db.execute(
                select(InventoryItem.quantity).where(
                    InventoryItem.product_variant_id == state.variant_id
                )
            ).scalar_one()
            assert stock == 0
    finally:
        _teardown(engine, state)


def test_concurrency_fixtures_leave_no_residue(engine):
    """Guards the cleanup itself, so these tests cannot pollute the shared database."""
    state = _build(engine, stock=1, buyers=2)
    _teardown(engine, state)

    with Session(engine) as db:
        assert (
            db.execute(
                select(func.count()).select_from(User).where(User.id.in_(state.user_ids))
            ).scalar_one()
            == 0
        )
        assert db.get(Product, state.product_id) is None
        assert (
            db.execute(
                select(func.count())
                .select_from(InventoryTransaction)
                .where(InventoryTransaction.product_variant_id == state.variant_id)
            ).scalar_one()
            == 0
        )
