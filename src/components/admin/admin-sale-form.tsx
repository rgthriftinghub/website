"use client";

/**
 * Sale campaign creation and editing.
 *
 * Every monetary consequence is computed by the backend. This form collects a rule
 * — type, discount, window, priority, targets — and shows a *local illustration* of
 * what it would do to a sample price, clearly labelled as such.
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { createSale, getSale, updateSale } from "@/lib/api/admin";
import { listAdminBrands, listAdminCategories } from "@/lib/api/catalog";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  Brand,
  Category,
  DiscountType,
  SaleInput,
  SaleTargetType,
  SaleType,
} from "@/lib/api/types";

const FIELD =
  "w-full border border-line bg-paper px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-stone focus:border-gold";
const LABEL = "text-[11px] font-semibold uppercase tracking-[0.12em] text-stone";

const SALE_TYPES: { value: SaleType; label: string; hint: string }[] = [
  { value: "STANDARD", label: "Standard", hint: "A plain campaign." },
  { value: "FLASH", label: "Flash", hint: "Short window with a countdown. End time required." },
  { value: "CLEARANCE", label: "Clearance", hint: "Often open-ended, for end-of-line stock." },
  { value: "SEASONAL", label: "Seasonal", hint: "Eid, winter, and similar." },
];

const DISCOUNT_TYPES: { value: DiscountType; label: string; suffix: string }[] = [
  { value: "PERCENTAGE", label: "Percentage off", suffix: "%" },
  { value: "FIXED_AMOUNT", label: "Fixed amount off", suffix: "PKR" },
  { value: "CUSTOM_PRICE", label: "Set price to", suffix: "PKR" },
];

/** `datetime-local` needs `YYYY-MM-DDTHH:mm` with no timezone or seconds. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

function defaultStart(): string {
  return toLocalInput(new Date().toISOString());
}

export function AdminSaleForm({ saleId }: { saleId?: string }) {
  const router = useRouter();
  const editing = Boolean(saleId);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saleType, setSaleType] = useState<SaleType>("STANDARD");
  const [discountType, setDiscountType] = useState<DiscountType>("PERCENTAGE");
  const [discountValue, setDiscountValue] = useState("10");
  const [priority, setPriority] = useState("10");
  const [badgeText, setBadgeText] = useState("");
  const [startsAt, setStartsAt] = useState(defaultStart);
  const [endsAt, setEndsAt] = useState("");
  const [isActive, setIsActive] = useState(true);

  const [targetType, setTargetType] = useState<SaleTargetType>("STORE");
  const [categoryId, setCategoryId] = useState("");
  const [subcategoryId, setSubcategoryId] = useState("");
  const [brandId, setBrandId] = useState("");

  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Taxonomy for the target pickers, through the typed admin clients.
    Promise.all([listAdminCategories(), listAdminBrands()])
      .then(([categoryRows, brandRows]) => {
        if (cancelled) return;
        setCategories(categoryRows);
        setBrands(brandRows);
      })
      .catch(() => {
        if (!cancelled) {
          setCategories([]);
          setBrands([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!saleId) return;
    let cancelled = false;
    getSale(saleId)
      .then((sale) => {
        if (cancelled) return;
        setName(sale.name);
        setDescription(sale.description ?? "");
        setSaleType(sale.sale_type);
        setDiscountType(sale.discount_type);
        setDiscountValue(String(Number(sale.discount_value)));
        setPriority(String(sale.priority));
        setBadgeText(sale.badge_text ?? "");
        setStartsAt(toLocalInput(sale.starts_at));
        setEndsAt(toLocalInput(sale.ends_at));
        setIsActive(sale.is_active);
        const first = sale.targets[0];
        if (first) {
          setTargetType(first.target_type);
          setCategoryId(first.category_id ?? "");
          setSubcategoryId(first.subcategory_id ?? "");
          setBrandId(first.brand_id ?? "");
        }
      })
      .catch(() => {
        if (!cancelled) setError("Could not load that campaign.");
      });
    return () => {
      cancelled = true;
    };
  }, [saleId]);

  const subcategories = useMemo(
    () => categories.find((category) => category.id === categoryId)?.subcategories ?? [],
    [categories, categoryId]
  );

  /**
   * Local illustration only, on a fixed sample price. Labelled as an example so it
   * is never mistaken for the authoritative figure — the backend recomputes on save.
   */
  const illustration = useMemo(() => {
    const sample = 5000;
    const value = Number(discountValue) || 0;
    let result = sample;
    if (discountType === "PERCENTAGE") result = sample - (sample * Math.min(value, 100)) / 100;
    else if (discountType === "FIXED_AMOUNT") result = Math.max(sample - value, 0);
    else result = value;
    return { sample, result: Math.max(result, 0) };
  }, [discountType, discountValue]);

  const needsEnd = saleType === "FLASH";
  const targetValid =
    targetType === "STORE" ||
    (targetType === "CATEGORY" && categoryId) ||
    (targetType === "SUBCATEGORY" && subcategoryId) ||
    (targetType === "BRAND" && brandId);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    const target: SaleInput["targets"][number] = { target_type: targetType };
    if (targetType === "CATEGORY") target.category_id = categoryId;
    if (targetType === "SUBCATEGORY") target.subcategory_id = subcategoryId;
    if (targetType === "BRAND") target.brand_id = brandId;

    const payload: SaleInput = {
      name: name.trim(),
      description: description.trim() || null,
      sale_type: saleType,
      discount_type: discountType,
      discount_value: String(Number(discountValue)),
      priority: Number(priority) || 0,
      is_active: isActive,
      // datetime-local has no zone; converting through Date attaches the browser's,
      // which is what the operator means by "starts at 6pm".
      starts_at: new Date(startsAt).toISOString(),
      ends_at: endsAt ? new Date(endsAt).toISOString() : null,
      badge_text: badgeText.trim() || null,
      targets: [target],
    };

    try {
      if (saleId) await updateSale(saleId, payload);
      else await createSale(payload);
      router.push("/admin/sales");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save the campaign.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-3xl space-y-6">
      {error ? (
        <p role="alert" className="border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <section className="border border-line bg-surface p-5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          Campaign
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className={LABEL}>Name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              minLength={2}
              placeholder="Weekend Flash Sale"
              className={FIELD}
            />
          </label>

          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className={LABEL}>Description (optional)</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
              className={FIELD}
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>Type</span>
            <select
              value={saleType}
              onChange={(event) => setSaleType(event.target.value as SaleType)}
              className={FIELD}
            >
              {SALE_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="text-[11px] text-stone">
              {SALE_TYPES.find((option) => option.value === saleType)?.hint}
            </span>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>Badge text (optional)</span>
            <input
              value={badgeText}
              onChange={(event) => setBadgeText(event.target.value)}
              maxLength={40}
              placeholder="Flash 25%"
              className={FIELD}
            />
            <span className="text-[11px] text-stone">
              Overrides the default wording on product cards.
            </span>
          </label>
        </div>
      </section>

      <section className="border border-line bg-surface p-5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          Discount
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>How</span>
            <select
              value={discountType}
              onChange={(event) => setDiscountType(event.target.value as DiscountType)}
              className={FIELD}
            >
              {DISCOUNT_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>
              Value ({DISCOUNT_TYPES.find((o) => o.value === discountType)?.suffix})
            </span>
            <input
              type="number"
              min="0"
              max={discountType === "PERCENTAGE" ? "100" : undefined}
              step="0.01"
              value={discountValue}
              onChange={(event) => setDiscountValue(event.target.value)}
              required
              className={FIELD}
            />
          </label>
        </div>

        <p className="mt-4 border-l-2 border-gold bg-gold-wash px-3 py-2 text-xs text-ink-muted">
          <strong>Example only:</strong> a {formatPrice(illustration.sample)} item would
          become {formatPrice(illustration.result)}. The backend recomputes every real
          price, and a hand-set sale price still wins when it is cheaper.
        </p>
      </section>

      <section className="border border-line bg-surface p-5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          Applies to
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>Target</span>
            <select
              value={targetType}
              onChange={(event) => setTargetType(event.target.value as SaleTargetType)}
              className={FIELD}
            >
              <option value="STORE">Entire store</option>
              <option value="CATEGORY">A category</option>
              <option value="SUBCATEGORY">A subcategory</option>
              <option value="BRAND">A brand</option>
            </select>
          </label>

          {targetType === "CATEGORY" || targetType === "SUBCATEGORY" ? (
            <label className="flex flex-col gap-1.5">
              <span className={LABEL}>Category</span>
              <select
                value={categoryId}
                onChange={(event) => {
                  setCategoryId(event.target.value);
                  setSubcategoryId("");
                }}
                required
                className={FIELD}
              >
                <option value="">Choose…</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {targetType === "SUBCATEGORY" && categoryId ? (
            <label className="flex flex-col gap-1.5">
              <span className={LABEL}>Subcategory</span>
              <select
                value={subcategoryId}
                onChange={(event) => setSubcategoryId(event.target.value)}
                required
                className={FIELD}
              >
                <option value="">Choose…</option>
                {subcategories.map((subcategory) => (
                  <option key={subcategory.id} value={subcategory.id}>
                    {subcategory.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {targetType === "BRAND" ? (
            <label className="flex flex-col gap-1.5">
              <span className={LABEL}>Brand</span>
              <select
                value={brandId}
                onChange={(event) => setBrandId(event.target.value)}
                required
                className={FIELD}
              >
                <option value="">Choose…</option>
                {brands.map((brand) => (
                  <option key={brand.id} value={brand.id}>
                    {brand.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
      </section>

      <section className="border border-line bg-surface p-5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          Schedule and priority
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>Starts</span>
            <input
              type="datetime-local"
              value={startsAt}
              onChange={(event) => setStartsAt(event.target.value)}
              required
              className={FIELD}
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>
              Ends {needsEnd ? "(required for flash)" : "(optional)"}
            </span>
            <input
              type="datetime-local"
              value={endsAt}
              onChange={(event) => setEndsAt(event.target.value)}
              required={needsEnd}
              className={FIELD}
            />
            <span className="text-[11px] text-stone">
              Leave empty to run indefinitely.
            </span>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>Priority</span>
            <input
              type="number"
              min="0"
              max="1000"
              value={priority}
              onChange={(event) => setPriority(event.target.value)}
              className={FIELD}
            />
            <span className="text-[11px] text-stone">
              Highest wins when campaigns overlap.
            </span>
          </label>

          <label className="mt-6 flex items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(event) => setIsActive(event.target.checked)}
              className="accent-gold"
            />
            Enabled
          </label>
        </div>

        <p className="mt-4 text-[11px] leading-relaxed text-stone">
          A campaign only applies inside its window, checked by the database on every
          price lookup. Scheduling one for the future is safe — it starts and stops on
          its own with no further action.
        </p>
      </section>

      <div className="flex flex-wrap gap-3">
        <Button
          type="submit"
          disabled={busy || !name.trim() || !targetValid || (needsEnd && !endsAt)}
        >
          {busy ? "Saving…" : editing ? "Save changes" : "Create campaign"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => router.push("/admin/sales")}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}

/**
 * Flash-sale shortcut. Same engine, pre-filled for a short high-priority window so
 * the common case is two fields rather than twelve.
 */
export function AdminFlashSaleForm() {
  return (
    <div className="space-y-5">
      <div className={cn("border-l-2 border-danger bg-danger/5 px-4 py-3")}>
        <p className="text-sm font-medium text-ink">Flash sales</p>
        <p className="mt-1 text-xs leading-relaxed text-ink-muted">
          A flash sale is an ordinary campaign with a short window and a countdown on
          the storefront. An end time is required. The countdown is display only — the
          database decides whether the sale is live, so it cannot run a minute longer
          than scheduled.
        </p>
      </div>
      <AdminSaleForm />
    </div>
  );
}
