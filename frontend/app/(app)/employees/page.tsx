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
  gender?: string;
  date_of_birth?: string;
  work_location?: string;
  aadhaar_no?: string;
  pan?: string;
  bank_name?: string;
  account_number?: string;
  ifsc?: string;
  account_holder_name?: string;
};

type Department = { id: string; name: string };
type Designation = { id: string; name: string };

const STATUSES = ["ACTIVE", "INACTIVE", "RESIGNED", "TERMINATED", "ON_NOTICE"];
const EMPLOYMENT_TYPES = ["FULL_TIME", "PART_TIME", "CONTRACT", "INTERN", "PROBATION"];
const GENDERS = ["MALE", "FEMALE", "OTHER"];

function fullName(e: Employee): string {
  return `${e.first_name || ""} ${e.last_name || ""}`.trim();
}

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
  const [editingId, setEditingId] = useState<string | null>(null);
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

  const resetForm = () => {
    setForm({ status: "ACTIVE", employment_type: "FULL_TIME" });
    setEditingId(null);
    setShowForm(false);
  };

  const openCreate = () => {
    setForm({ status: "ACTIVE", employment_type: "FULL_TIME" });
    setEditingId(null);
    setShowForm(true);
    setError("");
    setNotice("");
  };

  const openEdit = async (emp: Employee) => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const full = await api.get<Employee & { active_salary?: Record<string, unknown> }>(
        `/api/v1/employees/${emp.id}`
      );
      const f: Record<string, string> = {};
      for (const [k, v] of Object.entries(full)) {
        if (v === null || v === undefined) continue;
        f[k] = String(v);
      }
      const salary = full.active_salary || {};
      if (salary.basic_salary != null) f.basic_salary = String(salary.basic_salary);
      if (salary.gross_salary != null) f.gross_salary = String(salary.gross_salary);
      f.status = emp.status || f.status || "ACTIVE";
      setForm(f);
      setEditingId(emp.id);
      setShowForm(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load employee");
    } finally {
      setBusy(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const body: Record<string, unknown> = { ...form };
      delete body.id;
      delete body.active_salary;
      const salary: Record<string, unknown> = {};
      for (const k of ["effective_from", "basic_salary", "gross_salary", "salary_structure_id"] as const) {
        if (body[k]) {
          salary[k] = body[k];
          delete body[k];
        }
      }

      if (editingId) {
        delete body.basic_salary;
        delete body.gross_salary;
        delete body.effective_from;
        await api.patch(`/api/v1/employees/${editingId}`, body);
        if (Object.keys(salary).length > 1) {
          await api.post(`/api/v1/employees/${editingId}/salary`, salary);
        }
        setNotice("Employee updated");
      } else {
        if (Object.keys(salary).length > 1) body.salary = salary;
        await api.post("/api/v1/employees/", body);
        setNotice("Employee created");
      }
      resetForm();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : editingId ? "Failed to update employee" : "Failed to create employee");
    } finally {
      setBusy(false);
    }
  };

  const setRowStatus = async (emp: Employee, next: string) => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await api.patch(`/api/v1/employees/${emp.id}`, { status: next });
      setNotice(`${fullName(emp)} marked ${next}`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Employees"
        subtitle={`${total} total`}
        action={<Button onClick={openCreate}>+ New Employee</Button>}
      />

      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title={editingId ? "Edit employee" : "Create employee"} />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-3">
            <Input label="Employee Code *" value={form.employee_code || ""} onChange={set("employee_code")} required />
            <Input label="First name *" value={form.first_name || ""} onChange={set("first_name")} required />
            <Input label="Last name" value={form.last_name || ""} onChange={set("last_name")} />
            <Input label="Email" type="email" value={form.email || ""} onChange={set("email")} />
            <Input label="Phone" value={form.phone || ""} onChange={set("phone")} />
            <Select
              label="Gender"
              value={form.gender || ""}
              onChange={set("gender")}
              options={GENDERS.map((v) => ({ value: v, label: v }))}
            />
            <Input label="Date of birth" type="date" value={form.date_of_birth || ""} onChange={set("date_of_birth")} />
            <Input label="Joining date" type="date" value={form.joining_date || ""} onChange={set("joining_date")} />
            <Input label="Work location" value={form.work_location || ""} onChange={set("work_location")} />
            <Select
              label="Department"
              value={form.department_id || ""}
              onChange={set("department_id")}
              options={departments.map((d) => ({ value: d.id, label: d.name }))}
            />
            <Select
              label="Designation"
              value={form.designation_id || ""}
              onChange={set("designation_id")}
              options={designations.map((d) => ({ value: d.id, label: d.name }))}
            />
            <Select
              label="Employment type"
              value={form.employment_type || ""}
              onChange={set("employment_type")}
              options={EMPLOYMENT_TYPES.map((v) => ({ value: v, label: v }))}
            />
            <Select
              label="Status"
              value={form.status || ""}
              onChange={set("status")}
              options={STATUSES.map((v) => ({ value: v, label: v }))}
            />

            <div className="md:col-span-3 border-t border-neutral-100 pt-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Statutory & Bank
              </div>
            </div>
            <Input label="Aadhaar No" value={form.aadhaar_no || ""} onChange={set("aadhaar_no")} />
            <Input label="PAN" value={form.pan || ""} onChange={set("pan")} />
            <Input label="Bank name" value={form.bank_name || ""} onChange={set("bank_name")} />
            <Input label="Account holder" value={form.account_holder_name || ""} onChange={set("account_holder_name")} />
            <Input label="Account number" value={form.account_number || ""} onChange={set("account_number")} />
            <Input label="IFSC" value={form.ifsc || ""} onChange={set("ifsc")} />

            <div className="md:col-span-3 border-t border-neutral-100 pt-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Salary (optional)</div>
            </div>
            <Input label="Effective from" type="date" value={form.effective_from || ""} onChange={set("effective_from")} />
            <Input label="Basic salary" type="number" value={form.basic_salary || ""} onChange={set("basic_salary")} />
            <Input label="Gross salary" type="number" value={form.gross_salary || ""} onChange={set("gross_salary")} />

            <div className="md:col-span-3 flex justify-end gap-2">
              <Button variant="secondary" onClick={resetForm}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : editingId ? "Save changes" : "Create"}
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
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((e) => (
                  <tr key={e.id} className="hover:bg-neutral-50">
                    <td data-label="Code" className="px-5 py-3 font-medium text-neutral-800">{e.employee_code}</td>
                    <td data-label="Name" className="px-5 py-3">{fullName(e)}</td>
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
                    <td data-label="Actions" className="px-5 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Button variant="secondary" onClick={() => openEdit(e)} disabled={busy}>
                          Edit
                        </Button>
                        {e.status === "ACTIVE" ? (
                          <Button variant="secondary" onClick={() => setRowStatus(e, "INACTIVE")} disabled={busy}>
                            Deactivate
                          </Button>
                        ) : (
                          <Button variant="secondary" onClick={() => setRowStatus(e, "ACTIVE")} disabled={busy}>
                            Activate
                          </Button>
                        )}
                      </div>
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
