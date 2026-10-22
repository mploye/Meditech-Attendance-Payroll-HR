const COMPANY_TIME_ZONE = "Asia/Kolkata";

function toDate(value: string | Date): Date | null {
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatTime(value?: string | Date | null): string {
  if (!value) return "—";
  const d = toDate(value);
  if (!d) return String(value).slice(11, 16) || "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: COMPANY_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(d);
}

export function formatTimeWithSeconds(value?: string | Date | null): string {
  if (!value) return "—";
  const d = toDate(value);
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: COMPANY_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).format(d);
}

export function formatDateTime(value?: string | Date | null): string {
  if (!value) return "—";
  const d = toDate(value);
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: COMPANY_TIME_ZONE,
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(d);
}

export function dateKey(value: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: COMPANY_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(value);
}
