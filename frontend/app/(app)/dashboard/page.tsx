"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trend, setTrend] = useState<{ date: string; present: number }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setSummary(await api.get<Summary>("/api/v1/dashboard/summary"));
        setTrend(await api.get("/api/v1/dashboard/attendance-trend", { days: 14 }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      }
    })();
  }, []);

  const max = Math.max(1, ...trend.map((t) => t.present));

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Company overview for today" />
      <Alert kind="error" message={error} />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {METRIC_LABELS.map((m) => (
          <Card key={m.key} className="px-5 py-4">
            <div className="text-2xl font-bold text-neutral-900">
              {typeof summary?.[m.key] === "number" ? Number(summary[m.key]).toLocaleString("en-IN") : "—"}
            </div>
            <div className="mt-1 text-sm font-medium text-neutral-700">{m.label}</div>
            <div className="text-[11px] text-neutral-400">{m.hint}</div>
          </Card>
        ))}
      </div>

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