"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader } from "@/components/ui";

type Shift = {
  id: string;
  name: string;
  code?: string;
  start_time?: string;
  end_time?: string;
  grace_period_minutes: number;
  minimum_work_minutes: number;
  overtime_enabled: boolean;
  is_default: boolean;
  active: boolean;
};

export default function ShiftsPage() {
  const [items, setItems] = useState<Shift[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setItems(await api.get<Shift[]>("/api/v1/shifts"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load shifts");
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/v1/shifts", {
        ...form,
        grace_period_minutes: Number(form.grace_period_minutes || 0),
        minimum_work_minutes: Number(form.minimum_work_minutes || 0),
        break_minutes: Number(form.break_minutes || 0),
        overtime_after_minutes: Number(form.overtime_after_minutes || 60),
        overtime_enabled: form.overtime_enabled === "true",
        night_shift: form.night_shift === "true",
        is_default: form.is_default === "true",
        active: true,
      });
      setNotice("Shift created");
      setShowForm(false);
      setForm({});
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create shift");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Shifts"
        subtitle="Schedules for attendance and overtime"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : "+ New Shift"}</Button>}
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title="Create shift" />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-4">
            <Input label="Name *" required value={form.name} onChange={(v) => setForm((s) => ({ ...s, name: v }))} />
            <Input label="Code" value={form.code} onChange={(v) => setForm((s) => ({ ...s, code: v }))} />
            <Input label="Start time" type="time" value={form.start_time} onChange={(v) => setForm((s) => ({ ...s, start_time: v }))} />
            <Input label="End time" type="time" value={form.end_time} onChange={(v) => setForm((s) => ({ ...s, end_time: v }))} />
            <Input label="Grace period (min)" type="number" value={form.grace_period_minutes} onChange={(v) => setForm((s) => ({ ...s, grace_period_minutes: v }))} />
            <Input label="Min work (min)" type="number" value={form.minimum_work_minutes} onChange={(v) => setForm((s) => ({ ...s, minimum_work_minutes: v }))} />
            <Input label="Break (min)" type="number" value={form.break_minutes} onChange={(v) => setForm((s) => ({ ...s, break_minutes: v }))} />
            <Input label="OT after (min)" type="number" value={form.overtime_after_minutes} onChange={(v) => setForm((s) => ({ ...s, overtime_after_minutes: v }))} />
            <div className="flex items-end gap-4">
              <label className="flex items-center gap-2 text-sm text-neutral-700">
                <input type="checkbox" checked={form.overtime_enabled === "true"} onChange={(e) => setForm((s) => ({ ...s, overtime_enabled: String(e.target.checked) }))} />
                Overtime enabled
              </label>
              <label className="flex items-center gap-2 text-sm text-neutral-700">
                <input type="checkbox" checked={form.night_shift === "true"} onChange={(e) => setForm((s) => ({ ...s, night_shift: String(e.target.checked) }))} />
                Night shift
              </label>
            </div>
            <div className="flex justify-end gap-2 md:col-span-4">
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Create"}</Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        {items.length === 0 ? (
          <Empty />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Hours</th>
                  <th className="px-5 py-3 font-medium">Grace</th>
                  <th className="px-5 py-3 font-medium">Min work</th>
                  <th className="px-5 py-3 font-medium">OT</th>
                  <th className="px-5 py-3 font-medium">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((s) => (
                  <tr key={s.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-3 font-medium text-neutral-800">
                      {s.name} {s.code ? <span className="text-neutral-400">({s.code})</span> : null}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">
                      {s.start_time || "—"} – {s.end_time || "—"}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">{s.grace_period_minutes}</td>
                    <td className="px-5 py-3 text-neutral-500">{s.minimum_work_minutes}</td>
                    <td className="px-5 py-3 text-neutral-500">{s.overtime_enabled ? "Yes" : "No"}</td>
                    <td className="px-5 py-3">
                      {s.is_default ? <Badge tone="blue">Default</Badge> : null}
                      {!s.active ? <Badge tone="red">Inactive</Badge> : null}
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