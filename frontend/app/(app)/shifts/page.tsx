"use client";

import { useEffect, useState } from "react";
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
  overtime_after_minutes?: number;
  night_shift?: boolean;
  is_default: boolean;
  active: boolean;
  breaks?: ShiftBreak[];
};

type Assignment = {
  id: string;
  employee_id: string;
  effective_from?: string | null;
  effective_to?: string | null;
  employee_code: string;
  employee_name: string;
};

type EmployeeOption = {
  id: string;
  employee_code: string;
  first_name: string;
  last_name?: string | null;
};

const EMPTY_BREAK_FORM = { name: "", break_type: "SCHEDULED", start_time: "", max_duration_minutes: "15", is_paid: "true", sort_order: "0" };

function employeeName(e: EmployeeOption) {
  return `${e.first_name || ""} ${e.last_name || ""}`.trim();
}

export default function ShiftsPage() {
  const [items, setItems] = useState<Shift[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Shift | null>(null);
  const [editForm, setEditForm] = useState<Record<string, string>>({});
  const [breakForm, setBreakForm] = useState<Record<string, string>>(EMPTY_BREAK_FORM);
  const [schedules, setSchedules] = useState<Record<string, ShiftBreak[]>>({});
  const [assignments, setAssignments] = useState<Record<string, Assignment[]>>({});
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [assignSelection, setAssignSelection] = useState<Record<string, string[]>>({});
  const [assignFrom, setAssignFrom] = useState<Record<string, string>>({});
  const [assignSearch, setAssignSearch] = useState<Record<string, string>>({});
  const [assignLoading, setAssignLoading] = useState<string | null>(null);

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

  const loadEmployees = async () => {
    try {
      const data = await api.get<{ items: EmployeeOption[]; total: number }>("/api/v1/employees/", {
        status: "ACTIVE",
        page: 1,
        page_size: 200,
      });
      setEmployees(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load employees");
    }
  };

  const loadAssignments = async (shiftId: string) => {
    setAssignLoading(shiftId);
    try {
      const data = await api.get<Assignment[]>(`/api/v1/shifts/${shiftId}/assignments`);
      setAssignments((cur) => ({ ...cur, [shiftId]: data }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load assigned employees");
    } finally {
      setAssignLoading(null);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => {
      void load();
      void loadEmployees();
    }, 0);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!editing) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setEditing(null);
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [editing]);

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

  const startEdit = (shift: Shift) => {
    setEditing(shift);
    setEditForm({
      name: shift.name || "",
      code: shift.code || "",
      start_time: shift.start_time ? shift.start_time.slice(0, 5) : "",
      end_time: shift.end_time ? shift.end_time.slice(0, 5) : "",
      grace_period_minutes: String(shift.grace_period_minutes ?? 0),
      minimum_work_minutes: String(shift.minimum_work_minutes ?? 0),
      break_minutes: String(shift.break_minutes ?? 0),
      overtime_after_minutes: String(shift.overtime_after_minutes ?? 60),
      minimum_shift_hours: String(shift.minimum_shift_hours ?? 8),
      maximum_shift_hours: String(shift.maximum_shift_hours ?? 9),
      scheduled_break_count: String(shift.scheduled_break_count ?? 3),
      scheduled_break_duration: String(shift.scheduled_break_duration ?? 15),
      overtime_enabled: String(!!shift.overtime_enabled),
      night_shift: String(!!shift.night_shift),
      is_default: String(!!shift.is_default),
    });
    setBreakForm(EMPTY_BREAK_FORM);
    void loadAssignments(shift.id);
  };

  const saveShift = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    setError("");
    try {
      await api.patch(`/api/v1/shifts/${editing.id}`, {
        ...editForm,
        grace_period_minutes: Number(editForm.grace_period_minutes || 0),
        minimum_work_minutes: Number(editForm.minimum_work_minutes || 0),
        break_minutes: Number(editForm.break_minutes || 0),
        overtime_after_minutes: Number(editForm.overtime_after_minutes || 60),
        minimum_shift_hours: Number(editForm.minimum_shift_hours || 8),
        maximum_shift_hours: Number(editForm.maximum_shift_hours || 9),
        scheduled_break_count: Number(editForm.scheduled_break_count || 3),
        scheduled_break_duration: Number(editForm.scheduled_break_duration || 15),
        overtime_enabled: editForm.overtime_enabled === "true",
        night_shift: editForm.night_shift === "true",
        is_default: editForm.is_default === "true",
      });
      setNotice("Shift updated");
      await load();
      setEditing(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update shift");
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

  const availableEmployees = (shiftId: string) => {
    const assigned = new Set(
      (assignments[shiftId] || []).filter((a) => !a.effective_to).map((a) => a.employee_id)
    );
    const term = (assignSearch[shiftId] || "").trim().toLowerCase();
    return employees.filter((e) => {
      if (assigned.has(e.id)) return false;
      if (!term) return true;
      return `${e.employee_code} ${employeeName(e)}`.toLowerCase().includes(term);
    });
  };

  const toggleEmployee = (shiftId: string, employeeId: string) => {
    setAssignSelection((cur) => {
      const list = cur[shiftId] || [];
      return {
        ...cur,
        [shiftId]: list.includes(employeeId) ? list.filter((x) => x !== employeeId) : [...list, employeeId],
      };
    });
  };

  const assignEmployees = async (shiftId: string) => {
    const ids = assignSelection[shiftId] || [];
    if (!ids.length) {
      setError("Select at least one employee to assign");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.post(`/api/v1/shifts/${shiftId}/assign`, {
        employee_ids: ids,
        effective_from: assignFrom[shiftId] || null,
      });
      setNotice(`${ids.length} employee${ids.length === 1 ? "" : "s"} assigned`);
      setAssignSelection((cur) => ({ ...cur, [shiftId]: [] }));
      await loadAssignments(shiftId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign employees");
    } finally {
      setBusy(false);
    }
  };

  const unassign = async (shiftId: string, assignmentId: string) => {
    setBusy(true);
    setError("");
    try {
      await api.del(`/api/v1/shifts/${shiftId}/assignments/${assignmentId}`);
      setNotice("Employee removed from shift");
      await loadAssignments(shiftId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove employee");
    } finally {
      setBusy(false);
    }
  };

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
                  <th className="px-5 py-3 font-medium">Edit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((s) => (
                  <tr key={s.id} className="hover:bg-neutral-50">
                    <td data-label="Name" className="px-5 py-3 font-medium text-neutral-800">
                      <span>{s.name}</span>
                      {s.code ? <span className="text-neutral-400"> ({s.code})</span> : null}
                      <span className="ml-2 inline-flex gap-1 align-middle">
                        {s.is_default ? <Badge tone="blue">Default</Badge> : null}
                        {!s.active ? <Badge tone="red">Inactive</Badge> : null}
                      </span>
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
                    <td data-label="Edit" className="px-5 py-3">
                      <Button variant="secondary" onClick={() => startEdit(s)}>Edit</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {editing ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 md:items-center md:p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="shift-edit-title"
          onClick={() => setEditing(null)}
        >
          <div
            className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl bg-white shadow-xl md:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3 border-b border-neutral-100 px-5 py-4">
              <div>
                <h3 id="shift-edit-title" className="text-base font-semibold text-neutral-800">Edit shift</h3>
                <p className="text-xs text-neutral-400">{editing.name}</p>
              </div>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setEditing(null)}
                className="rounded-lg px-2 py-1 text-xl leading-none text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
              >
                ×
              </button>
            </div>

            <div className="overflow-y-auto px-5 py-4">
              <form onSubmit={saveShift} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Input label="Name *" required value={editForm.name || ""} onChange={(v) => setEditForm((f) => ({ ...f, name: v }))} />
                <Input label="Code" value={editForm.code || ""} onChange={(v) => setEditForm((f) => ({ ...f, code: v }))} />
                <Input label="Start time" type="time" value={editForm.start_time || ""} onChange={(v) => setEditForm((f) => ({ ...f, start_time: v }))} />
                <Input label="End time" type="time" value={editForm.end_time || ""} onChange={(v) => setEditForm((f) => ({ ...f, end_time: v }))} />
                <Input label="Grace period (min)" type="number" value={editForm.grace_period_minutes || ""} onChange={(v) => setEditForm((f) => ({ ...f, grace_period_minutes: v }))} />
                <Input label="Min work (min)" type="number" value={editForm.minimum_work_minutes || ""} onChange={(v) => setEditForm((f) => ({ ...f, minimum_work_minutes: v }))} />
                <Input label="Legacy break (min)" type="number" value={editForm.break_minutes || ""} onChange={(v) => setEditForm((f) => ({ ...f, break_minutes: v }))} />
                <Input label="OT after (min)" type="number" value={editForm.overtime_after_minutes || ""} onChange={(v) => setEditForm((f) => ({ ...f, overtime_after_minutes: v }))} />
                <Input label="Min shift hours" type="number" value={editForm.minimum_shift_hours || ""} onChange={(v) => setEditForm((f) => ({ ...f, minimum_shift_hours: v }))} />
                <Input label="Max shift hours" type="number" value={editForm.maximum_shift_hours || ""} onChange={(v) => setEditForm((f) => ({ ...f, maximum_shift_hours: v }))} />
                <Input label="Scheduled breaks (#)" type="number" value={editForm.scheduled_break_count || ""} onChange={(v) => setEditForm((f) => ({ ...f, scheduled_break_count: v }))} />
                <Input label="Break duration (min)" type="number" value={editForm.scheduled_break_duration || ""} onChange={(v) => setEditForm((f) => ({ ...f, scheduled_break_duration: v }))} />
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 sm:col-span-2">
                  <label className="flex items-center gap-2 text-sm text-neutral-700">
                    <input type="checkbox" checked={editForm.overtime_enabled === "true"} onChange={(e) => setEditForm((f) => ({ ...f, overtime_enabled: String(e.target.checked) }))} />
                    Overtime enabled
                  </label>
                  <label className="flex items-center gap-2 text-sm text-neutral-700">
                    <input type="checkbox" checked={editForm.night_shift === "true"} onChange={(e) => setEditForm((f) => ({ ...f, night_shift: String(e.target.checked) }))} />
                    Night shift
                  </label>
                  <label className="flex items-center gap-2 text-sm text-neutral-700">
                    <input type="checkbox" checked={editForm.is_default === "true"} onChange={(e) => setEditForm((f) => ({ ...f, is_default: String(e.target.checked) }))} />
                    Default shift
                  </label>
                </div>
                <div className="flex justify-end gap-2 sm:col-span-2">
                  <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
                  <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save changes"}</Button>
                </div>
              </form>

              <div className="mt-6 border-t border-neutral-100 pt-5">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Assigned employees</h4>
                {assignLoading === editing.id ? (
                  <p className="mt-2 text-sm text-neutral-400">Loading…</p>
                ) : (assignments[editing.id] || []).length === 0 ? (
                  <Empty text="No employees assigned to this shift yet" />
                ) : (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(assignments[editing.id] || []).map((a) => (
                      <span key={a.id} className="inline-flex items-center gap-2 rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-sm">
                        <span className="font-medium text-neutral-800">{a.employee_name || a.employee_code}</span>
                        <span className="text-neutral-400">
                          {a.employee_code}
                          {a.effective_from ? ` · from ${a.effective_from}` : ""}
                          {a.effective_to ? ` · to ${a.effective_to}` : ""}
                        </span>
                        <button
                          onClick={() => unassign(editing.id, a.id)}
                          className="text-xs text-rose-600 hover:underline"
                          disabled={busy}
                        >
                          Remove
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                <div className="mt-3 rounded-lg border border-neutral-200 bg-white p-3">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <Input
                      label="Search employees"
                      placeholder="Name or code"
                      value={assignSearch[editing.id] || ""}
                      onChange={(v) => setAssignSearch((cur) => ({ ...cur, [editing.id]: v }))}
                    />
                    <Input
                      label="Effective from"
                      type="date"
                      value={assignFrom[editing.id] || ""}
                      onChange={(v) => setAssignFrom((cur) => ({ ...cur, [editing.id]: v }))}
                    />
                    <div className="flex items-end">
                      <Button
                        onClick={() => void assignEmployees(editing.id)}
                        disabled={busy || !(assignSelection[editing.id] || []).length}
                      >
                        Assign selected ({(assignSelection[editing.id] || []).length})
                      </Button>
                    </div>
                  </div>
                  <div className="mt-3 max-h-48 overflow-y-auto rounded border border-neutral-100">
                    {availableEmployees(editing.id).length === 0 ? (
                      <p className="px-3 py-2 text-sm text-neutral-400">
                        {employees.length === 0 ? "No active employees found." : "All matching employees are already assigned."}
                      </p>
                    ) : (
                      availableEmployees(editing.id).map((e) => (
                        <label
                          key={e.id}
                          className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-neutral-50"
                        >
                          <input
                            type="checkbox"
                            checked={(assignSelection[editing.id] || []).includes(e.id)}
                            onChange={() => toggleEmployee(editing.id, e.id)}
                          />
                          <span className="font-medium text-neutral-800">{e.employee_code}</span>
                          <span className="text-neutral-500">{employeeName(e)}</span>
                        </label>
                      ))
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-6 border-t border-neutral-100 pt-5">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Scheduled breaks</h4>
                {(schedules[editing.id] || []).length === 0 ? (
                  <Empty text="No scheduled breaks configured yet" />
                ) : (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(schedules[editing.id] || [])
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
                            onClick={() => removeBreak(editing.id, b.id)}
                            className="text-xs text-rose-600 hover:underline"
                            disabled={busy}
                          >
                            Remove
                          </button>
                        </span>
                      ))}
                  </div>
                )}
                <form onSubmit={(e) => submitBreak(e, editing.id)} className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-6">
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
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
