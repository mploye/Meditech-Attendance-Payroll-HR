"use client";

import { useEffect, useState } from "react";
import { api, downloadFile } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, PageHeader, Select, statusTone } from "@/components/ui";

type Payslip = {
  id: string;
  employee_name?: string;
  employee_code?: string;
  payroll_period_id?: string;
  gross_earnings?: number;
  total_deductions?: number;
  net_pay?: number;
  status?: string;
  pdf_path?: string;
  downloaded?: boolean;
};
type Period = { id: string; month: number; year: number; status: string };

export default function PayslipsPage() {
  const [rows, setRows] = useState<Payslip[]>([]);
  const [periods, setPeriods] = useState<Period[]>([]);
  const [periodId, setPeriodId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async (pid: string) => {
    try {
      const qs: Record<string, string> = {};
      if (pid) qs.payroll_period_id = pid;
      setRows(await api.get<Payslip[]>("/api/v1/payslips", qs));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load payslips");
      setRows([]);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const per = await api.get<Period[]>("/api/v1/payroll/periods");
        setPeriods(per);
        if (per.length > 0) {
          setPeriodId(per[0].id);
          await load(per[0].id);
        }
      } catch {
        /* ignore */
      }
    })();
  }, []);

  const select = async (v: string) => {
    setPeriodId(v);
    await load(v);
  };

  const generate = async () => {
    if (!periodId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.post<Record<string, unknown>>("/api/v1/payslips/generate", { payroll_period_id: periodId });
      setNotice(`Generated: ${JSON.stringify(result)}`);
      await load(periodId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  };

  const openPdf = async (id: string) => {
    try {
      await downloadFile(`/api/v1/payslips/${id}/pdf`, `payslip-${id.slice(0, 8)}.pdf`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF download failed");
    }
  };

  return (
    <div>
      <PageHeader
        title="Payslips"
        subtitle="Generated payslips per payroll period"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Select
              value={periodId}
              onChange={select}
              options={periods.map((p) => ({
                value: p.id,
                label: `${String(p.month).padStart(2, "0")}/${p.year} (${p.status})`,
              }))}
              className="w-52"
            />
            <Button onClick={generate} disabled={busy || !periodId}>
              Generate payslips
            </Button>
          </div>
        }
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      <Card>
        <CardHeader title={`${rows.length} payslip(s)`} />
        {rows.length === 0 ? (
          <Empty text="No payslips — generate them for a locked payroll period" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Employee</th>
                  <th className="px-5 py-3 font-medium">Gross</th>
                  <th className="px-5 py-3 font-medium">Deductions</th>
                  <th className="px-5 py-3 font-medium">Net Pay</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">PDF</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {rows.map((d) => (
                  <tr key={d.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-3">
                      <div className="font-medium text-neutral-800">{d.employee_name || d.employee_code}</div>
                      {d.employee_code ? <div className="text-xs text-neutral-400">{d.employee_code}</div> : null}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">₹{Number(d.gross_earnings || 0).toLocaleString("en-IN")}</td>
                    <td className="px-5 py-3 text-neutral-500">₹{Number(d.total_deductions || 0).toLocaleString("en-IN")}</td>
                    <td className="px-5 py-3 font-medium text-neutral-800">₹{Number(d.net_pay || 0).toLocaleString("en-IN")}</td>
                    <td className="px-5 py-3">
                      <Badge tone={statusTone(d.status || (d.downloaded ? "DOWNLOADED" : "GENERATED"))}>
                        {d.status || (d.downloaded ? "DOWNLOADED" : "GENERATED")}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Button variant="secondary" onClick={() => openPdf(d.id)}>PDF</Button>
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