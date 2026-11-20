/**
 * Cart, wishlist, address, checkout, and order API functions.
 *
 * All of these are per-customer and rely on the HTTP-only session cookie, so
 * they are called from the browser rather than during server rendering — server
 * rendering has no cookie jar to send.
 */

import { apiRequest, buildQueryString, type QueryValue } from "@/lib/api/client";
import type {
  AddressInput,
  Address,
  AdminOrder,
  AdminOrderQuery,
  AdminOrderSummary,
  AdminReturnRequest,
  Cart,
  CheckoutConfig,
  CheckoutInput,
  InventoryTransaction,
  Order,
  OrderStats,
  OrderStatus,
  OrderSummary,
  Page,
  PaymentStatus,
  ReturnRequest,
  ReturnRequestType,
} from "@/lib/api/types";

// ---------------------------------------------------------------------- cart
export function getCart(): Promise<Cart> {
  return apiRequest<Cart>("/cart");
}

export function addToCart(productVariantId: string, quantity = 1): Promise<Cart> {
  return apiRequest<Cart>("/cart/items", {
    method: "POST",
    body: { product_variant_id: productVariantId, quantity },
  });
}

export function updateCartItem(itemId: string, quantity: number): Promise<Cart> {
  return apiRequest<Cart>(`/cart/items/${itemId}`, { method: "PUT", body: { quantity } });
}

export function removeCartItem(itemId: string): Promise<Cart> {
  return apiRequest<Cart>(`/cart/items/${itemId}`, { method: "DELETE" });
}

export function clearCart(): Promise<Cart> {
  return apiRequest<Cart>("/cart", { method: "DELETE" });
}

// ------------------------------------------------------------------ wishlist
export function getWishlist(): Promise<{
  items: { id: string; created_at: string; product: import("@/lib/api/types").ProductListItem }[];
  total: number;
}> {
  return apiRequest("/wishlist");
}

export function getWishlistIds(): Promise<string[]> {
  return apiRequest<string[]>("/wishlist/ids");
}

export function addToWishlist(productId: string): Promise<{ detail: string }> {
  return apiRequest(`/wishlist/${productId}`, { method: "POST" });
}

export function removeFromWishlist(productId: string): Promise<{ detail: string }> {
  return apiRequest(`/wishlist/${productId}`, { method: "DELETE" });
}

// ----------------------------------------------------------------- addresses
export function listAddresses(): Promise<Address[]> {
  return apiRequest<Address[]>("/customer/addresses");
}

export function createAddress(payload: AddressInput): Promise<Address> {
  return apiRequest<Address>("/customer/addresses", { method: "POST", body: payload });
}

export function updateAddress(id: string, payload: Partial<AddressInput>): Promise<Address> {
  return apiRequest<Address>(`/customer/addresses/${id}`, { method: "PUT", body: payload });
}

export function deleteAddress(id: string): Promise<void> {
  return apiRequest<void>(`/customer/addresses/${id}`, { method: "DELETE" });
}

// ------------------------------------------------------------------ checkout
export function getCheckoutConfig(): Promise<CheckoutConfig> {
  return apiRequest<CheckoutConfig>("/checkout/config");
}

export function placeOrder(payload: CheckoutInput): Promise<Order> {
  return apiRequest<Order>("/checkout", { method: "POST", body: payload });
}

// -------------------------------------------------------------------- orders
export function listMyOrders(page = 1, pageSize = 12): Promise<Page<OrderSummary>> {
  return apiRequest<Page<OrderSummary>>(
    `/customer/orders${buildQueryString({ page, page_size: pageSize })}`
  );
}

export function getMyOrder(orderNumber: string): Promise<Order> {
  return apiRequest<Order>(`/customer/orders/${encodeURIComponent(orderNumber)}`);
}

export function cancelMyOrder(orderNumber: string, reason?: string): Promise<Order> {
  return apiRequest<Order>(`/customer/orders/${encodeURIComponent(orderNumber)}/cancel`, {
    method: "POST",
    body: { reason: reason ?? null },
  });
}

export function requestReturn(
  orderNumber: string,
  payload: { type: ReturnRequestType; reason: string; description?: string }
): Promise<ReturnRequest> {
  return apiRequest<ReturnRequest>(
    `/customer/orders/${encodeURIComponent(orderNumber)}/returns`,
    { method: "POST", body: payload }
  );
}

/**
 * Invoice URLs are returned rather than fetched, so the browser can open the PDF
 * directly and send the session cookie with the request.
 */
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(
  /\/+$/,
  ""
);

export function myInvoiceUrl(orderNumber: string): string {
  return `${API_BASE}/customer/orders/${encodeURIComponent(orderNumber)}/invoice`;
}

export function adminInvoiceUrl(orderId: string): string {
  return `${API_BASE}/admin/orders/${orderId}/invoice`;
}

// --------------------------------------------------------------- admin orders
export function listAdminOrders(query: AdminOrderQuery = {}): Promise<Page<AdminOrderSummary>> {
  return apiRequest<Page<AdminOrderSummary>>(
    `/admin/orders${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getAdminOrder(orderId: string): Promise<AdminOrder> {
  return apiRequest<AdminOrder>(`/admin/orders/${orderId}`);
}

export function getAdminOrderStats(): Promise<OrderStats> {
  return apiRequest<OrderStats>("/admin/orders/stats");
}

export function getOrderInventoryImpact(orderId: string): Promise<InventoryTransaction[]> {
  return apiRequest<InventoryTransaction[]>(`/admin/orders/${orderId}/inventory`);
}

export function updateOrderStatus(
  orderId: string,
  status: OrderStatus,
  note?: string
): Promise<AdminOrder> {
  return apiRequest<AdminOrder>(`/admin/orders/${orderId}/status`, {
    method: "PUT",
    body: { status, note: note ?? null },
  });
}

export function updateOrderPaymentStatus(
  orderId: string,
  paymentStatus: PaymentStatus,
  note?: string
): Promise<AdminOrder> {
  return apiRequest<AdminOrder>(`/payments/manual-status/${orderId}`, {
    method: "POST",
    body: { payment_status: paymentStatus, note: note ?? null },
  });
}

export function updateOrderInternalNote(
  orderId: string,
  internalNote: string | null
): Promise<AdminOrder> {
  return apiRequest<AdminOrder>(`/admin/orders/${orderId}/note`, {
    method: "PUT",
    body: { internal_note: internalNote },
  });
}

export function listAdminReturnRequests(
  status?: string
): Promise<Page<AdminReturnRequest>> {
  return apiRequest<Page<AdminReturnRequest>>(
    `/admin/orders/returns${buildQueryString({ status })}`
  );
}

export function decideReturnRequest(
  requestId: string,
  status: string,
  resolutionNote?: string
): Promise<AdminReturnRequest> {
  return apiRequest<AdminReturnRequest>(`/admin/orders/returns/${requestId}`, {
    method: "PUT",
    body: { status, resolution_note: resolutionNote ?? null },
  });
}
