"""allow orders without customer accounts

Revision ID: a19f6b3d8c42
Revises: 2f4a7d9c1b30
Create Date: 2026-11-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a19f6b3d8c42"
down_revision: Union[str, Sequence[str], None] = "2f4a7d9c1b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _change_order_columns(*, nullable: bool, delete_action: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("orders_user_id_fkey", "orders", type_="foreignkey")
        op.alter_column("orders", "user_id", existing_type=sa.Uuid(), nullable=nullable)
        op.alter_column("orders", "contact_email", existing_type=sa.String(length=320), nullable=nullable)
        op.create_foreign_key(
            "fk_orders_user_id_users", "orders", "users", ["user_id"], ["id"],
            ondelete=delete_action,
        )
        return

    foreign_key = next(
        fk for fk in sa.inspect(bind).get_foreign_keys("orders")
        if fk["constrained_columns"] == ["user_id"]
    )
    with op.batch_alter_table(
        "orders",
        recreate="always",
        naming_convention={"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"},
    ) as batch:
        batch.drop_constraint(foreign_key["name"] or "fk_orders_user_id_users", type_="foreignkey")
        batch.alter_column("user_id", existing_type=sa.Uuid(), nullable=nullable)
        batch.alter_column("contact_email", existing_type=sa.String(length=320), nullable=nullable)
        batch.create_foreign_key(
            "fk_orders_user_id_users", "users", ["user_id"], ["id"],
            ondelete=delete_action,
        )


def upgrade() -> None:
    _change_order_columns(nullable=True, delete_action="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    guest_orders = bind.execute(
        sa.text("SELECT count(*) FROM orders WHERE user_id IS NULL OR contact_email IS NULL")
    ).scalar_one()
    if guest_orders:
        raise RuntimeError("Cannot downgrade guest checkout while guest orders exist")
    _change_order_columns(nullable=False, delete_action="RESTRICT")
