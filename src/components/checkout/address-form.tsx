"use client";

import { useState } from "react";

import { errorMessage } from "@/components/providers/store-provider";
import { Button } from "@/components/ui/button";
import { createAddress } from "@/lib/api/commerce";
import type { Address } from "@/lib/api/types";

const PROVINCES = [
  "Punjab",
  "Sindh",
  "Khyber Pakhtunkhwa",
  "Balochistan",
  "Islamabad Capital Territory",
  "Gilgit-Baltistan",
  "Azad Kashmir",
];

function Field({
  label,
  name,
  required = true,
  type = "text",
  autoComplete,
  defaultValue,
}: {
  label: string;
  name: string;
  required?: boolean;
  type?: string;
  autoComplete?: string;
  defaultValue?: string;
}) {
  return (
    <label className="block">
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
        {label}
        {required ? "" : " (optional)"}
      </span>
      <input
        name={name}
        type={type}
        required={required}
        autoComplete={autoComplete}
        defaultValue={defaultValue}
        className="mt-1.5 h-11 w-full border border-line bg-surface px-3 text-sm text-ink outline-none transition-colors focus:border-gold"
      />
    </label>
  );
}

export function AddressForm({
  onCreated,
  onCancel,
  defaultName,
  isFirst,
}: {
  onCreated: (address: Address) => void;
  onCancel?: () => void;
  defaultName?: string;
  isFirst: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);

    try {
      const address = await createAddress({
        full_name: String(form.get("full_name")),
        phone: String(form.get("phone")),
        address_line_1: String(form.get("address_line_1")),
        address_line_2: String(form.get("address_line_2") ?? "") || null,
        city: String(form.get("city")),
        province: String(form.get("province")),
        postal_code: String(form.get("postal_code") ?? "") || null,
        country: "Pakistan",
        // The first address a customer saves becomes their default.
        is_default: isFirst,
      });
      onCreated(address);
    } catch (caught) {
      setError(errorMessage(caught, "Could not save that address."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name" name="full_name" autoComplete="name" defaultValue={defaultName} />
        <Field label="Phone" name="phone" type="tel" autoComplete="tel" />
      </div>
      <Field label="Address" name="address_line_1" autoComplete="address-line1" />
      <Field
        label="Apartment, area, landmark"
        name="address_line_2"
        required={false}
        autoComplete="address-line2"
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="City" name="city" autoComplete="address-level2" />
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
            Province
          </span>
          <select
            name="province"
            required
            defaultValue="Punjab"
            className="mt-1.5 h-11 w-full border border-line bg-surface px-3 text-sm text-ink outline-none focus:border-gold"
          >
            {PROVINCES.map((province) => (
              <option key={province} value={province}>
                {province}
              </option>
            ))}
          </select>
        </label>
        <Field
          label="Postal code"
          name="postal_code"
          required={false}
          autoComplete="postal-code"
        />
      </div>
      <p className="text-xs text-stone">Currently delivering within Pakistan only.</p>

      {error ? (
        <p role="alert" className="border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex gap-2.5">
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save address"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}
