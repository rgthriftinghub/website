"""Owner supplied product photos used by the development seed."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.enums import Gender, ProductCondition, ProductType
from app.models.inventory import InventoryItem
from app.models.product import Product, ProductImage
from app.models.variant import ProductVariant

MEDIA = "/products/owner-uploaded"


@dataclass(frozen=True)
class OwnerPhotoProduct:
    slug: str
    name: str
    sku: str
    code: str
    brand: str
    category: str
    subcategory: str
    gender: Gender
    product_type: ProductType
    condition: ProductCondition
    price: Decimal
    size: str
    color: str
    fabric: str
    description: str
    photos: tuple[str, ...]
    sale_price: Decimal | None = None
    new_in: bool = False
    featured: bool = False


OWNER_PHOTO_PRODUCTS = (
    OwnerPhotoProduct("owner-photo-pale-pink-shirt", "Pale Pink Cotton Button Shirt", "RG-OP-001", "RG-THRIFT-001", "maison-ruz", "women", "tops", Gender.WOMEN, ProductType.SHIRT, ProductCondition.EXCELLENT, Decimal("3200"), "S", "Pale Pink", "Cotton", "A softly structured pink cotton shirt, checked and ready for everyday wear.", ("blouse-pale-pink.png",), new_in=True),
    OwnerPhotoProduct("owner-photo-pink-stripe-shirt", "Pink Stripe Fitted Shirt", "RG-OP-002", "RG-THRIFT-002", "sable-and-stone", "women", "tops", Gender.WOMEN, ProductType.SHIRT, ProductCondition.PREMIUM, Decimal("3400"), "M", "Pink Stripe", "Cotton", "A crisp striped shirt with a shaped fit and contrast cuffs.", ("shirt-pink-black-stripe.png",), Decimal("2900"), True),
    OwnerPhotoProduct("owner-photo-blue-stripe-shirt", "Blue Pinstripe Cotton Shirt", "RG-OP-003", "RG-THRIFT-003", "sable-and-stone", "men", "shirts", Gender.MEN, ProductType.SHIRT, ProductCondition.PREMIUM_PLUS, Decimal("3600"), "M", "Blue Stripe", "Cotton", "A clean blue pinstripe shirt with a button collar and long sleeves.", ("shirt-blue-stripe.png",), featured=True),
    OwnerPhotoProduct("owner-photo-light-grey-shirt", "Light Grey Everyday Shirt", "RG-OP-004", "RG-THRIFT-004", "northbay-denim", "men", "shirts", Gender.MEN, ProductType.SHIRT, ProductCondition.GOOD, Decimal("2800"), "L", "Light Grey", "Cotton Blend", "A versatile grey button-up with a subtle contrast detail at the collar.", ("shirt-light-grey.png",), Decimal("2300")),
    OwnerPhotoProduct("owner-photo-ivory-ruffle-blouse", "Ivory Ruffle Front Blouse", "RG-OP-005", "RG-THRIFT-005", "maison-ruz", "kids", "girls", Gender.KIDS, ProductType.SHIRT, ProductCondition.EXCELLENT, Decimal("2500"), "8Y", "Ivory", "Cotton Blend", "A light ivory blouse with a soft ruffle front and rounded collar.", ("blouse-ivory-ruffle.png",), new_in=True),
    OwnerPhotoProduct("owner-photo-ivory-stripe-shirt", "Ivory Fine Stripe Shirt", "RG-OP-006", "RG-THRIFT-006", "sable-and-stone", "kids", "boys", Gender.KIDS, ProductType.SHIRT, ProductCondition.PREMIUM, Decimal("2400"), "10Y", "Ivory Stripe", "Cotton", "A neat fine-stripe shirt with a button front and comfortable cuffs.", ("shirt-ivory-fine-stripe.png",)),
    OwnerPhotoProduct("owner-photo-logo-knit", "Black Graphic Knit Sweater", "RG-OP-007", "RG-THRIFT-007", "vertex-sport", "men", "hoodies", Gender.UNISEX, ProductType.SWEATER, ProductCondition.GOOD, Decimal("4600"), "L", "Black", "Knit", "A warm black statement knit with a bold all-over graphic.", ("sweater-black-logo.jpeg",), featured=True),
    OwnerPhotoProduct("owner-photo-green-turtleneck", "Forest Green Ribbed Turtleneck", "RG-OP-008", "RG-THRIFT-008", "sable-and-stone", "women", "tops", Gender.WOMEN, ProductType.SWEATER, ProductCondition.PREMIUM_PLUS, Decimal("4200"), "M", "Forest Green", "Rib Knit", "A fitted ribbed turtleneck in deep forest green.", ("sweater-green-turtleneck-01.jpeg", "sweater-green-turtleneck-02.jpeg"), new_in=True),
    OwnerPhotoProduct("owner-photo-black-v-neck", "Black Ribbed V-Neck Top", "RG-OP-009", "RG-THRIFT-009", "maison-ruz", "women", "tops", Gender.WOMEN, ProductType.SWEATER, ProductCondition.EXCELLENT, Decimal("3800"), "S", "Black", "Rib Knit", "A versatile long-sleeve ribbed top with a flattering V neckline.", ("top-black-v-neck.jpeg",), Decimal("3200")),
    OwnerPhotoProduct("owner-photo-burgundy-turtleneck", "Burgundy Ribbed Turtleneck", "RG-OP-010", "RG-THRIFT-010", "sable-and-stone", "women", "tops", Gender.WOMEN, ProductType.SWEATER, ProductCondition.PREMIUM, Decimal("4300"), "M", "Burgundy", "Rib Knit", "A cosy burgundy turtleneck with a slim, easy-to-layer profile.", ("sweater-burgundy-turtleneck.jpeg",), new_in=True),
    OwnerPhotoProduct("owner-photo-black-turtleneck", "Black Fine Rib Turtleneck", "RG-OP-011", "RG-THRIFT-011", "northbay-denim", "men", "hoodies", Gender.UNISEX, ProductType.SWEATER, ProductCondition.GOOD, Decimal("4100"), "L", "Black", "Rib Knit", "A classic black fine-rib turtleneck for cool-weather layering.", ("sweater-black-turtleneck.jpeg",), Decimal("3500")),
    OwnerPhotoProduct("owner-photo-black-blazer-one", "Black Tailored Single Button Blazer", "RG-OP-012", "RG-THRIFT-012", "sable-and-stone", "women", "tops", Gender.WOMEN, ProductType.JACKET, ProductCondition.PREMIUM_PLUS, Decimal("5900"), "M", "Black", "Woven Blend", "A clean black tailored blazer with notch lapels and a single-button front.", ("blazer-black-01.jpeg",), featured=True),
    OwnerPhotoProduct("owner-photo-black-blazer-two", "Black Classic Longline Blazer", "RG-OP-013", "RG-THRIFT-013", "maison-ruz", "women", "tops", Gender.WOMEN, ProductType.JACKET, ProductCondition.EXCELLENT, Decimal("5600"), "M", "Black", "Woven Blend", "A structured black blazer with a smooth lining and practical pockets.", ("blazer-black-02.jpeg",)),
    OwnerPhotoProduct("owner-photo-black-blazer-three", "Black Everyday Fitted Blazer", "RG-OP-014", "RG-THRIFT-014", "sable-and-stone", "women", "tops", Gender.WOMEN, ProductType.JACKET, ProductCondition.GOOD, Decimal("5200"), "L", "Black", "Woven Blend", "An easy-to-style black blazer with a fitted shape and soft lining.", ("blazer-black-03.jpeg",), Decimal("4400")),
    OwnerPhotoProduct("owner-photo-pinstripe-blazer", "Charcoal Pinstripe Tailored Blazer", "RG-OP-015", "RG-THRIFT-015", "northbay-denim", "women", "tops", Gender.WOMEN, ProductType.JACKET, ProductCondition.PREMIUM, Decimal("6200"), "M", "Charcoal Pinstripe", "Woven Blend", "A charcoal blazer with fine pinstripes and a sharply tailored silhouette.", ("blazer-charcoal-pinstripe.jpeg",), new_in=True),
    OwnerPhotoProduct("owner-photo-pink-blazer", "Rose Pink Cropped Blazer", "RG-OP-016", "RG-THRIFT-016", "maison-ruz", "women", "tops", Gender.WOMEN, ProductType.JACKET, ProductCondition.PREMIUM_PLUS, Decimal("5700"), "M", "Rose Pink", "Woven Blend", "A cropped rose-pink blazer with a modern tie-front finish.", ("blazer-pink.jpeg",), Decimal("4900"), True),
)


def seed_owner_photo_products(
    db: Session,
    categories: dict[str, Category],
    subcategories: dict[tuple[str, str], Subcategory],
    brands: dict[str, Brand],
) -> list[Product]:
    """Upsert the owner photo catalogue, keeping one one-piece variant per item."""
    products: list[Product] = []
    for data in OWNER_PHOTO_PRODUCTS:
        product = db.scalar(select(Product).where(Product.slug == data.slug))
        if product is None:
            product = Product(slug=data.slug)
            db.add(product)

        product.name = data.name
        product.sku = data.sku
        product.item_code = data.code
        product.single_piece = True
        product.description = data.description
        product.short_description = data.description
        product.brand_id = brands[data.brand].id
        product.category_id = categories[data.category].id
        product.subcategory_id = subcategories[(data.category, data.subcategory)].id
        product.regular_price = data.price
        product.sale_price = data.sale_price
        product.condition = data.condition
        product.gender = data.gender
        product.product_type = data.product_type
        product.color = data.color
        product.fabric = data.fabric
        product.is_featured = data.featured
        product.is_new_arrival = data.new_in
        product.is_active = True
        db.flush()

        for image in list(product.images):
            db.delete(image)
        db.flush()
        for order, filename in enumerate(data.photos):
            db.add(ProductImage(
                product_id=product.id,
                image_url=f"{MEDIA}/{filename}",
                alt_text=f"{data.name} — {('alternate view' if order else 'front view')}",
                sort_order=order,
                is_primary=order == 0,
            ))

        variant_sku = f"{data.sku}-ONE"
        variant = db.scalar(select(ProductVariant).where(ProductVariant.sku == variant_sku))
        if variant is None:
            variant = ProductVariant(product_id=product.id, sku=variant_sku)
            db.add(variant)
        variant.product_id = product.id
        variant.size = data.size
        variant.waist = None
        variant.color = data.color
        variant.variant_name = None
        variant.is_active = True
        db.flush()
        if variant.inventory is None:
            variant.inventory = InventoryItem(quantity=1, low_stock_threshold=1)
        else:
            variant.inventory.quantity = 1
            variant.inventory.low_stock_threshold = 1
        products.append(product)

    # Use actual catalog photos for departments that have a matching garment.
    categories["men"].image_url = f"{MEDIA}/sweater-black-logo.jpeg"
    categories["women"].image_url = f"{MEDIA}/blazer-black-01.jpeg"
    categories["kids"].image_url = f"{MEDIA}/blouse-ivory-ruffle.png"
    db.flush()
    return products
