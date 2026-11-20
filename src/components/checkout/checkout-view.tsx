"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Banknote,
  Check,
  Landmark,
  Loader2,
  Lock,
  Plus,
  Truck,
} from "lucide-react";
import { useEffect, useState } from "react";

import { AddressForm } from "@/components/checkout/address-form";
import { errorMessage, useStore } from "@/components/providers/store-provider";
import { Button, ButtonLink } from "@/components/ui/button";
import { getCheckoutConfig, listAddresses, placeOrder } from "@/lib/api/commerce";
import { listBankAccounts } from "@/lib/api/payments";
import type {
  Address,
  BankAccount,
  CheckoutConfig,
  PaymentMethod,
} from "@/lib/api/types";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAYMENT_COPY: Record<
  string,
  { label: string; blurb: string; icon: typeof Banknote }
> = {
  COD: {
    label: "Cash on Delivery",
    blurb: "Pay the courier in cash when your parcel arrives.",
    icon: Banknote,
  },
  BANK_TRANSFER: {
    label: "Bank Transfer",
    blurb: "We will share account details and confirm once your transfer clears.",
    icon: Landmark,
  },
  JAZZCASH: {
    label: "JazzCash",
    blurb: "Transfer to our JazzCash number, then share the payment screenshot on WhatsApp.",
    icon: Banknote,
  },
  EASYPAISA: {
    label: "Easypaisa",
    blurb: "Transfer to our Easypaisa number, then share the payment screenshot on WhatsApp.",
    icon: Banknote,
  },
};

/**
 * The store's own receiving accounts, fetched from the backend.
 *
 * Shown before the order is placed so the customer knows where to send the money,
 * and repeated on the order page afterwards.
 */
function BankAccountDetails({ accounts }: { accounts: BankAccount[] }) {
  if (accounts.length === 0) {
    return (
      <p className="mt-4 border-l-2 border-gold bg-gold-wash px-3 py-2.5 text-xs leading-relaxed text-ink-muted">
        Our team will share account details with you after you place the order.
      </p>
    );
  }

  return (
    <div className="mt-4 border border-line bg-paper-alt p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink">
        Transfer to
      </p>
      <ul className="mt-3 space-y-3">
        {accounts.map((account) => (
          <li key={account.id} className="text-sm">
            <p className="font-medium text-ink">{account.bank_name}</p>
            <p className="text-ink-muted">{account.account_title}</p>
            <p className="font-mono text-xs text-ink">{account.account_number}</p>
            {account.iban ? (
              <p className="font-mono text-xs text-ink-muted">IBAN {account.iban}</p>
            ) : null}
            {account.instructions ? (
              <p className="mt-1 text-xs leading-relaxed text-stone">
                {account.instructions}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-line pt-3 text-xs text-ink-muted">
        After ordering, submit your transfer reference on the order page so we can
        match it. We verify every transfer before confirming.
      </p>
    </div>
  );
}

function Section({
  step,
  title,
  children,
}: {
  step: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-line py-7 first:pt-0">
      <div className="flex items-center gap-3">
        <span className="grid size-6 shrink-0 place-items-center rounded-full bg-ink text-[11px] font-semibold text-paper">
          {step}
        </span>
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">{title}</h2>
      </div>
      <div className="mt-5 pl-9">{children}</div>
    </section>
  );
}

export function CheckoutView() {
  const router = useRouter();
  const { user, cart, refreshCart } = useStore();

  const [config, setConfig] = useState<CheckoutConfig | null>(null);
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(null);
  const [showAddressForm, setShowAddressForm] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("COD");
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [note, setNote] = useState("");
  const [couponCode, setCouponCode] = useState("");
  const [placing, setPlacing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getCheckoutConfig().then(setConfig).catch(() => setConfig(null));
    // Account details come from the backend so they can be corrected without a
    // redeploy, and so a wrong number is never baked into the bundle.
    void listBankAccounts()
      .then(setBankAccounts)
      .catch(() => setBankAccounts([]));
  }, []);

  useEffect(() => {
    void listAddresses()
      .then((rows) => {
        setAddresses(rows);
        // Preselect the default so a returning customer can place an order in
        // one click.
        const preferred = rows.find((row) => row.is_default) ?? rows[0];
        setSelectedAddressId(preferred?.id ?? null);
        setShowAddressForm(rows.length === 0);
      })
      .catch(() => setAddresses([]));
  }, []);

  async function handlePlaceOrder() {
    if (!selectedAddressId) {
      setError("Choose a delivery address first.");
      return;
    }
    setPlacing(true);
    setError(null);
    try {
      const order = await placeOrder({
        address_id: selectedAddressId,
        payment_method: paymentMethod,
        delivery_method: "STANDARD",
        customer_note: note.trim() || undefined,
        coupon_code: couponCode.trim().toUpperCase() || undefined,
      });
      // The bag was emptied server-side inside the same transaction.
      await refreshCart();
      router.push(`/checkout/success/${encodeURIComponent(order.order_number)}`);
    } catch (caught) {
      setError(errorMessage(caught, "We could not place your order. Please try again."));
      // Stock or availability may have changed; resync so the summary is honest.
      await refreshCart();
      setPlacing(false);
    }
  }

  if (cart === null || addresses === null) {
    return (
      <div className="grid place-items-center py-28">
        <p className="text-sm text-stone" role="status">
          Preparing checkout…
        </p>
      </div>
    );
  }

  if (cart.items.length === 0) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <h1 className="font-display text-3xl">Your bag is empty</h1>
        <p className="mt-3 text-sm text-ink-muted">
          Add something to your bag before checking out.
        </p>
        <ButtonLink href="/shop" size="lg" className="mt-8">
          Continue shopping
        </ButtonLink>
      </div>
    );
  }

  const methods = config?.payment_methods ?? ["COD", "BANK_TRANSFER"];
  const blocked = cart.has_unavailable_items;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-b border-line pb-6">
        <p className="eyebrow">Checkout</p>
        <h1 className="mt-2 text-4xl sm:text-5xl">Complete your order</h1>
      </header>

      {blocked ? (
        <p className="mt-6 flex items-start gap-2.5 border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          Some pieces in your bag are no longer available.{" "}
          <Link href="/cart" className="font-semibold underline">
            Update your bag
          </Link>{" "}
          to continue.
        </p>
      ) : null}

      <div className="mt-8 lg:grid lg:grid-cols-[1fr_23rem] lg:gap-12">
        <div>
          <Section step={1} title="Contact information">
            <p className="text-sm text-ink">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-sm text-ink-muted">{user?.email}</p>
            <p className="mt-2 text-xs text-stone">
              We will use this to confirm your order. Update it from your account page.
            </p>
          </Section>

          <Section step={2} title="Shipping address">
            {addresses.length > 0 ? (
              <div className="space-y-2.5">
                {addresses.map((address) => (
                  <label
                    key={address.id}
                    className={cn(
                      "flex cursor-pointer gap-3 border p-4 transition-colors",
                      selectedAddressId === address.id
                        ? "border-ink bg-paper-alt"
                        : "border-line hover:border-line-strong"
                    )}
                  >
                    <input
                      type="radio"
                      name="address"
                      value={address.id}
                      checked={selectedAddressId === address.id}
                      onChange={() => setSelectedAddressId(address.id)}
                      className="mt-1 accent-ink"
                    />
                    <span className="min-w-0 text-sm">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-ink">{address.full_name}</span>
                        {address.is_default ? (
                          <span className="bg-gold-wash px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] text-gold-deep">
                            Default
                          </span>
                        ) : null}
                      </span>
                      <span className="mt-1 block text-ink-muted">
                        {address.address_line_1}
                        {address.address_line_2 ? `, ${address.address_line_2}` : ""}
                        {`, ${address.city}, ${address.province}`}
                        {address.postal_code ? ` ${address.postal_code}` : ""}
                      </span>
                      <span className="mt-0.5 block text-stone">{address.phone}</span>
                    </span>
                  </label>
                ))}
              </div>
            ) : null}

            {showAddressForm ? (
              <div className={cn(addresses.length > 0 && "mt-5 border-t border-line pt-5")}>
                <AddressForm
                  isFirst={addresses.length === 0}
                  defaultName={user ? `${user.first_name} ${user.last_name}` : undefined}
                  onCancel={addresses.length > 0 ? () => setShowAddressForm(false) : undefined}
                  onCreated={(address) => {
                    setAddresses((current) => [...(current ?? []), address]);
                    setSelectedAddressId(address.id);
                    setShowAddressForm(false);
                  }}
                />
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowAddressForm(true)}
                className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
              >
                <Plus className="size-3.5" aria-hidden />
                Add a new address
              </button>
            )}
          </Section>

          <Section step={3} title="Delivery method">
            <div className="flex items-start gap-3 border border-ink bg-paper-alt p-4">
              <Truck className="mt-0.5 size-4 shrink-0 text-gold-deep" aria-hidden />
              <div className="text-sm">
                <p className="font-semibold text-ink">Standard Delivery</p>
                <p className="mt-0.5 text-ink-muted">
                  Delivered across Pakistan, typically in 3–5 working days.
                </p>
                <p className="mt-1 text-xs text-stone">
                  {Number(cart.delivery_amount) === 0
                    ? "Free on this order."
                    : `${formatPrice(cart.delivery_amount)} for this order.`}
                  {config?.free_delivery_threshold
                    ? ` Free above ${formatPrice(config.free_delivery_threshold)}.`
                    : ""}
                </p>
              </div>
            </div>
          </Section>

          <Section step={4} title="Payment method">
            <div className="space-y-2.5">
              {methods.map((method) => {
                const copy = PAYMENT_COPY[method];
                if (!copy) return null;
                const Icon = copy.icon;
                return (
                  <label
                    key={method}
                    className={cn(
                      "flex cursor-pointer gap-3 border p-4 transition-colors",
                      paymentMethod === method
                        ? "border-ink bg-paper-alt"
                        : "border-line hover:border-line-strong"
                    )}
                  >
                    <input
                      type="radio"
                      name="payment"
                      value={method}
                      checked={paymentMethod === method}
                      onChange={() => setPaymentMethod(method)}
                      className="mt-1 accent-ink"
                    />
                    <Icon className="mt-0.5 size-4 shrink-0 text-gold-deep" aria-hidden />
                    <span className="text-sm">
                      <span className="block font-semibold text-ink">{copy.label}</span>
                      <span className="mt-0.5 block text-ink-muted">{copy.blurb}</span>
                    </span>
                  </label>
                );
              })}
            </div>
            {/* Real account details, loaded from the backend. Never hardcoded —
                a wrong account number would send money to the wrong place. */}
            {paymentMethod === "BANK_TRANSFER" ? (
              <BankAccountDetails accounts={bankAccounts} />
            ) : null}

            {paymentMethod === "JAZZCASH" || paymentMethod === "EASYPAISA" ? (
              <div className="mt-4 border border-line bg-paper-alt p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink">Send payment to</p>
                <p className="mt-2 font-mono text-base text-ink">
                  {paymentMethod === "JAZZCASH" ? config?.jazzcash_number : config?.easypaisa_number}
                </p>
                <p className="mt-2 text-xs text-ink-muted">After placing your order, send the payment screenshot on WhatsApp with your order number.</p>
              </div>
            ) : null}

            <p className="mt-3 text-xs text-stone">
              Card payments are coming soon.
            </p>

            <label className="mt-6 block">
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
                Order note (optional)
              </span>
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={3}
                maxLength={1000}
                placeholder="Delivery instructions, landmark, preferred timing…"
                className="mt-1.5 w-full border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-gold"
              />
            </label>
          </Section>
        </div>

        {/* Order summary */}
        <aside className="mt-10 lg:mt-0">
          <div className="border border-line bg-surface p-6 lg:sticky lg:top-32">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Order summary
            </h2>

            <ul className="mt-5 space-y-4 border-b border-line pb-5">
              {cart.items.map((item) => (
                <li key={item.id} className="flex gap-3">
                  <div className="relative w-14 shrink-0 overflow-hidden bg-paper-alt aspect-[3/4]">
                    {item.image_url ? (
                      <Image
                        src={item.image_url}
                        alt={item.product_name}
                        fill
                        sizes="56px"
                        className="object-cover"
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1 text-xs">
                    <p className="truncate font-medium text-ink">{item.product_name}</p>
                    <p className="mt-0.5 text-stone">
                      {item.variant_label} · Qty {item.quantity}
                    </p>
                  </div>
                  <p className="shrink-0 text-xs tabular-nums text-ink">
                    {formatPrice(item.line_total)}
                  </p>
                </li>
              ))}
            </ul>

            <dl className="mt-5 space-y-2.5 text-sm">
              <label className="flex gap-2">
                <input value={couponCode} onChange={(event) => setCouponCode(event.target.value)} placeholder="Promo code" className="min-w-0 flex-1 border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-gold" maxLength={40} />
                <span className="self-center text-xs text-stone">Applied at checkout</span>
              </label>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Subtotal</dt>
                <dd className="tabular-nums text-ink">{formatPrice(cart.subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Delivery</dt>
                <dd className="tabular-nums text-ink">
                  {Number(cart.delivery_amount) === 0
                    ? "Free"
                    : formatPrice(cart.delivery_amount)}
                </dd>
              </div>
              <div className="flex justify-between text-stone">
                <dt>Discount</dt>
                <dd className="tabular-nums">—</dd>
              </div>
              <div className="flex items-baseline justify-between border-t border-line pt-3">
                <dt className="text-sm font-semibold text-ink">Total</dt>
                <dd className="font-display text-2xl text-ink">{formatPrice(cart.total)}</dd>
              </div>
            </dl>

            {error ? (
              <p
                role="alert"
                className="mt-5 border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger"
              >
                {error}
              </p>
            ) : null}

            <Button
              size="lg"
              className="mt-6 w-full"
              onClick={handlePlaceOrder}
              disabled={placing || blocked || !selectedAddressId}
            >
              {placing ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Placing order…
                </>
              ) : (
                <>
                  <Check className="size-4" aria-hidden />
                  Place order
                </>
              )}
            </Button>

            <p className="mt-4 flex items-start gap-2 text-xs leading-relaxed text-stone">
              <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Nothing is charged online. Your total is confirmed by our team before dispatch.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
