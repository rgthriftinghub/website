"""Allow long product descriptions."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3f7a91c6b42"
down_revision: Union[str, Sequence[str], None] = "a19f6b3d8c42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "products", "short_description",
        existing_type=sa.String(length=400),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="short_description::text",
    )
    op.alter_column(
        "products", "meta_description",
        existing_type=sa.String(length=320),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="meta_description::text",
    )


def downgrade() -> None:
    # Refuse the downgrade if it would truncate saved descriptions.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM products
                WHERE char_length(short_description) > 400
                   OR char_length(meta_description) > 320
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: product descriptions exceed VARCHAR limits';
            END IF;
        END
        $$;
    """)
    op.alter_column(
        "products", "short_description",
        existing_type=sa.Text(),
        type_=sa.String(length=400),
        existing_nullable=True,
        postgresql_using="short_description::varchar(400)",
    )
    op.alter_column(
        "products", "meta_description",
        existing_type=sa.Text(),
        type_=sa.String(length=320),
        existing_nullable=True,
        postgresql_using="meta_description::varchar(320)",
    )
