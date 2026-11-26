"""Demo catalogue definition.

Single source of truth for the seed script and the placeholder-image generator,
so image filenames and product slugs can never drift apart.

All brands, product names, descriptions, and prices here are invented for local
development. Nothing is taken from any real store's catalogue. Prices are in PKR.
"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class VariantSeed:
    sku_suffix: str
    size: str | None = None
    waist: int | None = None
    color: str | None = None
    quantity: int = 0
    low_stock_threshold: int = 3


@dataclass(frozen=True)
class ProductSeed:
    slug: str
    name: str
    sku: str
    category_slug: str
    subcategory_slug: str
    product_type: str
    gender: str
    condition: str
    regular_price: Decimal
    short_description: str
    description: str
    brand_slug: str | None = None
    sale_price: Decimal | None = None
    color: str | None = None
    fabric: str | None = None
    is_featured: bool = False
    is_new_arrival: bool = False
    barcode: str | None = None
    image_count: int = 2
    variants: tuple[VariantSeed, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SubcategorySeed:
    slug: str
    name: str
    sort_order: int = 0


@dataclass(frozen=True)
class CategorySeed:
    slug: str
    name: str
    description: str
    sort_order: int
    subcategories: tuple[SubcategorySeed, ...]


@dataclass(frozen=True)
class BrandSeed:
    slug: str
    name: str
    description: str


# --------------------------------------------------------------------------- taxonomy
CATEGORIES: tuple[CategorySeed, ...] = (
    CategorySeed(
        slug="men",
        name="Men",
        description="Curated menswear: denim, outerwear, shirting and everyday knitwear.",
        sort_order=1,
        subcategories=(
            SubcategorySeed(slug="jeans", name="Jeans", sort_order=1),
            SubcategorySeed(slug="shirts", name="Shirts", sort_order=2),
            SubcategorySeed(slug="t-shirts", name="T-Shirts", sort_order=3),
            SubcategorySeed(slug="jackets", name="Jackets", sort_order=4),
            SubcategorySeed(slug="hoodies", name="Hoodies", sort_order=5),
        ),
    ),
    CategorySeed(
        slug="women",
        name="Women",
        description="Hand-picked womenswear with an emphasis on fabric and fit.",
        sort_order=2,
        subcategories=(
            SubcategorySeed(slug="tops", name="Tops", sort_order=1),
            SubcategorySeed(slug="dresses", name="Dresses", sort_order=2),
            SubcategorySeed(slug="jeans", name="Jeans", sort_order=3),
            SubcategorySeed(slug="abayas", name="Abayas", sort_order=4),
        ),
    ),
    CategorySeed(
        slug="accessories",
        name="Accessories",
        description="Finishing pieces: bags, caps and belts chosen for durability.",
        sort_order=3,
        subcategories=(
            SubcategorySeed(slug="bags", name="Bags", sort_order=1),
            SubcategorySeed(slug="caps", name="Caps", sort_order=2),
            SubcategorySeed(slug="belts", name="Belts", sort_order=3),
        ),
    ),
    CategorySeed(
        slug="kids",
        name="Kids",
        description="Pre-loved clothing for girls and boys, checked and graded piece by piece.",
        sort_order=4,
        subcategories=(
            SubcategorySeed(slug="girls", name="Girls", sort_order=1),
            SubcategorySeed(slug="boys", name="Boys", sort_order=2),
        ),
    ),
)

BRANDS: tuple[BrandSeed, ...] = (
    BrandSeed(
        slug="northbay-denim",
        name="Northbay Denim",
        description="Denim specialists. Heavyweight cotton, honest hardware, built to outlast trends.",
    ),
    BrandSeed(
        slug="sable-and-stone",
        name="Sable & Stone",
        description="Quiet tailoring and knitwear in a restrained, neutral palette.",
    ),
    BrandSeed(
        slug="karachi-kraft",
        name="Karachi Kraft",
        description="Locally made staples in breathable cotton and khaddar.",
    ),
    BrandSeed(
        slug="vertex-sport",
        name="Vertex Sport",
        description="Performance-led layers for training and everyday movement.",
    ),
    BrandSeed(
        slug="maison-ruz",
        name="Maison Ruz",
        description="Considered womenswear with an emphasis on drape and finish.",
    ),
)


# --------------------------------------------------------------------------- products
PRODUCTS: tuple[ProductSeed, ...] = (
    # The variant matrix required for exercising per-size stock behaviour:
    # waist 30 -> 5, waist 32 -> 8, waist 34 -> 0 (that waist alone is unavailable).
    ProductSeed(
        slug="northbay-straight-leg-jeans-indigo",
        name="Straight Leg Jeans in Deep Indigo",
        sku="RG-MJ-1001",
        brand_slug="northbay-denim",
        category_slug="men",
        subcategory_slug="jeans",
        product_type="JEANS",
        gender="MEN",
        condition="GOOD",
        regular_price=Decimal("5200.00"),
        sale_price=Decimal("3900.00"),
        color="Indigo",
        fabric="Denim",
        is_featured=True,
        is_new_arrival=True,
        barcode="RGB1001001",
        short_description="Rigid 13oz denim with a clean straight leg and a mid rise.",
        description=(
            "A straight leg cut in deep indigo denim, hand-checked for wear and fit. "
            "The fabric is a rigid 13oz cotton that softens with use and holds its "
            "shape through repeated washes. Mid rise, five pockets, tonal stitching "
            "and a branded shank button. Waist sizes are stocked individually."
        ),
        image_count=3,
        variants=(
            VariantSeed(sku_suffix="W30", waist=30, color="Indigo", quantity=5),
            VariantSeed(sku_suffix="W32", waist=32, color="Indigo", quantity=8),
            VariantSeed(sku_suffix="W34", waist=34, color="Indigo", quantity=0),
        ),
    ),
    ProductSeed(
        slug="northbay-relaxed-carpenter-jeans",
        name="Relaxed Carpenter Jeans",
        sku="RG-MJ-1002",
        brand_slug="northbay-denim",
        category_slug="men",
        subcategory_slug="jeans",
        product_type="JEANS",
        gender="MEN",
        condition="GOOD",
        regular_price=Decimal("4800.00"),
        color="Mid Blue",
        fabric="Denim",
        is_new_arrival=True,
        short_description="Roomy carpenter fit with a utility pocket and reinforced seams.",
        description=(
            "A relaxed carpenter jean with a utility pocket at the thigh and a "
            "hammer loop. Cut wide through the leg with a straight opening, this "
            "pair sits comfortably over boots. Mid blue wash with light natural "
            "fading at the seat and knee."
        ),
        variants=(
            VariantSeed(sku_suffix="W30", waist=30, color="Mid Blue", quantity=3),
            VariantSeed(sku_suffix="W32", waist=32, color="Mid Blue", quantity=6),
            VariantSeed(sku_suffix="W34", waist=34, color="Mid Blue", quantity=2),
            VariantSeed(sku_suffix="W36", waist=36, color="Mid Blue", quantity=0),
        ),
    ),
    ProductSeed(
        slug="sable-oxford-shirt-ecru",
        name="Cotton Oxford Shirt in Ecru",
        sku="RG-MS-1003",
        brand_slug="sable-and-stone",
        category_slug="men",
        subcategory_slug="shirts",
        product_type="SHIRT",
        gender="MEN",
        condition="PREMIUM",
        regular_price=Decimal("3600.00"),
        sale_price=Decimal("2700.00"),
        color="Ecru",
        fabric="Cotton",
        is_featured=True,
        short_description="Button-down oxford in a soft ecru with a relaxed collar roll.",
        description=(
            "An oxford shirt in mid-weight cotton with a natural ecru tone that "
            "works with denim and tailoring alike. Button-down collar with a soft "
            "roll, single chest pocket, and a straight hem that sits well untucked."
        ),
        image_count=3,
        variants=(
            VariantSeed(sku_suffix="S", size="S", quantity=4),
            VariantSeed(sku_suffix="M", size="M", quantity=7),
            VariantSeed(sku_suffix="L", size="L", quantity=2),
            VariantSeed(sku_suffix="XL", size="XL", quantity=0),
        ),
    ),
    ProductSeed(
        slug="karachi-kraft-khaddar-shirt",
        name="Khaddar Shirt in Slate",
        sku="RG-MS-1004",
        brand_slug="karachi-kraft",
        category_slug="men",
        subcategory_slug="shirts",
        product_type="SHIRT",
        gender="MEN",
        condition="PREMIUM_PLUS",
        regular_price=Decimal("2900.00"),
        color="Slate",
        fabric="Khaddar",
        short_description="Handwoven khaddar with a dry finish that breathes in warm weather.",
        description=(
            "Cut from handwoven khaddar with a dry, textured finish. The weave is "
            "open enough to stay cool through the afternoon while keeping a crisp "
            "line at the shoulder. Spread collar and a curved hem."
        ),
        variants=(
            VariantSeed(sku_suffix="M", size="M", quantity=6),
            VariantSeed(sku_suffix="L", size="L", quantity=5),
            VariantSeed(sku_suffix="XL", size="XL", quantity=3),
        ),
    ),
    ProductSeed(
        slug="sable-heavyweight-tee-charcoal",
        name="Heavyweight Cotton Tee in Charcoal",
        sku="RG-MT-1005",
        brand_slug="sable-and-stone",
        category_slug="men",
        subcategory_slug="t-shirts",
        product_type="T_SHIRT",
        gender="UNISEX",
        condition="PREMIUM_PLUS",
        regular_price=Decimal("1800.00"),
        color="Charcoal",
        fabric="Cotton",
        is_new_arrival=True,
        short_description="240gsm cotton with a set-in sleeve and a ribbed neck that holds.",
        description=(
            "A heavyweight 240gsm cotton tee that hangs straight rather than "
            "clinging. Set-in sleeves, a ribbed collar bound to resist stretching, "
            "and a boxy body cut for a modern line."
        ),
        variants=(
            VariantSeed(sku_suffix="S", size="S", quantity=9),
            VariantSeed(sku_suffix="M", size="M", quantity=12),
            VariantSeed(sku_suffix="L", size="L", quantity=8),
            VariantSeed(sku_suffix="XL", size="XL", quantity=4),
        ),
    ),
    ProductSeed(
        slug="northbay-trucker-jacket-washed",
        name="Washed Denim Trucker Jacket",
        sku="RG-MJK-1006",
        brand_slug="northbay-denim",
        category_slug="men",
        subcategory_slug="jackets",
        product_type="JACKET",
        gender="UNISEX",
        condition="GOOD",
        regular_price=Decimal("7400.00"),
        sale_price=Decimal("5900.00"),
        color="Washed Blue",
        fabric="Denim",
        is_featured=True,
        short_description="Classic four-pocket trucker with honest fading and a broken-in feel.",
        description=(
            "A trucker jacket in washed denim that already carries a genuine "
            "broken-in softness. Four pockets, adjustable waist tabs, and a "
            "pointed western yoke. Layers over a hoodie without pulling."
        ),
        image_count=3,
        variants=(
            VariantSeed(sku_suffix="M", size="M", quantity=2),
            VariantSeed(sku_suffix="L", size="L", quantity=3),
            VariantSeed(sku_suffix="XL", size="XL", quantity=0),
        ),
    ),
    ProductSeed(
        slug="vertex-fleece-hoodie-olive",
        name="Brushed Fleece Hoodie in Olive",
        sku="RG-MH-1007",
        brand_slug="vertex-sport",
        category_slug="men",
        subcategory_slug="hoodies",
        product_type="HOODIE",
        gender="UNISEX",
        condition="PREMIUM",
        regular_price=Decimal("4200.00"),
        color="Olive",
        fabric="Fleece",
        short_description="Brushed-back fleece with a lined hood and ribbed cuffs.",
        description=(
            "A pullover hoodie in brushed-back fleece with a double-layer hood and "
            "flat drawcords. Ribbed cuffs and hem keep the shape after washing. "
            "Warm without bulk, in a muted olive."
        ),
        variants=(
            VariantSeed(sku_suffix="S", size="S", quantity=0),
            VariantSeed(sku_suffix="M", size="M", quantity=5),
            VariantSeed(sku_suffix="L", size="L", quantity=6),
        ),
    ),
    ProductSeed(
        slug="vertex-technical-shorts-black",
        name="Technical Training Shorts",
        sku="RG-MSH-1008",
        brand_slug="vertex-sport",
        category_slug="men",
        subcategory_slug="t-shirts",
        product_type="ACTIVEWEAR",
        gender="MEN",
        condition="PREMIUM_PLUS",
        regular_price=Decimal("2400.00"),
        sale_price=Decimal("1750.00"),
        color="Black",
        fabric="Polyester",
        short_description="Light woven shell with a zip pocket and a bonded waistband.",
        description=(
            "Training shorts in a light woven shell with a smooth bonded waistband "
            "that avoids pressure points. A zipped rear pocket holds a phone "
            "without bounce. Seven-inch inseam."
        ),
        variants=(
            VariantSeed(sku_suffix="S", size="S", quantity=6),
            VariantSeed(sku_suffix="M", size="M", quantity=10),
            VariantSeed(sku_suffix="L", size="L", quantity=7),
        ),
    ),
    ProductSeed(
        slug="maison-ruz-linen-blouse-sand",
        name="Linen Blend Blouse in Sand",
        sku="RG-WT-1009",
        brand_slug="maison-ruz",
        category_slug="women",
        subcategory_slug="tops",
        product_type="SHIRT",
        gender="WOMEN",
        condition="PREMIUM",
        regular_price=Decimal("4100.00"),
        color="Sand",
        fabric="Linen Blend",
        is_featured=True,
        is_new_arrival=True,
        short_description="Softly draping linen blend with a concealed placket.",
        description=(
            "A relaxed blouse in a linen blend that drapes rather than holds a "
            "stiff line. Concealed placket for a clean front, dropped shoulder, "
            "and a slightly longer back hem."
        ),
        image_count=3,
        variants=(
            VariantSeed(sku_suffix="XS", size="XS", quantity=3),
            VariantSeed(sku_suffix="S", size="S", quantity=6),
            VariantSeed(sku_suffix="M", size="M", quantity=4),
            VariantSeed(sku_suffix="L", size="L", quantity=0),
        ),
    ),
    ProductSeed(
        slug="maison-ruz-midi-dress-forest",
        name="Crepe Midi Dress in Forest",
        sku="RG-WD-1010",
        brand_slug="maison-ruz",
        category_slug="women",
        subcategory_slug="dresses",
        product_type="DRESS",
        gender="WOMEN",
        condition="PREMIUM_PLUS",
        regular_price=Decimal("8200.00"),
        sale_price=Decimal("6150.00"),
        color="Forest",
        fabric="Crepe",
        is_featured=True,
        short_description="Fluid crepe with a defined waist and a covered back zip.",
        description=(
            "A midi dress in fluid crepe with a defined waist seam and a gently "
            "flared skirt. Fully covered back zip, faced neckline, and a lining "
            "through the bodice. Falls below the calf on most heights."
        ),
        variants=(
            VariantSeed(sku_suffix="XS", size="XS", quantity=2),
            VariantSeed(sku_suffix="S", size="S", quantity=4),
            VariantSeed(sku_suffix="M", size="M", quantity=3),
        ),
    ),
    ProductSeed(
        slug="northbay-womens-mom-jeans",
        name="High Rise Mom Jeans",
        sku="RG-WJ-1011",
        brand_slug="northbay-denim",
        category_slug="women",
        subcategory_slug="jeans",
        product_type="JEANS",
        gender="WOMEN",
        condition="GOOD",
        regular_price=Decimal("4600.00"),
        color="Light Wash",
        fabric="Denim",
        is_new_arrival=True,
        short_description="High rise with a tapered leg and a genuine vintage wash.",
        description=(
            "A high rise mom jean with a tapered leg and a light vintage wash that "
            "was not chemically forced. Sits at the natural waist, roomy through "
            "the hip, and cropped just above the ankle."
        ),
        variants=(
            VariantSeed(sku_suffix="W26", waist=26, color="Light Wash", quantity=4),
            VariantSeed(sku_suffix="W28", waist=28, color="Light Wash", quantity=5),
            VariantSeed(sku_suffix="W30", waist=30, color="Light Wash", quantity=0),
            VariantSeed(sku_suffix="W32", waist=32, color="Light Wash", quantity=1),
        ),
    ),
    ProductSeed(
        slug="karachi-kraft-abaya-black",
        name="Nida Abaya in Black",
        sku="RG-WA-1012",
        brand_slug="karachi-kraft",
        category_slug="women",
        subcategory_slug="abayas",
        product_type="ABAYA",
        gender="WOMEN",
        condition="PREMIUM_PLUS",
        regular_price=Decimal("5400.00"),
        color="Black",
        fabric="Nida",
        short_description="Matte nida with a straight fall and covered front closure.",
        description=(
            "A straight-cut abaya in matte nida that resists shine under daylight. "
            "Covered front closure, set-in sleeves with a plain cuff, and a hem "
            "weighted to hang evenly."
        ),
        variants=(
            VariantSeed(sku_suffix="52", size="52", quantity=5),
            VariantSeed(sku_suffix="54", size="54", quantity=6),
            VariantSeed(sku_suffix="56", size="56", quantity=4),
            VariantSeed(sku_suffix="58", size="58", quantity=2),
        ),
    ),
    ProductSeed(
        slug="sable-canvas-tote-natural",
        name="Heavy Canvas Tote in Natural",
        sku="RG-AB-1013",
        brand_slug="sable-and-stone",
        category_slug="accessories",
        subcategory_slug="bags",
        product_type="ACCESSORY",
        gender="UNISEX",
        condition="PREMIUM_PLUS",
        regular_price=Decimal("2200.00"),
        color="Natural",
        fabric="Canvas",
        short_description="16oz canvas with bar-tacked handles and an inner pocket.",
        description=(
            "A tote in 16oz canvas with handles bar-tacked at the stress points, "
            "so they hold under a full load. One internal slip pocket and a flat "
            "base that lets the bag stand on its own."
        ),
        variants=(VariantSeed(sku_suffix="OS", size="One Size", quantity=15),),
    ),
    ProductSeed(
        slug="vertex-washed-cap-stone",
        name="Washed Cotton Cap in Stone",
        sku="RG-AC-1014",
        brand_slug="vertex-sport",
        category_slug="accessories",
        subcategory_slug="caps",
        product_type="ACCESSORY",
        gender="UNISEX",
        condition="PREMIUM",
        regular_price=Decimal("1500.00"),
        sale_price=Decimal("1100.00"),
        color="Stone",
        fabric="Cotton",
        short_description="Six-panel cap in washed cotton with a metal slide closure.",
        description=(
            "A six-panel cap in washed cotton twill with a pre-curved brim and a "
            "metal slide closure rather than plastic. Soft enough to fold into a "
            "bag without creasing permanently."
        ),
        variants=(VariantSeed(sku_suffix="OS", size="One Size", quantity=20),),
    ),
    ProductSeed(
        slug="karachi-kraft-leather-belt-brown",
        name="Full Grain Leather Belt in Brown",
        sku="RG-ABL-1015",
        brand_slug="karachi-kraft",
        category_slug="accessories",
        subcategory_slug="belts",
        product_type="ACCESSORY",
        gender="MEN",
        condition="PREMIUM_PLUS",
        regular_price=Decimal("2800.00"),
        color="Brown",
        fabric="Leather",
        short_description="Full grain leather with a solid brass buckle and stitched keeper.",
        description=(
            "A 35mm belt cut from full grain leather that develops a patina rather "
            "than cracking. Solid brass buckle on a stitched keeper, with edges "
            "burnished and sealed by hand."
        ),
        variants=(
            VariantSeed(sku_suffix="W32", waist=32, quantity=4),
            VariantSeed(sku_suffix="W34", waist=34, quantity=6),
            VariantSeed(sku_suffix="W36", waist=36, quantity=3),
            VariantSeed(sku_suffix="W38", waist=38, quantity=0),
        ),
    ),
    ProductSeed(
        slug="sable-merino-crew-oat",
        name="Merino Crew Neck in Oat",
        sku="RG-MK-1016",
        brand_slug="sable-and-stone",
        category_slug="men",
        subcategory_slug="hoodies",
        product_type="SWEATER",
        gender="UNISEX",
        condition="PREMIUM",
        regular_price=Decimal("6300.00"),
        sale_price=Decimal("4700.00"),
        color="Oat",
        fabric="Merino Wool",
        is_featured=True,
        short_description="Fine gauge merino that layers flat under a jacket.",
        description=(
            "A fine gauge merino crew that layers flat under outerwear without "
            "bunching. Naturally temperature regulating and far less prone to "
            "odour than synthetic knits. Fully fashioned shoulders."
        ),
        image_count=3,
        variants=(
            VariantSeed(sku_suffix="S", size="S", quantity=3),
            VariantSeed(sku_suffix="M", size="M", quantity=5),
            VariantSeed(sku_suffix="L", size="L", quantity=4),
            VariantSeed(sku_suffix="XL", size="XL", quantity=0),
        ),
    ),
)
