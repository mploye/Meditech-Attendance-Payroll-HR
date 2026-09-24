"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { getStoredUser, clearAuth } from "@/lib/api";

type NavItem = { href: string; label: string };

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Overview",
    items: [{ href: "/dashboard", label: "Dashboard" }],
  },
  {
    section: "Workforce",
    items: [
      { href: "/employees", label: "Employees" },
      { href: "/departments", label: "Departments" },
      { href: "/designations", label: "Designations" },
      { href: "/users", label: "Users" },
    ],
  },
  {
    section: "Time & Attendance",
    items: [
      { href: "/attendance", label: "Attendance" },
      { href: "/shifts", label: "Shifts" },
      { href: "/devices", label: "Devices" },
      { href: "/holidays", label: "Holidays" },
    ],
  },
  {
    section: "Leave & OT",
    items: [
      { href: "/leaves", label: "Leave Requests" },
      { href: "/overtime", label: "Overtime" },
      { href: "/loans", label: "Loans" },
    ],
  },
  {
    section: "Payroll",
    items: [
      { href: "/payroll", label: "Payroll Periods" },
      { href: "/payslips", label: "Payslips" },
      { href: "/reports", label: "Reports" },
    ],
  },
  {
    section: "System",
    items: [
      { href: "/settings", label: "Company & eSSL" },
      { href: "/audit", label: "Audit Logs" },
    ],
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href;
  return pathname.startsWith(href);
}

function BrandMark() {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/genetics-logo.png"
      width={64}
      height={50}
      alt="Genetics Meditech"
      className="h-8 w-auto rounded-lg"
    />
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<Record<string, unknown> | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      const u = getStoredUser();
      if (!u) {
        router.replace("/login");
        return;
      }
      setUser(u);
    }, 0);
    return () => clearTimeout(t);
  }, [router]);

  if (!user) return null;

  const logout = () => {
    clearAuth();
    router.replace("/login");
  };

  const sidebar = (
    <div className="flex h-full flex-col bg-gradient-to-b from-brand-900 via-brand-900 to-[#14261b] text-brand-200">
      <div className="relative overflow-hidden border-b border-white/10 px-5 py-5">
        <div className="absolute -right-6 -top-8 h-24 w-24 rotate-45 rounded-2xl bg-brand-600/20" />
        <div className="absolute -bottom-6 -left-6 h-16 w-16 rounded-full bg-brand-600/10" />
        <div className="relative flex items-center gap-3">
          <BrandMark />
          <div>
            <div className="text-sm font-bold tracking-wide text-white">Genetics Meditech</div>
            <div className="text-[11px] text-brand-300">Attendance · Payroll · HR</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {NAV.map((group) => (
          <div key={group.section} className="mb-5">
            <div className="px-2 text-[10px] font-semibold uppercase tracking-widest text-brand-500">
              {group.section}
            </div>
            <div className="mt-1.5 space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(typeof window !== "undefined" ? window.location.pathname : "", item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={`block rounded-lg px-3 py-2 text-sm transition ${
                      active
                        ? "bg-brand-600 text-white shadow-sm"
                        : "text-brand-200 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-white/10 px-5 py-4">
        <div className="text-sm font-medium text-white">{String(user.full_name ?? user.email ?? "")}</div>
        <div className="text-[11px] capitalize text-brand-300">
          {(String(user.role ?? "") || "").toLowerCase().replace(/_/g, " ")}
        </div>
        <button onClick={logout} className="mt-3 text-xs text-brand-400 hover:text-rose-400">
          Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">{sidebar}</aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64">{sidebar}</aside>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close menu"
            className="absolute right-4 top-4 rounded-lg bg-white/90 px-2.5 py-1.5 text-sm font-medium text-neutral-700 shadow-sm"
          >
            ✕
          </button>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-brand-100 bg-white/90 px-4 backdrop-blur lg:hidden">
          <button
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-semibold text-neutral-700 hover:bg-brand-50"
            aria-label="Open menu"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <path d="M2 4.5h14M2 9h14M2 13.5h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            Menu
          </button>
          <div className="flex items-center gap-2">
            <BrandMark />
            <span className="text-sm font-bold text-brand-900">Genetics Meditech</span>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-5 py-6">{children}</main>
      </div>
    </div>
  );
}
