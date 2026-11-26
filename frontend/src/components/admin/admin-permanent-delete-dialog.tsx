"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { permanentlyDeleteAdminProduct } from "@/lib/api/catalog";
import type { ProductAdmin } from "@/lib/api/types";

export function AdminPermanentDeleteDialog({
  product,
  onDeleted,
}: {
  product: ProductAdmin;
  onDeleted: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const blocked = product.has_past_orders;
  const confirmed = confirmation === product.item_code || confirmation === "DELETE";

  async function remove() {
    setBusy(true);
    setError("");
    try {
      await permanentlyDeleteAdminProduct(product.id);
      setOpen(false);
      onDeleted();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not permanently delete this product.");
    } finally {
      setBusy(false);
    }
  }

  return <>
    <button type="button" disabled={blocked} title={blocked ? "This product has past orders. Archive it instead." : undefined}
      onClick={() => { setConfirmation(""); setError(""); setOpen(true); }}
      className="text-xs font-semibold text-danger hover:underline disabled:cursor-not-allowed disabled:opacity-50">
      Delete permanently
    </button>
    {open ? <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="permanent-delete-title" className="w-full max-w-lg space-y-4 border border-line bg-paper p-6 shadow-xl">
        <div>
          <h2 id="permanent-delete-title" className="text-xl font-semibold text-danger">Delete permanently?</h2>
          <p className="mt-2 text-sm text-ink-muted">This cannot be undone. The product, variants, stock history, and related cart and wishlist entries will be removed. Shared image files will remain.</p>
          <p className="mt-2 text-sm">Product: <strong>{product.name}</strong> · Item code: <code>{product.item_code}</code></p>
        </div>
        {blocked ? <p role="alert" className="text-sm text-danger">This product has past orders. Archive it instead.</p> : <label className="block text-sm">Type the item code or DELETE to continue
          <input autoFocus value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-1 h-11 w-full border border-line px-3 font-mono" />
        </label>}
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" disabled={busy} onClick={() => setOpen(false)}>Cancel</Button>
          <span title={blocked ? "This product has past orders. Archive it instead." : undefined}>
            <Button type="button" disabled={blocked || !confirmed || busy} onClick={() => void remove()} className="bg-danger text-white hover:bg-danger/90">
              {busy ? "Deleting…" : "Delete permanently"}
            </Button>
          </span>
        </div>
      </section>
    </div> : null}
  </>;
}
