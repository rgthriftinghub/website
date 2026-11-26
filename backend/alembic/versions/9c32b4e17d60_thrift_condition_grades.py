"""Replace retail condition labels with thrift-specific grades.

Existing catalogue rows intentionally begin at GOOD so staff can inspect and
regrade items without us inventing a quality level for them.
"""
from alembic import op

revision = "9c32b4e17d60"
down_revision = "bc9e74d03a41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE product_condition RENAME TO product_condition_legacy")
    op.execute("CREATE TYPE product_condition AS ENUM ('PREMIUM_PLUS', 'PREMIUM', 'EXCELLENT', 'GOOD')")
    op.execute(
        "ALTER TABLE products ALTER COLUMN condition TYPE product_condition "
        "USING 'GOOD'::product_condition"
    )
    op.execute("DROP TYPE product_condition_legacy")


def downgrade() -> None:
    op.execute("ALTER TYPE product_condition RENAME TO product_condition_grades")
    op.execute("CREATE TYPE product_condition AS ENUM ('NEW', 'THRIFT', 'EXPORT_QUALITY')")
    op.execute(
        "ALTER TABLE products ALTER COLUMN condition TYPE product_condition "
        "USING CASE condition::text "
        "WHEN 'PREMIUM_PLUS' THEN 'NEW' "
        "WHEN 'PREMIUM' THEN 'EXPORT_QUALITY' "
        "ELSE 'THRIFT' END::product_condition"
    )
    op.execute("DROP TYPE product_condition_grades")
