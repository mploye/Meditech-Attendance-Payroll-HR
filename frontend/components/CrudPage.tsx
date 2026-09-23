"use client";

import { ReactNode, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Button, Card, CardHeader, Empty, Input, PageHeader } from "@/components/ui";

type Field = {
  key: string;
  label: string;
  type?: "text" | "number" | "date" | "time";
  required?: boolean;
};

export default function CrudPage({
  title,
  subtitle,
  path,
  fields,
  renderRow,
}: {
  title: string;
  subtitle: string;
  path: string;
  fields: Field[];
  renderRow: (item: Record<string, unknown>) => ReactNode;
}) {
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setItems(await api.get<Record<string, unknown>[]>(path));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post(path, form);
      setNotice(`${title.slice(0, -1)} created`);
      setShowForm(false);
      setForm({});
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Delete this record?")) return;
    setError("");
    try {
      await api.del(`${path}/${id}`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  return (
    <div>
      <PageHeader
        title={title}
        subtitle={subtitle}
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : `+ New ${title.slice(0, -1)}`}</Button>}
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title={`Create ${title.slice(0, -1)}`} />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-3">
            {fields.map((f) => (
              <Input
                key={f.key}
                label={f.label}
                type={f.type || "text"}
                required={f.required}
                value={form[f.key] || ""}
                onChange={(v) => setForm((s) => ({ ...s, [f.key]: v }))}
              />
            ))}
            <div className="flex justify-end gap-2 md:col-span-3">
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
        {items.length === 0 ? (
          <Empty />
        ) : (
          <div className="overflow-x-auto">
            <table className="mobile-stack w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Code</th>
                  <th className="px-5 py-3 font-medium">Details</th>
                  <th className="px-5 py-3 font-medium" />
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((item) => (
                  <tr key={String(item.id)} className="hover:bg-neutral-50">
                    {renderRow(item)}
                    <td className="actions px-5 py-3 text-right">
                      <button
                        onClick={() => remove(String(item.id))}
                        className="text-xs font-medium text-rose-500 hover:text-rose-700"
                      >
                        Delete
                      </button>
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