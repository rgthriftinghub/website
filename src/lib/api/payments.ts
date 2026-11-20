/**
 * Payment, shipping, and tracking API functions.
 *
 * Nothing here ever sends an amount or a status. The frontend can report a bank
 * reference and ask staff-side questions; the backend decides what a payment is
 * worth and whether it succeeded.
 */

import { apiRequest, buildQueryString, type QueryValue } from "@/lib/api/client";
import type {
  AdminPayment,
  BankAccount,
  CourierProvider,
  CourierStatus,
  Page,
  Payment,
  PaymentProviderStatus,
  PaymentQuery,
  PaymentStats,
  Refund,
  Shipment,
  ShippingMethod,
  ShippingStatus,
  TrackingResult,
} from "@/lib/api/types";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

// -------------------------------------------------------------- public config
export function listPaymentProviders(): Promise<PaymentProviderStatus[]> {
  return apiRequest<PaymentProviderStatus[]>("/payments/providers");
}

export function listBankAccounts(): Promise<BankAccount[]> {
  return apiRequest<BankAccount[]>("/payments/bank-accounts");
}

// ----------------------------------------------------------- customer payment
export function getMyOrderPayment(orderNumber: string): Promise<Payment> {
  return apiRequest<Payment>(
    `/customer/orders/${encodeURIComponent(orderNumber)}/payment`
  );
}

export function submitBankTransfer(
  orderNumber: string,
  payload: { reference: string; note?: string | null }
): Promise<Payment> {
  return apiRequest<Payment>(
    `/customer/orders/${encodeURIComponent(orderNumber)}/payment/bank-transfer`,
    { method: "POST", body: payload }
  );
}

// -------------------------------------------------------------------- tracking
export function trackOrder(
  orderNumber: string,
  contact: string
): Promise<TrackingResult> {
  return apiRequest<TrackingResult>("/track-order", {
    method: "POST",
    body: { order_number: orderNumber, contact },
  });
}

// -------------------------------------------------------------- admin payments
export function listAdminPayments(
  query: PaymentQuery = {}
): Promise<Page<AdminPayment>> {
  return apiRequest<Page<AdminPayment>>(
    `/admin/payments${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getAdminPaymentStats(): Promise<PaymentStats> {
  return apiRequest<PaymentStats>("/admin/payments/stats");
}

export function getAdminPayment(paymentId: string): Promise<AdminPayment> {
  return apiRequest<AdminPayment>(`/admin/payments/${paymentId}`);
}

export function verifyBankTransfer(
  paymentId: string,
  note?: string
): Promise<AdminPayment> {
  return apiRequest<AdminPayment>(
    `/admin/payments/${paymentId}/verify-bank-transfer`,
    { method: "POST", body: { note: note ?? null } }
  );
}

export function rejectBankTransfer(
  paymentId: string,
  reason: string
): Promise<AdminPayment> {
  return apiRequest<AdminPayment>(
    `/admin/payments/${paymentId}/reject-bank-transfer`,
    { method: "POST", body: { reason } }
  );
}

export function markCodCollected(
  paymentId: string,
  note?: string
): Promise<AdminPayment> {
  return apiRequest<AdminPayment>(
    `/admin/payments/${paymentId}/mark-cod-collected`,
    { method: "POST", body: { note: note ?? null } }
  );
}

export function requestRefund(
  paymentId: string,
  payload: { amount: string; reason: string }
): Promise<Refund> {
  return apiRequest<Refund>(`/admin/payments/${paymentId}/refunds`, {
    method: "POST",
    body: payload,
  });
}

export function completeRefund(refundId: string): Promise<Refund> {
  return apiRequest<Refund>(`/admin/payments/refunds/${refundId}/complete`, {
    method: "POST",
  });
}

// -------------------------------------------------------------- admin shipping
export function listShippingMethods(): Promise<ShippingMethod[]> {
  return apiRequest<ShippingMethod[]>("/admin/shipping/methods");
}

export function updateShippingMethod(
  methodId: string,
  payload: Partial<{
    name: string;
    description: string | null;
    price: string;
    free_threshold: string | null;
    is_active: boolean;
  }>
): Promise<ShippingMethod> {
  return apiRequest<ShippingMethod>(`/admin/shipping/methods/${methodId}`, {
    method: "PUT",
    body: payload,
  });
}

export function listCouriers(): Promise<CourierStatus[]> {
  return apiRequest<CourierStatus[]>("/admin/shipping/couriers");
}

export function getOrderShipment(orderId: string): Promise<Shipment> {
  return apiRequest<Shipment>(`/admin/shipping/orders/${orderId}`);
}

export function assignCourier(
  orderId: string,
  payload: {
    provider: CourierProvider;
    tracking_number?: string | null;
    shipment_reference?: string | null;
    tracking_url?: string | null;
    notes?: string | null;
  }
): Promise<Shipment> {
  return apiRequest<Shipment>(`/admin/shipping/orders/${orderId}/courier`, {
    method: "PUT",
    body: payload,
  });
}

export function updateShippingStatus(
  orderId: string,
  status: ShippingStatus,
  note?: string,
  location?: string
): Promise<Shipment> {
  return apiRequest<Shipment>(`/admin/shipping/orders/${orderId}/status`, {
    method: "PUT",
    body: { status, note: note ?? null, location: location ?? null },
  });
}

export function shippingLabelUrl(orderId: string): string {
  return `${API_BASE}/admin/shipping/orders/${orderId}/label.pdf`;
}
