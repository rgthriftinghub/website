import type { Metadata } from "next";

import { CheckoutView } from "@/components/checkout/checkout-view";
import { RequireAuth } from "@/components/providers/require-auth";

export const metadata: Metadata = {
  title: "Checkout",
  description: "Complete your RG Thrifting Hub order.",
  robots: { index: false },
};

export default function CheckoutPage() {
  return (
    // Checkout requires an account; unauthenticated visitors are sent to sign in
    // and returned here afterwards.
    <RequireAuth
      title="Sign in to check out"
      description="An account lets us confirm your order and keep your delivery details for next time."
    >
      <CheckoutView />
    </RequireAuth>
  );
}
