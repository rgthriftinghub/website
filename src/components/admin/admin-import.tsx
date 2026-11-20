"use client";

/**
 * Product import: upload → preview → confirm.
 *
 * The upload step writes nothing to the catalogue. What this screen shows is the
 * server's validation verdict per row; only the explicit confirm applies it.
 */

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  cancelImport,
  commitImport,
  importErrorReportUrl,
  importTemplateUrl,
  uploadImport,
} from "@/lib/api/admin";
import { cn } from "@/lib/utils";
import type { ImportBatch } from "@/lib/api/types";

export function AdminImport() {
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      setBatch(await uploadImport(file));
    } catch (cause) {
      setBatch(null);
      setError(cause instanceof Error ? cause.message : "Could not read that file.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function run(action: () => Promise<ImportBatch | { detail: string }>) {
    setBusy(true);
    setError(null);
    try {
      const result = await action();
      if ("rows" in result) setBatch(result);
      else setBatch(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That action failed.");
    } finally {
      setBusy(false);
    }
  }

  const committed = batch?.status === "COMMITTED";

  return (
    <div className="space-y-6">
      <section className="border border-line bg-surface p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-xl">
            <h2 className="font-serif text-lg text-ink">Upload a product file</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-muted">
              CSV or Excel. Nothing is imported until you review the preview and
              confirm. Existing SKUs have their price and stock updated; new SKUs
              create a product.
            </p>
          </div>
          <a
            href={importTemplateUrl()}
            className="inline-flex items-center border border-line-strong px-3.5 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink transition-colors hover:border-ink"
          >
            Download template
          </a>
        </div>

        <label className="mt-5 block cursor-pointer border border-dashed border-line-strong bg-paper-alt px-4 py-8 text-center transition-colors hover:border-gold">
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xlsm"
            className="sr-only"
            disabled={busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void handleFile(file);
            }}
          />
          <span className="text-sm font-medium text-ink">
            {busy ? "Reading file…" : "Choose a CSV or Excel file"}
          </span>
          <span className="mt-1 block text-xs text-stone">
            Up to 5MB and 2,000 rows per file
          </span>
        </label>

        {error ? (
          <p role="alert" className="mt-4 border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        ) : null}
      </section>

      {batch ? (
        <section className="border border-line bg-surface">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
            <div>
              <h2 className="font-serif text-lg text-ink">{batch.filename}</h2>
              <p className="text-xs text-stone">Status: {batch.status}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {batch.error_rows > 0 || batch.warning_rows > 0 ? (
                <a
                  href={importErrorReportUrl(batch.id)}
                  className="inline-flex items-center border border-line-strong px-3.5 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink transition-colors hover:border-ink"
                >
                  Error report
                </a>
              ) : null}
              {!committed ? (
                <>
                  <Button
                    disabled={busy || batch.valid_rows === 0}
                    onClick={() => run(() => commitImport(batch.id))}
                  >
                    {busy ? "Importing…" : `Import ${batch.valid_rows} rows`}
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={busy}
                    onClick={() => run(() => cancelImport(batch.id))}
                  >
                    Discard
                  </Button>
                </>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-4">
            {[
              { label: "Rows", value: batch.total_rows, tone: "" },
              { label: "Valid", value: batch.valid_rows, tone: "text-success" },
              { label: "Warnings", value: batch.warning_rows, tone: "text-gold-deep" },
              { label: "Errors", value: batch.error_rows, tone: "text-danger" },
            ].map((tile) => (
              <div key={tile.label} className="bg-surface px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone">
                  {tile.label}
                </p>
                <p className={cn("mt-1 font-serif text-2xl text-ink", tile.tone)}>
                  {tile.value}
                </p>
              </div>
            ))}
          </div>

          {committed ? (
            <p className="border-t border-line bg-success/8 px-5 py-3 text-sm text-success">
              Imported: {batch.created_count} created, {batch.updated_count} updated
              {batch.error_rows > 0 ? `, ${batch.error_rows} skipped` : ""}.
            </p>
          ) : null}

          {batch.error_summary ? (
            <p className="border-t border-line px-5 py-3 text-sm text-danger">
              {batch.error_summary}
            </p>
          ) : null}

          <div className="max-h-[28rem] overflow-auto border-t border-line">
            <table className="w-full min-w-[48rem] text-sm">
              <thead className="sticky top-0 bg-paper-alt">
                <tr className="text-left text-[11px] uppercase tracking-[0.12em] text-stone">
                  <th className="px-4 py-2.5 font-medium">Row</th>
                  <th className="px-4 py-2.5 font-medium">SKU</th>
                  <th className="px-4 py-2.5 font-medium">Product</th>
                  <th className="px-4 py-2.5 font-medium">Action</th>
                  <th className="px-4 py-2.5 font-medium">Messages</th>
                </tr>
              </thead>
              <tbody>
                {batch.rows.map((row) => {
                  const hasError = row.errors.length > 0;
                  return (
                    <tr
                      key={row.row_number}
                      className={cn(
                        "border-b border-line/60",
                        hasError ? "bg-danger/5" : row.warnings.length ? "bg-gold-wash/40" : ""
                      )}
                    >
                      <td className="px-4 py-2.5 tabular-nums text-stone">{row.row_number}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-ink">
                        {row.data.sku ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 text-ink">{row.data.name ?? "—"}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={cn(
                            "text-[11px] font-semibold uppercase tracking-[0.1em]",
                            hasError
                              ? "text-danger"
                              : row.action === "update"
                                ? "text-gold-deep"
                                : "text-success"
                          )}
                        >
                          {hasError ? "Skip" : row.action}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-ink-muted">
                        {[...row.errors, ...row.warnings].join("; ") || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
