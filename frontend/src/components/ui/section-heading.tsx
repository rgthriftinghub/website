import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { cn } from "@/lib/utils";

/** Eyebrow + serif title + optional link, used to open every homepage section. */
export function SectionHeading({
  eyebrow,
  title,
  description,
  href,
  linkLabel = "View all",
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  href?: string;
  linkLabel?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="max-w-2xl">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2 className="mt-2 text-3xl sm:text-4xl">{title}</h2>
        {description ? <p className="mt-3 text-sm text-ink-muted">{description}</p> : null}
      </div>
      {href ? (
        <Link
          href={href}
          className="nav-link inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted hover:text-ink"
        >
          {linkLabel}
          <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      ) : null}
    </div>
  );
}
