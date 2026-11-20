"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AdminGate } from "@/components/admin/admin-gate";
import { Button } from "@/components/ui/button";
import { createAdminProduct, getAdminProduct, listAdminCategories, listAdminProducts, updateAdminProduct } from "@/lib/api/catalog";
import type { CategoryDetail, ProductAdmin, ProductCondition } from "@/lib/api/types";

const PHOTOS = [
  ["blouse-pale-pink.png", "Pale pink button shirt"],
  ["shirt-pink-black-stripe.png", "Pink and black striped shirt"],
  ["shirt-blue-stripe.png", "Blue striped shirt"],
  ["shirt-light-grey.png", "Light grey shirt"],
  ["blouse-ivory-ruffle.png", "Ivory ruffle blouse"],
  ["shirt-ivory-fine-stripe.png", "Ivory fine-stripe shirt"],
  ["sweater-black-logo.jpeg", "Black logo sweater"],
  ["sweater-green-turtleneck-01.jpeg", "Green turtleneck sweater"],
  ["sweater-green-turtleneck-02.jpeg", "Green turtleneck sweater, second photo"],
  ["top-black-v-neck.jpeg", "Black V-neck top"],
  ["sweater-burgundy-turtleneck.jpeg", "Burgundy turtleneck sweater"],
  ["sweater-black-turtleneck.jpeg", "Black turtleneck sweater"],
  ["blazer-black-01.jpeg", "Black blazer"],
  ["blazer-black-02.jpeg", "Black blazer, second style"],
  ["blazer-black-03.jpeg", "Black blazer, third style"],
  ["blazer-charcoal-pinstripe.jpeg", "Charcoal pinstripe blazer"],
  ["blazer-pink.jpeg", "Pink blazer"],
] as const;

const ITEMS = [
  [PHOTOS[0][0], "Pale Pink Button Shirt", 3200, "SHIRT"],
  [PHOTOS[1][0], "Pink Stripe Button Shirt", 3400, "SHIRT"],
  [PHOTOS[2][0], "Blue Stripe Button Shirt", 3200, "SHIRT"],
  [PHOTOS[3][0], "Light Grey Button Shirt", 3000, "SHIRT"],
  [PHOTOS[4][0], "Ivory Ruffle Blouse", 3500, "SHIRT"],
  [PHOTOS[5][0], "Ivory Fine Stripe Shirt", 3200, "SHIRT"],
  [PHOTOS[6][0], "Black Logo Knit Sweater", 4200, "SWEATER"],
  [PHOTOS[7][0], "Green Turtleneck Sweater", 4200, "SWEATER"],
  [PHOTOS[9][0], "Black Ribbed V-Neck Top", 3800, "SWEATER"],
  [PHOTOS[10][0], "Burgundy Turtleneck Sweater", 4200, "SWEATER"],
  [PHOTOS[11][0], "Black Turtleneck Sweater", 4200, "SWEATER"],
  [PHOTOS[12][0], "Black Tailored Blazer", 5500, "JACKET"],
  [PHOTOS[13][0], "Black Button Blazer", 5500, "JACKET"],
  [PHOTOS[14][0], "Black Classic Blazer", 5500, "JACKET"],
  [PHOTOS[15][0], "Charcoal Pinstripe Blazer", 5800, "JACKET"],
  [PHOTOS[16][0], "Pink Cropped Blazer", 5200, "JACKET"],
] as const;

const imageUrl = (file: string) => `/products/owner-uploaded/${encodeURIComponent(file)}`;
const slugify = (value: string) => value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

export function AdminProductEditor({ productId }: { productId?: string }) {
  const [categories, setCategories] = useState<CategoryDetail[]>([]);
  const [product, setProduct] = useState<ProductAdmin | null>(null);
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [photo, setPhoto] = useState<string>(PHOTOS[0][0]);
  const [size, setSize] = useState("M");
  const [quantity, setQuantity] = useState("1");
  const [productType, setProductType] = useState("SHIRT");
  const [condition, setCondition] = useState<ProductCondition>("GOOD");
  const [itemCode, setItemCode] = useState("");
  const [singlePiece, setSinglePiece] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listAdminCategories().then(setCategories).catch(() => setError("Could not load product categories."));
    if (productId) getAdminProduct(productId).then((item) => {
      setProduct(item); setName(item.name); setPrice(item.regular_price);
      const primary = item.images.find((image) => image.is_primary) ?? item.images[0];
      if (primary) setPhoto(primary.image_url.split("/").pop() ?? PHOTOS[0][0]);
      setSize(item.variants[0]?.size ?? "M"); setQuantity(String(item.variants[0]?.quantity ?? 1));
      setCondition(item.condition);
      setItemCode(item.item_code);
      setSinglePiece(item.single_piece);
    }).catch(() => setError("Could not load this product."));
  }, [productId]);

  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      if (product) {
        await updateAdminProduct(product.id, {
          name, regular_price: price,
          condition,
          item_code: itemCode,
          single_piece: singlePiece,
          images: [{ image_url: imageUrl(photo), alt_text: name, sort_order: 0, is_primary: true }],
          variants: product.variants.map((variant, index) => ({
            sku: variant.sku, size: index === 0 ? size : variant.size,
            waist: variant.waist, color: variant.color, variant_name: variant.variant_name,
            price_override: variant.price_override, sale_price_override: variant.sale_price_override,
            is_active: variant.is_active, quantity: index === 0 ? Number(quantity) : variant.quantity,
            low_stock_threshold: 3,
          })),
        });
        setNotice("Product updated.");
      } else {
        const category = categories.find((row) => row.slug === "women");
        const subcategory = category?.subcategories.find((row) => row.slug === "tops") ?? category?.subcategories[0];
        if (!category) throw new Error("Add a Women category before creating these products.");
        const code = `${Date.now()}-${Math.floor(Math.random() * 10000)}`;
        const created = await createAdminProduct({
          name, slug: slugify(name), sku: `RG-W-${code}`,
          short_description: name, description: name,
          category_id: category.id, subcategory_id: subcategory?.id ?? null, brand_id: null,
          regular_price: price, sale_price: null, condition, single_piece: singlePiece, gender: "WOMEN",
          product_type: productType, color: null, fabric: null, is_featured: false, is_new_arrival: true,
          images: [{ image_url: imageUrl(photo), alt_text: name, is_primary: true }],
          variants: [{ sku: `RG-W-${code}-M`, size, quantity: Number(quantity) }],
        });
        setNotice(`Product added. Item code: ${created.item_code}`);
        setName(""); setPrice(""); setQuantity("1");
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save product."); }
    finally { setBusy(false); }
  }

  async function addAll() {
    const category = categories.find((row) => row.slug === "women");
    const subcategory = category?.subcategories.find((row) => row.slug === "tops") ?? category?.subcategories[0];
    if (!category) { setError("Add a Women category before creating these products."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const existing = await listAdminProducts({ page: 1, page_size: 100, include_inactive: true });
      const slugs = new Set(existing.items.map((row) => row.slug));
      let added = 0;
      for (const [file, title, cost, type] of ITEMS) {
        const slug = slugify(title);
        if (slugs.has(slug)) continue;
        const code = `UP-${file.replace(/[^A-Za-z0-9]/g, "").toUpperCase()}`;
        await createAdminProduct({ name: title, slug, sku: `RG-${code}`, short_description: title, description: title,
          category_id: category.id, subcategory_id: subcategory?.id ?? null, brand_id: null,
          regular_price: cost, sale_price: null, condition: "GOOD", gender: "WOMEN", product_type: type,
          color: null, fabric: null, is_featured: false, is_new_arrival: true,
          images: file === PHOTOS[7][0]
            ? [{ image_url: imageUrl(file), alt_text: title, is_primary: true }, { image_url: imageUrl(PHOTOS[8][0]), alt_text: `${title} alternate view`, sort_order: 1 }]
            : [{ image_url: imageUrl(file), alt_text: title, is_primary: true }],
          variants: [{ sku: `RG-${code}-M`, size: "M", quantity: 1 }] });
        slugs.add(slug); added++;
      }
      setNotice(`${added} products added. Suggested prices and size M / stock 1 can be edited below from the product list.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not add the uploaded products."); }
    finally { setBusy(false); }
  }

  return <AdminGate><main className="mx-auto max-w-5xl space-y-7 px-5 py-10">
    <Link href="/admin/products" className="text-sm text-ink-muted hover:text-ink">← Back to products</Link>
    <header><p className="eyebrow">Catalogue</p><h1 className="mt-2 text-3xl">{product ? "Edit product" : "Add product"}</h1>
      <p className="mt-2 text-sm text-ink-muted">Add your product photo, name, PKR price, size and stock. These can be changed later from this admin area.</p></header>
    {!productId ? <section className="border border-line bg-gold-wash p-5"><h2 className="font-semibold">Your uploaded photos</h2>
      <p className="mt-1 text-sm text-ink-muted">Add all 16 unique pieces with suggested names/prices. The second green sweater photo is an alternate view and is not duplicated as a separate item.</p>
      <Button type="button" className="mt-4" disabled={busy} onClick={() => void addAll()}>{busy ? "Adding…" : "Add all 16 products"}</Button>
    </section> : null}
    <form onSubmit={save} className="space-y-5 border border-line bg-paper p-5">
      <label className="block text-sm">Product name<input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} className="mt-1 block h-11 w-full border border-line px-3" /></label>
      <label className="block text-sm">Price (PKR)<input required type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className="mt-1 block h-11 w-full border border-line px-3" /></label>
      <label className="block text-sm">Condition grade<select value={condition} onChange={(e) => setCondition(e.target.value as ProductCondition)} className="mt-1 block h-11 w-full border border-line bg-white px-3"><option value="PREMIUM_PLUS">Premium Plus</option><option value="PREMIUM">Premium</option><option value="EXCELLENT">Excellent</option><option value="GOOD">Good</option></select></label>
      {product ? <label className="block text-sm">Item code<input required value={itemCode} onChange={(e) => setItemCode(e.target.value)} pattern="[A-Za-z0-9-]+" maxLength={32} className="mt-1 block h-11 w-full border border-line px-3 font-mono" /></label> : <p className="text-xs text-ink-muted">A unique item code will be generated automatically.</p>}
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={singlePiece} onChange={(e) => setSinglePiece(e.target.checked)} /> Single-piece item (maximum one unit in stock)</label>
      {!product ? <label className="block text-sm">Product type<select value={productType} onChange={(e) => setProductType(e.target.value)} className="mt-1 block h-11 w-full border border-line bg-white px-3"><option value="SHIRT">Shirt / blouse</option><option value="SWEATER">Sweater / knitwear</option><option value="JACKET">Jacket / blazer</option><option value="DRESS">Dress</option></select></label> : null}
      <div className="grid gap-4 sm:grid-cols-2"><label className="block text-sm">Size<input value={size} onChange={(e) => setSize(e.target.value)} className="mt-1 block h-11 w-full border border-line px-3" /></label>
        <label className="block text-sm">Stock quantity<input type="number" min="0" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="mt-1 block h-11 w-full border border-line px-3" /></label></div>
      <fieldset><legend className="mb-3 text-sm font-medium">Choose product image</legend><div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{PHOTOS.map(([file, label]) => <label key={file} className={`cursor-pointer border p-2 ${photo === file ? "border-gold-deep" : "border-line"}`}><input className="sr-only" type="radio" name="photo" checked={photo === file} onChange={() => setPhoto(file)} /><div className="relative aspect-[4/5] bg-paper-alt"><Image src={imageUrl(file)} alt={label} fill sizes="25vw" className="object-contain" /></div><span className="mt-2 block text-xs">{label}</span></label>)}</div></fieldset>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}{notice ? <p role="status" className="text-sm text-green-800">{notice}</p> : null}
      <Button disabled={busy}>{busy ? "Saving…" : product ? "Save product" : "Add product"}</Button>
    </form>
  </main></AdminGate>;
}
