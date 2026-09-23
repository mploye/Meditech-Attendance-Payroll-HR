"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, statusTone } from "@/components/ui";

type DailyRow = {
  id: string;
  employee_id: string;
  employee_name?: string;
  attendance_date: string;
  first_name?: string;
  last_name?: string;
  employee_code?: string;
  status: string;
  check_in?: string;
  check_out?: string;
  late_minutes?: number;
  overtime_minutes?: number;
  work_minutes?: number;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function AttendancePage() {
  const [date, setDate] = useState(today());
  const [rows, setRows] = useState<DailyRow[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setError("");
    try {
      const data = await api.get<{ items: DailyRow[] }>("/api/v1/attendance/daily", { date, page_size: 200 });
      setRows(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load attendance");
      setRows([]);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  const run = async (action: "sync" | "process") => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const endpoint = action === "process" ? `/api/v1/attendance/process` : `/api/v1/attendance/sync`;
      const result = await api.post<Record<string, unknown>>(endpoint, action === "process" ? { date } : {});
      setNotice(
        action === "process"
          ? `Processed for ${date}: ${JSON.stringify(result ?? {})}`
          : `Sync complete: ${JSON.stringify(result ?? {})}`
      );
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${action} failed`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Daily Attendance"
        subtitle="Punch logs processed into daily status"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Input type="date" value={date} onChange={setDate} className="w-full sm:w-44" />
            <Button variant="secondary" onClick={() => run("sync")} disabled={busy}>
              Sync punches
            </Button>
            <Button onClick={() => run("process")} disabled={busy}>
              Process day
            </Button>
          </div>
        }
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      <Card>
        <CardHeader title={`${rows.length} record(s) for ${date}`} />
        {rows.length === 0 ? (
          <Empty text="No daily records — sync punches then process the day" />
        ) : (
          <div className="overflow-x-auto">
            <table className="mobile-stack w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Employee</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">In</th>
                  <th className="px-5 py-3 font-medium">Out</th>
                  <th className="px-5 py-3 font-medium">Late (min)</th>
                  <th className="px-5 py-3 font-medium">OT (min)</th>
                  <th className="px-5 py-3 font-medium">Work (min)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-neutral-50">
                    <td data-label="Employee" className="px-5 py-3">
                      <div className="font-medium text-neutral-800">
                        {r.employee_name || `${r.first_name || ""} ${r.last_name || ""}`.trim() || r.employee_id}
                      </div>
                      {r.employee_code ? <div className="text-xs text-neutral-400">{r.employee_code}</div> : null}
                    </td>
                    <td data-label="Status" className="px-5 py-3">
                      <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                    </td>
                    <td data-label="In" className="px-5 py-3 text-neutral-500">{r.check_in ? String(r.check_in).slice(11, 16) : "—"}</td>
                    <td data-label="Out" className="px-5 py-3 text-neutral-500">{r.check_out ? String(r.check_out).slice(11, 16) : "—"}</td>
                    <td data-label="Late (min)" className="px-5 py-3 text-neutral-500">{r.late_minutes ?? "—"}</td>
                    <td data-label="OT (min)" className="px-5 py-3 text-neutral-500">{r.overtime_minutes ?? "—"}</td>
                    <td data-label="Work (min)" className="px-5 py-3 text-neutral-500">{r.work_minutes ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}