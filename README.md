# RG Thrifting Hub Website

The customer storefront and staff/admin interface for RG Thrifting Hub. This repository contains the **Next.js frontend**; product, account, order, inventory, and payment data come from the separate FastAPI backend.

## What’s included

- Storefront, searchable catalogue, category and brand pages, and product galleries
- Cart, checkout, wishlists, customer accounts, order history, and order tracking
- Admin pages for products, categories, inventory, orders, payments, customers, reports, and staff permissions
- Mobile responsive navigation and layouts
- Direct browser loading for API-served product images, avoiding the frontend image optimizer for backend media URLs

## Stack

- Next.js 16 App Router and React 19
- TypeScript and Tailwind CSS 4
- FastAPI backend API (configured separately)

## Requirements

- Node.js 22 or newer
- npm
- A running RG Thrifting Hub API for storefront data and admin actions

## Local setup

Install dependencies:

```bash
npm ci
```

Set the API URL the browser can reach. In PowerShell:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000/api/v1"
$env:API_INTERNAL_BASE_URL = "http://localhost:8000/api/v1"
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). `NEXT_PUBLIC_API_BASE_URL` is included in the browser bundle at build time, so set it to the public API address before building. Never put secrets in a `NEXT_PUBLIC_` variable.

When the frontend runs in Docker, set `API_INTERNAL_BASE_URL` to the backend service address (for example, `http://backend:8000/api/v1`) for server-side rendering. Keep `NEXT_PUBLIC_API_BASE_URL` pointed at the address browsers can reach.

## Useful routes

| Page | Path |
| --- | --- |
| Storefront | `/` |
| Shop | `/shop` |
| Product | `/shop/[slug]` |
| Cart | `/cart` |
| Checkout | `/checkout` |
| Wishlist | `/wishlist` |
| Account and orders | `/account` |
| Track an order | `/track-order` |
| Admin dashboard | `/admin` |

Admin pages require an authenticated staff or admin account with the appropriate backend permissions.

## Checks

```bash
npm run lint
npm run typecheck
npm run build
```

## Docker

The included Dockerfile builds a standalone Next.js server. Pass the browser-facing API URL at build time:

```bash
docker build --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com/api/v1 -t rg-thrifting-hub-frontend .
```

At runtime, set `API_INTERNAL_BASE_URL` if the frontend container can reach the backend through an internal service address. The API backend and its database/storage are managed separately from this repository.
