"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, statusTone } from "@/components/ui";

type Period = {
  id: string;
  month: number;
  year: number;
  start_date: string;
  end_date: string;
  status: string;
  employees_processed?: number;
  gross?: number;
  deductions?: number;
  net?: number;
  approved_by?: string;
};

type RecordRow = {
  id: string;
  employee_name?: string;
  employee_code?: string;
  gross_salary?: number;
  total_deductions?: number;
  net_salary?: number;
  status?: string;
};

export default function PayrollPage() {
  const [periods, setPeriods] = useState<Period[]>([]);
  const [selected, setSelected] = useState<Period | null>(null);
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [month, setMonth] = useState("");
  const [year, setYear] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const loadPeriods = async () => {
    const items = await api.get<Period[]>("/api/v1/payroll/periods");
    setPeriods(items);
    if (selected) {
      const match = items.find((p) => p.id === selected.id);
      if (match) setSelected(match);
    }
  };

  const loadRecords = async (id: string) => {
    try {
      setRecords(await api.get<RecordRow[]>(`/api/v1/payroll/periods/${id}/records`));
    } catch {
      setRecords([]);
    }
  };

  const select = async (p: Period) => {
    setSelected(p);
    await loadRecords(p.id);
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.post("/api/v1/payroll/periods", { month: Number(month), year: Number(year) });
      setNotice(`Period ${month}/${year} created`);
      setMonth("");
      setYear("");
      await loadPeriods();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create period");
    } finally {
      setBusy(false);
    }
  };

  const step = async (periodId: string, action: string) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.post<Record<string, unknown>>(`/api/v1/payroll/periods/${periodId}/${action}`);
      if (action === "calculate") {
        const s = result as Record<string, unknown>;
        setNotice(`Calculated: ${s.employees_processed ?? "?"} employees, net ₹${s.net ?? "?"}`);
      } else {
        setNotice(`Period ${action}d`);
      }
      await loadPeriods();
      if (selected && selected.id === periodId) await loadRecords(periodId);
    } catch (err) {
      setError(err instanceof Error ? err.message : `${action} failed`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Payroll" subtitle="Periods, calculation and approval workflow" />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      <Card className="mb-6">
        <CardHeader title="Create payroll period" />
        <form onSubmit={create} className="flex flex-wrap items-end gap-4 p-5">
          <Input label="Month" type="number" min={1} max={12} value={month} onChange={setMonth} className="w-32" required />
          <Input label="Year" type="number" value={year} onChange={setYear} className="w-32" required />
          <Button type="submit" disabled={busy}>Create period</Button>
        </form>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Periods" />
          {periods.length === 0 ? (
            <Empty text="No payroll periods" />
          ) : (
            <div className="divide-y divide-neutral-100">
              {periods.map((p) => (
                <button
                  key={p.id}
                  onClick={() => select(p)}
                  className={`flex w-full items-center justify-between px-5 py-3 text-left transition ${
                    selected?.id === p.id ? "bg-brand-50" : "hover:bg-neutral-50"
                  }`}
                >
                  <div>
                    <div className="text-sm font-semibold text-neutral-800">
                      {String(p.month).padStart(2, "0")}/{p.year}
                    </div>
                    <div className="text-xs text-neutral-400">
                      {p.start_date.slice(0, 10)} → {p.end_date.slice(0, 10)}
                    </div>
                  </div>
                  <Badge tone={statusTone(p.status)}>{p.status}</Badge>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card className="lg:col-span-2">
          {!selected ? (
            <Empty text="Select a period to view its records" />
          ) : (
            <>
              <CardHeader
                title={`Period ${String(selected.month).padStart(2, "0")}/${selected.year}`}
                action={
                  <div className="flex gap-2">
                    {["calculate", "review", "approve", "lock"].map((action) => (
                      <Button
                        key={action}
                        variant="secondary"
                        onClick={() => step(selected.id, action)}
                        disabled={busy}
                      >
                        {action[0].toUpperCase() + action.slice(1)}
                      </Button>
                    ))}
                  </div>
                }
              />
              <div className="grid grid-cols-2 gap-3 border-b border-neutral-100 px-5 py-4 md:grid-cols-4">
                <Stat label="Employees" value={selected.employees_processed ?? 0} />
                <Stat label="Gross" value={selected.gross ?? 0} currency />
                <Stat label="Deductions" value={selected.deductions ?? 0} currency />
                <Stat label="Net" value={selected.net ?? 0} currency />
              </div>
              {records.length === 0 ? (
                <Empty text="No records yet — run Calculate" />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                      <tr>
                        <th className="px-5 py-3 font-medium">Employee</th>
                        <th className="px-5 py-3 font-medium">Gross</th>
                        <th className="px-5 py-3 font-medium">Deductions</th>
                        <th className="px-5 py-3 font-medium">Net</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {records.map((r) => (
                        <tr key={r.id} className="hover:bg-neutral-50">
                          <td className="px-5 py-3">
                            <div className="font-medium text-neutral-800">{r.employee_name || r.employee_code}</div>
                            {r.employee_code ? <div className="text-xs text-neutral-400">{r.employee_code}</div> : null}
                          </td>
                          <td className="px-5 py-3 text-neutral-500">₹{Number(r.gross_salary || 0).toLocaleString("en-IN")}</td>
                          <td className="px-5 py-3 text-neutral-500">₹{Number(r.total_deductions || 0).toLocaleString("en-IN")}</td>
                          <td className="px-5 py-3 font-medium text-neutral-800">₹{Number(r.net_salary || 0).toLocaleString("en-IN")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value, currency }: { label: string; value: number; currency?: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-neutral-400">{label}</div>
      <div className="text-lg font-bold text-neutral-900">
        {currency ? `₹${Number(value).toLocaleString("en-IN")}` : Number(value).toLocaleString("en-IN")}
      </div>
    </div>
  );
}