"""Add unique item codes and one piece inventory flag."""
from alembic import op
import sqlalchemy as sa

revision = "ba172f3c80a9"
down_revision = "9c32b4e17d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("single_piece", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("products", sa.Column("item_code", sa.String(length=32), nullable=True))
    op.execute("""
        WITH numbered AS (
            SELECT id, row_number() OVER (ORDER BY created_at, id) AS n
            FROM products
        )
        UPDATE products AS p
        SET item_code = 'JS-' || lpad(numbered.n::text, 5, '0')
        FROM numbered
        WHERE p.id = numbered.id
    """)
    op.alter_column("products", "item_code", nullable=False)
    op.create_index("ix_products_item_code", "products", ["item_code"], unique=True)
    op.alter_column("products", "single_piece", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_products_item_code", table_name="products")
    op.drop_column("products", "item_code")
    op.drop_column("products", "single_piece")
