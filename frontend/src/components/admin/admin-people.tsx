"use client";

/**
 * Customers, notifications, activity log, and staff permissions.
 *
 * Customer notes are private staff annotations — they are never exposed on any
 * customer-facing response.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  addCustomerNote,
  listActivity,
  listCustomerNotes,
  listCustomers,
  listNotifications,
  listStaff,
  markAllNotificationsRead,
  markNotificationRead,
  setStaffPermissions,
} from "@/lib/api/admin";
import { formatDateTime, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  ActivityLogEntry,
  AdminNotificationList,
  CustomerNote,
  CustomerRow,
  Permission,
  StaffMember,
} from "@/lib/api/types";

const TH = "px-4 py-3 text-left text-[11px] uppercase tracking-[0.12em] font-medium text-stone";
const HEAD = "text-[11px] font-semibold uppercase tracking-[0.14em] text-ink";

const SEGMENT_TONES: Record<string, string> = {
  NEW: "bg-paper-alt text-ink-muted",
  REPEAT: "bg-gold-wash text-gold-deep",
  LOYAL: "bg-ink text-paper",
};

// -------------------------------------------------------------------- customers
export function AdminCustomers() {
  const [rows, setRows] = useState<CustomerRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<CustomerRow | null>(null);

  useEffect(() => {
    let cancelled = false;
    listCustomers({ search: search || undefined, page, page_size: 25 })
      .then((result) => {
        if (cancelled) return;
        setRows(result.items);
        setTotal(result.total);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [search, page]);

  return (
    <div className="space-y-5">
      <input
        defaultValue={search}
        onChange={(event) => {
          setSearch(event.target.value);
          setPage(1);
        }}
        placeholder="Search name or email"
        aria-label="Search customers"
        className="w-full max-w-sm border border-line bg-surface px-3 py-2 text-sm text-ink outline-none placeholder:text-stone focus:border-gold"
      />

      {rows === null ? (
        <p className="py-10 text-center text-sm text-stone">Loading customers…</p>
      ) : (
        <div className="overflow-x-auto border border-line bg-surface">
          <table className="w-full min-w-[52rem] text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className={TH}>Customer</th>
                <th className={TH}>Phone</th>
                <th className={cn(TH, "text-right")}>Orders</th>
                <th className={cn(TH, "text-right")}>Total spent</th>
                <th className={TH}>Last order</th>
                <th className={TH}>Segment</th>
                <th className={TH}>Joined</th>
                <th className={TH}>Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-line/60">
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/admin/customers/${row.id}`}
                      className="text-ink underline decoration-gold/40 underline-offset-4 hover:decoration-gold"
                    >
                      {row.first_name} {row.last_name}
                    </Link>
                    <p className="text-xs text-stone">{row.email}</p>
                  </td>
                  <td className="px-4 py-2.5 text-ink-muted">{row.phone ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink">{row.order_count}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium text-ink">
                    {formatPrice(row.total_spent)}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-stone">
                    {row.last_order_at ? formatDateTime(row.last_order_at) : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        "inline-flex rounded-sm px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
                        SEGMENT_TONES[row.segment] ?? "bg-paper-alt text-ink-muted"
                      )}
                    >
                      {row.segment}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-stone">
                    {formatDateTime(row.created_at)}
                  </td>
                  <td className="px-4 py-2.5">
                    <Button variant="ghost" onClick={() => setSelected(row)}>
                      Notes
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-ink-muted">
            <span>{total} customers</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page * 25 >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      {selected ? (
        <CustomerNotesPanel customer={selected} onClose={() => setSelected(null)} />
      ) : null}
    </div>
  );
}

function CustomerNotesPanel({
  customer,
  onClose,
}: {
  customer: CustomerRow;
  onClose: () => void;
}) {
  const [notes, setNotes] = useState<CustomerNote[] | null>(null);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listCustomerNotes(customer.id)
      .then((result) => {
        if (!cancelled) setNotes(result);
      })
      .catch(() => {
        if (!cancelled) setNotes([]);
      });
    return () => {
      cancelled = true;
    };
  }, [customer.id, reloadKey]);

  async function submit() {
    setBusy(true);
    try {
      await addCustomerNote(customer.id, body.trim());
      setBody("");
      setReloadKey((key) => key + 1);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className={HEAD}>
            Private notes · {customer.first_name} {customer.last_name}
          </h2>
          <p className="mt-1 text-xs text-stone">
            Internal only. The customer never sees these.
          </p>
        </div>
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={2}
          placeholder="Add a note about this customer"
          className="flex-1 border border-line bg-paper px-3 py-2 text-sm text-ink outline-none placeholder:text-stone focus:border-gold"
        />
        <Button disabled={busy || body.trim().length === 0} onClick={submit}>
          {busy ? "Saving…" : "Add note"}
        </Button>
      </div>

      {notes && notes.length > 0 ? (
        <ul className="mt-5 space-y-3 border-t border-line pt-4">
          {notes.map((note) => (
            <li key={note.id} className="text-sm">
              <p className="text-ink">{note.body}</p>
              <p className="mt-0.5 text-xs text-stone">
                {note.author_email ?? "system"} · {formatDateTime(note.created_at)}
              </p>
            </li>
          ))}
        </ul>
      ) : notes ? (
        <p className="mt-5 border-t border-line pt-4 text-sm text-stone">No notes yet.</p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------- notifications
export function AdminNotifications() {
  const [data, setData] = useState<AdminNotificationList | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listNotifications(unreadOnly)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [unreadOnly, reloadKey]);

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      setReloadKey((key) => key + 1);
    } finally {
      setBusy(false);
    }
  }

  const severityTone: Record<string, string> = {
    INFO: "border-l-line-strong",
    WARNING: "border-l-gold",
    CRITICAL: "border-l-danger",
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-ink-muted">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(event) => setUnreadOnly(event.target.checked)}
            className="accent-gold"
          />
          Unread only
        </label>
        {data && data.unread > 0 ? (
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => act(markAllNotificationsRead)}
          >
            Mark all read ({data.unread})
          </Button>
        ) : null}
      </div>

      {!data ? (
        <p className="py-10 text-center text-sm text-stone">Loading notifications…</p>
      ) : data.items.length === 0 ? (
        <p className="border border-line bg-surface py-12 text-center text-sm text-stone">
          Nothing to review.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((notification) => (
            <li
              key={notification.id}
              className={cn(
                "flex flex-wrap items-start justify-between gap-3 border border-line border-l-2 bg-surface px-4 py-3",
                severityTone[notification.severity] ?? "border-l-line-strong",
                notification.is_read ? "opacity-60" : ""
              )}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink">{notification.title}</p>
                {notification.body ? (
                  <p className="mt-0.5 text-xs text-ink-muted">{notification.body}</p>
                ) : null}
                <p className="mt-1 text-[11px] text-stone">
                  {notification.type.replace(/_/g, " ").toLowerCase()} ·{" "}
                  {formatDateTime(notification.created_at)}
                </p>
              </div>
              {!notification.is_read ? (
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() => act(() => markNotificationRead(notification.id))}
                >
                  Mark read
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// -------------------------------------------------------------------- activity
export function AdminActivity() {
  const [rows, setRows] = useState<ActivityLogEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelled = false;
    listActivity({ page, page_size: 50 })
      .then((result) => {
        if (cancelled) return;
        setRows(result.items);
        setTotal(result.total);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [page]);

  return (
    <div className="space-y-4">
      {rows === null ? (
        <p className="py-10 text-center text-sm text-stone">Loading activity…</p>
      ) : rows.length === 0 ? (
        <p className="border border-line bg-surface py-12 text-center text-sm text-stone">
          No recorded activity yet.
        </p>
      ) : (
        <div className="overflow-x-auto border border-line bg-surface">
          <table className="w-full min-w-[46rem] text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className={TH}>When</th>
                <th className={TH}>Who</th>
                <th className={TH}>Action</th>
                <th className={TH}>Entity</th>
                <th className={TH}>Description</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((entry) => (
                <tr key={entry.id} className="border-b border-line/60">
                  <td className="px-4 py-2.5 whitespace-nowrap text-xs text-stone">
                    {formatDateTime(entry.created_at)}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink-muted">
                    {entry.user_email ?? "system"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="font-mono text-[11px] text-ink">{entry.action}</span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink-muted">{entry.entity_type}</td>
                  <td className="px-4 py-2.5 text-ink">{entry.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-ink-muted">
            <span>{total} entries</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page * 50 >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
      <p className="text-[11px] text-stone">
        Append-only. Metadata is redacted when written, so no secret can appear here.
      </p>
    </div>
  );
}

// ------------------------------------------------------------------- permissions
const PERMISSION_GROUPS: { label: string; permissions: Permission[] }[] = [
  {
    label: "Products",
    permissions: ["PRODUCT_VIEW", "PRODUCT_CREATE", "PRODUCT_UPDATE", "PRODUCT_DELETE"],
  },
  { label: "Orders", permissions: ["ORDER_VIEW", "ORDER_UPDATE"] },
  { label: "Inventory", permissions: ["INVENTORY_VIEW", "INVENTORY_UPDATE"] },
  { label: "Customers", permissions: ["CUSTOMER_VIEW", "CUSTOMER_UPDATE"] },
  { label: "Sales", permissions: ["SALES_VIEW", "SALES_MANAGE"] },
  { label: "Payments", permissions: ["PAYMENT_VIEW", "PAYMENT_MANAGE"] },
  { label: "Other", permissions: ["REPORTS_VIEW", "SETTINGS_MANAGE"] },
];

export function AdminStaff() {
  const [staff, setStaff] = useState<StaffMember[] | null>(null);
  const [draft, setDraft] = useState<Record<string, Set<Permission>>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listStaff()
      .then((result) => {
        if (cancelled) return;
        setStaff(result);
        setDraft(
          Object.fromEntries(
            result.map((member) => [member.id, new Set(member.permissions)])
          )
        );
      })
      .catch(() => {
        if (!cancelled) setStaff([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function toggle(memberId: string, permission: Permission) {
    setDraft((current) => {
      const next = new Set(current[memberId] ?? []);
      if (next.has(permission)) next.delete(permission);
      else next.add(permission);
      return { ...current, [memberId]: next };
    });
  }

  async function save(member: StaffMember) {
    setBusyId(member.id);
    setMessage(null);
    try {
      const updated = await setStaffPermissions(
        member.id,
        Array.from(draft[member.id] ?? [])
      );
      setStaff((current) =>
        (current ?? []).map((entry) => (entry.id === member.id ? updated : entry))
      );
      setMessage(`Saved permissions for ${member.email}`);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Could not save.");
    } finally {
      setBusyId(null);
    }
  }

  if (staff === null) {
    return <p className="py-10 text-center text-sm text-stone">Loading staff…</p>;
  }

  return (
    <div className="space-y-5">
      {message ? <p className="text-sm text-ink-muted">{message}</p> : null}

      {staff.map((member) => (
        <section key={member.id} className="border border-line bg-surface p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-serif text-lg text-ink">
                {member.first_name} {member.last_name}
              </h2>
              <p className="text-xs text-stone">
                {member.email} · {member.role}
              </p>
            </div>
            {member.holds_all ? (
              <span className="inline-flex rounded-sm bg-ink px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-paper">
                All permissions
              </span>
            ) : (
              <Button disabled={busyId === member.id} onClick={() => save(member)}>
                {busyId === member.id ? "Saving…" : "Save"}
              </Button>
            )}
          </div>

          {member.holds_all ? (
            <p className="mt-3 text-sm text-ink-muted">
              Admin accounts hold every permission and cannot be restricted.
            </p>
          ) : (
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {PERMISSION_GROUPS.map((group) => (
                <fieldset key={group.label}>
                  <legend className="text-[11px] font-semibold uppercase tracking-[0.12em] text-stone">
                    {group.label}
                  </legend>
                  <div className="mt-2 space-y-1.5">
                    {group.permissions.map((permission) => (
                      <label
                        key={permission}
                        className="flex items-center gap-2 text-xs text-ink-muted"
                      >
                        <input
                          type="checkbox"
                          checked={draft[member.id]?.has(permission) ?? false}
                          onChange={() => toggle(member.id, permission)}
                          className="accent-gold"
                        />
                        {permission.split("_").slice(1).join(" ").toLowerCase() || "view"}
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>
          )}
        </section>
      ))}

      <p className="text-[11px] leading-relaxed text-stone">
        Saving replaces a staff member&apos;s permissions with exactly what is ticked —
        unticking removes. New staff accounts start read-only.
      </p>
    </div>
  );
}
