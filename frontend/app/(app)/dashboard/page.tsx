"use client";

import { useEffect, useState } from "react";
import { api, getStoredUser } from "@/lib/api";
import { Alert, Card, PageHeader, Empty } from "@/components/ui";

type Summary = {
  total_employees: number;
  present_today: number;
  absent_today: number;
  on_leave: number;
  late_today: number;
  pending_leaves: number;
  pending_payroll: number;
  payroll_amount: number;
  devices_online: number;
  devices_offline: number;
};

type MetricDetailRow = {
  employee_id: string;
  employee_code?: string;
  name?: string;
  status?: string | null;
  first_in?: string | null;
  last_out?: string | null;
  worked_minutes?: number | null;
  late_minutes?: number | null;
  overtime_minutes?: number | null;
  start_date?: string;
  end_date?: string;
  days?: number;
  reason?: string | null;
  department?: string | null;
  joining_date?: string | null;
  period?: string;
  period_id?: string;
};

type MetricDetail = {
  metric: string;
  date: string;
  count: number;
  items: MetricDetailRow[];
};

const METRIC_LABELS: { key: keyof Summary; label: string; hint: string }[] = [
  { key: "total_employees", label: "Active Employees", hint: "Total workforce" },
  { key: "present_today", label: "Present Today", hint: "Checked in" },
  { key: "absent_today", label: "Absent Today", hint: "No punch" },
  { key: "on_leave", label: "On Leave", hint: "Approved leave" },
  { key: "late_today", label: "Late Today", hint: "Arrived late" },
  { key: "pending_leaves", label: "Pending Leaves", hint: "Needs approval" },
  { key: "pending_payroll", label: "Open Payrolls", hint: "Draft/review" },
  { key: "payroll_amount", label: "Latest Net Payroll", hint: "Last approved period" },
];

const CLICKABLE = new Set<keyof Summary>([
  "total_employees",
  "present_today",
  "absent_today",
  "on_leave",
  "late_today",
  "pending_leaves",
  "pending_payroll",
]);

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trend, setTrend] = useState<{ date: string; present: number }[]>([]);
  const [error, setError] = useState("");
  const [noCompany, setNoCompany] = useState(false);
  const [selected, setSelected] = useState<keyof Summary | null>(null);
  const [detail, setDetail] = useState<MetricDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const openMetric = async (key: keyof Summary) => {
    if (!CLICKABLE.has(key)) return;
    if (selected === key) {
      setSelected(null);
      setDetail(null);
      return;
    }
    setSelected(key);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await api.get<MetricDetail>("/api/v1/dashboard/metric-detail", { metric: key }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load details");
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const me = getStoredUser();
        if (me?.role === "SUPER_ADMIN") {
          const companies = await api.get<{ id: string }[]>("/api/v1/companies");
          if (!companies.length) {
            setNoCompany(true);
            return;
          }
        }
        setSummary(await api.get<Summary>("/api/v1/dashboard/summary"));
        setTrend(await api.get("/api/v1/dashboard/attendance-trend", { days: 14 }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      }
    })();
  }, []);

  const max = Math.max(1, ...trend.map((t) => t.present));

  if (noCompany) {
    return (
      <div>
        <PageHeader title="Dashboard" subtitle="Company overview for today" />
        <Alert kind="error" message={error} />
        <Card className="px-5 py-12 text-center">
          <p className="text-sm font-semibold text-neutral-800">No company set up yet</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-neutral-500">
            Your workspace has no company. Create one from the Settings page to start managing
            employees, attendance, and payroll.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Company overview for today" />
      <Alert kind="error" message={error} />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {METRIC_LABELS.map((m) => {
          const clickable = CLICKABLE.has(m.key);
          const isActive = selected === m.key;
          return (
            <Card
              key={m.key}
              className={`px-5 py-4 transition ${
                clickable ? "cursor-pointer hover:border-brand-400 hover:shadow-sm" : ""
              } ${isActive ? "ring-2 ring-brand-500" : ""}`}
            >
              <button
                type="button"
                onClick={() => openMetric(m.key)}
                className="w-full text-left disabled:cursor-default"
                disabled={!clickable}
              >
                <div className="flex items-start justify-between">
                  <div className="text-2xl font-bold text-neutral-900">
                    {typeof summary?.[m.key] === "number"
                      ? Number(summary[m.key]).toLocaleString("en-IN")
                      : "—"}
                  </div>
                  {clickable ? (
                    <span className="text-[10px] font-medium text-brand-600">
                      {isActive ? "▲" : "▼"}
                    </span>
                  ) : null}
                </div>
                <div className="mt-1 text-sm font-medium text-neutral-700">{m.label}</div>
                <div className="text-[11px] text-neutral-400">
                  {clickable ? "Click to view list" : m.hint}
                </div>
              </button>
            </Card>
          );
        })}
      </div>

      {selected ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => {
            setSelected(null);
            setDetail(null);
          }}
        >
          <div
            className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-neutral-100 px-5 py-4">
              <div>
                <h3 className="text-sm font-semibold text-neutral-800">
                  {METRIC_LABELS.find((m) => m.key === selected)?.label}
                  {detail ? <span className="ml-2 text-neutral-400">({detail.count})</span> : null}
                </h3>
                {detail ? <p className="text-[11px] text-neutral-400">As of {detail.date}</p> : null}
              </div>
              <button
                onClick={() => {
                  setSelected(null);
                  setDetail(null);
                }}
                className="rounded-md px-2 py-1 text-lg leading-none text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="max-h-[65vh] overflow-y-auto px-3 py-3">
              {detailLoading ? (
                <Empty text="Loading…" />
              ) : !detail || detail.items.length === 0 ? (
                <Empty text="No records for this card" />
              ) : (
                <ul className="divide-y divide-neutral-100">
                  {detail.items.map((r, i) => (
                    <li
                      key={r.employee_id || r.period || i}
                      className="flex items-center justify-between gap-3 px-2 py-3"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-neutral-800">
                          {r.name || r.period || "—"}
                        </div>
                        {r.employee_code ? (
                          <div className="text-xs text-neutral-400">{r.employee_code}</div>
                        ) : null}
                      </div>
                      {selected === "late_today" ? (
                        <span className="whitespace-nowrap rounded-md bg-red-50 px-2 py-1 text-xs font-semibold text-red-600">
                          {r.late_minutes ? `${r.late_minutes} min` : "on time"}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="border-b border-neutral-100 px-5 py-4">
            <h3 className="text-sm font-semibold text-neutral-800">Attendance Trend (14 days)</h3>
          </div>
          <div className="flex h-56 items-end gap-1 px-5 py-4">
            {trend.length === 0 ? (
              <Empty text="Run the daily attendance process to see the trend" />
            ) : (
              trend.map((t) => (
                <div key={t.date} className="flex flex-1 flex-col items-center gap-1">
                  <div
                    className="w-full rounded-t bg-brand-600"
                    style={{ height: `${Math.round((t.present / max) * 160)}px` }}
                  />
                  <div className="text-[9px] text-neutral-400">{t.date.slice(5)}</div>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card>
          <div className="border-b border-neutral-100 px-5 py-4">
            <h3 className="text-sm font-semibold text-neutral-800">Devices</h3>
          </div>
          <div className="space-y-3 px-5 py-4">
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500">Online</span>
              <span className="font-semibold text-emerald-600">{summary?.devices_online ?? 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500">Offline</span>
              <span className="font-semibold text-rose-600">{summary?.devices_offline ?? 0}</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}