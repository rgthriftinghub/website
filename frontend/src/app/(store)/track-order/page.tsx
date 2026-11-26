import type { Metadata } from "next";

import { SectionHeading } from "@/components/ui/section-heading";
import { TrackOrderView } from "@/components/orders/track-order-view";

export const metadata: Metadata = {
  title: "Track your order · RG Thrifting Hub",
  description:
    "Follow your RG Thrifting Hub parcel. Enter your order number and the email or phone you ordered with.",
  // A lookup form has nothing to index, and indexing it invites crawlers to
  // probe order numbers.
  robots: { index: false, follow: true },
};

export default function TrackOrderPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
      <SectionHeading
        eyebrow="Delivery"
        title="Track your order"
        description="Enter your order number along with the email address or phone number you used at checkout."
      />
      <div className="mt-10">
        <TrackOrderView />
      </div>
    </div>
  );
}
