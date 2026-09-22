"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader, Select, statusTone } from "@/components/ui";

type Device = {
  id: string;
  name: string;
  model?: string;
  serial_number: string;
  device_type: string;
  provider: string;
  ip_address?: string;
  port?: number;
  location?: string;
  status: string;
  last_sync_at?: string;
  enabled?: boolean;
};

export default function DevicesPage() {
  const [items, setItems] = useState<Device[]>([]);
  const [form, setForm] = useState<Record<string, string>>({ device_type: "FACE_PUNCH", provider: "ESSL" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [acting, setActing] = useState<string | null>(null);

  const load = async () => {
    try {
      setItems(await api.get<Device[]>("/api/v1/devices"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load devices");
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
  }, []);

  const set = (k: string) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/v1/devices", { ...form, port: form.port ? Number(form.port) : undefined });
      setNotice("Device registered");
      setShowForm(false);
      setForm({ device_type: "FACE_PUNCH", provider: "ESSL" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create device");
    } finally {
      setBusy(false);
    }
  };

  const act = async (id: string, action: "test" | "sync") => {
    setActing(id);
    setError("");
    setNotice("");
    try {
      const result = await api.post<{ success?: boolean; status?: string; message?: string }>(`/api/v1/devices/${id}/${action}`);
      setNotice(result?.message || `${action} completed`);
      if (action === "sync") load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${action} failed`);
    } finally {
      setActing(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Devices"
        subtitle="eSSL eTimeTrackLite terminals"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Close form" : "+ Register Device"}</Button>}
      />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {showForm && (
        <Card className="mb-6">
          <CardHeader title="Register device" />
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-4">
            <Input label="Name *" required value={form.name} onChange={set("name")} />
            <Input label="Serial number *" required value={form.serial_number} onChange={set("serial_number")} />
            <Input label="Model" value={form.model} onChange={set("model")} />
            <Input label="Location" value={form.location} onChange={set("location")} />
            <Select
              label="Device type"
              value={form.device_type}
              onChange={set("device_type")}
              options={["FACE_PUNCH", "FINGERPRINT", "CARD", "USER_PUNCH"].map((v) => ({ value: v, label: v }))}
            />
            <Select
              label="Provider"
              value={form.provider}
              onChange={set("provider")}
              options={["ESSL", "MANUAL", "CSV", "OTHER"].map((v) => ({ value: v, label: v }))}
            />
            <Input label="IP address" value={form.ip_address} onChange={set("ip_address")} />
            <Input label="Port" type="number" value={form.port} onChange={set("port")} />
            <div className="flex justify-end gap-2 md:col-span-4">
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Register"}</Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        {items.length === 0 ? (
          <Empty text="No devices registered" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Device</th>
                  <th className="px-5 py-3 font-medium">Serial</th>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">IP</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((d) => (
                  <tr key={d.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-3">
                      <div className="font-medium text-neutral-800">{d.name}</div>
                      {d.location ? <div className="text-xs text-neutral-400">{d.location}</div> : null}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">{d.serial_number}</td>
                    <td className="px-5 py-3 text-neutral-500">
                      {d.device_type} <span className="text-neutral-300">·</span> {d.provider}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">
                      {d.ip_address ? `${d.ip_address}:${d.port ?? ""}` : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <Badge tone={statusTone(d.status)}>{d.status}</Badge>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="secondary" onClick={() => act(d.id, "test")} disabled={acting === d.id}>
                          Test
                        </Button>
                        <Button variant="primary" onClick={() => act(d.id, "sync")} disabled={acting === d.id}>
                          Sync
                        </Button>
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