"""Add redeemable coupon codes and snapshot the applied order code."""
from alembic import op
import sqlalchemy as sa

revision = "bc9e74d03a41"
down_revision = "8ad129bf31c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("minimum_order", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("redemption_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
    )
    op.create_index("ix_coupons_code", "coupons", ["code"])
    op.add_column("orders", sa.Column("coupon_code", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "coupon_code")
    op.drop_index("ix_coupons_code", table_name="coupons")
    op.drop_table("coupons")
