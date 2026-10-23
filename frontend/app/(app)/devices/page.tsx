"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
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
  last_seen_at?: string | null;
  last_punch_at?: string | null;
  clock_drift_minutes?: number | null;
  last_punch_clock?: string | null;
  timezone?: string | null;
  enabled?: boolean;
};

export default function DevicesPage() {
  const [items, setItems] = useState<Device[]>([]);
  const [form, setForm] = useState<Record<string, string>>({ device_type: "FACE_PUNCH", provider: "ESSL" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [acting, setActing] = useState<string | null>(null);
  const [clockDevice, setClockDevice] = useState<Device | null>(null);
  const [clockDate, setClockDate] = useState("");
  const [clockTime, setClockTime] = useState("");
  const [clockBusy, setClockBusy] = useState(false);
  const [clockResult, setClockResult] = useState("");

  const load = async () => {
    try {
      setItems(await api.get<Device[]>("/api/v1/devices"));
      setLoadError("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load devices";
      setLoadError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    const interval = setInterval(() => void load(), 30000);
    return () => {
      clearTimeout(t);
      clearInterval(interval);
    };
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

  const act = async (id: string, action: "test" | "sync" | "get-time" | "set-time") => {
    setActing(id);
    setError("");
    setNotice("");
    try {
      if (action === "get-time") {
        const result = await api.post<{ success?: boolean; status?: string; message?: string }>(`/api/v1/devices/${id}/get-time`);
        setNotice(result?.message || "Get time queued (check device response)");
      } else if (action === "set-time") {
        const result = await api.post<{ success?: boolean; message?: string; device_time?: string }>(
          `/api/v1/devices/${id}/set-time`,
          {},
        );
        setNotice(result?.message || `System time ${result?.device_time || ""} sent to device`);
      } else {
        const result = await api.post<{ success?: boolean; status?: string; message?: string }>(`/api/v1/devices/${id}/${action}`);
        setNotice(result?.message || `${action} completed`);
        if (action === "sync") load();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `${action} failed`);
    } finally {
      setActing(null);
    }
  };

  const istParts = (value: string) => {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Kolkata",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).formatToParts(d);
    const get = (type: string) => parts.find((p) => p.type === type)?.value || "00";
    return { date: `${get("year")}-${get("month")}-${get("day")}`, time: `${get("hour")}:${get("minute")}:${get("second")}` };
  };

  const openClock = (device: Device) => {
    const now = istParts(new Date().toISOString()) || { date: "", time: "" };
    setClockDevice(device);
    setClockDate(now.date);
    setClockTime(now.time);
    setClockResult("");
    setError("");
    setNotice("");
  };

  const submitClock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clockDevice) return;
    setClockBusy(true);
    setError("");
    try {
      const dt = `${clockDate} ${clockTime.length === 5 ? `${clockTime}:00` : clockTime}`;
      const result = await api.post<{ success?: boolean; message?: string; device_time?: string }>(
        `/api/v1/devices/${clockDevice.id}/set-time`,
        { datetime: dt },
      );
      setClockResult(result?.message || `Set time queued (${result?.device_time || dt})`);
      setNotice(`Set time queued for ${clockDevice.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Set time failed");
    } finally {
      setClockBusy(false);
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
        {loading ? (
          <div className="px-5 py-8 text-center text-sm text-neutral-500">Connecting to the server…</div>
        ) : loadError ? (
          <div className="flex flex-col items-center gap-3 px-5 py-8 text-center">
            <p className="text-sm text-neutral-600">
              The API server is starting up (Render free tier sleeps when idle). This usually takes 15–30 seconds.
            </p>
            <Button
              onClick={() => {
                setLoading(true);
                void load();
              }}
            >
              Retry
            </Button>
          </div>
        ) : items.length === 0 ? (
          <Empty text="No devices registered" />
        ) : (
          <div className="overflow-x-auto">
            <table className="mobile-stack w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">Device</th>
                  <th className="px-5 py-3 font-medium">Serial</th>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">IP</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Last contact / punch</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((d) => (
                  <tr key={d.id} className="hover:bg-neutral-50">
                    <td data-label="Device" className="px-5 py-3">
                      <div className="font-medium text-neutral-800">{d.name}</div>
                      {d.location ? <div className="text-xs text-neutral-400">{d.location}</div> : null}
                    </td>
                    <td data-label="Serial" className="px-5 py-3 text-neutral-500">{d.serial_number}</td>
                    <td data-label="Type" className="px-5 py-3 text-neutral-500">
                      {d.device_type} <span className="text-neutral-300">·</span> {d.provider}
                    </td>
                    <td data-label="IP" className="px-5 py-3 text-neutral-500">
                      {d.ip_address ? `${d.ip_address}:${d.port ?? ""}` : "—"}
                    </td>
                    <td data-label="Status" className="px-5 py-3">
                      <Badge tone={statusTone(d.status)}>{d.status}</Badge>
                      {d.clock_drift_minutes != null ? (
                        <div className="mt-1 text-[11px] font-medium text-amber-600">
                          Clock {Math.abs(d.clock_drift_minutes)} min {d.clock_drift_minutes < 0 ? "behind" : "ahead"}
                        </div>
                      ) : null}
                    </td>
                    <td data-label="Last contact" className="px-5 py-3 text-neutral-500">
                      <div>Contact {d.last_seen_at ? formatDateTime(d.last_seen_at) : "—"}</div>
                      <div className="text-xs text-neutral-400">
                        Punch {d.last_punch_at ? formatDateTime(d.last_punch_at) : "—"}
                      </div>
                      <div className="text-xs text-emerald-700">
                        Last punch (device clock) {d.last_punch_clock ? formatDateTime(d.last_punch_clock) : "—"}
                      </div>
                    </td>
                    <td className="actions px-5 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="secondary" onClick={() => act(d.id, "test")} disabled={acting === d.id}>
                          Test
                        </Button>
                        <Button variant="secondary" onClick={() => act(d.id, "get-time")} disabled={acting === d.id}>
                          Get Time
                        </Button>
                        <Button variant="secondary" onClick={() => openClock(d)} disabled={acting === d.id}>
                          Set Time
                        </Button>
                        <Button variant="secondary" onClick={() => act(d.id, "set-time")} disabled={acting === d.id}>
                          Sync to System Time
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

      {clockDevice ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 md:items-center md:p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="device-clock-title"
          onClick={() => setClockDevice(null)}
        >
          <div
            className="w-full max-w-md overflow-hidden rounded-t-2xl bg-white shadow-xl md:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3 border-b border-neutral-100 px-5 py-4">
              <div>
                <h3 id="device-clock-title" className="text-base font-semibold text-neutral-800">Set device time</h3>
                <p className="text-xs text-neutral-400">
                  {clockDevice.name} · {clockDevice.serial_number}
                </p>
              </div>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setClockDevice(null)}
                className="rounded-lg px-2 py-1 text-xl leading-none text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
              >
                ×
              </button>
            </div>

            <form onSubmit={submitClock} className="grid grid-cols-1 gap-4 px-5 py-4 sm:grid-cols-2">
              <div className="rounded-lg bg-neutral-50 px-3 py-2 text-xs text-neutral-600 sm:col-span-2">
                <div>
                  <span className="font-medium text-neutral-700">Device clock at last punch:</span>{" "}
                  {clockDevice.last_punch_clock ? formatDateTime(clockDevice.last_punch_clock) : "—"}
                  {clockDevice.last_seen_at ? (
                    <span className="text-neutral-400"> (contact {formatDateTime(clockDevice.last_seen_at)})</span>
                  ) : null}
                </div>
                <div className="mt-1">
                  <span className="font-medium text-neutral-700">Server time:</span>{" "}
                  {formatDateTime(new Date())}
                </div>
              </div>
              <Input label="Date" type="date" required value={clockDate} onChange={setClockDate} />
              <Input label="Time" type="time" required value={clockTime} onChange={setClockTime} />
              <p className="text-xs text-neutral-400 sm:col-span-2">
                Times are in {clockDevice.timezone || "Asia/Kolkata"} (IST). If the device clock does not change after
                ~30s, its firmware rejects remote time-set — set it once on the terminal keypad (Menu → Date/Time).
                {clockDevice.clock_drift_minutes != null
                  ? ` Measured offset: ${Math.abs(clockDevice.clock_drift_minutes)} min ${
                      clockDevice.clock_drift_minutes < 0 ? "behind" : "ahead"
                    } (punches auto-corrected).`
                  : ""}
              </p>
              {clockResult ? (
                <p className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700 sm:col-span-2">{clockResult}</p>
              ) : null}
              <div className="flex justify-end gap-2 sm:col-span-2">
                <Button variant="secondary" onClick={() => setClockDevice(null)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={clockBusy}>
                  {clockBusy ? "Sending…" : "Set Time"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}