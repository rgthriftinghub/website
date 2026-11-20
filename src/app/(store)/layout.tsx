import type { ReactNode } from "react";

import { StoreShell } from "@/components/layout/store-shell";

/**
 * Storefront pages render per request.
 *
 * Without this they would be prerendered during `docker build`, when the API is
 * not running — baking an empty catalogue into the image. Stock levels also
 * change, so a build-time snapshot would be wrong even if the API were up.
 * Individual fetches still use the data cache, so pages stay fast.
 */
export const dynamic = "force-dynamic";

/** Route group wrapping every customer-facing page in the store chrome. */
export default function StoreLayout({ children }: { children: ReactNode }) {
  return <StoreShell>{children}</StoreShell>;
}
