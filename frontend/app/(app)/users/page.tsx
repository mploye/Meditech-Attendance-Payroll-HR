"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, Select } from "@/components/ui";

type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  department_id?: string;
  employee_id?: string;
  last_login_at?: string;
};

const ROLES = ["COMPANY_ADMIN", "HR_ADMIN", "HR_MANAGER", "PAYROLL_ADMIN", "MANAGER", "EMPLOYEE"];

export default function UsersPage() {
  const [rows, setRows] = useState<User[]>([]);
  const [departments, setDepartments] = useState<{ id: string; name: string }[]>([]);
  const [employees, setEmployees] = useState<{ id: string; first_name: string; last_name?: string }[]>([]);
  const [form, setForm] = useState<Record<string, string>>({ role: "EMPLOYEE" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setRows(await api.get<User[]>("/api/v1/users"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    }
  };

  useEffect(() => {
    const t = setTimeout(() => {
      void (async () => {
        await load();
        try {
          const [deps, emps] = await Promise.all([
            api.get<{ id: string; name: string }[]>("/api/v1/departments"),
            api.get<{ items: { id: string; first_name: string; last_name?: string }[] }>("/api/v1/employees/", {
              page_size: 500,
            }),
          ]);
          setDepartments(deps);
          setEmployees(emps.items);
        } catch {
          /* ignore */
        }
      })();
    }, 0);
    return () => clearTimeout(t);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.post("/api/v1/users", {
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        role: form.role,
        department_id: form.department_id || undefined,
        employee_id: form.employee_id || undefined,
      });
      setNotice("User created");
      setShowForm(false);
      setForm({ role: "EMPLOYEE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (id: string, active: boolean) => {
    setBusy(true);
    setError("");
    try {
      await api.patch(`/api/v1/users/${id}`, { is_active: active });
      setRows((rs) => rs.map((r) => (r.id === id ? { ...r, is_active: active } : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Users"
        subtitle="Login accounts and roles"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : "+ New User"}</Button>}
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title="Create user" />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-3">
            <Input label="Full name *" required value={form.full_name} onChange={(v) => setForm((s) => ({ ...s, full_name: v }))} />
            <Input label="Email *" type="email" required value={form.email} onChange={(v) => setForm((s) => ({ ...s, email: v }))} />
            <Input label="Password *" type="password" required value={form.password} onChange={(v) => setForm((s) => ({ ...s, password: v }))} />
            <Select
              label="Role *"
              value={form.role}
              onChange={(v) => setForm((s) => ({ ...s, role: v }))}
              options={ROLES.map((r) => ({ value: r, label: r.replace(/_/g, " ") }))}
            />
            <Select
              label="Department"
              value={form.department_id}
              onChange={(v) => setForm((s) => ({ ...s, department_id: v }))}
              options={departments.map((d) => ({ value: d.id, label: d.name }))}
            />
            <Select
              label="Linked employee"
              value={form.employee_id}
              onChange={(v) => setForm((s) => ({ ...s, employee_id: v }))}
              options={employees.map((e) => ({ value: e.id, label: `${e.first_name} ${e.last_name || ""}`.trim() }))}
            />
            <div className="flex justify-end gap-2 md:col-span-3">
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
                  <th className="px-5 py-3 font-medium">User</th>
                  <th className="px-5 py-3 font-medium">Role</th>
                  <th className="px-5 py-3 font-medium">Department</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {rows.map((u) => (
                  <tr key={u.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-3">
                      <div className="font-medium text-neutral-800">{u.full_name}</div>
                      <div className="text-xs text-neutral-400">{u.email}</div>
                    </td>
                    <td className="px-5 py-3"><Badge tone="violet">{u.role}</Badge></td>
                    <td className="px-5 py-3 text-neutral-500">
                      {departments.find((d) => d.id === u.department_id)?.name || "—"}
                    </td>
                    <td className="px-5 py-3"><Badge tone={u.is_active ? "green" : "red"}>{u.is_active ? "ACTIVE" : "DISABLED"}</Badge></td>
                    <td className="px-5 py-3 text-right">
                      <Button
                        variant={u.is_active ? "secondary" : "danger"}
                        onClick={() => toggle(u.id, !u.is_active)}
                        disabled={busy}
                      >
                        {u.is_active ? "Disable" : "Enable"}
                      </Button>
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