"""add product reviews and SEO metadata"""
from alembic import op
import sqlalchemy as sa

revision = "8ad129bf31c0"
down_revision = "7453b1a4a3e4"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("products", sa.Column("seo_title", sa.String(200), nullable=True))
    op.add_column("products", sa.Column("meta_description", sa.String(320), nullable=True))
    op.create_table(
        "product_reviews",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "user_id", name="uq_review_product_user"),
    )
    op.create_index("ix_product_reviews_product_id", "product_reviews", ["product_id"])
    op.create_index("ix_product_reviews_user_id", "product_reviews", ["user_id"])

def downgrade() -> None:
    op.drop_index("ix_product_reviews_user_id", table_name="product_reviews")
    op.drop_index("ix_product_reviews_product_id", table_name="product_reviews")
    op.drop_table("product_reviews")
    op.drop_column("products", "meta_description")
    op.drop_column("products", "seo_title")
