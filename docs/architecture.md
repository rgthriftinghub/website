# Architecture

## System design

RG Thrifting Hub is a **modular monolith**: one Next.js frontend, one FastAPI REST API, one PostgreSQL database. A single deployable backend keeps operational complexity appropriate for a small-to-medium business while still enforcing clear internal module boundaries.

```
Next.js frontend (browser + server rendering)
        |
        |  REST over HTTP (JSON), session in an HTTP-only cookie
        v
FastAPI application  (modular monolith, versioned under /api/v1)
        |
        |  SQLAlchemy 2.x ORM + Alembic migrations
        v
PostgreSQL 16
```

No message broker, cache server, search cluster, or second datastore is involved. PostgreSQL is the only source of truth.

## Backend layout

| Directory | Responsibility |
| --- | --- |
| `app/api/v1/` | HTTP routing, request/response handling, auth dependencies |
| `app/schemas/` | Pydantic request/response models |
| `app/services/` | Write logic, cross-field validation, uniqueness checks |
| `app/repositories/` | Queries, including the catalogue filter builder |
| `app/models/` | SQLAlchemy ORM models and enums |
| `app/core/` | Settings, password hashing, JWT |
| `app/db/` | Engine, session factory, declarative base |
| `app/seeds/` | Demo catalogue definition and seeder |

The dependency direction is one-way: API → services → repositories → models. Route handlers hold no business rules, and persistence queries do not appear in route handlers.

Domain errors (`NotFoundError`, `ConflictError`, `InvalidRequestError`, `AuthenticationError`) are raised by services and mapped to status codes by exception handlers registered in `app/main.py`, so endpoints stay free of repetitive `try/except` blocks and the same failure always produces the same status code.

## Data model

```
User ──< CustomerAddress
  │
  ├──1:1── Cart ──< CartItem ─────────────┐
  ├──< WishlistItem ── Product            │
  └──< Order ──< OrderItem                │
        ├──< OrderStatusEvent             │
        └──< ReturnRequest                │
                                          │
Category ──< Subcategory                  │
    │            │                        │
    └────────────┴──< Product >── Brand   │
                        │                 │
                        ├──< ProductImage │
                        │                 │
                        └──< ProductVariant ──1:1── InventoryItem
                                    │
                                    └──< InventoryTransaction
```

Key decisions:

- **UUID primary keys** everywhere, so public URLs and admin ids do not leak row counts or allow trivial enumeration.
- **Money is `NUMERIC(10,2)`**, never floating point, and is carried to the browser as a decimal string so it is never rounded through a JS number.
- **Stock never lives on `Product`.** A thrift garment's availability differs per waist and size, so quantities belong to `InventoryItem`, keyed one-to-one to a `ProductVariant`. Product-level stock is the sum of its active variants, derived rather than stored.
- **Inventory is a separate table from the variant** so a later phase can add stock-movement history referencing `product_variant_id`, with the current quantity remaining here as the fast-read projection.
- **`barcode` is nullable but unique** on both products and variants: many thrift pieces have no barcode, and PostgreSQL permits multiple NULLs under a unique constraint.
- **`brand_id` and `subcategory_id` are nullable.** Unbranded thrift items are ordinary, and not every product needs a subcategory.
- **Soft delete only.** Catalogue rows are deactivated via `is_active`, never hard-deleted, because a one-of-a-kind piece's record stays useful after it stops being sellable. `DELETE` endpoints deactivate.

### Constraints worth knowing about

- `UNIQUE NULLS NOT DISTINCT (product_id, size, waist, color)` on variants. The `NULLS NOT DISTINCT` clause (PostgreSQL 15+) is essential: most variants set only one of size or waist, so without it two rows that are both `(waist 30, size NULL)` would count as distinct and slip past the constraint.
- A partial unique index enforces at most one primary image per product.
- Check constraints keep prices non-negative, keep `sale_price` below `regular_price`, and keep inventory quantities non-negative.
- Subcategory slugs are unique **within** a category, so `men/jeans` and `women/jeans` can coexist.

### Orders are immutable records

An order is a record of a past transaction, not a view over current data. It therefore stores **snapshots**:

- `Order.shipping_address_snapshot` (JSONB) — a customer who edits or deletes an address cannot rewrite where a past order was sent, and addresses are safe to hard-delete.
- `OrderItem` keeps `product_name_snapshot`, `product_slug_snapshot`, `brand_name_snapshot`, `sku_snapshot`, `variant_snapshot`, `image_url_snapshot`, `unit_price` and `line_total` — renaming or repricing a product does not alter history.

The foreign keys to product and variant are retained for reporting and restocking, but use `ON DELETE SET NULL`: a purged catalogue row must never block or corrupt an order. `Order.user_id` uses `RESTRICT` instead, because orders must outlive attempts to delete the account that placed them.

`OrderStatusEvent` is append-only and drives the customer-facing timeline. `Order.internal_note` is staff-only and is declared on no customer response model, so it cannot leak.

### Stock movement history

Every quantity change flows through `inventory.apply_movement`, which writes an `InventoryTransaction` recording `quantity_before`, `quantity_change` and `quantity_after`. Nothing else mutates `InventoryItem.quantity`, so current stock can always be reconciled against its own history. Movement types are `SALE`, `CANCELLED_ORDER`, `RESTOCK`, `ADJUSTMENT` and `RETURN`; `reference_type`/`reference_id` link a movement back to the order that caused it without adding a nullable foreign key per source.

### Extensibility without EAV

Additional product attributes are added as ordinary columns, or as a new related table when they are multi-valued. There is deliberately no entity-attribute-value store: it would trade query clarity, type safety, and index usefulness for flexibility this catalogue does not need.

### Timestamps

`created_at` and `updated_at` have both a Python-side default and a server default. The Python-side one is what ORM inserts use, and it is per-row on purpose: PostgreSQL's `now()` is fixed for an entire transaction, so relying on the server default alone would give every row inserted together an identical `created_at` and make "newest first" ordering arbitrary.

## API versioning

Everything is mounted below `/api/v1`.

**Public**

- `GET /health`
- `GET /products`, `GET /products/{slug}`, `GET /products/filter-options`
- `GET /categories`, `GET /categories/{slug}`
- `GET /brands`, `GET /brands/{slug}`
- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`

**Admin** (ADMIN or STAFF)

- `GET|POST /admin/products`, `GET|PUT|DELETE /admin/products/{id}`
- `GET|POST /admin/categories`, `GET|PUT|DELETE /admin/categories/{id}`
- `GET|POST /admin/subcategories`, `PUT|DELETE /admin/subcategories/{id}`
- `GET|POST /admin/brands`, `GET|PUT|DELETE /admin/brands/{id}`

The role dependency is attached to the **parent** admin router, so every current and future admin route inherits it and none can be added unprotected by accident.

**Authenticated customer**

- `GET|DELETE /cart`, `POST /cart/items`, `PUT|DELETE /cart/items/{id}`
- `GET /wishlist`, `GET /wishlist/ids`, `POST|DELETE /wishlist/{product_id}`
- `GET|POST /customer/addresses`, `GET|PUT|DELETE /customer/addresses/{id}`
- `GET /checkout/config` (public), `POST /checkout`
- `GET /customer/orders`, `GET /customer/orders/{order_number}`
- `POST /customer/orders/{order_number}/cancel`
- `POST /customer/orders/{order_number}/returns`
- `GET /customer/orders/{order_number}/invoice` (PDF)

**Admin orders** (ADMIN or STAFF)

- `GET /admin/orders` with status, payment-status, date-range, customer and order-number filters
- `GET /admin/orders/stats`, `GET /admin/orders/{id}`, `GET /admin/orders/{id}/inventory`
- `PUT /admin/orders/{id}/status`, `.../payment-status`, `.../note`
- `GET /admin/orders/{id}/invoice`
- `GET /admin/orders/returns`, `PUT /admin/orders/returns/{id}`

The customer router carries `Depends(get_current_user)` on the **parent**, matching the admin router's role dependency, so a route added later cannot ship unauthenticated by accident.

Reviews and coupons will mount under the same `/api/v1`. A breaking change would introduce `/api/v2` alongside it rather than altering `/api/v1`. OpenAPI documentation is at `/docs`.

## Cart and checkout

**The client never sends a price.** Cart requests carry a variant id and a quantity; checkout carries an address id, a payment method and an optional note. Every monetary value is computed server-side in `services/pricing.py`, which is the single source of truth shared by the cart preview, the checkout summary and the persisted order — so the three cannot disagree. `CartItem.unit_price` exists only as a cached display value and is recomputed on every read, so a stale price can never reach an order.

Adding a variant already in the bag raises its quantity rather than creating a second line, enforced both by the service and by a `UNIQUE (cart_id, product_variant_id)` constraint.

### Order placement is one transaction

`services/orders.place_order` performs, in order: load the cart → resolve the address (scoped to the requesting user) → **take row locks on the inventory rows** → validate each product and variant is still active → check stock against the locked quantities → recompute prices and totals → create the order and its items → decrement stock and write an `InventoryTransaction` per line → record the initial status event → empty the cart → commit.

Any failure raises before the commit, so the whole thing rolls back: no partial order, no stock change, and the customer's bag survives intact so they can fix the problem and retry.

### Overselling protection

`SELECT ... FOR UPDATE` on the inventory rows is what makes concurrent checkouts safe: a second transaction buying the same variant blocks until the first commits, then re-reads the reduced quantity and fails validation. Rows are locked in a deterministic order (by variant id) so two overlapping multi-item checkouts cannot deadlock.

One subtlety is load-bearing: the locking query uses `populate_existing=True`. These inventory rows are normally already in the session's identity map, loaded through the cart's eager-loaded variant relationship. Without it, SQLAlchemy would hand back those cached instances with their **pre-lock** quantity — so a transaction that waited on the lock would read the stale value it saw before blocking, and oversell the stock it had just waited for. `tests/test_concurrency.py` exercises this with real concurrent connections and caught exactly that bug.

### Order numbers

Human-facing numbers look like `RG-20260812-0001`. The UUID primary key is never shown to customers. The date is the **business-local** trading date (`BUSINESS_TIMEZONE`), not UTC, so an order taken late in the evening in Karachi is not stamped with the previous day — and the invoice prints the same date it encodes. A transaction-scoped PostgreSQL advisory lock serialises concurrent generation, with the `UNIQUE` constraint on `order_number` as the final backstop.

### Payments and delivery

`PaymentMethod` declares `COD`, `BANK_TRANSFER`, `JAZZCASH`, `EASYPAISA`, `PAYFAST` and `SAFEPAY`, but only the first two are in `SELECTABLE_PAYMENT_METHODS`; requesting any other is rejected at validation. Adding a gateway later is a service-layer change plus one set membership — it does not reshape orders.

Neither COD nor bank transfer is ever assumed paid: both start `PENDING`, and only a staff action marks an order `PAID`, because cash arrives at the door and a transfer needs a human to reconcile it.

Delivery pricing lives in configuration (`STANDARD_DELIVERY_CHARGE`, `FREE_DELIVERY_THRESHOLD`) and is served to the storefront by `GET /checkout/config`, so no charge is ever hardcoded in frontend code. `discount_amount` is carried through the pricing pipeline at zero, ready for coupons.

### Status machine

Allowed transitions live in `ORDER_STATUS_TRANSITIONS` as data rather than scattered conditionals, so an illegal move is impossible to request and the rules are reviewable in one place. Customers may cancel only from `PENDING` or `PROCESSING`; after that it becomes a staff decision or a return request. Cancelling from any stock-holding status restores every line's stock and records a `CANCELLED_ORDER` movement, in the same transaction as the status change.

### Returns and exchanges

`ReturnRequest` captures the customer's request and the staff decision. Requests are only accepted on `DELIVERED` orders, and only one may be open per order. Completing a request moves the order to `RETURNED` or `EXCHANGE`; approval alone does not. Courier pickup, refunds and automatic restocking are Phase 4 and attach to this row rather than replacing it.

### Notifications

`services/notifications.py` defines a `NotificationService` protocol and the order lifecycle events (`order_created`, `order_processing`, …, `return_decided`). The only implementation logs; nothing is emailed and no provider is configured. Delivery failures are swallowed and logged, so a notification problem can never roll back the order operation that triggered it. A later phase supplies another implementation without touching a single caller.

### Invoices

`services/invoices.py` renders a single-page A4 PDF with ReportLab — pure-Python wheels, so the slim image needs no system libraries. Every value comes from the order's own snapshots, so a reprint years later shows what was actually bought and where it went. The brand logo is a downscaled copy at `app/assets/logo.png`; the backend build context cannot reach `frontend/public`, and embedding the full-resolution artwork made each invoice about 1&nbsp;MB instead of ~100&nbsp;KB.

## Catalogue querying

All filtering, searching, sorting and pagination happens in SQL; nothing is filtered in Python, and only one page of rows is ever transferred.

- **Combinable filters.** Category, subcategory, brand, gender, condition, product type, colour, fabric, featured, new-arrival, price range, size, waist and availability are ANDed together.
- **One correlated `EXISTS` for variant filters.** Size, waist and in-stock predicates go into a single `EXISTS`, which is what makes "waist 32 and in stock" mean *the same variant* is both, rather than the product merely having some waist-32 variant and some other in-stock variant.
- **Price filters and price sorting use the effective price** — `COALESCE(sale_price, regular_price)` — so a discounted item sorts and filters by what a customer actually pays.
- **Search** is case-insensitive `ILIKE` across product name, SKU, brand name and category name. Each whitespace-separated word must match at least one field, so "northbay jeans" narrows rather than widens. No Elasticsearch.
- **Sorting** is a dictionary of ordering clauses keyed by a `ProductSort` enum. Adding "best selling" or "highest rated" later means one enum member and one dictionary entry; the endpoint does not change. Every sort carries an id tie-breaker so pagination cannot repeat or drop rows when values tie.
- **Pagination** always returns `{items, page, page_size, total, total_pages}`; `page_size` is capped server-side.

## Authentication and authorisation

- **Argon2id** password hashing via `argon2-cffi`. Plaintext passwords are never stored or logged, and stored hashes are transparently upgraded when the cost parameters change.
- **Signed JWT access token** (HS256, PyJWT) delivered **only** as an HTTP-only cookie, so page scripts — and anything injected into them — cannot read it. `Secure` is forced on when `ENVIRONMENT=production`; `SameSite` is configurable, and a `SameSite=None` cookie without `Secure` is rejected at startup rather than silently ignored by browsers.
- An `Authorization: Bearer` header is also accepted so non-browser API clients can authenticate without a cookie jar.
- **`password_hash` appears on no response model**, so it cannot be serialised out by accident.
- **Login does not reveal whether an email is registered**: the same message and status are returned for an unknown address and a wrong password, and a hash is computed either way so the two paths take a similar amount of time.
- **Roles** are `CUSTOMER`, `ADMIN`, `STAFF`. `require_roles(...)` builds a dependency admitting only the listed roles; `require_staff` currently admits ADMIN and STAFF together. Finer-grained staff permissions can be layered in later without changing call sites. Registration only ever creates a `CUSTOMER`; elevated accounts are provisioned deliberately.

The frontend's `AdminGate` is a usability measure, not the security boundary. Every admin endpoint independently enforces the role server-side, so hiding the UI is never the only thing between a customer and the data.

## Frontend

The Next.js App Router application owns presentation only. All backend access goes through `src/lib/api/`, which is split into transport (`client.ts`) and typed endpoint functions (`catalog.ts`). No database logic exists in Next.js.

- **Two API base URLs.** `NEXT_PUBLIC_API_BASE_URL` is inlined into the browser bundle and must be host-reachable. Server rendering runs inside the frontend container, where `localhost` is that container, so it uses `API_INTERNAL_BASE_URL` (the `backend` service name). This is the one intentional exception to "no localhost between services", and it applies only to requests the visitor's browser makes.
- **Storefront pages render per request** (`dynamic = "force-dynamic"` on the store route group). Without this they would be prerendered during `docker build`, when the API is not running, baking an empty catalogue into the image; stock levels also change, so a build-time snapshot would be wrong regardless. Individual fetches still use the data cache, so pages stay fast.
- **Design system** lives in `globals.css` as Tailwind v4 `@theme` tokens derived from the supplied logo: near-black ink, the logo's antique gold sampled at `#C39A51`, and a warm neutral ramp. Radii are small, transitions are limited to a nav underline and a subtle image zoom, and a `prefers-reduced-motion` block disables them.
- **The logo is used as supplied** — never recoloured, redrawn, or replaced with text. The artwork is a portrait badge with an opaque white background, so it is sized by height (not width, which would overflow any fixed-height bar) and placed on white surfaces; on the dark footer it sits on a deliberate white plate rather than showing an accidental halo.
- **Product imagery is fixed at a 3:4 ratio** throughout, which suits garments and reserves layout space before images load, so grids do not shift.
- **Per-variant availability is honoured in the UI.** A sold-out size is disabled and struck through on its own while remaining legible; every other size stays selectable and the product remains purchasable. Only when no variant has stock does the add-to-bag control become unavailable.
- Components reading `useSearchParams` are wrapped in a Suspense boundary at their own export site, since that hook opts a component out of static prerendering.

### Customer data is fetched in the browser

Cart, wishlist, addresses and orders all depend on the HTTP-only session cookie, which only the browser can send — server rendering has no cookie jar. Those views are therefore client components, and `StoreProvider` loads the session, bag and wishlist once into shared context so the header's counts and the cart pages cannot disagree. Catalogue pages remain server-rendered.

### Pages

**Storefront** `/` · `/shop` · `/shop/[slug]` · `/categories/[slug]` · `/brands/[slug]` · `/cart` · `/checkout` · `/checkout/success/[orderNumber]` · `/wishlist` · `/account` · `/account/orders` · `/account/orders/[orderNumber]` · `/account/addresses`

**Admin** `/admin` · `/admin/orders` · `/admin/orders/[id]` · `/admin/products` · `/admin/products/new` · `/admin/categories` · `/admin/brands`

**Infrastructure** `/api/health`

`RequireAuth` gates the customer pages and `AdminGate` gates the admin shell. Both are usability measures, not the security boundary: every endpoint independently requires a session, scopes its queries to the requesting user, or enforces a role.

## SEO foundation

Root metadata defines a title template, description, Open Graph and Twitter card defaults. Product, category and brand pages generate their own titles, descriptions, canonical URLs and Open Graph images from live data. Slugs are validated to a lowercase hyphenated pattern and are unique. The admin area and account page are marked `noindex`. Sitemap generation, structured data, and robots policy are later work.

## Configuration and secrets

`pydantic-settings` loads all configuration from environment variables, trying `../.env` then `./.env` so the app works from the repository root and from `backend/`; real environment variables always win, which is how the containers are configured. No secrets are committed: `.env.example` holds placeholders only and `.env` is ignored by Git.

CORS origins come from `CORS_ORIGINS` as an explicit allow-list, and configuration validation rejects a `*` wildcard when `ENVIRONMENT=production`, so a permissive development setting cannot reach production. `allow_credentials` is enabled because the session cookie must travel cross-origin between ports 3000 and 8000.

## Docker setup

Three services with health-gated startup ordering:

1. **db** — `postgres:16-alpine`, named `postgres_data` volume, `pg_isready` health check. Its host port is configurable so it can avoid a locally installed PostgreSQL.
2. **backend** — `python:3.12-slim`, Uvicorn on port 8000 as an unprivileged user, starts once `db` is healthy. Its health check calls the real `/api/v1/health`, which executes a database query, so a passing check proves end-to-end connectivity.
3. **frontend** — multi-stage `node:22-alpine` build producing a Next.js `standalone` bundle, port 3000 as the `node` user, starts once `backend` is healthy, probes `/api/health`.

Two details that are easy to get wrong and are handled explicitly:

- Health checks use `127.0.0.1`, not `localhost`. Both servers bind IPv4 only, while Alpine resolves `localhost` to `::1` first — which fails against a closed IPv6 socket.
- The `standalone` output excludes `static` and `public`, so the Dockerfile copies both separately. Without that, every asset including the brand logo 404s at runtime.

## Ownership and trust boundaries

Nothing from a request body is trusted for price, total, stock, user identity or status. Concretely:

- Money is always recomputed server-side; no request carries an amount.
- Ownership is enforced **inside the query** rather than checked afterwards — `get_order_for_user` filters on `user_id`, `_owned_item` joins through `Cart.user_id`, address lookups filter on `user_id`. Another customer's id therefore resolves to 404 rather than being readable, which also stops order numbers being probed for existence.
- Status changes are validated against the transition table; a customer cannot set a status at all.
- `internal_note` is declared on no customer schema, and `password_hash` on none at all.

## Testing approach

Catalogue and order tests run against a real PostgreSQL database, because native enums, `NUMERIC` money, correlated `EXISTS` variant filters, case-insensitive search and `SELECT ... FOR UPDATE` locking do not behave identically on SQLite. A dedicated `..._test` database is created on the same server; each test runs inside a transaction that is rolled back, with `join_transaction_mode="create_savepoint"` so production code can call `commit()` normally while the outer transaction still discards everything. When no server is reachable, the database-backed tests skip with a clear reason rather than passing silently.

The overselling tests are the deliberate exception. Demonstrating that two simultaneous checkouts cannot both take the last unit requires two real connections that genuinely commit, so `tests/test_concurrency.py` builds its own fixtures, commits them, runs threads released together from a barrier, and deletes everything in a `finally` block — with a further test that asserts the cleanup leaves no residue.

## Development workflow

1. Copy `.env.example` to `.env` and fill in local secrets.
2. `docker compose up --build`, then `alembic upgrade head` and `python -m app.seeds.seed`.
3. Add schema changes as SQLAlchemy models plus a generated Alembic migration; check the generated `downgrade()`, especially for enum types.
4. Add routes under `app/api/v1`, write logic in services, queries in repositories.
5. Call the backend from the frontend only through `src/lib/api/`.
6. Run `pytest` and the frontend lint/typecheck/build before committing.

## Designed for, but not yet built

Each of these has a seam waiting for it, so adding it does not reshape existing tables:

| Later work | Where it attaches |
| --- | --- |
| JazzCash, Easypaisa, PayFast, Safepay | `PaymentMethod` members already exist; add to `SELECTABLE_PAYMENT_METHODS` and implement a gateway service |
| Courier APIs, shipping labels | `DeliveryMethod` enum and `Order.delivery_method`; tracking fields join `Order` |
| Coupons and discounts | `discount_amount` already flows through `pricing.compute_totals` and is persisted on `Order` |
| Real email, SMS, WhatsApp | Another `NotificationService` implementation; no caller changes |
| Refunds and courier pickup | Attach to `ReturnRequest`; `PaymentStatus.REFUNDED` already exists |
| Stock audit reporting | `InventoryTransaction` is already the complete movement history |

## Not in use

No microservices, Kubernetes, Redis, Kafka, Celery, Elasticsearch, Firebase, Supabase, or MongoDB. PostgreSQL remains the primary and only database.
