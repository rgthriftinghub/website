"use client";

import Link from "next/link";
import { MapPin, Plus, Star, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { AddressForm } from "@/components/checkout/address-form";
import { errorMessage } from "@/components/providers/store-provider";
import { Button } from "@/components/ui/button";
import { deleteAddress, listAddresses, updateAddress } from "@/lib/api/commerce";
import type { Address } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function AddressBookView() {
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAddresses()
      .then(setAddresses)
      .catch(() => setError("Could not load your addresses."));
  }, []);

  async function reload() {
    setAddresses(await listAddresses().catch(() => []));
  }

  async function makeDefault(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await updateAddress(id, { is_default: true });
      await reload();
    } catch (caught) {
      setError(errorMessage(caught, "Could not update that address."));
    } finally {
      setBusyId(null);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this address? Past orders keep their own copy.")) return;
    setBusyId(id);
    setError(null);
    try {
      await deleteAddress(id);
      await reload();
    } catch (caught) {
      setError(errorMessage(caught, "Could not delete that address."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-b border-line pb-6">
        <Link
          href="/account"
          className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-ink"
        >
          ← Account
        </Link>
        <p className="eyebrow mt-4">Delivery</p>
        <h1 className="mt-2 text-4xl sm:text-5xl">Your addresses</h1>
        <p className="mt-3 text-sm text-ink-muted">
          Editing an address here never changes a past order — each order keeps its own copy of
          where it was sent.
        </p>
      </header>

      {error ? (
        <p role="alert" className="mt-6 border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      {addresses === null ? (
        <p className="mt-8 text-sm text-stone" role="status">
          Loading…
        </p>
      ) : (
        <>
          {addresses.length === 0 && !showForm ? (
            <div className="mt-10 border border-line bg-surface p-10 text-center">
              <span className="mx-auto grid size-14 place-items-center rounded-full bg-paper-alt">
                <MapPin className="size-5 text-gold-deep" aria-hidden />
              </span>
              <h2 className="mt-5 font-display text-2xl">No addresses saved</h2>
              <p className="mt-2 text-sm text-ink-muted">
                Add one now, or you will be asked for it at checkout.
              </p>
              <Button className="mt-6" onClick={() => setShowForm(true)}>
                <Plus className="size-4" aria-hidden />
                Add an address
              </Button>
            </div>
          ) : null}

          <ul className="mt-8 space-y-3">
            {addresses.map((address) => (
              <li
                key={address.id}
                className={cn(
                  "border bg-surface p-5",
                  address.is_default ? "border-gold" : "border-line",
                  busyId === address.id && "opacity-60"
                )}
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-ink">{address.full_name}</p>
                      {address.is_default ? (
                        <span className="bg-gold-wash px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] text-gold-deep">
                          Default
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
                      {address.address_line_1}
                      {address.address_line_2 ? `, ${address.address_line_2}` : ""}
                      <br />
                      {address.city}, {address.province}
                      {address.postal_code ? ` ${address.postal_code}` : ""}
                      <br />
                      {address.country}
                    </p>
                    <p className="mt-1 text-xs text-stone">{address.phone}</p>
                  </div>

                  <div className="flex shrink-0 items-center gap-1">
                    {!address.is_default ? (
                      <button
                        type="button"
                        onClick={() => makeDefault(address.id)}
                        disabled={busyId !== null}
                        title="Make default"
                        aria-label={`Make ${address.city} address the default`}
                        className="grid size-9 place-items-center text-stone transition-colors hover:text-gold-deep"
                      >
                        <Star className="size-4" aria-hidden />
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => remove(address.id)}
                      disabled={busyId !== null}
                      title="Delete address"
                      aria-label={`Delete ${address.city} address`}
                      className="grid size-9 place-items-center text-stone transition-colors hover:text-danger"
                    >
                      <Trash2 className="size-4" aria-hidden />
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {showForm ? (
            <div className="mt-6 border border-line bg-surface p-6">
              <h2 className="mb-5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
                New address
              </h2>
              <AddressForm
                isFirst={addresses.length === 0}
                onCancel={() => setShowForm(false)}
                onCreated={async () => {
                  setShowForm(false);
                  await reload();
                }}
              />
            </div>
          ) : addresses.length > 0 ? (
            <Button variant="secondary" className="mt-6" onClick={() => setShowForm(true)}>
              <Plus className="size-4" aria-hidden />
              Add another address
            </Button>
          ) : null}
        </>
      )}
    </div>
  );
}
