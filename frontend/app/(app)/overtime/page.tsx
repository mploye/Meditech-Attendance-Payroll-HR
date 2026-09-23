"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, Select, statusTone } from "@/components/ui";

type OTRow = {
  id: string;
  employee_id: string;
  date: string;
  minutes: number;
  rate?: number;
  status: string;
  overtime_pay?: number;
  remarks?: string;
};
type Employee = { id: string; first_name: string; last_name?: string };

export default function OvertimePage() {
  const [rows, setRows] = useState<OTRow[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [status, setStatus] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setRows(await api.get<OTRow[]>("/api/v1/overtime", { status }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load overtime");
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const emps = await api.get<{ items: Employee[] }>("/api/v1/employees/", { page_size: 500 });
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

  const empName = (id: string) => {
    const e = employees.find((x) => x.id === id);
    return e ? `${e.first_name} ${e.last_name || ""}`.trim() : id.slice(0, 8);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.post("/api/v1/overtime", {
        employee_id: form.employee_id,
        date: form.date,
        minutes: form.minutes,
        rate: form.rate ? Number(form.rate) : undefined,
        remarks: form.remarks,
      });
      setNotice("Overtime record created");
      setShowForm(false);
      setForm({});
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create overtime");
    } finally {
      setBusy(false);
    }
  };

  const decide = async (id: string, action: "approve" | "reject") => {
    setBusy(true);
    setError("");
    try {
      await api.post(`/api/v1/overtime/${id}/${action}`);
      setNotice(`Record ${action}d`);
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
        title="Overtime"
        subtitle="Approved overtime is paid in payroll"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : "+ Add Overtime"}</Button>}
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title="Add overtime" />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-4">
            <Select
              label="Employee *"
              value={form.employee_id}
              onChange={(v) => setForm((s) => ({ ...s, employee_id: v }))}
              options={employees.map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name || ""}`.trim() }))}
            />
            <Input label="Date *" type="date" required value={form.date} onChange={(v) => setForm((s) => ({ ...s, date: v }))} />
            <Input label="Minutes *" type="number" required value={form.minutes} onChange={(v) => setForm((s) => ({ ...s, minutes: v }))} />
            <Input label="Rate (optional)" type="number" value={form.rate} onChange={(v) => setForm((s) => ({ ...s, rate: v }))} />
            <Input label="Remarks" className="md:col-span-4" value={form.remarks} onChange={(v) => setForm((s) => ({ ...s, remarks: v }))} />
            <div className="flex justify-end gap-2 md:col-span-4">
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Create"}</Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        <div className="border-b border-neutral-100 px-5 py-3">
          <Select
            value={status}
            onChange={setStatus}
            options={["PENDING", "APPROVED", "REJECTED"].map((v) => ({ value: v, label: v }))}
            className="w-full sm:w-44"
          />
        </div>
        {rows.length === 0 ? (
          <Empty />
        ) : (
          <div className="overflow-x-auto">
            <table className="mobile-stack w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Employee</th>
                  <th className="px-5 py-3 font-medium">Date</th>
                  <th className="px-5 py-3 font-medium">Minutes</th>
                  <th className="px-5 py-3 font-medium">Est. Pay</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-neutral-50">
                    <td data-label="Employee" className="px-5 py-3 font-medium text-neutral-800">{empName(r.employee_id)}</td>
                    <td data-label="Date" className="px-5 py-3 text-neutral-500">{r.date.slice(0, 10)}</td>
                    <td data-label="Minutes" className="px-5 py-3 text-neutral-500">{r.minutes}</td>
                    <td data-label="Est. Pay" className="px-5 py-3 text-neutral-500">
                      {r.overtime_pay != null ? `₹${Number(r.overtime_pay).toLocaleString("en-IN")}` : "—"}
                    </td>
                    <td data-label="Status" className="px-5 py-3">
                      <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                    </td>
                    <td className="actions px-5 py-3 text-right">
                      {r.status === "PENDING" && (
                        <div className="flex justify-end gap-2">
                          <Button variant="secondary" onClick={() => decide(r.id, "approve")} disabled={busy}>Approve</Button>
                          <Button variant="danger" onClick={() => decide(r.id, "reject")} disabled={busy}>Reject</Button>
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