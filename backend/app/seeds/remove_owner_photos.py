"""Hide the owner-photo demo catalogue without disturbing historical orders.

Run with ``python -m app.seeds.remove_owner_photos`` from backend/.
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.product import Product
from app.seeds.owner_photos import OWNER_PHOTO_PRODUCTS


def run() -> None:
    db = SessionLocal()
    try:
        count = 0
        for data in OWNER_PHOTO_PRODUCTS:
            product = db.scalar(select(Product).where(Product.slug == data.slug))
            if product is None:
                continue
            product.is_active = False
            for variant in product.variants:
                variant.is_active = False
            count += 1
        for slug in ("men", "women", "kids"):
            category = db.scalar(select(Category).where(Category.slug == slug))
            if category is not None:
                category.image_url = f"/demo/categories/{slug}.png"
        db.commit()
        print(f"Hidden {count} owner-photo demo products from the storefront.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
