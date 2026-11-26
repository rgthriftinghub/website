import type { Metadata } from "next";

import { CartView } from "@/components/cart/cart-view";
import { RequireAuth } from "@/components/providers/require-auth";

export const metadata: Metadata = {
  title: "Your Bag",
  description: "Review the pieces in your RG Thrifting Hub bag before checkout.",
  robots: { index: false },
};

export default function CartPage() {
  return (
    <RequireAuth
      title="Sign in to see your bag"
      description="Your bag is saved to your account, so it is waiting for you on any device."
    >
      <CartView />
    </RequireAuth>
  );
}
