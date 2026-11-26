"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AdminGate } from "@/components/admin/admin-gate";
import { Button } from "@/components/ui/button";
import { MediaImage as Image } from "@/components/ui/media-image";
import { createAdminProduct, getAdminProduct, listAdminCategories, listAdminProducts, updateAdminProduct, uploadAdminProductImage } from "@/lib/api/catalog";
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
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedSubcategoryId, setSelectedSubcategoryId] = useState("");
  const [gender, setGender] = useState("WOMEN");
  const [product, setProduct] = useState<ProductAdmin | null>(null);
  const [name, setName] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [gallery, setGallery] = useState<Array<{ image_url: string; alt_text: string | null; sort_order: number; is_primary: boolean }>>([
    { image_url: imageUrl(PHOTOS[0][0]), alt_text: "Pale pink button shirt", sort_order: 0, is_primary: true },
  ]);
  type SizeRow = { size: string; quantity: string; existing?: ProductAdmin["variants"][number] };
  const [sizeRows, setSizeRows] = useState<SizeRow[]>([{ size: "M", quantity: "1" }]);
  const [newSize, setNewSize] = useState("");
  const [productType, setProductType] = useState("SHIRT");
  const [condition, setCondition] = useState<ProductCondition>("GOOD");
  const [itemCode, setItemCode] = useState("");
  const [singlePiece, setSinglePiece] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listAdminCategories().then((rows) => {
      setCategories(rows);
      const defaultCategory = rows.find((row) => row.slug === "women") ?? rows[0];
      if (defaultCategory) {
        setSelectedCategoryId(defaultCategory.id);
        const subcategories = defaultCategory.subcategories ?? [];
        setSelectedSubcategoryId(subcategories.find((row) => row.slug === "tops")?.id ?? subcategories[0]?.id ?? "");
      }
    }).catch(() => setError("Could not load product categories."));
    if (productId) getAdminProduct(productId).then((item) => {
      setProduct(item); setName(item.name); setPrice(item.regular_price);
      setShortDescription(item.short_description ?? ""); setDescription(item.description ?? "");
      setGallery(item.images.map((image, index) => ({ image_url: image.image_url, alt_text: image.alt_text, sort_order: index, is_primary: image.is_primary })));
      setSizeRows(item.variants.length
        ? item.variants.map((variant) => ({ size: variant.size ?? "", quantity: String(variant.quantity), existing: variant }))
        : [{ size: "", quantity: "1" }]);
      setCondition(item.condition);
      setItemCode(item.item_code);
      setSinglePiece(item.single_piece);
    }).catch(() => setError("Could not load this product."));
  }, [productId]);

  function addSize() {
    const value = newSize.trim();
    if (!value) return;
    if (sizeRows.some((row) => row.size.trim().toLowerCase() === value.toLowerCase())) {
      setError(`Size ${value} is already on this product.`);
      return;
    }
    setError("");
    if (singlePiece) setSinglePiece(false);
    setSizeRows((rows) => [...rows, { size: value, quantity: "1" }]);
    setNewSize("");
  }

  async function uploadImages(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const added: Array<{ image_url: string; alt_text: string; sort_order: number; is_primary: boolean }> = [];
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) throw new Error("Choose image files only.");
        const uploaded = await uploadAdminProductImage(file);
        added.push({ image_url: uploaded.image_url, alt_text: name || file.name, sort_order: gallery.length + added.length, is_primary: gallery.length === 0 && added.length === 0 });
      }
      setGallery((current) => [...current, ...added.map((image, index) => ({ ...image, sort_order: current.length + index, is_primary: current.length === 0 && index === 0 }))]);
      setNotice(`${added.length} image${added.length === 1 ? "" : "s"} uploaded. Save the product to update its gallery.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not upload images."); }
    finally { setBusy(false); }
  }

  function addPresetPhoto(file: string, label: string) {
    const url = imageUrl(file);
    setGallery((current) => current.some((image) => image.image_url === url) ? current : [...current, { image_url: url, alt_text: label, sort_order: current.length, is_primary: current.length === 0 }]);
  }

  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      if (!product && !sizeRows.some((row) => row.size.trim())) throw new Error("Add at least one size before saving.");
      if (gallery.length === 0) throw new Error("Add at least one product photo before saving.");
      if (product) {
        await updateAdminProduct(product.id, {
          name, short_description: shortDescription.trim() || null,
          description: description.trim() || null, regular_price: price,
          condition,
          item_code: itemCode,
          single_piece: singlePiece,
          images: gallery.map((image, index) => ({ ...image, alt_text: name || image.alt_text, sort_order: index, is_primary: image.is_primary })),
          variants: sizeRows.filter((row) => row.size.trim() || row.existing?.waist || row.existing?.color).map((row) => ({
            sku: row.existing?.sku ?? `RG-${product.id.slice(0, 8)}-${crypto.randomUUID().replace(/-/g, "").slice(0, 10)}`,
            size: row.size.trim() || null,
            waist: row.existing?.waist ?? null, color: row.existing?.color ?? null, variant_name: row.existing?.variant_name ?? null,
            price_override: row.existing?.price_override ?? null, sale_price_override: row.existing?.sale_price_override ?? null,
            is_active: row.existing?.is_active ?? true, quantity: Number(row.quantity),
            low_stock_threshold: 3,
          })),
        });
        setNotice("Product updated.");
      } else {
        const category = categories.find((row) => row.id === selectedCategoryId);
        const subcategory = category?.subcategories.find((row) => row.id === selectedSubcategoryId);
        if (!category) throw new Error("Choose a category. Use “Add a category” to create one first.");
        const code = `${Date.now()}-${Math.floor(Math.random() * 10000)}`;
        const created = await createAdminProduct({
          name, slug: slugify(name), sku: `RG-W-${code}`,
          short_description: shortDescription.trim() || null,
          description: description.trim() || null,
          category_id: category.id, subcategory_id: subcategory?.id ?? null, brand_id: null,
          regular_price: price, sale_price: null, condition, single_piece: singlePiece, gender,
          product_type: productType, color: null, fabric: null, is_featured: false, is_new_arrival: true,
          images: gallery.map((image, index) => ({ ...image, alt_text: name || image.alt_text, sort_order: index, is_primary: image.is_primary || (!gallery.some((item) => item.is_primary) && index === 0) })),
          variants: sizeRows.filter((row) => row.size.trim()).map((row, index) => ({
            sku: `RG-W-${code}-${index + 1}`, size: row.size.trim(), quantity: Number(row.quantity),
          })),
        });
        setNotice(`Product added. Item code: ${created.item_code}`);
        setName(""); setPrice(""); setSizeRows([{ size: "M", quantity: "1" }]);
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
      <label className="block text-sm">Short description (optional)<textarea maxLength={400} rows={2} value={shortDescription} onChange={(e) => setShortDescription(e.target.value)} placeholder="A brief summary shown with the product" className="mt-1 block w-full border border-line px-3 py-2" /><span className="mt-1 block text-xs text-stone">{shortDescription.length}/400 characters</span></label>
      <label className="block text-sm">Product description (optional)<textarea rows={5} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Details, fit, fabric, condition, or other notes" className="mt-1 block w-full border border-line px-3 py-2" /></label>
      <label className="block text-sm">Price (PKR)<input required type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className="mt-1 block h-11 w-full border border-line px-3" /></label>
      {!product ? <section className="space-y-3 border border-line bg-paper-alt p-4">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">Product category</h2><Link href="/admin/categories" className="text-sm font-semibold text-gold-deep underline">+ Add a category</Link></div>
        <label className="block text-sm">Category<select required value={selectedCategoryId} onChange={(e) => { const row = categories.find((item) => item.id === e.target.value); setSelectedCategoryId(e.target.value); setSelectedSubcategoryId(""); if (row?.slug === "men") setGender("MEN"); else if (row?.slug === "women") setGender("WOMEN"); else if (row?.slug === "kids") setGender("KIDS"); else if (row?.slug === "unisex") setGender("UNISEX"); }} className="mt-1 block h-11 w-full border border-line bg-white px-3"><option value="">Choose category</option>{categories.filter((row) => row.is_active).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        {(categories.find((row) => row.id === selectedCategoryId)?.subcategories ?? []).filter((row) => row.is_active).length ? <label className="block text-sm">Subcategory (optional)<select value={selectedSubcategoryId} onChange={(e) => setSelectedSubcategoryId(e.target.value)} className="mt-1 block h-11 w-full border border-line bg-white px-3"><option value="">No subcategory</option>{(categories.find((row) => row.id === selectedCategoryId)?.subcategories ?? []).filter((row) => row.is_active).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label> : null}
        <label className="block text-sm">Gender<select value={gender} onChange={(e) => setGender(e.target.value)} className="mt-1 block h-11 w-full border border-line bg-white px-3"><option value="MEN">Men</option><option value="WOMEN">Women</option><option value="UNISEX">Unisex</option><option value="KIDS">Kids</option></select></label>
      </section> : null}
      <label className="block text-sm">Condition grade<select value={condition} onChange={(e) => setCondition(e.target.value as ProductCondition)} className="mt-1 block h-11 w-full border border-line bg-white px-3"><option value="PREMIUM_PLUS">Premium Plus</option><option value="PREMIUM">Premium</option><option value="EXCELLENT">Excellent</option><option value="GOOD">Good</option></select></label>
      {product ? <label className="block text-sm">Item code<input required value={itemCode} onChange={(e) => setItemCode(e.target.value)} pattern="[A-Za-z0-9-]+" maxLength={32} className="mt-1 block h-11 w-full border border-line px-3 font-mono" /></label> : <p className="text-xs text-ink-muted">A unique item code will be generated automatically.</p>}
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={singlePiece} onChange={(e) => setSinglePiece(e.target.checked)} /> Single-piece item (maximum one unit in stock)</label>
      {!product ? <label className="block text-sm">Product type<select value={productType} onChange={(e) => setProductType(e.target.value)} className="mt-1 block h-11 w-full border border-line bg-white px-3"><option value="SHIRT">Shirt / blouse</option><option value="SWEATER">Sweater / knitwear</option><option value="JACKET">Jacket / blazer</option><option value="DRESS">Dress</option></select></label> : null}
      <section className="space-y-3 border border-line p-4">
        <div><h2 className="text-sm font-medium">Available sizes and stock</h2><p className="mt-1 text-xs text-ink-muted">Add each size once and set its available quantity.</p></div>
        <div className="space-y-2">{sizeRows.map((row, index) => <div key={row.existing?.id ?? `new-${index}`} className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <label className="block text-sm">Size<input value={row.size} placeholder={row.existing?.waist ? `Waist ${row.existing.waist}` : "e.g. XS, M, 32"} onChange={(event) => setSizeRows((rows) => rows.map((item, i) => i === index ? { ...item, size: event.target.value } : item))} className="mt-1 block h-11 w-full border border-line px-3" /></label>
          <label className="block text-sm">Stock quantity<input type="number" min="0" value={row.quantity} onChange={(event) => setSizeRows((rows) => rows.map((item, i) => i === index ? { ...item, quantity: event.target.value } : item))} className="mt-1 block h-11 w-full border border-line px-3" /></label>
          <button type="button" className="h-11 px-3 text-sm text-danger underline" onClick={() => setSizeRows((rows) => rows.filter((_, i) => i !== index))}>Remove</button>
        </div>)}</div>
        <div className="flex flex-wrap gap-2"><input aria-label="New size" value={newSize} onChange={(event) => setNewSize(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addSize(); } }} placeholder="Add a size" className="h-11 min-w-0 flex-1 border border-line px-3" /><Button type="button" variant="secondary" onClick={addSize}>Add Size</Button></div>
      </section>
      <section className="space-y-4 border border-line p-4">
        <div><h2 className="text-sm font-medium">Product photo gallery</h2><p className="mt-1 text-xs text-ink-muted">Upload JPG, PNG, or WebP photos (up to 8 MB each). Select a cover photo, remove unwanted photos, then save.</p></div>
        <label className="inline-flex cursor-pointer items-center border border-line-strong px-4 py-2 text-xs font-semibold uppercase tracking-wider hover:border-ink">Add photos<input type="file" accept="image/jpeg,image/png,image/webp" multiple className="sr-only" disabled={busy} onChange={(event) => { void uploadImages(event.target.files); event.currentTarget.value = ""; }} /></label>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{gallery.map((image, index) => <div key={`${image.image_url}-${index}`} className="border border-line p-2"><div className="relative aspect-[4/5] bg-paper-alt"><Image src={image.image_url} alt={image.alt_text ?? name} fill sizes="25vw" className="object-contain" /></div><div className="mt-2 flex items-center justify-between gap-2 text-xs"><label className="flex items-center gap-1"><input type="radio" name="primary-image" checked={image.is_primary} onChange={() => setGallery((current) => current.map((entry, i) => ({ ...entry, is_primary: i === index })))} /> Cover</label><button type="button" className="text-danger underline" onClick={() => setGallery((current) => current.filter((_, i) => i !== index).map((entry, i) => ({ ...entry, sort_order: i, is_primary: entry.is_primary || i === 0 })))}>Remove</button></div></div>)}</div>
        <details><summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-ink-muted">Add one of the existing sample photos</summary><div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">{PHOTOS.map(([file, label]) => <button key={file} type="button" onClick={() => addPresetPhoto(file, label)} className="border border-line p-2 text-left hover:border-gold-deep"><div className="relative aspect-[4/5] bg-paper-alt"><Image src={imageUrl(file)} alt={label} fill sizes="25vw" className="object-contain" /></div><span className="mt-2 block text-xs">Add {label}</span></button>)}</div></details>
      </section>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}{notice ? <p role="status" className="text-sm text-green-800">{notice}</p> : null}
      <Button disabled={busy}>{busy ? "Saving…" : product ? "Save product" : "Add product"}</Button>
    </form>
  </main></AdminGate>;
}
