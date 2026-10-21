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

function hhmm(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(11, 16);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: true });
}

function hoursOf(minutes?: number | null): string {
  if (!minutes) return "—";
  return (minutes / 60).toFixed(1) + "h";
}

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
        <Card className="mt-6">
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
              className="text-sm text-neutral-400 hover:text-neutral-700"
            >
              Close
            </button>
          </div>
          {detailLoading ? (
            <Empty text="Loading…" />
          ) : !detail || detail.items.length === 0 ? (
            <Empty text="No records for this card" />
          ) : (
            <div className="overflow-x-auto">
              <table className="mobile-stack w-full text-left text-sm">
                <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                  <tr>
                    <th className="px-5 py-3 font-medium">Employee</th>
                    {selected === "on_leave" || selected === "pending_leaves" ? (
                      <>
                        <th className="px-5 py-3 font-medium">From</th>
                        <th className="px-5 py-3 font-medium">To</th>
                        <th className="px-5 py-3 font-medium">Days</th>
                        <th className="px-5 py-3 font-medium">Status</th>
                        <th className="px-5 py-3 font-medium">Reason</th>
                      </>
                    ) : selected === "pending_payroll" ? (
                      <>
                        <th className="px-5 py-3 font-medium">Period</th>
                        <th className="px-5 py-3 font-medium">Status</th>
                      </>
                    ) : selected === "total_employees" ? (
                      <>
                        <th className="px-5 py-3 font-medium">Department</th>
                        <th className="px-5 py-3 font-medium">Joined</th>
                      </>
                    ) : (
                      <>
                        <th className="px-5 py-3 font-medium">In</th>
                        <th className="px-5 py-3 font-medium">Out</th>
                        <th className="px-5 py-3 font-medium">Hours</th>
                        <th className="px-5 py-3 font-medium">Late</th>
                        <th className="px-5 py-3 font-medium">OT</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {detail.items.map((r, i) => (
                    <tr key={r.employee_id || r.period || i} className="hover:bg-neutral-50">
                      <td data-label="Employee" className="px-5 py-3">
                        {r.employee_code || r.period ? (
                          <>
                            <div className="font-medium text-neutral-800">{r.name || r.period}</div>
                            {r.employee_code ? (
                              <div className="text-xs text-neutral-400">{r.employee_code}</div>
                            ) : null}
                          </>
                        ) : (
                          <span className="text-neutral-400">—</span>
                        )}
                      </td>
                      {selected === "on_leave" || selected === "pending_leaves" ? (
                        <>
                          <td data-label="From" className="px-5 py-3 text-neutral-600">{r.start_date}</td>
                          <td data-label="To" className="px-5 py-3 text-neutral-600">{r.end_date}</td>
                          <td data-label="Days" className="px-5 py-3 text-neutral-600">{r.days}</td>
                          <td data-label="Status" className="px-5 py-3 text-neutral-600">{r.status}</td>
                          <td data-label="Reason" className="px-5 py-3 text-neutral-500">{r.reason || "—"}</td>
                        </>
                      ) : selected === "pending_payroll" ? (
                        <>
                          <td data-label="Period" className="px-5 py-3 text-neutral-600">{r.period}</td>
                          <td data-label="Status" className="px-5 py-3 text-neutral-600">{r.status}</td>
                        </>
                      ) : selected === "total_employees" ? (
                        <>
                          <td data-label="Department" className="px-5 py-3 text-neutral-500">{r.department || "—"}</td>
                          <td data-label="Joined" className="px-5 py-3 text-neutral-500">{r.joining_date || "—"}</td>
                        </>
                      ) : (
                        <>
                          <td data-label="In" className="px-5 py-3 text-green-700">{hhmm(r.first_in)}</td>
                          <td data-label="Out" className="px-5 py-3 text-neutral-700">{hhmm(r.last_out)}</td>
                          <td data-label="Hours" className="px-5 py-3 text-blue-700">{hoursOf(r.worked_minutes)}</td>
                          <td data-label="Late" className="px-5 py-3 text-red-600">
                            {r.late_minutes ? `${r.late_minutes}m` : "—"}
                          </td>
                          <td data-label="OT" className="px-5 py-3 text-purple-600">
                            {r.overtime_minutes ? `${r.overtime_minutes}m` : "—"}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
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