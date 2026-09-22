"use client";

import { useEffect, useState } from "react";
import { api, downloadFile } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Input, PageHeader, Select } from "@/components/ui";

type Period = { id: string; month: number; year: number; status: string };

export default function ReportsPage() {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [month, setMonth] = useState(String(new Date().getMonth() + 1));
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [periods, setPeriods] = useState<Period[]>([]);
  const [periodId, setPeriodId] = useState("");
  const [format, setFormat] = useState("xlsx");
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const per = await api.get<Period[]>("/api/v1/payroll/periods");
        setPeriods(per);
        if (per.length > 0) setPeriodId(per[0].id);
      } catch {
        /* ignore */
      }
    })();
  }, []);

  const startDownload = async (path: string, filename: string) => {
    try {
      await downloadFile(path, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Download failed: ${filename}`);
    }
  };

  const base = `/api/v1/reports`;
  const q = format;
  const rangeParams = `from_date=${fromDate}&to_date=${toDate}`;

  const attendanceReports = [
    { label: "Daily Attendance", path: `${base}/attendance/daily?${rangeParams}`, openable: () => !!fromDate && !!toDate },
    { label: "Monthly Attendance", path: `${base}/attendance/monthly?month=${month}&year=${year}`, openable: () => !!month && !!year },
    { label: "Late Comers", path: `${base}/attendance/late?${rangeParams}`, openable: () => !!fromDate && !!toDate },
    { label: "Missing Punch", path: `${base}/attendance/missing-punch?${rangeParams}`, openable: () => !!fromDate && !!toDate },
  ];
  const payrollReports = [
    { label: "Salary Register", path: `${base}/payroll/salary-register?payroll_period_id=${periodId}`, openable: () => !!periodId },
    { label: "Monthly Payroll", path: `${base}/payroll/monthly?payroll_period_id=${periodId}`, openable: () => !!periodId },
    { label: "Deductions Summary", path: `${base}/payroll/deductions?payroll_period_id=${periodId}`, openable: () => !!periodId },
    { label: "Loans Report", path: `${base}/loans`, openable: () => true },
  ];

  return (
    <div>
      <PageHeader title="Reports" subtitle="Exportable attendance and payroll reports" />
      <Alert kind="error" message={error} />

      <Card className="mb-6">
        <CardHeader title="Options" />
        <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-4">
          <Input label="From date" type="date" value={fromDate} onChange={setFromDate} />
          <Input label="To date" type="date" value={toDate} onChange={setToDate} />
          <Input label="Month" type="number" min={1} max={12} value={month} onChange={setMonth} />
          <Input label="Year" type="number" value={year} onChange={setYear} />
          <Select
            label="Period"
            value={periodId}
            onChange={setPeriodId}
            options={periods.map((p) => ({
              value: p.id,
              label: `${String(p.month).padStart(2, "0")}/${p.year} (${p.status})`,
            }))}
          />
          <Select
            label="Format"
            value={format}
            onChange={setFormat}
            options={["xlsx", "csv", "pdf"].map((v) => ({ value: v, label: v.toUpperCase() }))}
          />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <ReportCard
          title="Attendance"
          reports={attendanceReports}
          format={q}
          onDownload={(path, name) => startDownload(`${path}&format=${q}`, name)}
        />
        <ReportCard
          title="Payroll & Loans"
          reports={payrollReports}
          format={q}
          onDownload={(path, name) => startDownload(`${path}&format=${q}`, name)}
        />
      </div>
    </div>
  );
}

function ReportCard({
  title,
  reports,
  format,
  onDownload,
}: {
  title: string;
  reports: { label: string; path: string; openable: () => boolean }[];
  format: string;
  onDownload: (path: string, name: string) => void;
}) {
  return (
    <Card>
      <CardHeader title={title} />
      <div className="divide-y divide-neutral-100">
        {reports.map((r) => (
          <div key={r.label} className="flex items-center justify-between px-5 py-3">
            <div>
              <div className="text-sm font-medium text-neutral-800">{r.label}</div>
              <Badge tone="blue">{format.toUpperCase()}</Badge>
            </div>
            <Button
              variant="secondary"
              onClick={() => onDownload(r.path, `${r.label.replace(/\s+/g, "-").toLowerCase()}.${format}`)}
            >
              Download
            </Button>
          </div>
        ))}
      </div>
    </Card>
  );
}