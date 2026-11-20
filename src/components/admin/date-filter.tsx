"use client";

/**
 * Shared date-range control for every analytics screen.
 *
 * Only ever reports *which* range is selected — the backend resolves it into real
 * boundaries in the business timezone, so "today" means today in Karachi rather
 * than in the viewer's browser timezone.
 */

import { useState } from "react";

import { cn } from "@/lib/utils";
import type { DatePreset, DateRangeQuery } from "@/lib/api/types";

const PRESETS: { value: DatePreset; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "last_7_days", label: "7 days" },
  { value: "last_30_days", label: "30 days" },
  { value: "this_month", label: "This month" },
  { value: "previous_month", label: "Last month" },
  { value: "this_year", label: "This year" },
  { value: "all_time", label: "All time" },
];

export function DateFilter({
  value,
  onChange,
  rangeLabel,
}: {
  value: DateRangeQuery;
  onChange: (next: DateRangeQuery) => void;
  rangeLabel?: string;
}) {
  const [custom, setCustom] = useState(Boolean(value.date_from || value.date_to));
  const activePreset = value.date_from || value.date_to ? null : value.preset ?? "last_30_days";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1 border border-line bg-surface p-1">
        {PRESETS.map((preset) => (
          <button
            key={preset.value}
            type="button"
            onClick={() => {
              setCustom(false);
              onChange({ preset: preset.value });
            }}
            className={cn(
              "px-2.5 py-1.5 text-xs font-medium transition-colors",
              activePreset === preset.value
                ? "bg-ink text-paper"
                : "text-ink-muted hover:bg-paper-alt hover:text-ink"
            )}
          >
            {preset.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setCustom((open) => !open)}
          className={cn(
            "px-2.5 py-1.5 text-xs font-medium transition-colors",
            custom ? "bg-ink text-paper" : "text-ink-muted hover:bg-paper-alt hover:text-ink"
          )}
        >
          Custom
        </button>
      </div>

      {custom ? (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={value.date_from ?? ""}
            onChange={(event) =>
              onChange({ ...value, preset: undefined, date_from: event.target.value })
            }
            aria-label="From date"
            className="border border-line bg-surface px-2 py-1.5 text-xs text-ink outline-none focus:border-gold"
          />
          <span className="text-xs text-stone">to</span>
          <input
            type="date"
            value={value.date_to ?? ""}
            onChange={(event) =>
              onChange({ ...value, preset: undefined, date_to: event.target.value })
            }
            aria-label="To date"
            className="border border-line bg-surface px-2 py-1.5 text-xs text-ink outline-none focus:border-gold"
          />
        </div>
      ) : null}

      {rangeLabel ? (
        <span className="text-xs text-stone">{rangeLabel}</span>
      ) : null}
    </div>
  );
}

/** Small KPI tile used across the dashboard and analytics pages. */
export function KpiTile({
  label,
  value,
  hint,
  change,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  /** Period-over-period percentage, computed by the backend. */
  change?: number | null;
  tone?: "default" | "warning" | "critical" | "good";
}) {
  const toneClass = {
    default: "",
    good: "text-success",
    warning: "text-gold-deep",
    critical: "text-danger",
  }[tone];

  return (
    <div className="bg-surface px-4 py-3.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone">
        {label}
      </p>
      <p className={cn("mt-1.5 font-serif text-2xl leading-none text-ink", toneClass)}>
        {value}
      </p>
      <div className="mt-1.5 flex items-baseline gap-2">
        {hint ? <span className="text-[11px] text-stone">{hint}</span> : null}
        {change !== null && change !== undefined ? (
          <span
            className={cn(
              "text-[11px] font-medium tabular-nums",
              change > 0 ? "text-success" : change < 0 ? "text-danger" : "text-stone"
            )}
          >
            {change > 0 ? "▲" : change < 0 ? "▼" : "—"} {Math.abs(change)}%
          </span>
        ) : null}
      </div>
    </div>
  );
}
