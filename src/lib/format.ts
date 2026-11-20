/** Display formatting helpers. */

import type { Gender, ProductCondition, ProductType } from "@/lib/api/types";

const priceFormatter = new Intl.NumberFormat("en-PK", {
  maximumFractionDigits: 0,
  minimumFractionDigits: 0,
});

/**
 * Format a decimal price string for display.
 *
 * The value stays a string until this point so the exact decimal from the
 * database is never rounded through a float.
 */
export function formatPrice(amount: string | number): string {
  const numeric = typeof amount === "number" ? amount : Number.parseFloat(amount);
  if (Number.isNaN(numeric)) return "—";
  return `PKR ${priceFormatter.format(numeric)}`;
}

/**
 * Format an ISO timestamp for display in Pakistan Standard Time.
 *
 * Timestamps arrive from the backend as UTC; the store trades in one timezone, so
 * rendering them in PKT is what staff and customers expect to read.
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("en-PK", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Karachi",
  });
}

/** Date only, for order lists where the time adds noise. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleDateString("en-PK", {
    dateStyle: "medium",
    timeZone: "Asia/Karachi",
  });
}

const CONDITION_LABELS: Record<ProductCondition, string> = {
  PREMIUM_PLUS: "Premium Plus",
  PREMIUM: "Premium",
  EXCELLENT: "Excellent",
  GOOD: "Good",
};

const GENDER_LABELS: Record<Gender, string> = {
  MEN: "Men",
  WOMEN: "Women",
  UNISEX: "Unisex",
  KIDS: "Kids",
};

export function conditionLabel(condition: ProductCondition): string {
  return CONDITION_LABELS[condition] ?? condition;
}

export function genderLabel(gender: Gender): string {
  return GENDER_LABELS[gender] ?? gender;
}

/** Turn an enum member such as `T_SHIRT` into `T Shirt` for display. */
export function productTypeLabel(productType: ProductType | string): string {
  return productType
    .split("_")
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(" ");
}
