"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { Suspense, useState } from "react";

import { cn } from "@/lib/utils";

interface SearchFieldProps {
  className?: string;
  autoFocus?: boolean;
  onSubmitted?: () => void;
}

function SearchFieldInner({ className, autoFocus = false, onSubmitted }: SearchFieldProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlTerm = searchParams.get("search") ?? "";

  const [term, setTerm] = useState(urlTerm);
  const [syncedTerm, setSyncedTerm] = useState(urlTerm);

  // Adjust state during render rather than in an effect, which is React's
  // recommended way to resync a controlled input when the URL it mirrors
  // changes. An effect here would cause an extra render pass on every
  // navigation.
  if (urlTerm !== syncedTerm) {
    setSyncedTerm(urlTerm);
    setTerm(urlTerm);
  }

  return (
    <form
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        const trimmed = term.trim();
        router.push(trimmed ? `/shop?search=${encodeURIComponent(trimmed)}` : "/shop");
        onSubmitted?.();
      }}
      className={cn("relative", className)}
    >
      <label htmlFor="site-search" className="sr-only">
        Search products
      </label>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-stone"
        aria-hidden
      />
      <input
        id="site-search"
        type="search"
        value={term}
        autoFocus={autoFocus}
        onChange={(event) => setTerm(event.target.value)}
        placeholder="Search for jeans, jackets, brands…"
        className="h-11 w-full border border-line bg-paper pl-9 pr-3 text-sm text-ink outline-none transition-colors placeholder:text-stone focus:border-gold"
      />
    </form>
  );
}

/**
 * Search box that navigates to /shop with a `search` query parameter.
 *
 * The Suspense boundary is required because `useSearchParams` opts a component
 * out of static prerendering; keeping it here means every call site is safe
 * without repeating the boundary. The fallback matches the input height exactly
 * so the header does not shift.
 */
export function SearchField(props: SearchFieldProps) {
  return (
    <Suspense
      fallback={<div className={cn("h-11 border border-line bg-paper", props.className)} />}
    >
      <SearchFieldInner {...props} />
    </Suspense>
  );
}
