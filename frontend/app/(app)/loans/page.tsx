"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, Select, statusTone } from "@/components/ui";

type Loan = {
  id: string;
  employee_name?: string;
  employee_code?: string;
  employee_id: string;
  loan_amount: number;
  installment_amount: number;
  number_of_installments: number;
  start_date?: string;
  status: string;
  outstanding_amount?: number;
  paid_installments?: number;
  interest_rate?: number;
};
type Employee = { id: string; first_name: string; last_name?: string };
type Period = { id: string; month: number; year: number; status: string };

export default function LoansPage() {
  const [rows, setRows] = useState<Loan[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [periods, setPeriods] = useState<Period[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setRows(await api.get<Loan[]>("/api/v1/loans"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load loans");
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const [emps, per] = await Promise.all([
          api.get<{ items: Employee[] }>("/api/v1/employees/", { page_size: 500 }),
          api.get<Period[]>("/api/v1/payroll/periods"),
        ]);
        setEmployees(emps.items);
        setPeriods(per);
      } catch {
        /* ignore */
      }
    })();
  }, []);

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.post("/api/v1/loans", {
        employee_id: form.employee_id,
        loan_amount: Number(form.loan_amount),
        installment_amount: Number(form.installment_amount),
        number_of_installments: Number(form.number_of_installments),
        start_date: form.start_date || undefined,
        interest_rate: form.interest_rate ? Number(form.interest_rate) : 0,
        remarks: form.remarks,
      });
      setNotice("Loan created");
      setShowForm(false);
      setForm({});
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create loan");
    } finally {
      setBusy(false);
    }
  };

  const pay = async (loanId: string) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const ref = window.prompt("Installment no (blank = next pending):", "");
      await api.post(`/api/v1/loans/${loanId}/pay`, { installment_no: ref || undefined });
      setNotice("Installment marked paid");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Payment failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Loans"
        subtitle="Employee loans recovered through payroll installments"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : "+ New Loan"}</Button>}
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title="Create loan" />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-4">
            <Select
              label="Employee *"
              value={form.employee_id}
              onChange={(v) => setForm((s) => ({ ...s, employee_id: v }))}
              options={employees.map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name || ""}`.trim() }))}
            />
            <Input label="Loan amount *" type="number" required value={form.loan_amount} onChange={(v) => setForm((s) => ({ ...s, loan_amount: v }))} />
            <Input label="Installment amount *" type="number" required value={form.installment_amount} onChange={(v) => setForm((s) => ({ ...s, installment_amount: v }))} />
            <Input label="# Installments *" type="number" required value={form.number_of_installments} onChange={(v) => setForm((s) => ({ ...s, number_of_installments: v }))} />
            <Input label="Start date" type="date" value={form.start_date} onChange={(v) => setForm((s) => ({ ...s, start_date: v }))} />
            <Input label="Interest rate %" type="number" value={form.interest_rate} onChange={(v) => setForm((s) => ({ ...s, interest_rate: v }))} />
            <Input label="Remarks" className="md:col-span-2" value={form.remarks} onChange={(v) => setForm((s) => ({ ...s, remarks: v }))} />
            <div className="flex justify-end gap-2 md:col-span-4">
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Create"}</Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        {rows.length === 0 ? (
          <Empty />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Employee</th>
                  <th className="px-5 py-3 font-medium">Amount</th>
                  <th className="px-5 py-3 font-medium">Installment</th>
                  <th className="px-5 py-3 font-medium">Start</th>
                  <th className="px-5 py-3 font-medium">Outstanding</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {rows.map((l) => (
                  <tr key={l.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-3">
                      <div className="font-medium text-neutral-800">{l.employee_name || l.employee_id.slice(0, 8)}</div>
                      {l.employee_code ? <div className="text-xs text-neutral-400">{l.employee_code}</div> : null}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">₹{Number(l.loan_amount).toLocaleString("en-IN")}</td>
                    <td className="px-5 py-3 text-neutral-500">
                      ₹{Number(l.installment_amount).toLocaleString("en-IN")} × {l.number_of_installments}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">{(l.start_date || "—").slice(0, 10)}</td>
                    <td className="px-5 py-3 text-neutral-500">
                      {l.outstanding_amount != null ? `₹${Number(l.outstanding_amount).toLocaleString("en-IN")}` : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <Badge tone={statusTone(l.status)}>{l.status}</Badge>
                    </td>
                    <td className="px-5 py-3 text-right">
                      {l.status === "ACTIVE" && (
                        <Button variant="secondary" onClick={() => pay(l.id)} disabled={busy}>
                          Pay installment
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {periods.length > 0 && (
        <Card className="mt-6">
          <CardHeader title="Payroll periods (for loan deductions)" />
          <div className="grid grid-cols-2 gap-2 p-5 md:grid-cols-4">
            {periods.map((p) => (
              <div key={p.id} className="rounded-lg border border-neutral-200 px-3 py-2 text-sm">
                <div className="font-medium text-neutral-800">
                  {String(p.month).padStart(2, "0")}/{p.year}
                </div>
                <Badge tone={statusTone(p.status)}>{p.status}</Badge>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}