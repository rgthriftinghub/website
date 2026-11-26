"""Add editable storefront content."""
from alembic import op
import sqlalchemy as sa

revision = "2f4a7d9c1b30"
down_revision = "ba172f3c80a9"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "store_content",
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_store_content_key"),
    )
    op.create_index("ix_store_content_key", "store_content", ["key"])

def downgrade() -> None:
    op.drop_index("ix_store_content_key", table_name="store_content")
    op.drop_table("store_content")
