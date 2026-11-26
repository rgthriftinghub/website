import type { Metadata } from "next";

import { OrderSuccessView } from "@/components/checkout/order-success-view";
import { RequireAuth } from "@/components/providers/require-auth";

export const metadata: Metadata = {
  title: "Order confirmation",
  robots: { index: false },
};

export default async function CheckoutSuccessPage({
  params,
}: {
  params: Promise<{ orderNumber: string }>;
}) {
  const { orderNumber } = await params;

  return (
    <RequireAuth
      title="Sign in to view your order"
      description="Your order is saved to your account. Sign in to view its confirmation details."
    >
      <OrderSuccessView orderNumber={orderNumber} />
    </RequireAuth>
  );
}
