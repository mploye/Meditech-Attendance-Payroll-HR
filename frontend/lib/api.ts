"use client";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "hrms.token";
const USER_KEY = "hrms.user";

const GET_CACHE_TTL_MS = 20_000;
const getCache = new Map<string, { at: number; data: unknown }>();

function invalidateGetCache() {
  getCache.clear();
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token: string, user: Record<string, unknown>) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  invalidateGetCache();
}

export function getStoredUser(): Record<string, unknown> | null {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(window.localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export function clearAuth() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  invalidateGetCache();
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: { raw?: boolean; retries?: number } = {}
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const maxRetries = opts.retries ?? 3;
  const retryableStatus = new Set([429, 500, 502, 503, 504]);
  let res: Response | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      res = await fetch(`${BASE}${path}`, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        cache: "no-store",
      });
      if (!retryableStatus.has(res.status) || attempt === maxRetries - 1) break;
    } catch {
      if (attempt === maxRetries - 1) {
        res = null;
        break;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 3000 * (attempt + 1)));
  }

  if (!res) {
    throw new Error(
      "Unable to connect to the API server. Render free tier may be waking up from sleep mode. Please wait 10-15 seconds and try signing in again."
    );
  }



  const isFile = opts.raw;
  if (isFile) {
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res as unknown as T;
  }

  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    throw new Error(`Invalid response (${res.status})`);
  }

  if (!res.ok) {
    const p = (payload ?? {}) as { error?: { message?: string }; detail?: string };
    const message = p.error?.message || p.detail || `Request failed (${res.status})`;
    if (res.status === 401) clearAuth();
    throw new Error(message);
  }
  const box = payload as { data?: T } | null;
  return (box?.data ?? payload) as T;
}

export const api = {
  get: async <T,>(path: string, qs?: Record<string, string | number | undefined>, opts: { fresh?: boolean } = {}) => {
    const search = qs
      ? "?" +
        Object.entries(qs)
          .filter(([, v]) => v !== undefined && v !== null && v !== "")
          .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
          .join("&")
      : "";
    const url = path + search;
    const cached = getCache.get(url);
    if (!opts.fresh && cached && Date.now() - cached.at < GET_CACHE_TTL_MS) {
      return cached.data as T;
    }
    const data = await request<T>("GET", url, undefined, { retries: 5 });
    getCache.set(url, { at: Date.now(), data });
    return data;
  },
  post: async <T,>(path: string, body?: unknown) => {
    const data = await request<T>("POST", path, body);
    invalidateGetCache();
    return data;
  },
  patch: async <T,>(path: string, body?: unknown) => {
    const data = await request<T>("PATCH", path, body);
    invalidateGetCache();
    return data;
  },
  put: async <T,>(path: string, body?: unknown) => {
    const data = await request<T>("PUT", path, body);
    invalidateGetCache();
    return data;
  },
  del: async <T,>(path: string) => {
    const data = await request<T>("DELETE", path);
    invalidateGetCache();
    return data;
  },
  download: (path: string) => request<Response>("GET", path, undefined, { raw: true }),
  login: (email: string, password: string) =>
    request<{ access_token: string; user: Record<string, unknown> }>("POST", "/api/v1/auth/login", {
      email,
      password,
    }),
};

export function fileUrl(path: string) {
  return `${BASE}${path}`;
}

export async function downloadFile(path: string, filename?: string) {
  const res = await api.download(path);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || path.split("/").pop() || "download";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}