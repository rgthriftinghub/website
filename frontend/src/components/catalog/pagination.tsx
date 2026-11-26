import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

/** Compact page list: first, last, current and its neighbours, with gaps elided. */
function pageNumbers(current: number, total: number): (number | "gap")[] {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1);

  const pages = new Set<number>([1, total, current]);
  if (current - 1 > 1) pages.add(current - 1);
  if (current + 1 < total) pages.add(current + 1);

  const sorted = [...pages].sort((a, b) => a - b);
  const result: (number | "gap")[] = [];
  let previous = 0;
  for (const page of sorted) {
    if (previous && page - previous > 1) result.push("gap");
    result.push(page);
    previous = page;
  }
  return result;
}

export function Pagination({
  page,
  totalPages,
  buildHref,
  className,
}: {
  page: number;
  totalPages: number;
  /** Preserves the current filters when producing each page link. */
  buildHref: (page: number) => string;
  className?: string;
}) {
  if (totalPages <= 1) return null;

  return (
    <nav aria-label="Pagination" className={cn("flex items-center justify-center gap-1.5", className)}>
      {page > 1 ? (
        <Link
          href={buildHref(page - 1)}
          aria-label="Previous page"
          className="grid size-10 place-items-center border border-line-strong text-ink transition-colors hover:border-ink"
        >
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
      ) : (
        <span
          aria-hidden
          className="grid size-10 place-items-center border border-line text-line-strong"
        >
          <ChevronLeft className="size-4" />
        </span>
      )}

      {pageNumbers(page, totalPages).map((entry, index) =>
        entry === "gap" ? (
          <span key={`gap-${index}`} className="px-1 text-stone">
            …
          </span>
        ) : (
          <Link
            key={entry}
            href={buildHref(entry)}
            aria-current={entry === page ? "page" : undefined}
            className={cn(
              "grid size-10 place-items-center border text-xs transition-colors",
              entry === page
                ? "border-ink bg-ink text-paper"
                : "border-line-strong text-ink-muted hover:border-ink hover:text-ink"
            )}
          >
            {entry}
          </Link>
        )
      )}

      {page < totalPages ? (
        <Link
          href={buildHref(page + 1)}
          aria-label="Next page"
          className="grid size-10 place-items-center border border-line-strong text-ink transition-colors hover:border-ink"
        >
          <ChevronRight className="size-4" aria-hidden />
        </Link>
      ) : (
        <span
          aria-hidden
          className="grid size-10 place-items-center border border-line text-line-strong"
        >
          <ChevronRight className="size-4" />
        </span>
      )}
    </nav>
  );
}
