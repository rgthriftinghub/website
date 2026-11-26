/**
 * Admin analytics, sales, bulk operations, reports, and import.
 *
 * Every number displayed by the dashboard comes from these endpoints already
 * aggregated. Nothing in the frontend totals, averages, or discounts anything.
 */

import { apiRequest, buildQueryString, type QueryValue } from "@/lib/api/client";
import type {
  ActivityLogEntry,
  AdminNotificationList,
  BulkResult,
  CustomerDetail,
  CustomerNote,
  CustomerRow,
  DashboardSummary,
  DateRangeQuery,
  ImportBatch,
  InventoryMovement,
  InventorySummary,
  OrderAnalytics,
  Page,
  Permission,
  PricePreview,
  ProductPerformanceRow,
  Sale,
  SaleInput,
  SalesAnalytics,
  StaffMember,
  StockAlertRow,
  StockRow,
} from "@/lib/api/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL!.replace(/\/+$/, "");

export interface AdminAccess {
  role: "ADMIN" | "STAFF";
  permissions: Permission[];
}

export function getAdminAccess(): Promise<AdminAccess> {
  return apiRequest<AdminAccess>("/admin/me/access");
}

export interface AdminCoupon {
  id: string; code: string; discount_type: "PERCENTAGE" | "FIXED_AMOUNT";
  discount_value: string; minimum_order: string; max_redemptions: number | null;
  redemption_count: number; starts_at: string | null; ends_at: string | null;
  is_active: boolean; created_at: string; updated_at: string;
}
export function listCoupons(): Promise<AdminCoupon[]> { return apiRequest("/admin/coupons"); }
export function createCoupon(payload: Omit<AdminCoupon,"id"|"redemption_count"|"created_at"|"updated_at">): Promise<AdminCoupon> { return apiRequest("/admin/coupons",{method:"POST",body:payload}); }
export function deleteCoupon(id:string): Promise<{detail:string}> { return apiRequest(`/admin/coupons/${id}`,{method:"DELETE"}); }

// ------------------------------------------------------------------ analytics
export function getDashboard(query: DateRangeQuery = {}): Promise<DashboardSummary> {
  return apiRequest<DashboardSummary>(
    `/admin/analytics/dashboard${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getSalesAnalytics(
  query: DateRangeQuery & { granularity?: string; brand_sort?: string } = {}
): Promise<SalesAnalytics> {
  return apiRequest<SalesAnalytics>(
    `/admin/analytics/sales${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getProductAnalytics(
  query: DateRangeQuery & { sort?: string; page?: number; page_size?: number } = {}
): Promise<Page<ProductPerformanceRow>> {
  return apiRequest<Page<ProductPerformanceRow>>(
    `/admin/analytics/products${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getInventoryAnalytics(): Promise<InventorySummary> {
  return apiRequest<InventorySummary>("/admin/analytics/inventory");
}

export function getInventoryAlerts(
  outOfStock: boolean,
  page = 1,
  pageSize = 50
): Promise<Page<StockAlertRow>> {
  return apiRequest<Page<StockAlertRow>>(
    `/admin/analytics/inventory/alerts${buildQueryString({
      out_of_stock: outOfStock,
      page,
      page_size: pageSize,
    })}`
  );
}

export function getCustomerAnalytics(query: DateRangeQuery = {}) {
  return apiRequest<DashboardSummary["customers"]>(
    `/admin/analytics/customers${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getOrderAnalytics(query: DateRangeQuery = {}): Promise<OrderAnalytics> {
  return apiRequest<OrderAnalytics>(
    `/admin/analytics/orders${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

// ---------------------------------------------------------------------- sales
export function listSales(
  query: { status?: string; search?: string; page?: number; page_size?: number } = {}
): Promise<Page<Sale>> {
  return apiRequest<Page<Sale>>(
    `/admin/sales${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getSale(saleId: string): Promise<Sale> {
  return apiRequest<Sale>(`/admin/sales/${saleId}`);
}

export function createSale(payload: SaleInput): Promise<Sale> {
  return apiRequest<Sale>("/admin/sales", { method: "POST", body: payload });
}

export function updateSale(saleId: string, payload: Partial<SaleInput>): Promise<Sale> {
  return apiRequest<Sale>(`/admin/sales/${saleId}`, { method: "PUT", body: payload });
}

export function setSaleActive(saleId: string, active: boolean): Promise<Sale> {
  return apiRequest<Sale>(
    `/admin/sales/${saleId}/${active ? "activate" : "deactivate"}`,
    { method: "POST" }
  );
}

export function deleteSale(saleId: string): Promise<{ detail: string }> {
  return apiRequest(`/admin/sales/${saleId}`, { method: "DELETE" });
}

// ------------------------------------------------------------------ bulk ops
export function bulkUpdateProducts(payload: {
  product_ids: string[];
  is_active?: boolean;
  is_featured?: boolean;
  is_new_arrival?: boolean;
  category_id?: string;
  subcategory_id?: string;
  brand_id?: string;
}): Promise<BulkResult> {
  return apiRequest<BulkResult>("/admin/bulk/products", { method: "POST", body: payload });
}

type PriceBody = {
  product_ids?: string[];
  category_id?: string;
  brand_id?: string;
  mode: string;
  value: string;
  field?: "regular_price" | "sale_price";
};

export function previewPrices(payload: PriceBody): Promise<PricePreview> {
  return apiRequest<PricePreview>("/admin/bulk/prices/preview", {
    method: "POST",
    body: payload,
  });
}

export function applyPrices(payload: PriceBody): Promise<BulkResult> {
  return apiRequest<BulkResult>("/admin/bulk/prices/apply", {
    method: "POST",
    body: payload,
  });
}

export function bulkUpdateStock(payload: {
  adjustments: { variant_id: string; mode: "add" | "remove" | "set"; quantity: number }[];
  reason: string;
}): Promise<BulkResult> {
  return apiRequest<BulkResult>("/admin/bulk/stock", { method: "POST", body: payload });
}

export function getSelectionVariants(productIds: string[]) {
  return apiRequest<
    {
      variant_id: string;
      sku: string;
      size: string | null;
      waist: number | null;
      product_name: string;
      quantity: number;
    }[]
  >(`/admin/bulk/variants${buildQueryString({ product_ids: productIds })}`);
}

// ---------------------------------------------------------- activity + alerts
export function listActivity(
  query: { action?: string; entity_type?: string; page?: number; page_size?: number } = {}
): Promise<Page<ActivityLogEntry>> {
  return apiRequest<Page<ActivityLogEntry>>(
    `/admin/activity${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function listNotifications(unreadOnly = false): Promise<AdminNotificationList> {
  return apiRequest<AdminNotificationList>(
    `/admin/notifications${buildQueryString({ unread_only: unreadOnly })}`
  );
}

export function scanStockAlerts(): Promise<Record<string, number>> {
  return apiRequest("/admin/notifications/scan", { method: "POST" });
}

export function markNotificationRead(id: string): Promise<{ detail: string }> {
  return apiRequest(`/admin/notifications/${id}/read`, { method: "POST" });
}

export function markAllNotificationsRead(): Promise<{ detail: string }> {
  return apiRequest("/admin/notifications/read-all", { method: "POST" });
}

// ----------------------------------------------------------------- staff + customers
export function listStaff(): Promise<StaffMember[]> {
  return apiRequest<StaffMember[]>("/admin/staff");
}

export function setStaffPermissions(
  userId: string,
  permissions: Permission[]
): Promise<StaffMember> {
  return apiRequest<StaffMember>(`/admin/staff/${userId}/permissions`, {
    method: "PUT",
    body: { permissions },
  });
}

export function listCustomers(
  query: { search?: string; page?: number; page_size?: number } = {}
): Promise<Page<CustomerRow>> {
  return apiRequest<Page<CustomerRow>>(
    `/admin/customers${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function listCustomerNotes(customerId: string): Promise<CustomerNote[]> {
  return apiRequest<CustomerNote[]>(`/admin/customers/${customerId}/notes`);
}

export function addCustomerNote(customerId: string, body: string): Promise<CustomerNote> {
  return apiRequest<CustomerNote>(`/admin/customers/${customerId}/notes`, {
    method: "POST",
    body: { body },
  });
}

// --------------------------------------------------------------------- reports
export function listDatasets(): Promise<{ key: string; label: string }[]> {
  return apiRequest("/admin/reports/datasets");
}

/**
 * Export URLs are returned rather than fetched, so the browser downloads the file
 * directly and sends the session cookie with the request.
 */
export function exportUrl(
  dataset: string,
  format: "csv" | "xlsx",
  query: DateRangeQuery & { granularity?: string; include_inactive?: boolean } = {}
): string {
  return `${API_BASE}/admin/reports/export/${dataset}.${format}${buildQueryString(
    query as Record<string, QueryValue>
  )}`;
}

export function importTemplateUrl(): string {
  return `${API_BASE}/admin/reports/import/template.csv`;
}

export function importErrorReportUrl(batchId: string): string {
  return `${API_BASE}/admin/reports/import/${batchId}/errors.csv`;
}

/** Multipart upload, so this bypasses the JSON apiRequest helper. */
export async function uploadImport(file: File): Promise<ImportBatch> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/admin/reports/import`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? "Upload failed");
  }
  return response.json();
}

export function commitImport(batchId: string): Promise<ImportBatch> {
  return apiRequest<ImportBatch>(`/admin/reports/import/${batchId}/commit`, {
    method: "POST",
  });
}

export function cancelImport(batchId: string): Promise<{ detail: string }> {
  return apiRequest(`/admin/reports/import/${batchId}/cancel`, { method: "POST" });
}

// ------------------------------------------------------------------ inventory
export function listStock(
  query: { search?: string; status?: string; page?: number; page_size?: number } = {}
): Promise<Page<StockRow>> {
  return apiRequest<Page<StockRow>>(
    `/admin/inventory${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function adjustVariantStock(
  variantId: string,
  payload: {
    mode: "add" | "remove" | "set";
    quantity: number;
    reason: string;
    low_stock_threshold?: number;
  }
): Promise<StockRow> {
  return apiRequest<StockRow>(`/admin/inventory/variants/${variantId}/adjust`, {
    method: "POST",
    body: payload,
  });
}

export function listInventoryHistory(
  query: {
    search?: string;
    type?: string;
    variant_id?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  } = {}
): Promise<Page<InventoryMovement>> {
  return apiRequest<Page<InventoryMovement>>(
    `/admin/inventory/history${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getCustomerDetail(customerId: string): Promise<CustomerDetail> {
  return apiRequest<CustomerDetail>(`/admin/customers/${customerId}`);
}
