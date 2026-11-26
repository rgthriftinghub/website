import type { Metadata } from "next";

import { WishlistView } from "@/components/catalog/wishlist-view";

export const metadata: Metadata = {
  title: "Wishlist",
  description: "Pieces you have saved at RG Thrifting Hub.",
  robots: { index: false },
};

export default function WishlistPage() {
  return (
    <WishlistView />
  );
}
