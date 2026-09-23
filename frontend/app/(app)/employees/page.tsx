"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Empty,
  Input,
  PageHeader,
  Select,
  statusTone,
} from "@/components/ui";

type Employee = {
  id: string;
  employee_code: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  department_id?: string;
  designation_id?: string;
  status: string;
  employment_type?: string;
  joining_date?: string;
};

type Department = { id: string; name: string };
type Designation = { id: string; name: string };

const STATUSES = ["ACTIVE", "INACTIVE", "RESIGNED", "TERMINATED", "ON_NOTICE"];

export default function EmployeesPage() {
  const [items, setItems] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [departments, setDepartments] = useState<Department[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState<Record<string, string>>({ status: "ACTIVE", employment_type: "FULL_TIME" });

  const load = async () => {
    try {
      const data = await api.get<{ items: Employee[]; total: number }>("/api/v1/employees/", {
        search,
        status,
        page: 1,
        page_size: 100,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load employees");
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const [deps, desigs] = await Promise.all([
          api.get<Department[]>("/api/v1/departments/"),
          api.get<Designation[]>("/api/v1/designations/"),
        ]);
        setDepartments(deps);
        setDesignations(desigs);
      } catch {
        /* org refs may not exist yet */
      }
    })();
  }, []);

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, status]);

  const set = (key: string) => (v: string) => setForm((f) => ({ ...f, [key]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const body: Record<string, unknown> = { ...form };
      const salary: Record<string, unknown> = {};
      for (const k of ["effective_from", "basic_salary", "gross_salary", "salary_structure_id"] as const) {
        if (body[k]) {
          salary[k] = body[k];
          delete body[k];
        }
      }
      if (Object.keys(salary).length > 1) body.salary = salary;
      await api.post("/api/v1/employees/", body);
      setNotice("Employee created");
      setShowForm(false);
      setForm({ status: "ACTIVE", employment_type: "FULL_TIME" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create employee");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Employees"
        subtitle={`${total} total`}
        action={
          <Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : "+ New Employee"}</Button>
        }
      />

      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title="Create employee" />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-3">
            <Input label="Employee Code *" value={form.employee_code} onChange={set("employee_code")} required />
            <Input label="First name *" value={form.first_name} onChange={set("first_name")} required />
            <Input label="Last name" value={form.last_name} onChange={set("last_name")} />
            <Input label="Email" type="email" value={form.email} onChange={set("email")} />
            <Input label="Phone" value={form.phone} onChange={set("phone")} />
            <Select
              label="Department"
              value={form.department_id}
              onChange={set("department_id")}
              options={departments.map((d) => ({ value: d.id, label: d.name }))}
            />
            <Select
              label="Designation"
              value={form.designation_id}
              onChange={set("designation_id")}
              options={designations.map((d) => ({ value: d.id, label: d.name }))}
            />
            <Select
              label="Employment type"
              value={form.employment_type}
              onChange={set("employment_type")}
              options={["FULL_TIME", "PART_TIME", "CONTRACT", "INTERN", "PROBATION"].map((v) => ({ value: v, label: v }))}
            />
            <Select
              label="Status"
              value={form.status}
              onChange={set("status")}
              options={STATUSES.map((v) => ({ value: v, label: v }))}
            />
            <Input label="Joining date" type="date" value={form.joining_date} onChange={set("joining_date")} />

            <div className="md:col-span-3 border-t border-neutral-100 pt-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Salary (optional)</div>
            </div>
            <Input label="Effective from" type="date" value={form.effective_from} onChange={set("effective_from")} />
            <Input label="Basic salary" type="number" value={form.basic_salary} onChange={set("basic_salary")} />
            <Input label="Gross salary" type="number" value={form.gross_salary} onChange={set("gross_salary")} />

            <div className="md:col-span-3 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : "Create"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-neutral-100 px-5 py-3">
          <Input placeholder="Search…" value={search} onChange={setSearch} className="w-full sm:w-56" />
          <Select
            value={status}
            onChange={setStatus}
            options={STATUSES.map((v) => ({ value: v, label: v }))}
            className="w-full sm:w-40"
          />
        </div>
        {items.length === 0 ? (
          <Empty text="No employees found" />
        ) : (
          <div className="overflow-x-auto">
            <table className="mobile-stack w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Code</th>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Department</th>
                  <th className="px-5 py-3 font-medium">Designation</th>
                  <th className="px-5 py-3 font-medium">Phone</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((e) => (
                  <tr key={e.id} className="hover:bg-neutral-50">
                    <td data-label="Code" className="px-5 py-3 font-medium text-neutral-800">{e.employee_code}</td>
                    <td data-label="Name" className="px-5 py-3">{`${e.first_name} ${e.last_name || ""}`}</td>
                    <td data-label="Department" className="px-5 py-3 text-neutral-500">
                      {departments.find((d) => d.id === e.department_id)?.name || "—"}
                    </td>
                    <td data-label="Designation" className="px-5 py-3 text-neutral-500">
                      {designations.find((d) => d.id === e.designation_id)?.name || "—"}
                    </td>
                    <td data-label="Phone" className="px-5 py-3 text-neutral-500">{e.phone || "—"}</td>
                    <td data-label="Status" className="px-5 py-3">
                      <Badge tone={statusTone(e.status)}>{e.status}</Badge>
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