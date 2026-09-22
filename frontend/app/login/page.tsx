"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setAuth } from "@/lib/api";
import { Alert, Button, Input } from "@/components/ui";

function BrandMark() {
  return (
    <svg width="40" height="40" viewBox="0 0 34 34" fill="none" aria-hidden>
      <rect width="34" height="34" rx="9" fill="#ffffff" />
      <path d="M7 23 L17 8 L27 23 Z" fill="#437244" />
      <circle cx="17" cy="21" r="6" fill="#c9d9ca" />
      <rect x="14" y="18" width="6" height="6" rx="1" fill="#437244" />
    </svg>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await api.login(email.trim(), password);
      setAuth(data.access_token, data.user);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      <div className="relative hidden w-1/2 overflow-hidden bg-gradient-to-br from-brand-900 via-brand-900 to-[#14261b] lg:block">
        <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" aria-hidden>
          <defs>
            <pattern id="login-grid" width="56" height="56" patternUnits="userSpaceOnUse">
              <path d="M 56 0 L 0 0 0 56" fill="none" stroke="#ffffff" strokeOpacity="0.06" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#login-grid)" />
        </svg>
        <div className="absolute -top-24 -right-24 h-96 w-96 rotate-45 rounded-[2.5rem] bg-brand-600/25" />
        <div className="absolute bottom-10 -left-16 h-64 w-64 rounded-full border-[24px] border-brand-600/20" />
        <div className="absolute right-16 bottom-24 h-20 w-20 rotate-45 rounded-xl bg-brand-200/15" />

        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <BrandMark />
            <div>
              <div className="text-lg font-bold tracking-wide text-white">Genetics Meditech</div>
              <div className="text-xs text-brand-300">Attendance · Payroll · HR</div>
            </div>
          </div>

          <div>
            <h1 className="max-w-md text-3xl font-bold leading-tight text-white">
              Manage your workforce from a single, secure platform
            </h1>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-brand-300">
              Attendance, leaves, payroll and eSSL device integration — powered by a clean, modern
              interface your team will love.
            </p>
            <ul className="mt-8 space-y-3 text-sm text-brand-100">
              {["Live attendance & shift tracking", "One-click payroll runs and payslips", "Real-time reports and audit trails"].map(
                (f) => (
                  <li key={f} className="flex items-center gap-3">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-600">
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden>
                        <path d="M2 5 L4.5 7.5 L8 3" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </span>
                    {f}
                  </li>
                ),
              )}
            </ul>
          </div>

          <p className="text-[11px] text-brand-500">© {new Date().getFullYear()} Genetics Meditech Private Limited</p>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <BrandMark />
            <div>
              <div className="text-lg font-bold text-brand-900">Genetics Meditech</div>
              <div className="text-xs text-neutral-500">Attendance · Payroll · HR</div>
            </div>
          </div>
          <div className="rounded-2xl border border-brand-100 bg-white p-8 shadow-sm">
            <div className="mb-6">
              <h1 className="text-xl font-bold text-brand-900">Sign in</h1>
              <p className="mt-1 text-sm text-neutral-500">Welcome back, please enter your details.</p>
            </div>
            <Alert kind="error" message={error} />
            <form onSubmit={submit} className="space-y-4">
              <Input label="Email" type="email" value={email} onChange={setEmail} placeholder="admin@company.com" required />
              <Input label="Password" type="password" value={password} onChange={setPassword} placeholder="••••••••" required />
              <Button type="submit" disabled={busy} className="w-full">
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          </div>
          <p className="mt-5 text-[11px] leading-relaxed text-neutral-400">
            Connects to the FastAPI backend at {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}. First run:
            register the super admin via <code className="text-neutral-500">POST /api/v1/auth/register-super-admin</code>.
          </p>
        </div>
      </div>
    </div>
  );
}