# Security and test work status

## Changes made

- Audited the API router groupings and customer resource services. Customer cart and wishlist routers require a session; customer order, invoice, payment, and address services scope record queries by the authenticated user ID. Admin routes inherit `require_staff`, with operation-specific permission checks in the sensitive admin handlers. Public order tracking requires order number plus matching contact detail and already has a request limiter. No missing customer ownership check was found in the inspected flows.
- Added a process-local limit of five requests per minute per IP and endpoint to registration and login. There is no password-reset endpoint in this application, so there is no reset route to throttle yet.
- Added security response headers: `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, and HSTS on HTTPS production requests.
- Disabled FastAPI docs, ReDoc, and OpenAPI schema endpoints when `ENVIRONMENT=production`.
- Sanitized dangerous formula-leading prefixes in text fields parsed from CSV/XLSX imports. Numeric and boolean fields are left as parsed so legitimate numeric values are preserved.
- Added webhook amount comparison when a provider supplies an amount. A mismatch is recorded as rejected and does not change payment state.
- Added auth limiter/header/admin-access and CSV/XLSX formula sanitization tests, and an amount-mismatch webhook test. Existing tests already cover login/session behavior, cart, checkout, webhook signatures/duplicates, and admin authorization.
- Updated frontend `next` and `eslint-config-next` semver ranges to `^16.4.6` based on the current npm package listing. The npm registry command could not complete in this environment, so `package-lock.json` remains on 16.3.0 and must be refreshed with `npm install --package-lock-only` in a network-enabled environment.
- Added `loadtest/store.js`, parameterized by `BASE_URL`, with the requested user mix and stages at 10, 25, and 50 VUs. Checkout creates orders; only use a disposable local/staging account and database.

## Not run / not verified

No tests, Docker commands, frontend build, audit, or load test were run, as requested. The added tests are authored but unexecuted. Production HSTS behavior depends on the app seeing HTTPS (`X-Forwarded-Proto` must be correctly set by the trusted proxy). The in-memory limiter is per worker/process and requires trusted proxy address forwarding to distinguish client IPs behind Nginx. PayFast/Safepay provider implementations remain intentionally unconfigured in this repository; their real signatures cannot be tested here. Webhook amount is checked when the provider parser supplies one; real providers must populate it.

## Prioritized follow-up

### Must do before production

1. In a network-enabled frontend checkout, run `npm install --package-lock-only` and confirm both packages resolve to 16.4.6 or a later patched 16.x release.
2. Run the new and existing backend tests against the dedicated test database; address failures.
3. Ensure Uvicorn trusts only the local Nginx proxy for forwarded IP/scheme headers, then confirm client rate limiting and HTTPS HSTS in staging.
4. Verify gateway webhook parsers supply and validate amount and currency against the stored payment before settlement.

### Should do

1. Add password reset with a separate rate-limited flow if reset functionality is introduced.
2. Replace the in-memory auth limiter with shared storage before running multiple API workers/instances.
3. Keep checking new API routes for explicit router-level authentication and user-scoped database queries.

### Nice to have

1. Add automated API-route inventory checks to ensure private routes stay under authenticated/admin router groups.
2. Run the staged k6 script with disposable data and record latency, error rate, CPU, memory, and database connections.
