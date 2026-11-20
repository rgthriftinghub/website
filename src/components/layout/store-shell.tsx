import type { ReactNode } from "react";

import { Footer } from "@/components/layout/footer";
import { Header } from "@/components/layout/header";
import { AnnouncementBar } from "@/components/layout/announcement-bar";
import { StoreProvider } from "@/components/providers/store-provider";
import { listCategories } from "@/lib/api/catalog";
import type { Category } from "@/lib/api/types";

/**
 * Storefront chrome.
 *
 * Categories are fetched once here and passed to both the header and footer, so
 * navigation reflects the real catalogue rather than a hardcoded list. If the
 * API is unreachable the chrome still renders with an empty nav rather than
 * failing the whole page.
 */
export async function StoreShell({ children }: { children: ReactNode }) {
  let categories: Category[] = [];
  try {
    categories = await listCategories();
  } catch {
    categories = [];
  }

  return (
    // The provider wraps the chrome so the header's bag and wishlist counts come
    // from the same client-side state the cart pages mutate.
    <StoreProvider>
      <div className="flex min-h-screen flex-col">
        <Header categories={categories} />
        <AnnouncementBar />
        <main className="flex-1">{children}</main>
        <Footer categories={categories} />
      </div>
    </StoreProvider>
  );
}
