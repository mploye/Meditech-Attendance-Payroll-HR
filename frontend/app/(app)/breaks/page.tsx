"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getStoredUser } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, statusTone } from "@/components/ui";

type BreakRow = {
  id: string;
  employee_id: string;
  employee_name?: string;
  employee_code?: string;
  name?: string | null;
  break_type: "SCHEDULED" | "RESTROOM";
  break_date: string;
  start_time?: string | null;
  end_time?: string | null;
  duration_minutes: number;
  is_paid: boolean;
  status: string;
  elapsed_minutes?: number;
  remarks?: string | null;
};

type AvailableBreak = {
  id: string;
  name: string;
  start_time?: string | null;
  max_duration_minutes: number;
  is_paid: boolean;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function fmtTime(ts?: string | null): string {
  if (!ts) return "—";
  return String(ts).slice(11, 16);
}

function fmtHM(min: number | string | undefined | null): string {
  const m = Number(min || 0);
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

const isEmployeeRole = () => {
  const user = getStoredUser();
  return String(user?.role ?? "EMPLOYEE") === "EMPLOYEE";
};

export default function BreaksPage() {
  const isEmployee = isEmployeeRole();
  const [date, setDate] = useState(today());
  const [rows, setRows] = useState<BreakRow[]>([]);
  const [onBreak, setOnBreak] = useState<BreakRow[]>([]);
  const [active, setActive] = useState<BreakRow | null>(null);
  const [available, setAvailable] = useState<AvailableBreak[]>([]);
  const [canViewAdmin, setCanViewAdmin] = useState(!isEmployee);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const loadSelf = useCallback(async () => {
    try {
      const [a, av] = await Promise.all([
        api.get<BreakRow | null>("/api/v1/breaks/active"),
        api.get<AvailableBreak[]>("/api/v1/breaks/available"),
      ]);
      setActive(a);
      setAvailable(av);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load your break status");
    }
  }, []);

  const loadAdmin = useCallback(
    async (d: string) => {
      try {
        const [feed, daily] = await Promise.all([
          api.get<BreakRow[]>("/api/v1/breaks/today"),
          api.get<BreakRow[]>("/api/v1/breaks/daily", { date: d, page_size: 200 }),
        ]);
        setOnBreak(feed);
        setRows(daily);
        setCanViewAdmin(true);
      } catch {
        setCanViewAdmin(false);
      }
    },
    []
  );

  useEffect(() => {
    const t = setTimeout(() => {
      void loadSelf();
      if (!isEmployee) void loadAdmin(date);
      const timer = setInterval(() => void loadSelf(), 30_000);
      return () => clearInterval(timer);
    }, 0);
    return () => clearTimeout(t);
  }, [isEmployee, date, loadSelf, loadAdmin]);

  useEffect(() => {
    if (!isEmployee) void loadAdmin(date);
  }, [date, isEmployee, loadAdmin]);

  useEffect(() => {
    const interval = setInterval(() => setActive((a) => (a ? { ...a } : a)), 30_000);
    return () => clearInterval(interval);
  }, []);

  const run = async (path: string, body?: unknown, success?: string) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.post(path, body);
      setNotice(success || "Done");
      await Promise.all([loadSelf(), !isEmployee && loadAdmin(date)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const startScheduled = (sb: AvailableBreak) =>
    run("/api/v1/breaks/start", { break_type: "SCHEDULED", scheduled_break_id: sb.id }, `${sb.name} started`);

  const startRestroom = () => run("/api/v1/breaks/start", { break_type: "RESTROOM" }, "Restroom break started");

  const endBreak = (id: string) => run(`/api/v1/breaks/${id}/end`, {}, "Break ended");

  return (
    <div>
      <PageHeader
        title="Breaks"
        subtitle="Scheduled, restroom and ad-hoc break tracking"
        action={
          !isEmployee ? (
            <div className="flex flex-wrap items-center gap-2">
              <Input type="date" value={date} onChange={setDate} className="w-full sm:w-44" />
            </div>
          ) : null
        }
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {isEmployee ? (
          <div className="lg:col-span-2">
            <Card>
              <CardHeader title="My break" />
              <div className="p-5">
                {active ? (
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-neutral-800">
                        {active.name || (active.break_type === "RESTROOM" ? "Restroom break" : "Break")}
                      </div>
                      <div className="text-xs text-neutral-500">
                        Started {fmtTime(active.start_time)} · {fmtHM(active.elapsed_minutes ?? active.duration_minutes)} so far
                      </div>
                    </div>
                    <Button onClick={() => endBreak(active.id)} disabled={busy}>
                      End break
                    </Button>
                  </div>
                ) : (
                  <div>
                    <p className="mb-3 text-sm text-neutral-500">
                      {available.length > 0
                        ? "Choose a scheduled break or take a quick restroom break."
                        : "No scheduled breaks for your shift — you can still log a restroom break."}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {available.map((sb) => (
                        <Button key={sb.id} variant="secondary" onClick={() => startScheduled(sb)} disabled={busy}>
                          {sb.name} {sb.start_time ? `· ${fmtTime(sb.start_time)}` : ""}
                        </Button>
                      ))}
                      <Button onClick={startRestroom} disabled={busy}>
                        Restroom break
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>
        ) : null}

        {canViewAdmin ? (
          <Card>
            <CardHeader title="Currently on break" />
            {onBreak.length === 0 ? (
              <Empty text="Nobody is on break right now" />
            ) : (
              <ul className="divide-y divide-neutral-100">
                {onBreak.map((b) => (
                  <li key={b.id} className="flex items-center justify-between px-5 py-3">
                    <div>
                      <div className="text-sm font-medium text-neutral-800">{b.employee_name || b.employee_id}</div>
                      <div className="text-xs text-neutral-400">
                        {b.employee_code} · {b.name || b.break_type} · {fmtTime(b.start_time)}
                      </div>
                    </div>
                    <Badge tone="amber">{fmtHM(b.elapsed_minutes ?? b.duration_minutes)}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ) : null}
      </div>

      {canViewAdmin ? (
        <Card>
          <CardHeader title={`${rows.length} break record(s) for ${date}`} />
          {rows.length === 0 ? (
            <Empty text="No breaks recorded for this day" />
          ) : (
            <div className="overflow-x-auto">
              <table className="mobile-stack w-full text-left text-sm">
                <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                  <tr>
                    <th className="px-5 py-3 font-medium">Employee</th>
                    <th className="px-5 py-3 font-medium">Break</th>
                    <th className="px-5 py-3 font-medium">Type</th>
                    <th className="px-5 py-3 font-medium">Start</th>
                    <th className="px-5 py-3 font-medium">End</th>
                    <th className="px-5 py-3 font-medium">Duration</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {rows.map((r) => (
                    <tr key={r.id} className="hover:bg-neutral-50">
                      <td data-label="Employee" className="px-5 py-3">
                        <div className="font-medium text-neutral-800">{r.employee_name || r.employee_id}</div>
                        {r.employee_code ? <div className="text-xs text-neutral-400">{r.employee_code}</div> : null}
                      </td>
                      <td data-label="Break" className="px-5 py-3 text-neutral-600">
                        {r.name || (r.break_type === "RESTROOM" ? "Restroom" : "Break")}
                        {!r.is_paid ? <Badge tone="amber">Unpaid</Badge> : null}
                      </td>
                      <td data-label="Type" className="px-5 py-3 text-neutral-500">
                        <Badge tone={r.break_type === "SCHEDULED" ? "blue" : "neutral"}>{r.break_type}</Badge>
                      </td>
                      <td data-label="Start" className="px-5 py-3 text-neutral-500">{fmtTime(r.start_time)}</td>
                      <td data-label="End" className="px-5 py-3 text-neutral-500">{fmtTime(r.end_time)}</td>
                      <td data-label="Duration" className="px-5 py-3 text-neutral-500">
                        {r.status === "ACTIVE" ? fmtHM(r.elapsed_minutes ?? r.duration_minutes) : fmtHM(r.duration_minutes)}
                      </td>
                      <td data-label="Status" className="px-5 py-3">
                        <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : null}
    </div>
  );
}