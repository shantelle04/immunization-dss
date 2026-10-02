// API client. The access token lives only in memory (never localStorage); the refresh token is an
// HttpOnly cookie the browser sends to /api/v1/auth/ only, so page scripts can never read it.

export type Role = "healthcare_worker" | "facility_manager" | "system_admin";

export interface User {
  username: string;
  role: Role;
  facility: { code: string; name: string; level: string } | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
  ) {
    super(ApiError.describe(status, data));
  }

  static describe(status: number, data: unknown): string {
    if (data && typeof data === "object") {
      const values = Object.values(data as Record<string, unknown>).flat();
      const text = values.filter((v) => typeof v === "string").join(" ");
      if (text) return text;
    }
    return `Request failed (${status}).`;
  }
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

interface Options {
  method?: "GET" | "POST" | "PUT" | "PATCH";
  body?: unknown;
  query?: Record<string, string>;
}

async function send(path: string, { method = "GET", body, query }: Options): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (path.startsWith("/auth/")) headers["X-CSRFToken"] = csrfToken();
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const qs = query ? `?${new URLSearchParams(query)}` : "";
  return fetch(`/api/v1${path}${qs}`, { method, headers, body: payload, credentials: "same-origin" });
}

async function parse<T>(response: Response): Promise<T> {
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

let refreshing: Promise<User | null> | null = null;

// The refresh token is rotated on use, so two refreshes in flight would make the second one fail and sign
// the user out; every caller shares the one request.
export function refreshSession(): Promise<User | null> {
  refreshing ??= requestRefresh().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function requestRefresh(): Promise<User | null> {
  const response = await send("/auth/refresh", { method: "POST" });
  if (!response.ok) {
    setAccessToken(null);
    return null;
  }
  const data = (await response.json()) as { access: string; user: User };
  setAccessToken(data.access);
  return data.user;
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  let response = await send(path, options);
  if (response.status === 401 && !path.startsWith("/auth/") && (await refreshSession())) {
    response = await send(path, options);
  }
  return parse<T>(response);
}

export async function login(username: string, password: string): Promise<User> {
  const data = await parse<{ access: string; user: User }>(
    await send("/auth/login", { method: "POST", body: { username, password } }),
  );
  setAccessToken(data.access);
  return data.user;
}

export async function logout(): Promise<void> {
  try {
    await send("/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}
