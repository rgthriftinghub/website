/**
 * Editorial plate manifest.
 *
 * These are original, generated lookbook illustrations — not photography. Real
 * fashion images are copyrighted, so rather than borrow a shoot the plates are
 * drawn in the brand palette by `backend/scripts/generate_editorial_images.py`.
 *
 * When a real shoot arrives, replace the files at these paths and keep the names;
 * nothing else needs to change.
 */

import type { MarqueeItem } from "@/components/home/marquee";

const DIR = "/editorial";

type Plate = MarqueeItem & { gender: "women" | "men" };

export const EDITORIAL_PLATES: Plate[] = [
  { src: `${DIR}/women-denim-01.jpg`, alt: "Straight-leg denim, styled", caption: "Denim", gender: "women", href: "/shop?product_type=JEANS&gender=WOMEN" },
  { src: `${DIR}/women-baggy-01.jpg`, alt: "Baggy wide-leg jeans, styled", caption: "Baggy fit", gender: "women", href: "/shop?product_type=JEANS" },
  { src: `${DIR}/women-coat-01.jpg`, alt: "Long wool coat, styled", caption: "Outerwear", gender: "women", href: "/shop?product_type=JACKET" },
  { src: `${DIR}/women-jacket-01.jpg`, alt: "Denim jacket, styled", caption: "Jackets", gender: "women", href: "/shop?gender=WOMEN" },
  { src: `${DIR}/women-sweater-01.jpg`, alt: "Knitwear, styled", caption: "Knitwear", gender: "women", href: "/shop?product_type=SWEATER" },
  { src: `${DIR}/women-dress-01.jpg`, alt: "Midi dress, styled", caption: "Dresses", gender: "women", href: "/shop?product_type=DRESS" },
  { src: `${DIR}/women-skirt-01.jpg`, alt: "Midi skirt, styled", caption: "Skirts", gender: "women", href: "/shop?product_type=SKIRT" },
  { src: `${DIR}/men-denim-01.jpg`, alt: "Straight-leg denim, styled", caption: "Denim", gender: "men", href: "/shop?product_type=JEANS&gender=MEN" },
  { src: `${DIR}/men-baggy-01.jpg`, alt: "Baggy wide-leg jeans, styled", caption: "Baggy fit", gender: "men", href: "/shop?product_type=JEANS" },
  { src: `${DIR}/men-coat-01.jpg`, alt: "Overcoat, styled", caption: "Overcoats", gender: "men", href: "/shop?gender=MEN" },
  { src: `${DIR}/men-jacket-01.jpg`, alt: "Leather jacket, styled", caption: "Jackets", gender: "men", href: "/shop?product_type=JACKET" },
  { src: `${DIR}/men-shirt-01.jpg`, alt: "Linen shirt, styled", caption: "Shirting", gender: "men", href: "/shop?product_type=SHIRT" },
  { src: `${DIR}/men-hoodie-01.jpg`, alt: "Hooded sweat, styled", caption: "Sweats", gender: "men", href: "/shop?product_type=HOODIE" },
];

export const HERO_PLATE = `${DIR}/hero-women-01.jpg`;
export const HERO_PLATE_ALT = `${DIR}/hero-men-01.jpg`;

/** Women first and in greater number, as the buying mix skews that way. */
export const WOMENS_PLATES = EDITORIAL_PLATES.filter((plate) => plate.gender === "women");
export const MENS_PLATES = EDITORIAL_PLATES.filter((plate) => plate.gender === "men");

/**
 * Second band: men's plates padded with women's so the row is never sparse, and
 * so the two marquees never show the same sequence side by side.
 */
export const MIXED_PLATES = [...MENS_PLATES, ...WOMENS_PLATES.slice(0, 4)];

/**
 * Homepage hero slides.
 *
 * Wide banners with the headline overlaid. Each image is composed with its figures
 * on the right and the left third emptied, because that is where the type sits.
 *
 * To use real photography: drop files at these exact paths (2400x1100 or wider,
 * subject right-of-centre) and nothing else needs to change.
 */
export type HeroSlide = {
  image: string;
  alt: string;
  eyebrow: string;
  title: string;
  titleAccent: string;
  body: string;
  cta: string;
  href: string;
};

export const HERO_SLIDES: HeroSlide[] = [
  {
    image: `${DIR}/hero-wide-01.jpg`,
    alt: "Outerwear collection",
    eyebrow: "Lahore · Est. 2026",
    title: "Worn once.",
    titleAccent: "Wanted again.",
    body:
      "Hand-picked thrift and export-surplus clothing, inspected and graded piece by piece. Stock is tracked size by size — if a waist 32 shows as available, it is hanging on the rail.",
    cta: "Shop the collection",
    href: "/shop",
  },
  {
    image: `${DIR}/hero-wide-02.jpg`,
    alt: "Women's denim",
    eyebrow: "Women · Denim",
    title: "Denim that",
    titleAccent: "holds its shape.",
    body:
      "Straight legs, high rises and honest fades. Every waist measured by hand and listed exactly as it falls — 26 through 38.",
    cta: "Shop women's denim",
    href: "/shop?product_type=JEANS&gender=WOMEN",
  },
  {
    image: `${DIR}/hero-wide-03.jpg`,
    alt: "Menswear",
    eyebrow: "Men",
    title: "The menswear",
    titleAccent: "edit.",
    body:
      "Field jackets, oxford shirting and heavyweight sweats. Built to be worn hard and still look right.",
    cta: "Shop men",
    href: "/shop?gender=MEN",
  },
  {
    image: `${DIR}/hero-wide-04.jpg`,
    alt: "Winter collection",
    eyebrow: "Winter",
    title: "Coats with the",
    titleAccent: "weight still in them.",
    body:
      "Wool, tweed and heavy knit — the pieces that outlast a season. Graded honestly, so you know what you are buying.",
    cta: "Shop winter",
    href: "/shop?product_type=JACKET",
  },
  {
    image: `${DIR}/hero-wide-05.jpg`,
    alt: "Baggy jeans",
    eyebrow: "Baggy fit",
    title: "Room to",
    titleAccent: "move.",
    body:
      "Wide legs, dropped crotches and slouchy denim. The relaxed silhouette, in the sizes that actually run big.",
    cta: "Shop baggy jeans",
    href: "/shop?product_type=JEANS",
  },
];
