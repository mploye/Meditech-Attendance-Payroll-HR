"use client";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "hrms.token";
const USER_KEY = "hrms.user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token: string, user: Record<string, unknown>) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
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
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: { raw?: boolean } = {}
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch (err) {
    throw new Error(
      "Unable to connect to the API server. The backend service on Render may be waking up from sleep mode. Please wait 10-20 seconds and try signing in again."
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
  get: <T,>(path: string, qs?: Record<string, string | number | undefined>) => {
    const search = qs
      ? "?" +
        Object.entries(qs)
          .filter(([, v]) => v !== undefined && v !== null && v !== "")
          .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
          .join("&")
      : "";
    return request<T>("GET", path + search);
  },
  post: <T,>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T,>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  put: <T,>(path: string, body?: unknown) => request<T>("PUT", path, body),
  del: <T,>(path: string) => request<T>("DELETE", path),
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