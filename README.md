# RG Thrifting Hub

Modular-monolith e-commerce platform for RG Thrifting Hub: a Next.js storefront, a FastAPI REST API, and PostgreSQL.

The store includes product reviews and ratings, Highest Rated and Best Selling sorting, per-product SEO metadata, individual variant inventory, admin analytics and reports, scheduled sale campaigns, coupon codes, bulk catalogue tools, customer profiles/notes, staff permissions, manual payment confirmation, generated printable shipping labels, manual courier/tracking entry, and daily PostgreSQL backups. JazzCash and Easypaisa are manual-number transfers with a prefilled WhatsApp screenshot handoff; no wallet gateway API is connected. Courier APIs are not connected: staff can keep entering courier/tracking details manually. Seeded product images are demo placeholders until real product photos are supplied.

Product condition grades are **Premium Plus**, **Premium**, **Excellent**, and **Good**. Existing product rows migrate to **Good**. Legacy import/API labels (`NEW`, `EXPORT_QUALITY`, `THRIFT`) continue to map to their corresponding grades. The condition collections and guide are available at `/condition` and `/condition-guide`.

The storefront also includes Kids (Girls/Boys), unique generated item codes with single-piece inventory history, privacy-safe order tracking, guest and account wishlists, catalog search, editable policy pages and announcement text, and a cart free-delivery progress bar. Staff can edit policy pages and the announcement under **Admin → Store content**; the free-delivery threshold is managed there through the standard shipping method. The default/seeded threshold is PKR 4,000. Payments remain manual: JazzCash/Easypaisa transfers still show the store number and direct customers to WhatsApp to send their payment screenshot. Courier and tracking details remain staff-entered; no payment or courier API is connected.

The product import template includes optional **Item Code** and **Single Piece** columns; product exports include both fields as well.

## Multiple product sizes and per-size stock

The admin product editor supports adding and removing multiple sizes on one product. Each size is saved as a product variant and has its own stock quantity. Size labels are custom text, so standard labels such as `XS`, `S`, `M`, `L`, `XL`, and custom labels such as `32` are supported. Duplicate labels are checked case-insensitively in the editor; the backend also rejects duplicate variant combinations case-insensitively.

On edit, existing variants keep their identifiers and inventory history. Removing a variant from the form marks it inactive through the existing catalogue update behavior, which preserves references from carts and order history. Adding another size to a single-piece product clears the single-piece setting because that setting only permits one total unit.

The catalogue API already accepts and returns a `variants` list. The storefront lets a customer choose an active, in-stock variant; the cart stores that variant, checkout uses it for inventory, and orders save its label in the item snapshot. Customer and admin order views display the selected variant.

### Database compatibility

No migration is needed for multi-size support. This application has stored size on `product_variants` since the catalogue migration (`069b1183812d_phase_2_catalog_and_accounts.py`), with stock attached to each variant. A product that previously had one size is already represented as a one-variant list; its size and stock remain intact. Do not add a separate product-level size array unless the variant/inventory model is intentionally being redesigned.

### Manual verification

1. In **Admin → Products → Add product**, add two or more sizes, set a different quantity for each, save, and confirm a case-only duplicate such as `m` after `M` is rejected.
2. Edit that product, change a size quantity, add a size, remove another, save, and confirm the remaining variants and quantities are correct.
3. Open the product in the storefront, choose a size, add it to the cart, and place an order. Confirm the selected size appears in the cart and customer/admin order details.

Apply all schema changes with `docker compose exec backend alembic upgrade head`. New reversible migrations add condition grades (`9c32b4e17d60`), item codes/single-piece stock (`ba172f3c80a9`), and editable store content (`2f4a7d9c1b30`). Roll back in reverse order with Alembic downgrades if needed.

## Prerequisites

- **Docker Desktop** with Docker Compose v2 — for the full local stack
- For running the apps directly instead: **Node.js 22+** and **Python 3.12+**

## Environment variables

```bash
cp .env.example .env
```

Replace every placeholder. `.env` is ignored by Git and must never be committed.

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | `development`, `staging`, or `production` |
| `SECRET_KEY` | General application secret |
| `JWT_SECRET_KEY` | Signs the access token; use 32+ random bytes |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Staff/customer session lifetime in minutes; defaults to `480` (8 hours) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Credentials for the Compose `db` service |
| `POSTGRES_HOST_PORT` | Host port for PostgreSQL (default `5432`; change it if you already run PostgreSQL locally) |
| `DATABASE_URL` | SQLAlchemy URL used by the backend and Alembic |
| `CORS_ORIGINS` | Comma-separated allowed browser origins (`*` is rejected when `ENVIRONMENT=production`) |
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL **the browser** uses; baked into the client bundle at build time |
| `API_INTERNAL_BASE_URL` | Backend URL **server-side rendering** uses, e.g. `http://backend:8000/api/v1` |
| `STANDARD_DELIVERY_CHARGE` | Delivery charge, default `250.00`. Never hardcoded in frontend code |
| `FREE_DELIVERY_THRESHOLD` | Environment fallback for free delivery, default `4000.00`; the seeded standard shipping method is admin-editable |
| `MAX_QUANTITY_PER_ITEM` | Cap on units of one variant per order, default `10` |
| `BUSINESS_TIMEZONE` | Trading timezone for order numbers and invoice dates, default `Asia/Karachi` |
| `CURRENCY_CODE` | Display currency, default `PKR` |
| `JAZZCASH_NUMBER` / `EASYPAISA_NUMBER` | Store receiving numbers for manual mobile-wallet transfers |
| `PAYMENT_WHATSAPP_NUMBER` | WhatsApp destination for payment screenshots, digits with country code |

Two things that commonly trip people up:

- `DATABASE_URL` uses host `db` inside Docker and `localhost` when the backend runs directly on your machine. If you change `POSTGRES_PASSWORD`, change it inside `DATABASE_URL` too.
- The frontend needs **two** API URLs. Server rendering happens inside the frontend container, where `localhost` is that container rather than the API, so it uses `API_INTERNAL_BASE_URL`. The browser uses `NEXT_PUBLIC_API_BASE_URL`.

## Product image uploads

Staff with product-create permission can upload JPG, PNG, and WebP images up to 8 MB each. The backend validates the image bytes, saves the file under `uploads/products`, and serves it from `/api/v1/media/products/`. Docker Compose mounts this directory as the persistent `product_media` volume, so uploaded photos survive backend container rebuilds. The frontend displays these API-hosted files directly instead of sending them through Next.js image optimization.

To back up product photos, back up the `product_media` volume along with the database. A database backup alone does not contain the uploaded image files.

## Run the full Docker stack

```bash
docker compose up --build
```

Services start in dependency order, each waiting for the previous to report healthy: `db` → `backend` → `frontend`.

The `db-backup` service takes a PostgreSQL custom-format dump at startup and every 24 hours into the persistent `postgres_backups` volume, retaining 14 days. Backups can be listed with `docker compose exec db-backup ls -lh /backups` and restored with `pg_restore` into a PostgreSQL database. Keep an off-host copy of this volume for disaster recovery; it is separate from `postgres_data`.

Then apply migrations and load demo data:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seeds.seed
```

The idempotent development seed includes 16 owner-photo products using the 17 files in `frontend/public/products/owner-uploaded/` (the green knit’s second photo is an alternate view). Re-run the seed with the same command to restore those demo records. To hide those products from the storefront while keeping any order history intact, run:

```bash
docker compose exec backend python -m app.seeds.remove_owner_photos
```

For a local backend, run `python -m app.seeds.seed` or `python -m app.seeds.remove_owner_photos` from `backend/`.

| Service | URL |
| --- | --- |
| Storefront | http://localhost:3000 |
| Shop | http://localhost:3000/shop |
| Bag | http://localhost:3000/cart |
| Checkout | http://localhost:3000/checkout |
| Wishlist | http://localhost:3000/wishlist |
| Account & orders | http://localhost:3000/account |
| Admin area | http://localhost:3000/admin |
| Admin orders | http://localhost:3000/admin/orders |
| Backend | http://localhost:8000 |
| FastAPI docs | http://localhost:8000/docs |
| Backend health | http://localhost:8000/api/v1/health |
| Frontend health (infrastructure) | http://localhost:3000/api/health |

Manage the stack:

```bash
docker compose ps          # includes each service's health state
docker compose logs -f     # follow logs
docker compose down        # stop and remove containers
docker compose down -v     # also delete the PostgreSQL volume (destroys local data)
```

## Run locally without Docker

### PostgreSQL

```bash
docker compose up -d db
```

Then point `DATABASE_URL` at `127.0.0.1` on whatever `POSTGRES_HOST_PORT` you set.

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
alembic upgrade head
python -m app.seeds.seed
uvicorn app.main:app --reload
```

Settings are read from `../.env` and `./.env`, so running from `backend/` picks up the repository-root `.env` automatically. Real environment variables always win.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Leave `API_INTERNAL_BASE_URL` unset outside Docker; server rendering then uses the public URL.

## Demo accounts

Created by the seed script for local development only. Override the passwords with `SEED_ADMIN_PASSWORD`, `SEED_STAFF_PASSWORD`, and `SEED_CUSTOMER_PASSWORD`.

| Role | Email | Password |
| --- | --- | --- |
| ADMIN | `admin@rgthriftinghub.pk` | `RgThrift!2026` |
| STAFF | `staff@rgthriftinghub.pk` | `RgThrift!2026` |
| CUSTOMER | `customer@rgthriftinghub.pk` | `RgThrift!2026` |

Sign in at `/account`. Admin and staff accounts can then open `/admin`. Each seeded account also gets a default delivery address, so checkout works immediately after seeding.

### Trying the shopping flow

1. Sign in as the customer and open `/shop/northbay-straight-leg-jeans-indigo` — this product is seeded with waist 30 → 5, waist 32 → 8, waist 34 → **0**, so you can see a single sold-out size disabled while the product stays purchasable.
2. Pick an available waist, add it to the bag, and open `/cart`.
3. Check out with Cash on Delivery or Bank Transfer. You land on `/checkout/success/<order number>`.
4. Follow the order at `/account/orders`, download its invoice, and cancel it while it is still pending to watch the stock return.
5. Sign in as the admin and manage the same order at `/admin/orders`, including its inventory impact.

## Tests and checks

Backend:

```bash
cd backend
pytest
```

Catalogue and order tests run against a real PostgreSQL database, because native enums, `NUMERIC` money, correlated `EXISTS` variant filters, case-insensitive search and — critically — `SELECT ... FOR UPDATE` row locking do not behave identically on SQLite. A dedicated `rg_thrifting_hub_test` database is created automatically on the same server, and each test runs inside a transaction that is rolled back afterwards.

The overselling tests in `tests/test_concurrency.py` are the exception: proving two simultaneous checkouts cannot both take the last unit needs two real connections that actually commit, so those tests create their own data, commit it, and delete it again in a `finally` block.

Point the suite elsewhere with `TEST_DATABASE_URL`. If no PostgreSQL server is reachable, the database-backed tests **skip** with a clear reason rather than passing silently.

Frontend:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

## Database migrations

```bash
cd backend
alembic upgrade head                                  # apply
alembic revision --autogenerate -m "describe change"  # after editing models
alembic downgrade -1                                  # step back
alembic current                                       # show applied revision
```

## Production deployment

The Compose setup builds both app images and stores PostgreSQL data and daily
database dumps in Docker volumes. For a production host, use a Linux VPS with
Docker Engine/Compose and a domain name, then:

1. Copy the project to the host and create `.env` from `.env.example`.
2. Set unique long random `SECRET_KEY`, `JWT_SECRET_KEY`, and PostgreSQL credentials;
   set `ENVIRONMENT=production`, the public HTTPS storefront in `CORS_ORIGINS`,
   and the public API base URL in `NEXT_PUBLIC_API_BASE_URL`.
3. Set `JAZZCASH_NUMBER`, `EASYPAISA_NUMBER`, and `PAYMENT_WHATSAPP_NUMBER` to the
   store's numbers. The WhatsApp number must be digits with country code, without `+`.
4. Configure a reverse proxy (such as Caddy or Nginx) to terminate HTTPS and route
   the storefront and API hostnames to ports 3000 and 8000. Do not expose PostgreSQL
   to the public internet.
5. Run `docker compose up --build -d`, then `docker compose exec backend alembic upgrade head`.
   Create the first admin account securely; do not seed demo accounts on production.
6. Confirm `/api/v1/health`, the storefront, customer checkout, admin sign-in, and
   that a dated dump appears in the `postgres_backups` volume after the first cycle.

Keep `.env` and database backup files outside public web roots and arrange a separate
off-host copy of backups. HTTPS certificates are supplied by the host reverse proxy;
the app containers do not issue certificates themselves.

Autogenerate does not drop the PostgreSQL enum types it creates, so a migration that adds an enum must drop it in `downgrade()` — otherwise re-upgrading fails with "type already exists". The Phase 2 migration shows the pattern.

## Demo imagery

The owner-photo product records use the owner-supplied files under `frontend/public/products/owner-uploaded/`. The accessories category and some brand/editorial fallback artwork still use the original generated placeholders under `frontend/public/demo/` and `frontend/public/editorial/`; the provided photos did not include accessories or brand assets.

To regenerate them (Pillow is a developer tool and deliberately not in `requirements.txt`):

```bash
cd backend
pip install pillow
python scripts/generate_demo_images.py
```

## Project layout

```
backend/
  app/api/v1/        routing (public, customer, admin), auth dependencies
  app/core/          settings, password hashing, JWT, business timezone
  app/db/            engine, session, declarative base
  app/models/        SQLAlchemy models and enums
  app/repositories/  queries: catalogue filters, admin order filters
  app/schemas/       Pydantic request/response models
  app/services/      cart, pricing, orders, inventory, returns, invoices, notifications
  app/seeds/         demo catalogue data and seeder
  app/assets/        server-side invoice logo
  alembic/           migrations
  scripts/           developer tools
  tests/             pytest suite
frontend/
  src/app/(store)/   storefront: shop, cart, checkout, account, wishlist
  src/app/admin/     admin: products, taxonomy, orders
  src/components/    ui, catalog, cart, checkout, orders, account, admin, providers
  src/lib/api/       typed API client (client, catalog, commerce)
  public/brand/      the official logo
  public/demo/       generated placeholder imagery
docs/                architecture documentation
```

See [docs/architecture.md](docs/architecture.md) for the system design.
