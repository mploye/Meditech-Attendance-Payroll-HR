"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, Select, statusTone } from "@/components/ui";

type LeaveType = { id: string; name: string; days_duration?: number };
type Employee = { id: string; first_name: string; last_name?: string; employee_code?: string };
type Request = {
  id: string;
  employee_id: string;
  leave_type_id: string;
  start_date: string;
  end_date: string;
  days: number;
  status: string;
  reason?: string;
  is_half_day?: boolean;
};

const STATUSES = ["PENDING", "APPROVED", "REJECTED", "CANCELLED"];

export default function LeavesPage() {
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [rows, setRows] = useState<Request[]>([]);
  const [status, setStatus] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const data = await api.get<{ items: Request[] }>("/api/v1/leaves/requests", { status, page_size: 200 });
      setRows(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leave requests");
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const [t, emps] = await Promise.all([
          api.get<LeaveType[]>("/api/v1/leaves/types"),
          api.get<{ items: Employee[] }>("/api/v1/employees/", { page_size: 500 }),
        ]);
        setTypes(t);
        setEmployees(emps.items);
      } catch {
        /* ignore */
      }
    })();
  }, []);

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const setName = (id: string) => {
    const e = employees.find((x) => x.id === id);
    return e ? `${e.first_name} ${e.last_name || ""}`.trim() : id.slice(0, 8);
  };
  const typeName = (id: string) => types.find((t) => t.id === id)?.name || id.slice(0, 8);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.post("/api/v1/leaves/apply", { ...form, is_half_day: form.is_half_day === "true" });
      setNotice("Leave request submitted");
      setShowForm(false);
      setForm({});
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply leave");
    } finally {
      setBusy(false);
    }
  };

  const decide = async (id: string, action: "approve" | "reject") => {
    setBusy(true);
    setError("");
    try {
      await api.post(`/api/v1/leaves/${id}/${action}`, {});
      setNotice(`Request ${action}d`);
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
        title="Leave Requests"
        subtitle="Apply and manage employee leave"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : "+ Apply Leave"}</Button>}
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title="Apply leave" />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-4">
            <Select
              label="Employee *"
              value={form.employee_id}
              onChange={(v) => setForm((s) => ({ ...s, employee_id: v }))}
              options={employees.map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name || ""}`.trim() }))}
            />
            <Select
              label="Leave type *"
              value={form.leave_type_id}
              onChange={(v) => setForm((s) => ({ ...s, leave_type_id: v }))}
              options={types.map((t) => ({ value: t.id, label: t.name }))}
            />
            <Input label="Start date *" type="date" required value={form.start_date} onChange={(v) => setForm((s) => ({ ...s, start_date: v }))} />
            <Input label="End date *" type="date" required value={form.end_date} onChange={(v) => setForm((s) => ({ ...s, end_date: v }))} />
            <Input label="Reason" className="md:col-span-3" value={form.reason} onChange={(v) => setForm((s) => ({ ...s, reason: v }))} />
            <label className="flex items-end gap-2 pb-2 text-sm text-neutral-700">
              <input type="checkbox" checked={form.is_half_day === "true"} onChange={(e) => setForm((s) => ({ ...s, is_half_day: String(e.target.checked) }))} />
              Half day
            </label>
            <div className="flex justify-end gap-2 md:col-span-4">
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button type="submit" disabled={busy || types.length === 0}>{busy ? "Submitting…" : "Apply"}</Button>
            </div>
          </form>
        </Card>
      )}

      {types.length === 0 && (
        <Card className="mb-6 p-4 text-sm text-amber-600 bg-amber-50 border-amber-200">
          No leave types configured. Add leave types via the API before applying for leave.
        </Card>
      )}

      <Card>
        <div className="border-b border-neutral-100 px-5 py-3">
          <Select value={status} onChange={setStatus} options={STATUSES.map((v) => ({ value: v, label: v }))} className="w-44" />
        </div>
        {rows.length === 0 ? (
          <Empty />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Employee</th>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">Dates</th>
                  <th className="px-5 py-3 font-medium">Days</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Reason</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-3 font-medium text-neutral-800">{setName(r.employee_id)}</td>
                    <td className="px-5 py-3 text-neutral-500">{typeName(r.leave_type_id)}</td>
                    <td className="px-5 py-3 text-neutral-500">
                      {r.start_date.slice(0, 10)} → {r.end_date.slice(0, 10)}
                      {r.is_half_day ? <Badge tone="amber" >½ day</Badge> : null}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">{r.days}</td>
                    <td className="px-5 py-3">
                      <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                    </td>
                    <td className="max-w-[220px] truncate px-5 py-3 text-neutral-500">{r.reason || "—"}</td>
                    <td className="px-5 py-3 text-right">
                      {r.status === "PENDING" && (
                        <div className="flex justify-end gap-2">
                          <Button variant="secondary" onClick={() => decide(r.id, "approve")} disabled={busy}>
                            Approve
                          </Button>
                          <Button variant="danger" onClick={() => decide(r.id, "reject")} disabled={busy}>
                            Reject
                          </Button>
                        </div>
                      )}
                    </td>
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