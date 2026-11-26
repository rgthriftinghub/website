import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Tone = "sale" | "new" | "neutral" | "soldout" | "low" | "outline";

const TONES: Record<Tone, string> = {
  sale: "bg-ink text-paper",
  new: "bg-gold text-ink",
  neutral: "bg-paper-alt text-ink-muted",
  soldout: "bg-line-strong text-ink-muted",
  low: "bg-gold-wash text-gold-deep",
  outline: "border border-line-strong text-ink-muted",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
        TONES[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
