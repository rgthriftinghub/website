/**
 * Inline SVG charts.
 *
 * Hand-rolled rather than pulling in a charting library: these are four simple
 * shapes, a library would add ~100KB to the admin bundle, and none of them theme
 * cleanly to the brand palette without overriding most of their defaults anyway.
 *
 * All of them take pre-aggregated numbers. No chart computes a total, an average,
 * or a percentage — the backend already did.
 */

import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

const GOLD = "var(--gold)";
const INK = "var(--ink)";

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / magnitude) * magnitude;
}

/** Area + line chart for a revenue series. */
export function RevenueChart({
  points,
  height = 200,
  label = "Net sales",
}: {
  points: { bucket: string; net_sales: number; orders: number }[];
  height?: number;
  label?: string;
}) {
  if (points.length === 0) {
    return (
      <p className="grid h-40 place-items-center text-sm text-stone">
        No sales in this period.
      </p>
    );
  }

  const width = 1000;
  const padding = { top: 12, right: 8, bottom: 24, left: 8 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const max = niceMax(Math.max(...points.map((point) => point.net_sales)));

  // A single point has no span to divide by, so it is pinned to the centre.
  const stepX =
    points.length > 1 ? innerWidth / (points.length - 1) : innerWidth / 2;

  const coords = points.map((point, index) => ({
    x: padding.left + (points.length > 1 ? index * stepX : innerWidth / 2),
    y: padding.top + innerHeight - (point.net_sales / max) * innerHeight,
    point,
  }));

  const line = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");
  const area = `${padding.left},${padding.top + innerHeight} ${line} ${
    padding.left + innerWidth
  },${padding.top + innerHeight}`;

  const first = points[0]?.bucket ?? "";
  const last = points[points.length - 1]?.bucket ?? "";

  return (
    <figure className="w-full">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label={`${label} over time, ${points.length} points, peak ${formatPrice(max)}`}
        preserveAspectRatio="none"
      >
        {[0.25, 0.5, 0.75].map((ratio) => (
          <line
            key={ratio}
            x1={padding.left}
            x2={padding.left + innerWidth}
            y1={padding.top + innerHeight * ratio}
            y2={padding.top + innerHeight * ratio}
            stroke="var(--line)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        ))}

        <polygon points={area} fill={GOLD} opacity="0.12" />
        <polyline
          points={line}
          fill="none"
          stroke={GOLD}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
        />

        {/* Only mark points on a short series; 60 dots is noise. */}
        {coords.length <= 32
          ? coords.map((c) => (
              <circle key={c.point.bucket} cx={c.x} cy={c.y} r="3" fill={INK}>
                <title>{`${c.point.bucket}: ${formatPrice(c.point.net_sales)} · ${c.point.orders} orders`}</title>
              </circle>
            ))
          : null}
      </svg>
      <figcaption className="mt-1 flex justify-between text-[11px] text-stone">
        <span>{first}</span>
        <span className="text-ink-muted">peak {formatPrice(max)}</span>
        <span>{last}</span>
      </figcaption>
    </figure>
  );
}

/** Horizontal bars for a ranked breakdown (category, brand, product). */
export function RankedBars({
  rows,
  valueKey = "revenue",
  formatValue = formatPrice,
}: {
  rows: { id?: string; name: string; revenue?: number; units_sold?: number }[];
  valueKey?: "revenue" | "units_sold";
  formatValue?: (value: number) => string;
}) {
  if (rows.length === 0) {
    return <p className="py-6 text-center text-sm text-stone">No data in this period.</p>;
  }
  const max = Math.max(...rows.map((row) => Number(row[valueKey] ?? 0)), 1);

  return (
    <ul className="space-y-2.5">
      {rows.map((row, index) => {
        const value = Number(row[valueKey] ?? 0);
        const pct = (value / max) * 100;
        return (
          <li key={row.id ?? `${row.name}-${index}`}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-ink">{row.name}</span>
              <span className="shrink-0 tabular-nums text-ink-muted">
                {formatValue(value)}
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full bg-line">
              <div
                className="h-full bg-gold"
                style={{ width: `${Math.max(pct, 1.5)}%` }}
                role="presentation"
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Stacked proportional bar, for status mixes. */
export function StatusBar({
  segments,
}: {
  segments: { label: string; value: number; tone: string }[];
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  if (total === 0) {
    return <p className="py-4 text-sm text-stone">No orders in this period.</p>;
  }

  return (
    <div>
      <div
        className="flex h-2.5 w-full overflow-hidden"
        role="img"
        aria-label={segments.map((s) => `${s.label}: ${s.value}`).join(", ")}
      >
        {segments
          .filter((segment) => segment.value > 0)
          .map((segment) => (
            <div
              key={segment.label}
              className={segment.tone}
              style={{ width: `${(segment.value / total) * 100}%` }}
            >
              <title>{`${segment.label}: ${segment.value}`}</title>
            </div>
          ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs">
        {segments
          .filter((segment) => segment.value > 0)
          .map((segment) => (
            <li key={segment.label} className="flex items-center gap-1.5">
              <span className={cn("size-2 shrink-0", segment.tone)} aria-hidden />
              <span className="text-ink-muted">{segment.label}</span>
              <span className="tabular-nums font-medium text-ink">{segment.value}</span>
            </li>
          ))}
      </ul>
    </div>
  );
}

/** Compact donut, for a two- or three-way split such as new vs returning. */
export function SplitDonut({
  segments,
  centerLabel,
  centerValue,
}: {
  segments: { label: string; value: number; color: string }[];
  centerLabel: string;
  centerValue: string;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-5">
      <svg viewBox="0 0 120 120" className="size-28 shrink-0" role="img"
           aria-label={segments.map((s) => `${s.label}: ${s.value}`).join(", ")}>
        <circle cx="60" cy="60" r={radius} fill="none" stroke="var(--line)" strokeWidth="14" />
        {total > 0
          ? segments.map((segment) => {
              const length = (segment.value / total) * circumference;
              const dash = `${length} ${circumference - length}`;
              const element = (
                <circle
                  key={segment.label}
                  cx="60"
                  cy="60"
                  r={radius}
                  fill="none"
                  stroke={segment.color}
                  strokeWidth="14"
                  strokeDasharray={dash}
                  strokeDashoffset={-offset}
                  transform="rotate(-90 60 60)"
                >
                  <title>{`${segment.label}: ${segment.value}`}</title>
                </circle>
              );
              offset += length;
              return element;
            })
          : null}
        <text
          x="60" y="56" textAnchor="middle"
          className="fill-[var(--ink)] font-serif" style={{ fontSize: 18 }}
        >
          {centerValue}
        </text>
        <text
          x="60" y="72" textAnchor="middle"
          className="fill-[var(--stone)]" style={{ fontSize: 9, letterSpacing: "0.08em" }}
        >
          {centerLabel.toUpperCase()}
        </text>
      </svg>
      <ul className="space-y-1.5 text-sm">
        {segments.map((segment) => (
          <li key={segment.label} className="flex items-center gap-2">
            <span
              className="size-2.5 shrink-0 rounded-full"
              style={{ background: segment.color }}
              aria-hidden
            />
            <span className="text-ink-muted">{segment.label}</span>
            <span className="tabular-nums font-medium text-ink">{segment.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
