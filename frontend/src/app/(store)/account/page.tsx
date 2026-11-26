import type { Metadata } from "next";

import { AccountPanel } from "@/components/account/account-panel";

export const metadata: Metadata = {
  title: "Account",
  description: "Sign in to your RG Thrifting Hub account or create a new one.",
  robots: { index: false },
};

export default function AccountPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6 lg:py-24">
      <div className="text-center">
        <p className="eyebrow">Your account</p>
        <h1 className="mt-2 text-4xl">RG Thrifting Hub</h1>
        <p className="mt-3 text-sm text-ink-muted">
          Accounts exist so orders can be linked to you in a later phase. Nothing is charged today.
        </p>
      </div>
      <AccountPanel />
    </div>
  );
}
