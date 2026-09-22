import { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-brand-100 bg-white shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-brand-100 px-5 py-4">
      <h3 className="text-sm font-semibold text-neutral-800">{title}</h3>
      {action}
    </div>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold text-neutral-900">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-neutral-500">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  type = "button",
  disabled,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  type?: "button" | "submit";
  disabled?: boolean;
  className?: string;
}) {
  const styles: Record<string, string> = {
    primary:
      "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-200",
    secondary:
      "bg-white text-neutral-700 border border-brand-200 hover:bg-brand-50",
    danger: "bg-rose-600 text-white hover:bg-rose-700",
    ghost: "text-brand-700 hover:bg-brand-100",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Input({
  label,
  name,
  value,
  onChange,
  placeholder,
  type = "text",
  required,
  min,
  max,
  className = "",
}: {
  label?: string;
  name?: string;
  value?: string;
  onChange?: (v: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
  min?: number;
  max?: number;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      {label ? <span className="mb-1 block text-xs font-medium text-neutral-600">{label}</span> : null}
      <input
        type={type}
        name={name}
        placeholder={placeholder}
        required={required}
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600"
      />
    </label>
  );
}

export function Select({
  label,
  value,
  onChange,
  options,
  className = "",
}: {
  label?: string;
  value?: string;
  onChange?: (v: string) => void;
  options: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      {label ? <span className="mb-1 block text-xs font-medium text-neutral-600">{label}</span> : null}
      <select
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-600"
      >
        <option value="">— Select —</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "green" | "red" | "amber" | "blue" | "neutral" | "violet" }) {
  const tones: Record<string, string> = {
    green: "bg-brand-100 text-brand-800 border-brand-200",
    red: "bg-rose-50 text-rose-700 border-rose-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    blue: "bg-sky-50 text-sky-700 border-sky-200",
    violet: "bg-violet-50 text-violet-700 border-violet-200",
    neutral: "bg-neutral-100 text-neutral-600 border-neutral-200",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function statusTone(value: string): "green" | "red" | "amber" | "blue" | "violet" | "neutral" {
  const v = value.toUpperCase();
  if (["ACTIVE", "APPROVED", "PAID", "SUCCESS", "PRESENT", "LOCKED", "ONLINE", "GENERATED", "COMPLETED", "CLOSED"].includes(v))
    return "green";
  if (["INACTIVE", "REJECTED", "TERMINATED", "ABSENT", "FAILED", "DISABLED", "ERROR", "RED"].includes(v)) return "red";
  if (["PENDING", "REVIEW", "DRAFT", "SYNCING", "RESIGNED", "ON_NOTICE", "MISSING_PUNCH", "REQUESTED", "PARTIAL"].includes(v))
    return "amber";
  if (["PROCESSING", "CALCULATING", "SUBMITTED"].includes(v)) return "blue";
  return "neutral";
}

export function Alert({ kind, message }: { kind: "error" | "success"; message: string }) {
  if (!message) return null;
  const styles =
    kind === "error"
      ? "bg-rose-50 text-rose-700 border-rose-200"
      : "bg-brand-100 text-brand-800 border-brand-200";
  return <div className={`mb-4 rounded-lg border px-4 py-3 text-sm ${styles}`}>{message}</div>;
}

export function Empty({ text = "No records yet" }: { text?: string }) {
  return <div className="py-10 text-center text-sm text-neutral-400">{text}</div>;
}