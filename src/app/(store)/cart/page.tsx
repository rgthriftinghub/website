import type { Metadata } from "next";

import { CartView } from "@/components/cart/cart-view";

export const metadata: Metadata = {
  title: "Your Bag",
  description: "Review the pieces in your RG Thrifting Hub bag before checkout.",
  robots: { index: false },
};

export default function CartPage() {
  return <CartView />;
}
