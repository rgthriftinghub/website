# Analytics, sales, and admin operations

## The rule

**Every business figure is computed by PostgreSQL.** Nothing is aggregated in
Python and nothing is aggregated in React — the browser receives finished numbers.
`GET /admin/analytics/dashboard` returns one payload assembled from a handful of
grouped queries, not one query per KPI tile.

## Two conventions that shape every query

**Cancelled orders are excluded from revenue.** A cancelled order is money that
never arrived, so counting it would overstate sales. It *is* counted in order-status
breakdowns, because "how many did we cancel" is a real operational question.

**Category and brand reporting joins the live catalogue.** `OrderItem` snapshots the
product name and SKU so history cannot be rewritten, but it does not snapshot
category or brand. Those breakdowns therefore reflect *current* categorisation —
re-filing a product retroactively moves its history. This is documented on each
function in `services/analytics.py`; snapshotting category on `OrderItem` would fix
it if the trade-off ever becomes a problem.

## Date ranges

Presets: `today`, `yesterday`, `last_7_days`, `last_30_days`, `this_month`,
`previous_month`, `this_year`, `all_time`, plus an explicit `date_from`/`date_to`
pair which overrides the preset.

Boundaries are computed in the **business timezone** (`BUSINESS_TIMEZONE`, default
`Asia/Karachi`) and converted to UTC, so "today" means today in Karachi rather than
in UTC or the viewer's browser. `date_to` is inclusive of the whole day.

Time buckets use `date_trunc` against the local timezone, so a sale at 1am Karachi
lands on the correct local day.

## Customer segmentation

By **lifetime non-cancelled order count**, using the thresholds in
`CUSTOMER_SEGMENT_THRESHOLDS`:

| Segment | Orders |
| --- | --- |
| NEW | 0–1 |
| REPEAT | 2–4 |
| LOYAL | 5+ |

The rule is returned in the API response as `segment_rule` and displayed on the
dashboard, so the reader never has to guess what "loyal" means.

## Low-selling products

The product-performance query uses a **LEFT JOIN** from products to order items, so
a product with zero sales appears with zeroes instead of vanishing. That is what
makes `sort=units_asc` meaningful — the worst performers are precisely the ones a
plain aggregation over order items would omit. **No arbitrary "low selling"
threshold is applied anywhere.**

## Inventory valuation

Valued at each product's effective selling price (its manual sale price when set,
otherwise regular). **Campaign discounts are deliberately excluded**: a two-day
promotion should not restate the value of goods on hand.

Low stock compares each variant against its **own** `low_stock_threshold`, not a
global number — a staple and a one-off thrift piece do not warrant the same reorder
point.

---

# Sales and discounts

## Activation is time-based, in SQL

A sale is live when `is_active` is true **and** the clock is inside its window. That
predicate runs on every price lookup, so a scheduled campaign starts and stops on
its own: no cron job, no background worker, no admin toggling anything.

`Sale.is_live()` mirrors the same rule in Python. The two must stay in step or a
listing and a detail page could quote different prices — `test_is_live_matches_the_sql_predicate`
guards this.

## Priority — the exact, deterministic rule

Several campaigns can cover one product. The winner is chosen by comparing, in
order:

1. **`priority` descending** — the explicit, admin-controlled field. Highest wins.
2. **Target specificity descending** — PRODUCT > BRAND > SUBCATEGORY > CATEGORY >
   STORE. A rule written for one product is a more deliberate decision than a
   store-wide banner.
3. **Larger resulting discount** — if two rules are equally deliberate, the customer
   gets the better one.
4. **Later `starts_at`** — the more recent campaign supersedes.
5. **Sale id** — an arbitrary but *stable* final tiebreak.

Nothing here is ever random. `test_resolution_is_deterministic` asserts repeated
resolution of identical input always yields the same winner.

## Stacking

**Campaigns never stack.** Exactly one wins, computed from `regular_price`. If the
product also carries a manual `sale_price`, the final price is the **lower** of the
two — so a hand-set clearance price is never silently undercut by a campaign, and a
campaign never double-discounts an already-reduced item.

## A sale is a rule, not a catalogue edit

`Sale` + `SaleTarget` never touch product rows. Consequences:

- Ending or deleting a campaign restores original prices **instantly**, with no
  catalogue update and no batch job.
- Products are never duplicated to put them on sale.
- Past orders are unaffected: they hold their own price snapshots.

## How the price reaches every surface

Campaign pricing is resolved at the **product repository**, the single choke point
every product read passes through, and attached to `Product.campaign_price` — a
transient in-memory attribute, never a column. `Product.effective_price` consults
it.

That one hook made listings, detail pages, the cart, and checkout sale-aware
**without changing a single call site**. Checkout resolves campaigns before any
price is read, so an order is frozen at the price the customer was shown.

## Discount types

| Type | `discount_value` means | Example on 5000 |
| --- | --- | --- |
| PERCENTAGE | percent off (clamped to 100) | 20 → 4000 |
| FIXED_AMOUNT | rupees off (floored at 0) | 1000 → 4000 |
| CUSTOM_PRICE | absolute price | 2499 → 2499 |

## Sale types

`STANDARD`, `FLASH`, `CLEARANCE`, `SEASONAL`. The maths is identical; only
presentation differs. A `FLASH` sale is required to have an end time — a flash sale
without one is not a flash sale.

**The storefront countdown is presentation only.** When it hits zero the price does
not change client-side; the next request simply returns the undiscounted price,
because the server owns the activation rule.

---

# Staff permissions

16 permissions, deliberately a flat list rather than a roles-and-scopes IAM system.

- **ADMIN** implicitly holds every permission. There is no way to create a
  half-privileged admin.
- **STAFF** holds only what has been explicitly granted. A new staff account starts
  read-only (`PRODUCT_VIEW`, `ORDER_VIEW`, `INVENTORY_VIEW`), so a mis-provisioned
  account cannot change data.
- **Granting replaces** rather than accumulates, so the admin checklist reflects
  reality — an unticked permission is a removed one.

Checks are a database read, not something carried on the token, so revoking takes
effect on the next request rather than when a session happens to expire.

Routes declare the specific permission they need (`require_permission(...)`), so a
staff member with only `INVENTORY_UPDATE` can adjust stock without also gaining the
ability to reprice the catalogue.

---

# Bulk operations

**Price changes preview before applying.** The preview computes the exact
before/after for every affected product and writes nothing; applying recomputes
through the same function, so what was shown is what gets written. A percentage
applied to the wrong selection is expensive to undo.

**Stock changes go through the inventory service.** Every bulk adjustment calls
`inventory.apply_movement`, writing an `InventoryTransaction` with before/after
quantities exactly like a sale does. There is no bulk path that bypasses the audit
trail, and a **reason is mandatory** — an unexplained stock change cannot be
reconciled later.

**Relationships are validated before any write.** A subcategory must belong to the
category it is applied alongside, so a product cannot end up filed under a
subcategory of a different category.

Selections are capped at 500 products per operation.

---

# Import and export

## Export

Seven datasets: products, inventory, inventory history, orders, order items,
customers, sales by period.

**CSV streams** row by row through a generator, so exporting a full order history
never builds the file in memory. It has no row limit. A UTF-8 BOM is emitted first
because without it Excel on Windows mangles accented product names.

**Excel** cannot be streamed — the format needs a complete workbook — so it is
capped at 20,000 rows and **says so in a final row** when the cap is hit, rather
than silently truncating. The response also carries `X-Export-Truncated`.

No export includes a password hash, a gateway payload, or a staff note. Customer
exports carry contact details because that is their purpose. All exports require
`REPORTS_VIEW`.

## Import

```
upload → parse → validate → ImportBatch (VALIDATED) → admin confirms → commit
```

**Uploaded rows are never written straight to the catalogue.** They are parsed into
`rows_json` with per-row verdicts and stored; only an explicit confirm applies them.
The preview an admin approves is exactly what gets applied — the file is not
re-parsed and cannot change in between.

Rows are classified **per row**, not per file: a file with three bad rows still
imports the other ninety-seven. Errors block a row; warnings do not. Duplicate SKUs
*within the file* are caught as well as against the database.

Existing SKUs have price and stock updated; new SKUs create a product. Column names
are matched case-insensitively ignoring spaces and underscores, so `Product Name`,
`product_name`, and `productname` all work. A template with the recognised columns
and a worked example is downloadable.

Failed and warned rows are downloadable as a CSV error report. Committing twice is
blocked. Limits: 5MB, 2,000 rows per file.

---

# Activity log and notifications

**Activity log** is append-only. `metadata_json` passes through the same `redact()`
helper the payment layer uses, so a secret cannot land there even if a caller is
careless. The actor's email is denormalised so entries stay readable after an
account is removed. Logging failures are swallowed and logged — recording an action
must never break it.

**Notifications** are deduped by `dedupe_key`, so a variant that has been low on
stock for a week produces one alert rather than hundreds. Low and out-of-stock are
distinct keys, so a variant going from low to out raises a new, more severe alert.

`scan_stock_alerts` runs on request rather than on a schedule — alerts appear when
someone opens the notifications screen or calls the scan endpoint.

---

# Charts

Hand-rolled inline SVG (`components/admin/charts.tsx`) rather than a charting
library: these are four simple shapes, a library would add ~100KB to the admin
bundle, and none theme cleanly to the brand palette without overriding most of
their defaults. All of them take pre-aggregated numbers — no chart computes a total,
an average, or a percentage.
