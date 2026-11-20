/**
 * Infinite image marquee.
 *
 * CSS-only: the track holds the children twice and slides exactly -50%, so the
 * second copy lands where the first began and the loop is seamless. No JS timer,
 * no scroll listener, nothing to get out of step on a slow frame.
 *
 * Runs on the compositor (`transform` only), pauses on hover and on focus within,
 * and stops entirely under `prefers-reduced-motion`.
 */

import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

export type MarqueeItem = {
  src: string;
  alt: string;
  caption?: string;
  href?: string;
};

type MarqueeProps = {
  items: MarqueeItem[];
  /** "left" scrolls right-to-left; "right" scrolls left-to-right. */
  direction?: "left" | "right";
  /** Seconds for one full pass. Longer is slower and calmer. */
  duration?: number;
  className?: string;
  priority?: boolean;
};

export function Marquee({
  items,
  direction = "left",
  duration = 60,
  className,
  priority = false,
}: MarqueeProps) {
  if (items.length === 0) return null;

  // Two copies back to back. `aria-hidden` on the second keeps the duplicate out
  // of the accessibility tree so a screen reader hears each item once.
  const sequence = [
    { items, hidden: false },
    { items, hidden: true },
  ];

  return (
    <div
      className={cn("marquee group relative overflow-hidden", className)}
      // Edge fade, so tiles dissolve at the boundary instead of being guillotined.
      style={{
        maskImage:
          "linear-gradient(to right, transparent, black 6%, black 94%, transparent)",
        WebkitMaskImage:
          "linear-gradient(to right, transparent, black 6%, black 94%, transparent)",
      }}
    >
      <div
        className={cn(
          "marquee-track flex w-max gap-3 sm:gap-4",
          direction === "right" && "marquee-track--reverse"
        )}
        style={{ animationDuration: `${duration}s` }}
      >
        {sequence.map((copy, copyIndex) =>
          copy.items.map((item, index) => (
            <MarqueeTile
              key={`${copyIndex}-${item.src}-${index}`}
              item={item}
              hidden={copy.hidden}
              priority={priority && copyIndex === 0 && index < 3}
            />
          ))
        )}
      </div>
    </div>
  );
}

function MarqueeTile({
  item,
  hidden,
  priority,
}: {
  item: MarqueeItem;
  hidden: boolean;
  priority: boolean;
}) {
  const body = (
    <>
      <Image
        src={item.src}
        alt={hidden ? "" : item.alt}
        fill
        // Fixed tile widths, so the browser never downloads a 1000px file for a
        // 200px tile.
        sizes="(min-width: 1024px) 260px, (min-width: 640px) 220px, 170px"
        priority={priority}
        className="object-cover transition-transform duration-700 ease-out group-hover/tile:scale-[1.04]"
      />
      {item.caption ? (
        <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink/80 to-transparent px-3 pb-2.5 pt-8 text-[11px] font-medium uppercase tracking-[0.14em] text-paper">
          {item.caption}
        </span>
      ) : null}
    </>
  );

  const shell =
    "group/tile relative block aspect-[4/5] w-[170px] shrink-0 overflow-hidden bg-paper-alt sm:w-[220px] lg:w-[260px]";

  if (item.href && !hidden) {
    return (
      <Link href={item.href} className={shell}>
        {body}
      </Link>
    );
  }

  return (
    <div className={shell} aria-hidden={hidden || undefined}>
      {body}
    </div>
  );
}
