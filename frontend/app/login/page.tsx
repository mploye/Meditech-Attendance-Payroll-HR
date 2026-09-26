"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, setAuth } from "@/lib/api";
import { Alert, Button, Input } from "@/components/ui";
import LoginScene from "@/components/LoginScene";

function BrandMark() {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/genetics-logo.png"
      width={80}
      height={62}
      alt="Genetics Meditech"
      className="h-10 w-auto rounded-xl"
    />
  );
}

function TiltCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    const rx = (0.5 - py) * 10;
    const ry = (px - 0.5) * 14;
    el.style.transform = `perspective(900px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`;
    el.style.setProperty("--glare-x", `${(px * 100).toFixed(1)}%`);
    el.style.setProperty("--glare-y", `${(py * 100).toFixed(1)}%`);
  };

  const onLeave = () => {
    const el = ref.current;
    if (!el) return;
    el.style.transform = "";
  };

  return (
    <div ref={ref} className={`card-3d ${className}`} onMouseMove={onMove} onMouseLeave={onLeave}>
      {children}
      <span className="card-3d__glare" aria-hidden />
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Silent pre-warm ping to wake Render backend from sleep on page visit
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${baseUrl}/api/v1/health`, { cache: "no-store" }).catch(() => {});
  }, []);


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
        <LoginScene />
        <div className="animate-float absolute -top-24 -right-24 h-96 w-96 rotate-45 rounded-[2.5rem] bg-brand-600/25" style={{ animationDuration: "18s" }} />
        <div className="animate-float absolute bottom-10 -left-16 h-64 w-64 rounded-full border-[24px] border-brand-600/20" style={{ animationDuration: "26s" }} />
        <div className="animate-float absolute right-16 bottom-24 h-20 w-20 rotate-45 rounded-xl bg-brand-200/15" style={{ animationDuration: "12s", animationDelay: "0.6s" }} />

        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="animate-fade-up flex items-center gap-3">
            <span className="animate-glow inline-flex rounded-2xl">
              <BrandMark />
            </span>
            <div>
              <div className="text-lg font-bold tracking-wide text-white">Genetics Meditech</div>
              <div className="text-xs text-brand-300">Attendance · Payroll · HR</div>
            </div>
          </div>

          <div>
            <h1 className="animate-fade-up max-w-md text-3xl font-bold leading-tight text-white" style={{ animationDelay: "150ms" }}>
              Manage your workforce from a single, secure platform
            </h1>
            <p className="animate-fade-up mt-4 max-w-md text-sm leading-relaxed text-brand-300" style={{ animationDelay: "280ms" }}>
              Attendance, leaves, payroll and eSSL device integration — powered by a clean, modern
              interface your team will love.
            </p>
            <ul className="animate-fade-up mt-8 space-y-3 text-sm text-brand-100" style={{ animationDelay: "420ms" }}>
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
          <div className="animate-fade-up mb-6 flex items-center gap-3 lg:hidden">
            <BrandMark />
            <div>
              <div className="text-lg font-bold text-brand-900">Genetics Meditech</div>
              <div className="text-xs text-neutral-500">Attendance · Payroll · HR</div>
            </div>
          </div>
          <TiltCard className="animate-fade-up rounded-2xl border border-brand-100 bg-white p-6 shadow-sm sm:p-8" >
            <div className="mb-6">
              <h1 className="text-xl font-bold text-brand-900">Sign in</h1>
              <p className="mt-1 text-sm text-neutral-500">Welcome back, please enter your details.</p>
            </div>
            <Alert kind="error" message={error} />
            <form onSubmit={submit} className="space-y-4">
              <Input label="Email" type="email" value={email} onChange={setEmail} placeholder="admin@company.com" required />
              <Input label="Password" type="password" value={password} onChange={setPassword} placeholder="••••••••" required />
              <Button type="submit" disabled={busy} className="w-full">
                {busy ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    Signing in…
                  </span>
                ) : (
                  "Sign in"
                )}
              </Button>
            </form>
          </TiltCard>
          <p className="mt-5 text-[11px] leading-relaxed text-neutral-400">
            Connects to the FastAPI backend at {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}. First run:
            register the super admin via <code className="text-neutral-500">POST /api/v1/auth/register-super-admin</code>.
          </p>
        </div>
      </div>
    </div>
  );
}