import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * The official RG Thrifting Hub logo.
 *
 * The supplied artwork is used as-is and never recoloured, redrawn, or replaced
 * with a text substitute. `priority` is set where it appears in the header so it
 * is never the element that pops in late.
 */
// Intrinsic artwork is 1122 x 1402 — a portrait badge, so it is sized by height
// and the width follows. Sizing by width would make the logo overflow any
// fixed-height bar it sits in.
const LOGO_ASPECT = 1122 / 1402;

export function Logo({
  className,
  height = 64,
  priority = false,
}: {
  className?: string;
  height?: number;
  priority?: boolean;
}) {
  const width = Math.round(height * LOGO_ASPECT);

  return (
    <Image
      src="/brand/logo.png"
      alt="RG Thrifting Hub"
      width={width}
      height={height}
      priority={priority}
      className={cn("object-contain", className)}
      style={{ height, width }}
    />
  );
}

export function LogoLink({
  className,
  height,
  priority,
  onClick,
}: {
  className?: string;
  height?: number;
  priority?: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      href="/"
      aria-label="RG Thrifting Hub — home"
      onClick={onClick}
      className={cn("inline-flex", className)}
    >
      <Logo height={height} priority={priority} />
    </Link>
  );
}
