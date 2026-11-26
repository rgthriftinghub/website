/**
 * Types mirroring the FastAPI response schemas.
 *
 * Money arrives as a decimal string (the backend uses NUMERIC, never float), so
 * it stays a string here and is formatted for display rather than parsed into a
 * lossy JS number.
 */

export type ProductCondition = "PREMIUM_PLUS" | "PREMIUM" | "EXCELLENT" | "GOOD";
export type Gender = "MEN" | "WOMEN" | "UNISEX" | "KIDS";
export type UserRole = "CUSTOMER" | "ADMIN" | "STAFF";

export type ProductType =
  | "SHIRT"
  | "T_SHIRT"
  | "POLO"
  | "JEANS"
  | "TROUSERS"
  | "SHORTS"
  | "JACKET"
  | "HOODIE"
  | "SWEATER"
  | "DRESS"
  | "KURTA"
  | "ABAYA"
  | "SKIRT"
  | "ACTIVEWEAR"
  | "FOOTWEAR"
  | "ACCESSORY";

export type ProductSort = "newest" | "price_low" | "price_high" | "best_selling" | "highest_rated";
export type Availability = "in_stock" | "out_of_stock";

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface BrandSummary {
  id: string;
  name: string;
  slug: string;
}

export interface Brand extends BrandSummary {
  description: string | null;
  logo_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CategorySummary {
  id: string;
  name: string;
  slug: string;
}

export interface Subcategory extends CategorySummary {
  category_id: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface Category extends CategorySummary {
  description: string | null;
  image_url: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
  /** Always returned by the category endpoints, so nav and filters need one call. */
  subcategories: Subcategory[];
}

export type CategoryDetail = Category;

export interface ProductImage {
  id: string;
  image_url: string;
  alt_text: string | null;
  sort_order: number;
  is_primary: boolean;
}

export interface ProductVariant {
  id: string;
  sku: string;
  size: string | null;
  waist: number | null;
  color: string | null;
  variant_name: string | null;
  price_override: string | null;
  sale_price_override: string | null;
  is_active: boolean;
  label: string;
  quantity: number;
  in_stock: boolean;
  is_low_stock: boolean;
}

/**
 * Campaign pricing resolved by the backend.
 *
 * `effective_price` on the product already reflects the winning campaign, so the
 * frontend never applies a discount itself. This carries the extra detail a badge
 * or countdown needs.
 */
export interface SalePricing {
  original_price: string;
  final_price: string;
  discount_amount: string;
  discount_percent: number;
  sale_id: string | null;
  sale_name: string | null;
  sale_type: "STANDARD" | "FLASH" | "CLEARANCE" | "SEASONAL" | null;
  badge_text: string | null;
  /** Drives the countdown. Presentation only; the server decides if the sale applies. */
  ends_at: string | null;
}

export interface ProductListItem {
  id: string;
  name: string;
  slug: string;
  short_description: string | null;
  sku: string;
  item_code: string;
  single_piece: boolean;
  regular_price: string;
  sale_price: string | null;
  effective_price: string;
  is_on_sale: boolean;
  discount_percent: number;
  condition: ProductCondition;
  gender: Gender;
  product_type: ProductType;
  color: string | null;
  fabric: string | null;
  is_featured: boolean;
  is_new_arrival: boolean;
  is_active: boolean;
  in_stock: boolean;
  total_stock: number;
  created_at: string;
  brand: BrandSummary | null;
  category: CategorySummary;
  subcategory: CategorySummary | null;
  images: ProductImage[];
  /** Null when no campaign covers this product. */
  sale_pricing: SalePricing | null;
  average_rating: number;
  review_count: number;
}

export interface ProductDetail extends ProductListItem {
  description: string | null;
  seo_title: string | null;
  meta_description: string | null;
  barcode: string | null;
  updated_at: string;
  variants: ProductVariant[];
}

export interface ProductAdmin extends ProductDetail {
  brand_id: string | null;
  category_id: string;
  subcategory_id: string | null;
}

export interface FilterOptions {
  colors: string[];
  fabrics: string[];
  sizes: string[];
  waists: number[];
  min_price: number | null;
  max_price: number | null;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at: string | null;
}

// ------------------------------------------------------------------ commerce
export type PaymentMethod =
  | "COD"
  | "BANK_TRANSFER"
  | "JAZZCASH"
  | "EASYPAISA"
  | "PAYFAST"
  | "SAFEPAY";

export type PaymentStatus =
  | "PENDING"
  | "PROCESSING"
  | "PAID"
  | "FAILED"
  | "CANCELLED"
  | "REFUNDED";

/** Which integration settles a payment, as distinct from the customer's choice. */
export type PaymentProvider =
  | "COD"
  | "BANK_TRANSFER"
  | "PAYFAST"
  | "SAFEPAY"
  | "JAZZCASH"
  | "EASYPAISA";

export type PaymentTransactionEvent =
  | "INITIATED"
  | "REDIRECTED"
  | "CALLBACK_RECEIVED"
  | "WEBHOOK_RECEIVED"
  | "WEBHOOK_DUPLICATE"
  | "WEBHOOK_REJECTED"
  | "VERIFIED"
  | "FAILED"
  | "CANCELLED"
  | "PROOF_SUBMITTED"
  | "MANUALLY_VERIFIED"
  | "MANUALLY_REJECTED"
  | "REFUND_REQUESTED"
  | "REFUNDED";

export type RefundStatus = "REQUESTED" | "PROCESSING" | "COMPLETED" | "FAILED";

export type CourierProvider =
  | "MANUAL"
  | "TCS"
  | "LEOPARDS"
  | "MP"
  | "TRAX"
  | "POSTEX";

export type ShippingStatus =
  | "PENDING"
  | "READY"
  | "DISPATCHED"
  | "IN_TRANSIT"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED"
  | "RETURNED"
  | "CANCELLED";

export type OrderStatus =
  | "PENDING"
  | "PROCESSING"
  | "PACKED"
  | "DISPATCHED"
  | "DELIVERED"
  | "CANCELLED"
  | "RETURNED"
  | "EXCHANGE";

export type DeliveryMethod = "STANDARD";
export type ReturnRequestType = "RETURN" | "EXCHANGE";
export type ReturnRequestStatus = "REQUESTED" | "APPROVED" | "REJECTED" | "COMPLETED";

export interface Address {
  id: string;
  full_name: string;
  phone: string;
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  province: string;
  postal_code: string | null;
  country: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export type AddressInput = Omit<Address, "id" | "created_at" | "updated_at">;

/** Address as frozen onto an order — no id, so it cannot be confused with a live row. */
export type AddressSnapshot = Omit<
  Address,
  "id" | "created_at" | "updated_at" | "is_default"
>;

export interface CartItem {
  id: string;
  product_id: string;
  product_name: string;
  product_slug: string;
  brand_name: string | null;
  image_url: string | null;
  product_variant_id: string;
  variant_label: string;
  sku: string;
  size: string | null;
  waist: number | null;
  color: string | null;
  unit_price: string;
  quantity: number;
  line_total: string;
  available_stock: number;
  is_available: boolean;
  unavailable_reason: string | null;
}

export interface Cart {
  id: string | null;
  items: CartItem[];
  item_count: number;
  subtotal: string;
  delivery_amount: string;
  total: string;
  currency: string;
  has_unavailable_items: boolean;
}

export interface CheckoutConfig {
  currency: string;
  standard_delivery_charge: string;
  free_delivery_threshold: string | null;
  payment_methods: PaymentMethod[];
  delivery_methods: DeliveryMethod[];
  max_quantity_per_item: number;
  jazzcash_number: string | null;
  easypaisa_number: string | null;
  payment_whatsapp_number: string | null;
}

export interface CheckoutInput {
  address_id: string;
  payment_method: PaymentMethod;
  delivery_method?: DeliveryMethod;
  contact_email?: string;
  contact_phone?: string;
  customer_note?: string;
  coupon_code?: string;
}

export interface GuestCartLine {
  product_variant_id: string;
  quantity: number;
}

export interface GuestDeliveryInput {
  full_name: string;
  phone: string;
  address_line_1: string;
  address_line_2?: string;
  city: string;
  province?: string;
  postal_code?: string;
  country?: string;
}

export interface GuestCheckoutInput {
  items: GuestCartLine[];
  delivery: GuestDeliveryInput;
  payment_method: "COD";
  delivery_method?: DeliveryMethod;
  contact_email?: string;
  customer_note?: string;
  coupon_code?: string;
}

export interface OrderItem {
  id: string;
  product_id: string | null;
  product_variant_id: string | null;
  product_name_snapshot: string;
  product_slug_snapshot: string;
  brand_name_snapshot: string | null;
  sku_snapshot: string;
  variant_snapshot: Record<string, unknown>;
  variant_label: string;
  image_url_snapshot: string | null;
  unit_price: string;
  quantity: number;
  line_total: string;
}

export interface OrderStatusEvent {
  id: string;
  status: OrderStatus;
  note: string | null;
  created_at: string;
}

export interface ReturnRequest {
  id: string;
  type: ReturnRequestType;
  reason: string;
  description: string | null;
  status: ReturnRequestStatus;
  created_at: string;
  updated_at: string;
}

export interface OrderSummary {
  id: string;
  order_number: string;
  order_status: OrderStatus;
  payment_status: PaymentStatus;
  payment_method: PaymentMethod;
  coupon_code: string | null;
  total_amount: string;
  item_count: number;
  created_at: string;
}

export interface Order extends OrderSummary {
  contact_email: string | null;
  contact_phone: string;
  shipping_address_snapshot: AddressSnapshot;
  billing_address_snapshot: AddressSnapshot | null;
  delivery_method: DeliveryMethod;
  subtotal: string;
  discount_amount: string;
  shipping_amount: string;
  customer_note: string | null;
  cancelled_at: string | null;
  updated_at: string;
  is_cancellable_by_customer: boolean;
  items: OrderItem[];
  status_events: OrderStatusEvent[];
  return_requests: ReturnRequest[];
  /** Shipping progresses independently of order status. */
  shipment: Shipment | null;
  /** The active payment. Carries no gateway payload or staff notes. */
  payment: Payment | null;
}

export interface OrderCustomer {
  id: string | null;
  email: string | null;
  first_name: string;
  last_name: string;
  is_guest: boolean;
}

export interface AdminOrderSummary extends OrderSummary {
  customer: OrderCustomer;
}

export interface AdminOrder extends Order {
  customer: OrderCustomer;
  internal_note: string | null;
}

export interface AdminReturnRequest extends ReturnRequest {
  order_id: string;
  order_number: string;
  resolution_note: string | null;
}

export interface InventoryTransaction {
  id: string;
  product_variant_id: string;
  type: string;
  quantity_change: number;
  quantity_before: number;
  quantity_after: number;
  reference_type: string | null;
  reference_id: string | null;
  note: string | null;
  created_at: string;
}

export interface OrderStats {
  total_orders: number;
  status_counts: Record<string, number>;
  revenue_total: number;
}

export interface AdminOrderQuery {
  status?: OrderStatus;
  payment_status?: PaymentStatus;
  date_from?: string;
  date_to?: string;
  customer?: string;
  order_number?: string;
  page?: number;
  page_size?: number;
}

/** Query parameters accepted by the product listing endpoint. */
export interface ProductQuery {
  category?: string;
  subcategory?: string;
  brand?: string;
  gender?: Gender;
  condition?: ProductCondition;
  product_type?: ProductType;
  color?: string;
  fabric?: string;
  is_featured?: boolean;
  is_new_arrival?: boolean;
  min_price?: string | number;
  max_price?: string | number;
  size?: string;
  waist?: number;
  availability?: Availability;
  search?: string;
  sort?: ProductSort;
  page?: number;
  page_size?: number;
}

// ============================================================ payments (Phase 4)

/** Whether a provider can actually process a payment, and what it still needs. */
export interface PaymentProviderStatus {
  code: PaymentProvider;
  display_name: string;
  /** True only for a provider with a working implementation. */
  is_live: boolean;
  has_credentials: boolean;
  configuration_hint: string;
  integration_checklist: string[];
}

/** The store's own published receiving details. */
export interface BankAccount {
  id: string;
  bank_name: string;
  account_title: string;
  account_number: string;
  iban: string | null;
  branch: string | null;
  instructions: string | null;
}

export interface PaymentTransaction {
  id: string;
  event_type: PaymentTransactionEvent;
  provider_transaction_id: string | null;
  amount: string | null;
  status: PaymentStatus | null;
  message: string | null;
  created_at: string;
}

export interface Refund {
  id: string;
  amount: string;
  reason: string;
  status: RefundStatus;
  provider_refund_id: string | null;
  created_at: string;
}

/** Customer-facing payment view. Carries no gateway payload or staff notes. */
export interface Payment {
  id: string;
  provider: PaymentProvider;
  payment_method: PaymentMethod;
  status: PaymentStatus;
  amount: string;
  currency: string;
  customer_reference: string | null;
  proof_submitted_at: string | null;
  failure_reason: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface AdminPayment extends Payment {
  order_id: string;
  order_number: string;
  customer_email: string;
  customer_name: string;
  provider_transaction_id: string | null;
  customer_note: string | null;
  proof_url: string | null;
  internal_note: string | null;
  verified_at: string | null;
  raw_response: Record<string, unknown> | null;
  transactions: PaymentTransaction[];
  refunds: Refund[];
  updated_at: string;
}

export interface PaymentStats {
  total_payments: number;
  status_counts: Record<string, number>;
  method_counts: Record<string, number>;
  awaiting_verification: number;
  collected_total: number;
}

export interface PaymentQuery {
  provider?: PaymentProvider;
  payment_method?: PaymentMethod;
  status?: PaymentStatus;
  awaiting_verification?: boolean;
  date_from?: string;
  date_to?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

// ============================================================ shipping (Phase 4)

export interface ShippingMethod {
  id: string;
  code: DeliveryMethod;
  name: string;
  description: string | null;
  price: string;
  free_threshold: string | null;
  estimated_days_min: number | null;
  estimated_days_max: number | null;
  is_active: boolean;
}

export interface CourierStatus {
  code: CourierProvider;
  display_name: string;
  is_automated: boolean;
  is_configured: boolean;
  configuration_hint: string;
}

export interface ShipmentEvent {
  id: string;
  status: ShippingStatus;
  note: string | null;
  location: string | null;
  created_at: string;
}

export interface Shipment {
  id: string;
  provider: CourierProvider;
  tracking_number: string | null;
  shipment_id: string | null;
  shipping_status: ShippingStatus;
  label_url: string | null;
  tracking_url: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  events: ShipmentEvent[];
  notes?: string | null;
}

/** Public tracking response. Deliberately carries no address, price, or identity. */
export interface TrackingResult {
  order_number: string;
  order_status: OrderStatus;
  payment_status: PaymentStatus;
  placed_at: string;
  item_count: number;
  items: { name: string; variant_label: string; quantity: number }[];
  shipping_status: ShippingStatus | null;
  courier: CourierProvider | null;
  tracking_number: string | null;
  tracking_url: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  status_history: ShipmentEvent[];
}

// ======================================================= admin ops (Phase 5)

export type Permission =
  | "PRODUCT_VIEW" | "PRODUCT_CREATE" | "PRODUCT_UPDATE" | "PRODUCT_DELETE"
  | "ORDER_VIEW" | "ORDER_UPDATE"
  | "INVENTORY_VIEW" | "INVENTORY_UPDATE"
  | "CUSTOMER_VIEW" | "CUSTOMER_UPDATE"
  | "SALES_VIEW" | "SALES_MANAGE"
  | "REPORTS_VIEW" | "PAYMENT_VIEW" | "PAYMENT_MANAGE" | "SETTINGS_MANAGE";

export type SaleType = "STANDARD" | "FLASH" | "CLEARANCE" | "SEASONAL";
export type DiscountType = "PERCENTAGE" | "FIXED_AMOUNT" | "CUSTOM_PRICE";
export type SaleTargetType = "STORE" | "CATEGORY" | "SUBCATEGORY" | "BRAND" | "PRODUCT";

export type DatePreset =
  | "today" | "yesterday" | "last_7_days" | "last_30_days"
  | "this_month" | "previous_month" | "this_year" | "all_time";

export interface DateRangeQuery {
  preset?: DatePreset;
  date_from?: string;
  date_to?: string;
}

export interface RangeInfo {
  start: string;
  end: string;
  label: string;
}

export interface SalesTotals {
  gross_sales: number;
  discounts: number;
  shipping_revenue: number;
  net_sales: number;
  order_count: number;
  items_sold: number;
  average_order_value: number;
}

export interface TimeseriesPoint {
  bucket: string;
  net_sales: number;
  gross_sales: number;
  orders: number;
}

export interface GroupedSalesRow {
  id: string;
  name: string;
  orders: number;
  units_sold: number;
  revenue: number;
  category_name?: string | null;
}

export interface ProductPerformanceRow {
  id: string;
  name: string;
  sku: string;
  brand_name: string | null;
  category_name: string | null;
  units_sold: number;
  revenue: number;
  orders: number;
  average_selling_price: number;
  stock: number;
  regular_price: number;
}

export interface InventorySummary {
  active_products: number;
  total_variants: number;
  total_units: number;
  low_stock_variants: number;
  out_of_stock_variants: number;
  inventory_value: number;
}

export interface StockAlertRow {
  product_id: string;
  product_name: string;
  product_slug: string;
  variant_id: string;
  sku: string;
  size: string | null;
  waist: number | null;
  quantity: number;
  low_stock_threshold: number;
}

export interface CustomerAnalytics {
  total: number;
  new: number;
  repeat: number;
  loyal: number;
  with_orders: number;
  average_order_value: number;
  total_revenue: number;
  /** The documented order-count boundaries behind the segment counts. */
  segment_rule: Record<string, number>;
}

export interface DashboardSummary {
  range: RangeInfo;
  today: { orders: Record<string, number>; sales: number };
  period_sales: { today: number; week: number; month: number; year: number };
  selected: SalesTotals & {
    net_sales_change_percent: number | null;
    order_count_change_percent: number | null;
  };
  order_statuses: Record<string, number>;
  payment_statuses: Record<string, number>;
  payment_methods: Record<string, number>;
  inventory: InventorySummary;
  customers: CustomerAnalytics;
  timeseries: TimeseriesPoint[];
  top_products: ProductPerformanceRow[];
  low_selling_products: ProductPerformanceRow[];
  category_sales: GroupedSalesRow[];
  brand_sales: GroupedSalesRow[];
  generated_at: string;
}

export interface SalesAnalytics {
  range: RangeInfo;
  totals: SalesTotals;
  timeseries: TimeseriesPoint[];
  by_category: GroupedSalesRow[];
  by_subcategory: GroupedSalesRow[];
  by_brand: GroupedSalesRow[];
}

export interface OrderAnalytics {
  range: RangeInfo;
  order_statuses: Record<string, number>;
  payment_statuses: Record<string, number>;
  payment_methods: Record<string, number>;
  total_orders: number;
}

export interface SaleTarget {
  id: string;
  target_type: SaleTargetType;
  product_id: string | null;
  category_id: string | null;
  subcategory_id: string | null;
  brand_id: string | null;
  label: string | null;
}

export interface Sale {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  sale_type: SaleType;
  discount_type: DiscountType;
  discount_value: string;
  priority: number;
  is_active: boolean;
  starts_at: string;
  ends_at: string | null;
  badge_text: string | null;
  created_at: string;
  updated_at: string;
  targets: SaleTarget[];
  /** Running right now, per the same predicate the pricing engine uses. */
  is_live: boolean;
  is_scheduled: boolean;
  affected_product_count: number;
}

export interface SaleInput {
  name: string;
  description?: string | null;
  sale_type: SaleType;
  discount_type: DiscountType;
  discount_value: string;
  priority: number;
  is_active: boolean;
  starts_at: string;
  ends_at?: string | null;
  badge_text?: string | null;
  targets: {
    target_type: SaleTargetType;
    product_id?: string;
    category_id?: string;
    subcategory_id?: string;
    brand_id?: string;
  }[];
}

export interface BulkResult {
  affected: number;
  detail: string;
}

export interface PricePreviewRow {
  product_id: string;
  name: string;
  sku: string;
  current_price: number;
  new_price: number;
  change: number;
}

export interface PricePreview {
  rows: PricePreviewRow[];
  affected: number;
  total_before: number;
  total_after: number;
  total_change: number;
}

export interface ActivityLogEntry {
  id: string;
  user_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  description: string;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface AdminNotification {
  id: string;
  type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AdminNotificationList {
  items: AdminNotification[];
  total: number;
  unread: number;
}

export interface StaffMember {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  permissions: Permission[];
  /** True for ADMIN, who hold everything and cannot be restricted. */
  holds_all: boolean;
}

export interface CustomerRow {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  order_count: number;
  total_spent: number;
  last_order_at: string | null;
  segment: string;
  created_at: string;
}

export interface CustomerNote {
  id: string;
  body: string;
  author_email: string | null;
  created_at: string;
}

export interface ImportRow {
  row_number: number;
  data: Record<string, string | null>;
  errors: string[];
  warnings: string[];
  action: string;
}

export interface ImportBatch {
  id: string;
  filename: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  warning_rows: number;
  error_rows: number;
  created_count: number;
  updated_count: number;
  error_summary: string | null;
  rows: ImportRow[];
}

export interface StockRow {
  product_id: string;
  product_name: string;
  variant_id: string;
  sku: string;
  variant_label: string;
  size: string | null;
  waist: number | null;
  quantity: number;
  low_stock_threshold: number;
  /** Derived from this variant's own threshold, not a global number. */
  status: "in_stock" | "low" | "out";
  is_active: boolean;
}

export interface InventoryMovement {
  id: string;
  created_at: string;
  product_name: string;
  sku: string;
  variant_label: string;
  type: string;
  quantity_change: number;
  quantity_before: number;
  quantity_after: number;
  reference_type: string | null;
  reference_id: string | null;
  note: string | null;
}

export interface CustomerOrderRow {
  id: string;
  order_number: string;
  order_status: string;
  payment_status: string;
  total_amount: string;
  item_count: number;
  created_at: string;
}

/** Full admin customer profile. Carries no authentication material. */
export interface CustomerDetail extends CustomerRow {
  is_active: boolean;
  is_verified: boolean;
  last_login_at: string | null;
  addresses: Address[];
  orders: CustomerOrderRow[];
  wishlist: string[];
  notes: CustomerNote[];
}
