/**
 * Low-level API transport.
 *
 * All backend access goes through here. The frontend never talks to the
 * database; it only consumes the FastAPI REST API.
 */

// Browser-facing base URL is required and inlined during `next build`.
const PUBLIC_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL!;

// Server-side base URL. Server rendering happens inside the frontend container,
// where "localhost" is that container rather than the API, so requests must go
// to the backend's Docker service name. Falls back to the public URL when the
// app runs outside Docker.
const INTERNAL_BASE_URL = process.env.API_INTERNAL_BASE_URL ?? PUBLIC_BASE_URL;

function resolveBaseUrl(): string {
  const base = typeof window === "undefined" ? INTERNAL_BASE_URL : PUBLIC_BASE_URL;
  return base.replace(/\/+$/, "");
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown
  ) {
    super(message);
    this.name = "ApiClientError";
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isUnauthorized(): boolean {
    return this.status === 401 || this.status === 403;
  }
}

export type QueryScalar = string | number | boolean | undefined | null;
export type QueryValue = QueryScalar | QueryScalar[];

/**
 * Drop empty values so the URL only carries filters the user actually set.
 *
 * Arrays become repeated parameters (`?id=a&id=b`), which is what FastAPI's
 * `Query(list[...])` expects — a comma-joined single value would arrive as one
 * malformed string.
 */
export function buildQueryString(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      for (const entry of value) {
        if (entry === undefined || entry === null || entry === "") continue;
        search.append(key, String(entry));
      }
      continue;
    }
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Seconds to cache the response. Omit for no caching. */
  revalidate?: number;
}

async function readDetail(response: Response): Promise<unknown> {
  try {
    const body = await response.json();
    return typeof body === "object" && body !== null && "detail" in body
      ? (body as { detail: unknown }).detail
      : body;
  } catch {
    return undefined;
  }
}

function describe(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((entry) => {
      const issue = entry as { msg?: string; loc?: unknown[] };
      if (!issue?.msg) return null;
      const path = Array.isArray(issue.loc)
        ? issue.loc.filter((part) => part !== "body" && part !== "query" && part !== "path").join(".")
        : "";
      return path ? `${path}: ${issue.msg}` : issue.msg;
    }).filter((message): message is string => message !== null);
    if (messages.length) return messages.join("; ");
  }
  return `Request failed with status ${status}`;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, revalidate, headers, ...rest } = options;

  const response = await fetch(`${resolveBaseUrl()}${path}`, {
    ...rest,
    // Send the HTTP-only session cookie on every request.
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    ...(revalidate === undefined ? { cache: "no-store" } : { next: { revalidate } }),
  });

  if (!response.ok) {
    const detail = await readDetail(response);
    throw new ApiClientError(describe(detail, response.status), response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
