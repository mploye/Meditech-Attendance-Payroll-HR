"use client";

import { Fragment, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, Select } from "@/components/ui";

type ShiftBreak = {
  id: string;
  name: string;
  break_type: "SCHEDULED" | "RESTROOM";
  start_time?: string | null;
  max_duration_minutes: number;
  is_paid: boolean;
  sort_order: number;
  active: boolean;
};

type Shift = {
  id: string;
  name: string;
  code?: string;
  start_time?: string;
  end_time?: string;
  grace_period_minutes: number;
  minimum_work_minutes: number;
  break_minutes: number;
  minimum_shift_hours: number;
  maximum_shift_hours: number;
  scheduled_break_count: number;
  scheduled_break_duration: number;
  overtime_enabled: boolean;
  is_default: boolean;
  active: boolean;
  breaks?: ShiftBreak[];
};

const EMPTY_BREAK_FORM = { name: "", break_type: "SCHEDULED", start_time: "", max_duration_minutes: "15", is_paid: "true", sort_order: "0" };

export default function ShiftsPage() {
  const [items, setItems] = useState<Shift[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [breakForm, setBreakForm] = useState<Record<string, string>>(EMPTY_BREAK_FORM);
  const [schedules, setSchedules] = useState<Record<string, ShiftBreak[]>>({});

  const load = async () => {
    try {
      const data = await api.get<Shift[]>("/api/v1/shifts");
      setItems(data);
      const byId: Record<string, ShiftBreak[]> = {};
      for (const s of data) byId[s.id] = s.breaks || [];
      setSchedules(byId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load shifts");
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/v1/shifts", {
        ...form,
        grace_period_minutes: Number(form.grace_period_minutes || 0),
        minimum_work_minutes: Number(form.minimum_work_minutes || 0),
        break_minutes: Number(form.break_minutes || 0),
        minimum_shift_hours: Number(form.minimum_shift_hours || 8),
        maximum_shift_hours: Number(form.maximum_shift_hours || 9),
        scheduled_break_count: Number(form.scheduled_break_count || 3),
        scheduled_break_duration: Number(form.scheduled_break_duration || 15),
        overtime_after_minutes: Number(form.overtime_after_minutes || 60),
        overtime_enabled: form.overtime_enabled === "true",
        night_shift: form.night_shift === "true",
        is_default: form.is_default === "true",
        active: true,
      });
      setNotice("Shift created");
      setShowForm(false);
      setForm({});
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create shift");
    } finally {
      setBusy(false);
    }
  };

  const submitBreak = async (e: React.FormEvent, shiftId: string) => {
    e.preventDefault();
    if (!shiftId) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/api/v1/shifts/${shiftId}/breaks`, {
        ...breakForm,
        break_type: breakForm.break_type || "SCHEDULED",
        max_duration_minutes: Number(breakForm.max_duration_minutes || 15),
        sort_order: Number(breakForm.sort_order || 0),
        is_paid: breakForm.is_paid === "true",
        active: true,
      });
      setNotice("Scheduled break added");
      setBreakForm(EMPTY_BREAK_FORM);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add break");
    } finally {
      setBusy(false);
    }
  };

  const removeBreak = async (shiftId: string, breakId: string) => {
    setBusy(true);
    setError("");
    try {
      await api.del(`/api/v1/shifts/${shiftId}/breaks/${breakId}`);
      setNotice("Scheduled break removed");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove break");
    } finally {
      setBusy(false);
    }
  };

  const toggle = (id: string) => setExpanded((cur) => (cur === id ? null : id));

  return (
    <div>
      <PageHeader
        title="Shifts"
        subtitle="Schedules, break rules and overtime for attendance"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : "+ New Shift"}</Button>}
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title="Create shift" />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-4">
            <Input label="Name *" required value={form.name} onChange={(v) => setForm((s) => ({ ...s, name: v }))} />
            <Input label="Code" value={form.code} onChange={(v) => setForm((s) => ({ ...s, code: v }))} />
            <Input label="Start time" type="time" value={form.start_time} onChange={(v) => setForm((s) => ({ ...s, start_time: v }))} />
            <Input label="End time" type="time" value={form.end_time} onChange={(v) => setForm((s) => ({ ...s, end_time: v }))} />
            <Input label="Grace period (min)" type="number" value={form.grace_period_minutes} onChange={(v) => setForm((s) => ({ ...s, grace_period_minutes: v }))} />
            <Input label="Min work (min)" type="number" value={form.minimum_work_minutes} onChange={(v) => setForm((s) => ({ ...s, minimum_work_minutes: v }))} />
            <Input label="Legacy break (min)" type="number" value={form.break_minutes} onChange={(v) => setForm((s) => ({ ...s, break_minutes: v }))} />
            <Input label="OT after (min)" type="number" value={form.overtime_after_minutes} onChange={(v) => setForm((s) => ({ ...s, overtime_after_minutes: v }))} />
            <Input label="Min shift hours" type="number" value={form.minimum_shift_hours} onChange={(v) => setForm((s) => ({ ...s, minimum_shift_hours: v }))} />
            <Input label="Max shift hours" type="number" value={form.maximum_shift_hours} onChange={(v) => setForm((s) => ({ ...s, maximum_shift_hours: v }))} />
            <Input label="Scheduled breaks (#)" type="number" value={form.scheduled_break_count} onChange={(v) => setForm((s) => ({ ...s, scheduled_break_count: v }))} />
            <Input label="Break duration (min)" type="number" value={form.scheduled_break_duration} onChange={(v) => setForm((s) => ({ ...s, scheduled_break_duration: v }))} />
            <div className="flex items-end gap-4">
              <label className="flex items-center gap-2 text-sm text-neutral-700">
                <input type="checkbox" checked={form.overtime_enabled === "true"} onChange={(e) => setForm((s) => ({ ...s, overtime_enabled: String(e.target.checked) }))} />
                Overtime enabled
              </label>
              <label className="flex items-center gap-2 text-sm text-neutral-700">
                <input type="checkbox" checked={form.night_shift === "true"} onChange={(e) => setForm((s) => ({ ...s, night_shift: String(e.target.checked) }))} />
                Night shift
              </label>
              <label className="flex items-center gap-2 text-sm text-neutral-700">
                <input type="checkbox" checked={form.is_default === "true"} onChange={(e) => setForm((s) => ({ ...s, is_default: String(e.target.checked) }))} />
                Default shift
              </label>
            </div>
            <div className="flex justify-end gap-2 md:col-span-4">
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Create"}</Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        {items.length === 0 ? (
          <Empty />
        ) : (
          <div className="overflow-x-auto">
            <table className="mobile-stack w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Hours</th>
                  <th className="px-5 py-3 font-medium">Shift hrs</th>
                  <th className="px-5 py-3 font-medium">Breaks</th>
                  <th className="px-5 py-3 font-medium">OT</th>
                  <th className="px-5 py-3 font-medium">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((s) => (
                  <Fragment key={s.id}>
                    <tr className="hover:bg-neutral-50">
                      <td data-label="Name" className="px-5 py-3 font-medium text-neutral-800">
                        <button onClick={() => toggle(s.id)} className="text-left underline-offset-2 hover:underline">
                          {s.name}
                        </button>
                        {s.code ? <span className="text-neutral-400"> ({s.code})</span> : null}
                      </td>
                      <td data-label="Hours" className="px-5 py-3 text-neutral-500">
                        {s.start_time || "—"} – {s.end_time || "—"}
                      </td>
                      <td data-label="Shift hrs" className="px-5 py-3 text-neutral-500">
                        {s.minimum_shift_hours ?? 8}–{s.maximum_shift_hours ?? 9}
                      </td>
                      <td data-label="Breaks" className="px-5 py-3 text-neutral-500">
                        {s.breaks && s.breaks.length > 0
                          ? `${s.breaks.filter((b) => b.active && b.break_type === "SCHEDULED").length} × ${s.breaks.find((b) => b.break_type === "SCHEDULED")?.max_duration_minutes ?? "?"} min`
                          : `${s.scheduled_break_count ?? 3} × ${s.scheduled_break_duration ?? 15} min`}
                      </td>
                      <td data-label="OT" className="px-5 py-3 text-neutral-500">{s.overtime_enabled ? "Yes" : "No"}</td>
                      <td data-label="Flags" className="px-5 py-3">
                        {s.is_default ? <Badge tone="blue">Default</Badge> : null}
                        {!s.active ? <Badge tone="red">Inactive</Badge> : null}
                      </td>
                    </tr>
                    {expanded === s.id ? (
                      <tr>
                        <td colSpan={6} className="bg-neutral-50 px-5 py-4">
                          <div className="mb-3">
                            <h4 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Scheduled breaks</h4>
                            {(schedules[s.id] || []).length === 0 ? (
                              <Empty text="No scheduled breaks configured yet" />
                            ) : (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {(schedules[s.id] || [])
                                  .slice()
                                  .sort((a, b) => a.sort_order - b.sort_order)
                                  .map((b) => (
                                    <span key={b.id} className="inline-flex items-center gap-2 rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-sm">
                                      <span className="font-medium text-neutral-800">{b.name}</span>
                                      <span className="text-neutral-400">
                                        {b.start_time ? `${b.start_time} · ` : ""}{b.max_duration_minutes} min · {b.is_paid ? "Paid" : "Unpaid"}
                                      </span>
                                      {!b.active ? <Badge tone="red">Inactive</Badge> : null}
                                      <button
                                        onClick={() => removeBreak(s.id, b.id)}
                                        className="text-xs text-rose-600 hover:underline"
                                        disabled={busy}
                                      >
                                        Remove
                                      </button>
                                    </span>
                                  ))}
                              </div>
                            )}
                          </div>
                          <form onSubmit={(e) => submitBreak(e, s.id)} className="grid grid-cols-2 gap-3 md:grid-cols-6">
                            <Input label="Name *" required value={breakForm.name} onChange={(v) => setBreakForm((f) => ({ ...f, name: v }))} />
                            <Select
                              label="Type"
                              value={breakForm.break_type}
                              options={[
                                { value: "SCHEDULED", label: "Scheduled" },
                                { value: "RESTROOM", label: "Restroom" },
                              ]}
                              onChange={(v) => setBreakForm((f) => ({ ...f, break_type: v }))}
                            />
                            <Input label="Start time" type="time" value={breakForm.start_time} onChange={(v) => setBreakForm((f) => ({ ...f, start_time: v }))} />
                            <Input label="Max (min)" type="number" value={breakForm.max_duration_minutes} onChange={(v) => setBreakForm((f) => ({ ...f, max_duration_minutes: v }))} />
                            <Select
                              label="Paid"
                              value={breakForm.is_paid}
                              options={[
                                { value: "true", label: "Paid" },
                                { value: "false", label: "Unpaid" },
                              ]}
                              onChange={(v) => setBreakForm((f) => ({ ...f, is_paid: v }))}
                            />
                            <div className="flex items-end">
                              <Button type="submit" disabled={busy}>Add break</Button>
                            </div>
                          </form>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}