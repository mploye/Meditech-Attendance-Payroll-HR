"use client";

import { useEffect, useState } from "react";
import { api, downloadFile } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, PageHeader, Select, statusTone } from "@/components/ui";
import { Payslip } from "@/components/Payslip";

type PayslipRow = {
  id: string;
  employee_name?: string;
  employee_code?: string;
  payroll_period_id?: string;
  gross?: number;
  total_deductions?: number;
  net?: number;
  status?: string;
  pdf_path?: string;
  downloaded?: boolean;
  generated_at?: string;
};
type Period = { id: string; month: number; year: number; status: string };
type Format = "pdf" | "html" | "text" | "json";

interface PayslipJson {
  company: string;
  employee: { code: string; name: string; department: string; designation: string };
  period: string;
  attendance: { working_days: number; present_days: number; leave_days: number; lop_days: number; overtime_minutes: number };
  earnings: { name: string; amount: number }[];
  deductions: { name: string; amount: number }[];
  gross_salary: number;
  total_deductions: number;
  net_pay: number;
  generated_at?: string;
  status?: string;
  payslip_id?: string;
}

export default function PayslipsPage() {
  const [rows, setRows] = useState<PayslipRow[]>([]);
  const [periods, setPeriods] = useState<Period[]>([]);
  const [periodId, setPeriodId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [format, setFormat] = useState<Format>("pdf");
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [payslipData, setPayslipData] = useState<PayslipJson | null>(null);
  const [loadingPayslip, setLoadingPayslip] = useState(false);
  const [companyInfo, setCompanyInfo] = useState<{ name: string; address: string }>({ name: "", address: "" });

  const load = async (pid: string) => {
    try {
      const qs: Record<string, string> = {};
      if (pid) qs.payroll_period_id = pid;
      setRows(await api.get<PayslipRow[]>("/api/v1/payslips", qs));
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

  const fetchPayslipDetail = async (id: string) => {
    setLoadingPayslip(true);
    setError("");
    try {
      const data = await api.get<PayslipJson>(`/api/v1/payslips/${id}/json`);
      setPayslipData(data);
      setCompanyInfo({
        name: data.company || "Company",
        address: data.employee?.department ? `${data.employee.department}` : "",
      });
      setViewingId(id);
    } catch {
      // Fallback: use list data
      const row = rows.find((r) => r.id === id);
      if (row) {
        setPayslipData({
          company: "ESSL HRMS",
          employee: { code: row.employee_code || "", name: row.employee_name || "", department: "N/A", designation: "" },
          period: "",
          attendance: { working_days: 0, present_days: 0, leave_days: 0, lop_days: 0, overtime_minutes: 0 },
          earnings: [],
          deductions: [],
          gross_salary: row.gross || 0,
          total_deductions: row.total_deductions || 0,
          net_pay: row.net || 0,
        });
        setCompanyInfo({ name: "ESSL HRMS", address: "Genetics Meditech" });
        setViewingId(id);
      }
    } finally {
      setLoadingPayslip(false);
    }
  };

  const fetchFormat = async (id: string, f: Format) => {
    try {
      const res = await fetch(`/api/v1/payslips/${id}/${f}`);
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(body || `Failed to fetch ${f}`);
      }
      const blob = await res.blob();
      const ext = f === "html" ? ".html" : f === "text" ? ".txt" : f === "json" ? ".json" : ".pdf";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `payslip-${id.slice(0, 8)}${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setNotice(`Downloaded as ${f.toUpperCase()}`);
    } catch (err) {
      if (f === "pdf") {
        setError(
          `Cannot read this payslip PDF — the current model does not support PDF input. ` +
          `Use the HTML, Text, or JSON version above instead.`
        );
      } else {
        setError(err instanceof Error ? err.message : `Failed to fetch ${f}`);
      }
    }
  };

  const openPdf = async (id: string) => {
    try {
      await fetchFormat(id, "pdf");
    } catch {
      /* error already set */
    }
  };

  const monthLabel = (m: number) => new Date(2000, m - 1).toLocaleString("en-IN", { month: "long" });

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

      {viewingId && payslipData ? (
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-4">
            <Button variant="secondary" onClick={() => { setViewingId(null); setPayslipData(null); }}>
              ← Back to list
            </Button>
          </div>
          <Payslip
            company={{ name: companyInfo.name, address: companyInfo.address }}
            employee={{
              employeeId: payslipData.employee.code,
              name: payslipData.employee.name,
              department: payslipData.employee.department,
            }}
            attendance={{
              workingDays: payslipData.attendance.working_days,
              presentDays: payslipData.attendance.present_days,
              leaveDays: payslipData.attendance.leave_days,
              lopDays: payslipData.attendance.lop_days,
              overtimeMinutes: payslipData.attendance.overtime_minutes,
            }}
            month={monthLabel(payslipData.period ? parseInt(payslipData.period.split(" ")[0]) : 8)}
            year={payslipData.period ? parseInt(payslipData.period.split(" ")[1]) : 2026}
            earnings={payslipData.earnings}
            deductions={payslipData.deductions}
          />
        </div>
      ) : (
        <Card>
          <CardHeader title={`${rows.length} payslip(s)`} />
          {rows.length === 0 ? (
            <Empty text="No payslips — generate them for a locked payroll period" />
          ) : (
            <div>
              <div className="flex items-center gap-2 px-5 py-3 border-b border-neutral-100 text-xs text-neutral-400">
                <span>Export format:</span>
                {(["pdf", "html", "text", "json"] as Format[]).map((f) => (
                  <Button
                    key={f}
                    variant={format === f ? "primary" : "secondary"}
                    onClick={() => setFormat(f)}
                  >
                    {f.toUpperCase()}
                  </Button>
                ))}
                {format === "pdf" && (
                  <span className="ml-2 text-xs text-amber-600">⚠ AI models cannot read PDF — switch to HTML/Text/JSON</span>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="mobile-stack w-full text-left text-sm">
                  <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                    <tr>
                      <th className="px-5 py-3 font-medium">Employee</th>
                      <th className="px-5 py-3 font-medium">Gross</th>
                      <th className="px-5 py-3 font-medium">Deductions</th>
                      <th className="px-5 py-3 font-medium">Net Pay</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                      <th className="px-5 py-3 font-medium text-right">{format.toUpperCase()}</th>
                      <th className="px-5 py-3 font-medium text-right">View</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {rows.map((d) => (
                      <tr key={d.id} className="hover:bg-neutral-50">
                        <td data-label="Employee" className="px-5 py-3">
                          <div className="font-medium text-neutral-800">{d.employee_name || d.employee_code}</div>
                          {d.employee_code ? <div className="text-xs text-neutral-400">{d.employee_code}</div> : null}
                        </td>
                        <td data-label="Gross" className="px-5 py-3 text-neutral-500">₹{Number(d.gross || 0).toLocaleString("en-IN")}</td>
                        <td data-label="Deductions" className="px-5 py-3 text-neutral-500">₹{Number(d.total_deductions || 0).toLocaleString("en-IN")}</td>
                        <td data-label="Net Pay" className="px-5 py-3 font-medium text-neutral-800">₹{Number(d.net || 0).toLocaleString("en-IN")}</td>
                        <td data-label="Status" className="px-5 py-3">
                          <Badge tone={statusTone(d.status || (d.downloaded ? "DOWNLOADED" : "GENERATED"))}>
                            {d.status || (d.downloaded ? "DOWNLOADED" : "GENERATED")}
                          </Badge>
                        </td>
                        <td className="actions px-5 py-3 text-right">
                          <Button variant="secondary" onClick={() => { void fetchFormat(d.id, format); }}>
                            {format.toUpperCase()}
                          </Button>
                        </td>
                        <td className="actions px-5 py-3 text-right">
                          <Button variant="secondary" onClick={() => void fetchPayslipDetail(d.id)}>
                            View
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
