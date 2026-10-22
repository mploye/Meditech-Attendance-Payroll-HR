"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { dateKey, formatTime, formatTimeWithSeconds } from "@/lib/datetime";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, statusTone } from "@/components/ui";

type Punch = {
  time: string;
  event_type: string;
  source?: string;
};

type BreakSeg = {
  id: string;
  name?: string;
  break_type: string;
  start_time?: string;
  end_time?: string;
  duration_minutes?: number;
  is_paid?: boolean;
  status: string;
};

type DailyRow = {
  id: string;
  employee_id: string;
  employee_name?: string;
  attendance_date: string;
  first_name?: string;
  last_name?: string;
  employee_code?: string;
  status: string;
  first_in?: string;
  last_out?: string;
  late_minutes?: number;
  overtime_minutes?: number;
  worked_minutes?: number;
  break_minutes?: number;
  punches?: Punch[];
  breaks?: BreakSeg[];
};

type DeviceInfo = {
  id: string;
  name?: string;
  serial_number?: string;
  status?: string;
  last_seen_at?: string | null;
  last_punch_at?: string | null;
  last_sync_at?: string | null;
  clock_drift_minutes?: number | null;
};

type SummaryRow = {
  employee_id: string;
  employee_code?: string;
  employee_name?: string;
  present_days: number;
  absent_days: number;
  missing_punch_days: number;
  worked_minutes: number;
  present_worked_minutes: number;
  late_minutes: number;
  overtime_minutes: number;
  total_days: number;
};

type Tab = "daily" | "weekly" | "monthly";

function ymd(d: Date): string {
  const tz = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return tz.toISOString().slice(0, 10);
}

function today(): string {
  return dateKey(new Date());
}

function startOfWeek(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day; // Monday start
  d.setDate(d.getDate() + diff);
  return ymd(d);
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return ymd(d);
}

function startOfMonth(iso: string): string {
  return iso.slice(0, 8) + "01";
}

function endOfMonth(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return ymd(new Date(d.getFullYear(), d.getMonth() + 1, 0));
}

function hours(minutes?: number): string {
  if (!minutes) return "0.0h";
  return (minutes / 60).toFixed(1) + "h";
}

function hhmm(value?: string): string {
  if (!value) return "—";
  return formatTime(value);
}

function mins(value?: number): string {
  if (!value) return "—";
  const h = Math.floor(value / 60);
  const m = value % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

function breakLabel(b: BreakSeg): string {
  if (b.name) return b.name;
  if (b.break_type === "RESTROOM") return "Restroom";
  if (b.break_type === "SCHEDULED") return "Scheduled";
  if (b.break_type === "PUNCHED") return "Punch break";
  return b.break_type;
}

function punchLabel(p: Punch): string {
  const t = (p.event_type || "").toUpperCase();
  if (t.includes("IN")) return "IN";
  if (t.includes("OUT")) return "OUT";
  return t || "PUNCH";
}

const POLL_MS = 30000;
const CACHE_PREFIX = "hrms.attendance.";

function readCache<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(CACHE_PREFIX + key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeCache(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(CACHE_PREFIX + key, JSON.stringify(value));
  } catch {
    // storage unavailable — caching is best effort
  }
}

export default function AttendancePage() {
  const [tab, setTab] = useState<Tab>("daily");
  const [date, setDate] = useState(today());
  const [rows, setRows] = useState<DailyRow[]>([]);
  const [summary, setSummary] = useState<SummaryRow[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [mobileIndex, setMobileIndex] = useState(0);
  const [device, setDevice] = useState<DeviceInfo | null>(null);

  const loadDevice = useCallback(async () => {
    try {
      const data = await api.get<{ items: DeviceInfo[] } | DeviceInfo[]>("/api/v1/devices/", {
        page_size: 50,
      });
      const items = Array.isArray(data) ? data : data.items;
      setDevice(items[0] ?? null);
    } catch {
      // device status is informational only
    }
  }, []);

  const activeRange = useMemo((): { from: string; to: string } => {
    if (tab === "daily") return { from: date, to: date };
    if (tab === "weekly") {
      const from = startOfWeek(date);
      return { from, to: addDays(from, 6) };
    }
    return { from: startOfMonth(date), to: endOfMonth(date) };
  }, [tab, date]);

  const loadDaily = useCallback(
    async (silent = false) => {
      const key = `daily:${date}`;
      const cached = readCache<DailyRow[]>(key);
      if (cached) {
        setRows(cached);
        setLoading(false);
      } else if (!silent) {
        setLoading(true);
      }
      try {
        const data = await api.get<{ items: DailyRow[] }>("/api/v1/attendance/daily", {
          date,
          page_size: 200,
        });
        setRows(data.items);
        writeCache(key, data.items);
        setError("");
      } catch (err) {
        if (!cached && !silent) setError(err instanceof Error ? err.message : "Failed to load attendance");
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [date]
  );

  const loadSummary = useCallback(
    async (silent = false) => {
      const key = `summary:${activeRange.from}:${activeRange.to}`;
      const cached = readCache<SummaryRow[]>(key);
      if (cached) {
        setSummary(cached);
        setLoading(false);
      } else if (!silent) {
        setLoading(true);
      }
      try {
        const data = await api.get<SummaryRow[]>("/api/v1/attendance/range-summary", {
          from_date: activeRange.from,
          to_date: activeRange.to,
        });
        setSummary(data);
        writeCache(key, data);
        setError("");
      } catch (err) {
        if (!cached && !silent) setError(err instanceof Error ? err.message : "Failed to load summary");
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [activeRange.from, activeRange.to]
  );

  const reload = useCallback(
    async (silent = false) => {
      const device = loadDevice();
      if (tab === "daily") await loadDaily(silent);
      else await loadSummary(silent);
      void device;
      setLastUpdated(formatTimeWithSeconds(new Date()));
    },
    [tab, loadDaily, loadSummary, loadDevice]
  );

  // Initial paint and tab/date changes load the visible data first. The
  // attendance engine already recomputes on every device push and every
  // minute in the background, so the page must not block on a manual
  // reprocess (that call is slow and was causing multi-second loading).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await reload(false);
      if (cancelled) return;
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, date]);

  // live auto-poll every 30s (data only — no reprocess)
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => {
      void reload(true);
    }, POLL_MS);
    return () => clearInterval(t);
  }, [live, reload]);

  const run = async (action: "sync" | "process") => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (action === "process") {
        const { from, to } = activeRange;
        const result = await api.post<Record<string, unknown>>(
          `/api/v1/attendance/process?from_date=${from}&to_date=${to}`,
          undefined
        );
        setNotice(`Processed ${from} → ${to}: ${JSON.stringify(result ?? {})}`);
      } else {
        const result = await api.post<Record<string, unknown>>("/api/v1/attendance/sync", undefined);
        setNotice(`Sync complete: ${JSON.stringify(result ?? {})}`);
      }
      await reload(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : `${action} failed`);
    } finally {
      setBusy(false);
    }
  };

  const totals = summary.reduce(
    (acc, r) => {
      acc.present += r.present_days;
      acc.absent += r.absent_days;
      acc.worked += r.worked_minutes;
      return acc;
    },
    { present: 0, absent: 0, worked: 0 }
  );

  const tabLabels: Record<Tab, string> = { daily: "Daily", weekly: "Weekly", monthly: "Monthly" };

  return (
    <div>
      <PageHeader
        title="Attendance"
        subtitle="Live punch data — daily, weekly and monthly"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                live ? "bg-green-50 text-green-700" : "bg-neutral-100 text-neutral-500"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${live ? "animate-pulse bg-green-500" : "bg-neutral-400"}`}
              />
              {live ? "LIVE" : "PAUSED"}
            </span>
            <Button variant="secondary" onClick={() => setLive((v) => !v)}>
              {live ? "Pause" : "Resume"}
            </Button>
            <Input type="date" value={date} onChange={setDate} className="w-full sm:w-44" />
            <Button variant="secondary" onClick={() => run("sync")} disabled={busy}>
              Sync
            </Button>
            <Button onClick={() => run("process")} disabled={busy}>
              Process
            </Button>
          </div>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {(["daily", "weekly", "monthly"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              tab === t ? "bg-neutral-900 text-white" : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
            }`}
          >
            {tabLabels[t]}
          </button>
        ))}
        {lastUpdated ? (
          <span className="ml-auto self-center text-xs text-neutral-400">
            Updated {lastUpdated}
          </span>
        ) : null}
      </div>

      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />
      {device ? <DeviceBanner device={device} /> : null}

      {tab === "daily" ? (
        <Card>
          <CardHeader title={`${rows.length} record(s) for ${date}`} />
          {rows.length === 0 ? (
            <Empty text={loading ? "Loading…" : "No daily records — punches sync automatically"} />
          ) : (
            <>
              <MobileEmployeePager
                rows={rows}
                index={Math.min(mobileIndex, rows.length - 1)}
                onIndex={(i) => setMobileIndex(i)}
              />
              <div className="hidden overflow-x-auto md:block">
              <table className="mobile-stack w-full text-left text-sm">
                <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                  <tr>
                    <th className="px-5 py-3 font-medium">Employee</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">In</th>
                    <th className="px-5 py-3 font-medium">Break</th>
                    <th className="px-5 py-3 font-medium">Out</th>
                    <th className="px-5 py-3 font-medium">Total Hours</th>
                    <th className="px-5 py-3 font-medium">Late</th>
                    <th className="px-5 py-3 font-medium">OT</th>
                    <th className="px-5 py-3 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {rows.map((r) => {
                    const isOpen = !!expanded[r.id];
                    const breakCount = r.breaks?.length ?? 0;
                    const isIn = (r.punches || [])
                      .filter((p) => punchLabel(p) === "IN").length;
                    return (
                      <Fragment key={r.id}>
                        <tr className="hover:bg-neutral-50">
                          <td data-label="Employee" className="px-5 py-3">
                            <div className="font-medium text-neutral-800">
                              {r.employee_name || `${r.first_name || ""} ${r.last_name || ""}`.trim() || r.employee_id}
                            </div>
                            {r.employee_code ? (
                              <div className="text-xs text-neutral-400">{r.employee_code}</div>
                            ) : null}
                          </td>
                          <td data-label="Status" className="px-5 py-3">
                            <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                          </td>
                          <td data-label="In" className="px-5 py-3 font-medium text-green-700">{hhmm(r.first_in)}</td>
                          <td data-label="Break" className="px-5 py-3 text-neutral-500">
                            {breakCount ? (
                              <button
                                onClick={() => setExpanded((s) => ({ ...s, [r.id]: !isOpen }))}
                                className="rounded bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 hover:bg-amber-100"
                              >
                                {mins(r.break_minutes)} · {breakCount}
                              </button>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td data-label="Out" className="px-5 py-3 font-medium text-neutral-700">{hhmm(r.last_out)}</td>
                          <td data-label="Total Hours" className="px-5 py-3 font-medium text-blue-700">{hours(r.worked_minutes)}</td>
                          <td data-label="Late" className="px-5 py-3 text-red-600">{r.late_minutes ? `${r.late_minutes}m` : "—"}</td>
                          <td data-label="OT" className="px-5 py-3 text-purple-600">{r.overtime_minutes ? `${r.overtime_minutes}m` : "—"}</td>
                          <td data-label="" className="px-5 py-3">
                            <Button variant="secondary" onClick={() => setExpanded((s) => ({ ...s, [r.id]: !isOpen }))}>
                              {isOpen ? "Hide" : "Detail"}
                            </Button>
                          </td>
                        </tr>
                        {isOpen ? (
                          <tr className="bg-neutral-50/60">
                            <td colSpan={9} className="px-5 py-4">
                              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                <div>
                                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                                    Punch sequence ({isIn} IN · {(r.punches || []).length - isIn} OUT)
                                  </div>
                                  {(r.punches || []).length === 0 ? (
                                    <div className="text-sm text-neutral-400">No raw punches recorded</div>
                                  ) : (
                                    <div className="flex flex-wrap gap-2">
                                      {(r.punches || []).map((p, i) => {
                                        const label = punchLabel(p);
                                        return (
                                          <span
                                            key={i}
                                            className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ${
                                              label === "IN"
                                                ? "bg-green-50 text-green-700"
                                                : "bg-neutral-100 text-neutral-600"
                                            }`}
                                          >
                                            <span className="opacity-70">{label}</span>
                                            {hhmm(p.time)}
                                          </span>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                                <div>
                                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                                    Breaks ({breakCount})
                                  </div>
                                  {breakCount === 0 ? (
                                    <div className="text-sm text-neutral-400">No breaks recorded</div>
                                  ) : (
                                    <table className="w-full text-left text-xs">
                                      <thead className="text-neutral-400">
                                        <tr>
                                          <th className="py-1 font-medium">Type</th>
                                          <th className="py-1 font-medium">Start</th>
                                          <th className="py-1 font-medium">End</th>
                                          <th className="py-1 font-medium">Duration</th>
                                          <th className="py-1 font-medium">Status</th>
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-neutral-100">
                                        {(r.breaks || []).map((b) => (
                                          <tr key={b.id}>
                                            <td className="py-1.5 text-neutral-700">{breakLabel(b)}</td>
                                            <td className="py-1.5 text-neutral-500">{hhmm(b.start_time)}</td>
                                            <td className="py-1.5 text-neutral-500">{hhmm(b.end_time)}</td>
                                            <td className="py-1.5 text-neutral-500">{mins(b.duration_minutes)}</td>
                                            <td className="py-1.5">
                                              <span className={b.status === "ACTIVE" ? "text-green-600" : "text-neutral-400"}>
                                                {b.status}
                                              </span>
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
              </div>
            </>
          )}
        </Card>
      ) : (
        <Card>
          <CardHeader
            title={`${summary.length} employee(s) — ${activeRange.from} → ${activeRange.to}`}
          />
          {summary.length === 0 ? (
            <Empty text={loading ? "Loading…" : "No summary records"} />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 border-b border-neutral-100 px-5 py-4 sm:grid-cols-3">
                <Stat label="Present (days)" value={String(totals.present)} tone="green" />
                <Stat label="Absent (days)" value={String(totals.absent)} tone="red" />
                <Stat label="Total hours" value={hours(totals.worked)} tone="blue" />
              </div>
              <div className="overflow-x-auto">
                <table className="mobile-stack w-full text-left text-sm">
                  <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                    <tr>
                      <th className="px-5 py-3 font-medium">Employee</th>
                      <th className="px-5 py-3 font-medium">Present</th>
                      <th className="px-5 py-3 font-medium">Absent</th>
                      <th className="px-5 py-3 font-medium">Missing</th>
                      <th className="px-5 py-3 font-medium">Hours</th>
                      <th className="px-5 py-3 font-medium">Late (min)</th>
                      <th className="px-5 py-3 font-medium">OT (min)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {summary.map((r) => (
                      <tr key={r.employee_id} className="hover:bg-neutral-50">
                        <td data-label="Employee" className="px-5 py-3">
                          <div className="font-medium text-neutral-800">
                            {r.employee_name || r.employee_id}
                          </div>
                          {r.employee_code ? (
                            <div className="text-xs text-neutral-400">{r.employee_code}</div>
                          ) : null}
                        </td>
                        <td data-label="Present" className="px-5 py-3">
                          <Badge tone="green">{r.present_days}</Badge>
                        </td>
                        <td data-label="Absent" className="px-5 py-3">
                          {r.absent_days ? <Badge tone="red">{r.absent_days}</Badge> : "0"}
                        </td>
                        <td data-label="Missing" className="px-5 py-3 text-neutral-500">
                          {r.missing_punch_days ?? 0}
                        </td>
                        <td data-label="Hours" className="px-5 py-3 text-neutral-500">
                          {hours(r.worked_minutes)}
                        </td>
                        <td data-label="Late (min)" className="px-5 py-3 text-neutral-500">
                          {r.late_minutes ?? 0}
                        </td>
                        <td data-label="OT (min)" className="px-5 py-3 text-neutral-500">
                          {r.overtime_minutes ?? 0}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Card>
      )}
    </div>
  );
}

function MobileEmployeePager({
  rows,
  index,
  onIndex,
}: {
  rows: DailyRow[];
  index: number;
  onIndex: (i: number) => void;
}) {
  const r = rows[index];
  if (!r) return null;
  const breakCount = r.breaks?.length ?? 0;
  const punches = r.punches || [];
  const isIn = punches.filter((p) => punchLabel(p) === "IN").length;
  const canPrev = index > 0;
  const canNext = index < rows.length - 1;
  const name = r.employee_name || `${r.first_name || ""} ${r.last_name || ""}`.trim() || r.employee_id;

  return (
    <div className="md:hidden">
      <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-3">
        <Button variant="secondary" onClick={() => canPrev && onIndex(index - 1)} disabled={!canPrev}>
          ‹ Prev
        </Button>
        <span className="text-xs font-medium text-neutral-400">
          {index + 1} of {rows.length}
        </span>
        <Button variant="secondary" onClick={() => canNext && onIndex(index + 1)} disabled={!canNext}>
          Next ›
        </Button>
      </div>

      <div className="px-4 py-4">
        <div className="mb-3 flex items-start justify-between">
          <div>
            <div className="text-base font-semibold text-neutral-900">{name}</div>
            {r.employee_code ? <div className="text-xs text-neutral-400">{r.employee_code}</div> : null}
          </div>
          <Badge tone={statusTone(r.status)}>{r.status}</Badge>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <MiniStat label="In" value={hhmm(r.first_in)} tone="text-green-700" />
          <MiniStat label="Break" value={breakCount ? mins(r.break_minutes) : "—"} tone="text-amber-700" />
          <MiniStat label="Out" value={hhmm(r.last_out)} tone="text-neutral-700" />
          <MiniStat label="Total Hours" value={hours(r.worked_minutes)} tone="text-blue-700" />
          <MiniStat label="Late" value={r.late_minutes ? `${r.late_minutes}m` : "—"} tone="text-red-600" />
          <MiniStat label="OT" value={r.overtime_minutes ? `${r.overtime_minutes}m` : "—"} tone="text-purple-600" />
        </div>

        <div className="mt-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Punch sequence ({isIn} IN · {punches.length - isIn} OUT)
          </div>
          {punches.length === 0 ? (
            <div className="text-sm text-neutral-400">No raw punches recorded</div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {punches.map((p, i) => {
                const label = punchLabel(p);
                return (
                  <span
                    key={i}
                    className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ${
                      label === "IN" ? "bg-green-50 text-green-700" : "bg-neutral-100 text-neutral-600"
                    }`}
                  >
                    <span className="opacity-70">{label}</span>
                    {hhmm(p.time)}
                  </span>
                );
              })}
            </div>
          )}
        </div>

        <div className="mt-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Breaks ({breakCount})
          </div>
          {breakCount === 0 ? (
            <div className="text-sm text-neutral-400">No breaks recorded</div>
          ) : (
            <div className="space-y-1.5">
              {(r.breaks || []).map((b) => (
                <div
                  key={b.id}
                  className="flex items-center justify-between rounded-md bg-neutral-50 px-3 py-2 text-xs"
                >
                  <span className="font-medium text-neutral-700">{breakLabel(b)}</span>
                  <span className="text-neutral-500">
                    {hhmm(b.start_time)} → {hhmm(b.end_time)}
                  </span>
                  <span className="text-neutral-500">{mins(b.duration_minutes)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-lg bg-neutral-50 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-neutral-400">{label}</div>
      <div className={`text-sm font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

function DeviceBanner({ device }: { device: DeviceInfo }) {
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const t = setInterval(() => setNowTick(Date.now()), 10000);
    return () => clearInterval(t);
  }, []);

  const ageOf = (value?: string | null): number | null => {
    if (!value) return null;
    const t = new Date(value).getTime();
    if (Number.isNaN(t)) return null;
    return Math.max(0, Math.round((nowTick - t) / 1000));
  };

  const contactAge = ageOf(device.last_seen_at);
  const punchAge = ageOf(device.last_punch_at);
  const drift = device.clock_drift_minutes ?? null;

  const offline = contactAge === null || contactAge > 180;
  const connectedNoPunch = !offline && (punchAge === null || punchAge > 900);
  const clockOff = drift !== null && Math.abs(drift) >= 90;

  const tone = offline
    ? "border-red-200 bg-red-50 text-red-800"
    : "border-amber-200 bg-amber-50 text-amber-800";

  const label =
    contactAge === null
      ? "Device has never contacted the server"
      : offline
        ? "Device not reporting since " + ago(contactAge)
        : connectedNoPunch
          ? punchAge === null
            ? "Device connected but no punches received yet"
            : "Device connected but not sending punches — last punch " + ago(punchAge)
          : clockOff
            ? `Device clock is ${Math.floor(Math.abs(drift) / 60)}h ${Math.abs(drift) % 60}m ${drift < 0 ? "behind" : "ahead"}`
            : "Device connected — punches are uploading automatically";

  const healthy = !offline && !connectedNoPunch && !clockOff;

  return (
    <div
      className={`mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border px-4 py-2.5 text-xs ${
        healthy ? "border-green-200 bg-green-50 text-green-800" : tone
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${
            healthy ? "animate-pulse bg-green-500" : offline ? "bg-red-500" : "bg-amber-500"
          }`}
        />
        <span className="font-medium">{label}</span>
        <span className="opacity-70">
          {device.name || "Attendance device"}
          {device.serial_number ? ` · ${device.serial_number}` : ""}
        </span>
      </div>
      <span className="opacity-70">
        {device.last_seen_at ? `Last contact ${formatTime(device.last_seen_at)}` : "Never contacted"}
        {device.last_punch_at ? ` · Last punch ${formatTime(device.last_punch_at)}` : ""}
      </span>
    </div>
  );
}

function ago(seconds: number): string {
  if (seconds < 60) return `${seconds}s ago`;
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function Stat({ label, value, tone }: { label: string; value: string; tone: "green" | "red" | "blue" }) {
  const tones = {
    green: "text-green-600",
    red: "text-red-600",
    blue: "text-blue-600",
  };
  return (
    <div className="rounded-lg bg-neutral-50 px-4 py-3">
      <div className="text-xs uppercase text-neutral-400">{label}</div>
      <div className={`text-xl font-semibold ${tones[tone]}`}>{value}</div>
    </div>
  );
}
