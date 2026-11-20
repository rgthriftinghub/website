/**
 * Catalogue API functions.
 *
 * Every backend call the storefront and admin area make is defined here, so
 * pages never construct URLs themselves.
 */

import { apiRequest, buildQueryString, type QueryValue } from "@/lib/api/client";
import type {
  Brand,
  Category,
  CategoryDetail,
  FilterOptions,
  Page,
  ProductAdmin,
  ProductDetail,
  ProductListItem,
  ProductQuery,
  User,
} from "@/lib/api/types";

// Catalogue reads are cached briefly: content changes rarely, and this keeps
// listing pages fast without serving obviously stale stock numbers.
const CATALOG_REVALIDATE_SECONDS = 30;

function toQueryRecord(query: ProductQuery): Record<string, QueryValue> {
  return { ...query } as Record<string, QueryValue>;
}

export function listProducts(query: ProductQuery = {}): Promise<Page<ProductListItem>> {
  return apiRequest<Page<ProductListItem>>(`/products${buildQueryString(toQueryRecord(query))}`, {
    revalidate: CATALOG_REVALIDATE_SECONDS,
  });
}

export function getProduct(slug: string): Promise<ProductDetail> {
  return apiRequest<ProductDetail>(`/products/${encodeURIComponent(slug)}`, {
    revalidate: CATALOG_REVALIDATE_SECONDS,
  });
}

export function getProductsByIds(ids: string[]): Promise<ProductListItem[]> {
  const params = new URLSearchParams();
  ids.slice(0, 50).forEach((id) => params.append("ids", id));
  return apiRequest<ProductListItem[]>(`/products/by-ids?${params.toString()}`);
}

export function getFilterOptions(): Promise<FilterOptions> {
  return apiRequest<FilterOptions>("/products/filter-options", {
    revalidate: CATALOG_REVALIDATE_SECONDS,
  });
}

export function listCategories(): Promise<Category[]> {
  return apiRequest<Category[]>("/categories", { revalidate: CATALOG_REVALIDATE_SECONDS });
}

export function getCategory(slug: string): Promise<CategoryDetail> {
  return apiRequest<CategoryDetail>(`/categories/${encodeURIComponent(slug)}`, {
    revalidate: CATALOG_REVALIDATE_SECONDS,
  });
}

export function listBrands(): Promise<Brand[]> {
  return apiRequest<Brand[]>("/brands", { revalidate: CATALOG_REVALIDATE_SECONDS });
}

export function getBrand(slug: string): Promise<Brand> {
  return apiRequest<Brand>(`/brands/${encodeURIComponent(slug)}`, {
    revalidate: CATALOG_REVALIDATE_SECONDS,
  });
}

// ------------------------------------------------------------------------ auth
export function register(payload: {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
}): Promise<User> {
  return apiRequest<User>("/auth/register", { method: "POST", body: payload });
}

export function login(payload: { email: string; password: string }): Promise<User> {
  return apiRequest<User>("/auth/login", { method: "POST", body: payload });
}

export function logout(): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>("/auth/logout", { method: "POST" });
}

export function getCurrentUser(): Promise<User> {
  return apiRequest<User>("/auth/me");
}

// ----------------------------------------------------------------------- admin
export function listAdminProducts(
  query: ProductQuery & { include_inactive?: boolean } = {}
): Promise<Page<ProductAdmin>> {
  return apiRequest<Page<ProductAdmin>>(
    `/admin/products${buildQueryString(query as Record<string, QueryValue>)}`
  );
}

export function getAdminProduct(id: string): Promise<ProductAdmin> {
  return apiRequest<ProductAdmin>(`/admin/products/${encodeURIComponent(id)}`);
}

export function createAdminProduct(payload: Record<string, unknown>): Promise<ProductAdmin> {
  return apiRequest<ProductAdmin>("/admin/products", { method: "POST", body: payload });
}

export function updateAdminProduct(id: string, payload: Record<string, unknown>): Promise<ProductAdmin> {
  return apiRequest<ProductAdmin>(`/admin/products/${encodeURIComponent(id)}`, { method: "PUT", body: payload });
}

export function listAdminCategories(): Promise<CategoryDetail[]> {
  return apiRequest<CategoryDetail[]>("/admin/categories");
}

export function listAdminBrands(): Promise<Brand[]> {
  return apiRequest<Brand[]>("/admin/brands");
}
