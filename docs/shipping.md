# Shipping

## Integration status

| Provider | Status | Notes |
| --- | --- | --- |
| **Manual (staff-entered tracking)** | **LIVE** | Fully implemented. Staff book with the courier and record the tracking number. |
| TCS | **NOT CONFIGURED** | Selectable as a label only. No API integration. |
| Leopards | **NOT CONFIGURED** | Selectable as a label only. No API integration. |
| M&P | **NOT CONFIGURED** | Selectable as a label only. No API integration. |
| Trax | **NOT CONFIGURED** | Selectable as a label only. No API integration. |
| PostEx | **NOT CONFIGURED** | Selectable as a label only. No API integration. |

### Why no courier API is integrated

Same reason as the payment gateways: a real courier integration needs the
courier's official API documentation and merchant credentials — endpoint URLs,
authentication scheme, consignment payload, address format rules, label format,
and the tracking status vocabulary to map onto `ShippingStatus`. None of that was
available here.

Inventing it would produce shipments that *look* booked but were never lodged with
anyone, and a customer chasing a fabricated tracking number is a worse outcome
than an honest manual process.

**The MANUAL provider is not a stub.** It is a complete implementation of the
workflow most Pakistani sellers actually use today: staff book the consignment in
the courier's own portal, then record the number here. A tracking number exists in
this system only because a human entered one.

Selecting a named courier (TCS, Leopards, …) is still useful — it records *which*
courier is carrying the parcel — but its API methods refuse rather than pretend.

### Adding a real courier

Write one subclass of `BaseCourierProvider` in `backend/app/shipping_ops/base.py`
implementing `create_shipment`, `cancel_shipment`, `get_tracking`, and `get_label`
against the courier's official documentation, then register it. The shipment
record, admin screens, customer tracking, and status history already work through
that contract.

## Shipping configuration

Delivery pricing lives in the **database**, not in an environment variable and
never in frontend code.

`ShippingMethod` rows are admin-editable via
`GET|PUT /admin/shipping/methods`. `shipping_ops.service.delivery_charge()` reads
the active row for the requested method; when no active row exists it falls back
to `STANDARD_DELIVERY_CHARGE` / `FREE_DELIVERY_THRESHOLD` from the environment, so
a fresh database still prices correctly.

| Field | Meaning |
| --- | --- |
| `price` | Flat charge for this method. |
| `free_threshold` | Subtotal at or above which delivery is free. `NULL` means never free; `0` means always free. |
| `is_active` | Deactivating falls back to the environment default, not to free. |

The cart preview, the checkout summary, and the persisted order all call the same
function, so the three can never quote different amounts.

## Shipment records

```
Order 1──1 Shipment 1──* ShipmentEvent
```

One shipment per order. A future return shipment would add a `direction` column
rather than a second row of ambiguous meaning.

| Field | Purpose |
| --- | --- |
| `provider` | Which courier is carrying it. |
| `tracking_number` | Entered by staff, or returned by a courier API when one exists. |
| `shipment_id` | The courier's own consignment identifier, when it differs. |
| `shipping_status` | See below. |
| `label_url`, `tracking_url` | Optional links, when the courier supplies them. |
| `shipped_at`, `delivered_at` | Set automatically on the relevant transitions. |
| `provider_response` | Redacted courier API payload. `NULL` while manual. |

A shipment row is created automatically when an order is placed, inside the same
transaction, so every order has one from the start.

## Shipping status

`PENDING → READY → DISPATCHED → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED`, with
`RETURNED` and `CANCELLED` branches.

Enforced by `SHIPPING_STATUS_TRANSITIONS` in `app/models/enums.py`. The admin UI
mirrors the same table so it only offers legal moves.

Two guards worth noting:

- **A parcel cannot be marked dispatched without a tracking number.** Doing so
  would tell the customer it is on its way with nothing to track.
- **Shipping status never rewrites order status.** They are separate fields moving
  on separate clocks; an order can be `PROCESSING` while shipping is `PENDING`, or
  `DISPATCHED` while shipping is `IN_TRANSIT`. Advancing a shipment notifies the
  customer, it does not silently change their order.

## Admin workflow

On `/admin/orders/{id}`:

1. Choose the courier.
2. Paste the tracking number from the courier's portal (optionally a tracking URL
   and label URL).
3. Save — the shipment moves `PENDING → READY` automatically once a tracking
   number exists.
4. Advance the status as the parcel moves. Each change is recorded as a
   `ShipmentEvent` with the staff member who made it.

## Customer tracking

Two routes:

- **Signed in** — the shipping panel on `/account/orders/{orderNumber}` shows the
  progress rail, tracking number, courier, and full history.
- **Public** — `/track-order` accepts an order number **plus** a matching contact
  detail (the email or phone on the order). Phone matching ignores spacing and
  punctuation.

The public response is deliberately narrow: status, item names, and courier
tracking. **No address, no prices, no customer name.**

A wrong contact detail and a non-existent order produce the *identical* error, so
the endpoint cannot be used to discover which order numbers exist. `/track-order`
is also `noindex`, so crawlers are not invited to probe it.

## Endpoints

**Public** — `POST /track-order`

**Admin** — `GET /admin/shipping/methods` · `PUT /admin/shipping/methods/{id}` ·
`GET /admin/shipping/couriers` · `GET /admin/shipping/orders/{order_id}` ·
`PUT /admin/shipping/orders/{order_id}/courier` ·
`PUT /admin/shipping/orders/{order_id}/status`

## Environment variables

```
STANDARD_DELIVERY_CHARGE=250.00      # fallback when no ShippingMethod row is active
FREE_DELIVERY_THRESHOLD=10000.00     # 0 disables free delivery

COURIER_PROVIDER=manual              # only "manual" is implemented
COURIER_API_KEY=                     # read but unused; no courier API exists
COURIER_API_URL=
```
