"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getStoredUser } from "@/lib/api";
import { Alert, Badge, Button, Card, CardHeader, Empty, Input, PageHeader } from "@/components/ui";

type Company = {
  id: string;
  name: string;
  short_name: string;
  legal_name?: string;
  email?: string;
  phone?: string;
  address?: string;
  settings?: Record<string, unknown>;
};

type EsslConfig = {
  enabled: boolean;
  base_url?: string;
  username?: string;
  company_short_name?: string;
  timeout_sec?: number;
  sync_interval_sec?: number;
};

type Rule = {
  id: string;
  rule_type: string;
  rule_key?: string;
  value: number;
  effective_from?: string;
};

export default function SettingsPage() {
  const [company, setCompany] = useState<Company | null>(null);
  const [essl, setEssl] = useState<EsslConfig>({ enabled: false });
  const [rules, setRules] = useState<Rule[]>([]);
  const [esslForm, setEsslForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const user = typeof window !== "undefined" ? getStoredUser() : null;

  const loadAll = async () => {
    try {
      const [cfg, rls] = await Promise.all([
        api.get<EsslConfig>("/api/v1/integrations/essl/config"),
        api.get<Rule[]>("/api/v1/salary/statutory-rules"),
      ]);
      setEssl(cfg);
      setEsslForm({
        base_url: cfg.base_url || "",
        username: cfg.username || "",
        company_short_name: cfg.company_short_name || "",
        timeout_sec: String(cfg.timeout_sec || 10),
        sync_interval_sec: String(cfg.sync_interval_sec || 300),
      });
      setRules(rls);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const companies = await api.get<Company[]>("/api/v1/companies");
        if (companies.length > 0) {
          setCompany(companies[0]);
          await loadAll();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load company");
      }
    })();
  }, []);

  const saveCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.patch(`/api/v1/companies/${company.id}`, {
        name: company.name,
        legal_name: company.legal_name,
        email: company.email,
        phone: company.phone,
        address: company.address,
      });
      setNotice("Company updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update company");
    } finally {
      setBusy(false);
    }
  };

  const saveEssl = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const body: Record<string, unknown> = { ...esslForm };
      body.timeout_sec = Number(body.timeout_sec || 10);
      body.sync_interval_sec = Number(body.sync_interval_sec || 300);
      body.enabled = essl.enabled;
      if (!body.password) delete body.password;
      if (!body.api_key) delete body.api_key;
      const cfg = await api.patch<EsslConfig>("/api/v1/integrations/essl/config", body);
      setEssl(cfg);
      setNotice("eSSL configuration saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save eSSL config");
    } finally {
      setBusy(false);
    }
  };

  const testEssl = async () => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.post<{ success?: boolean; message?: string; status?: string }>("/api/v1/integrations/essl/test");
      setNotice(result?.message || `Test: ${result?.status || "ok"}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setBusy(false);
    }
  };

  const setC = (key: string) => (v: string) => setCompany((c) => (c ? { ...c, [key]: v } : c));
  const setE = (key: string) => (v: string) => setEsslForm((f) => ({ ...f, [key]: v }));

  return (
    <div>
      <PageHeader title="Settings" subtitle="Company, eSSL integration and statutory configuration" />
      <Alert kind="error" message={error} />
      <Alert kind="success" message={notice} />

      {user && (user.role === "SUPER_ADMIN" || user.role === "COMPANY_ADMIN") && (
        <Card className="mb-6">
          <CardHeader title="Company" />
          {!company ? (
            <Empty text="No company found" />
          ) : (
            <form onSubmit={saveCompany} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-3">
              <Input label="Name" value={company.name} onChange={setC("name")} required />
              <Input label="Legal name" value={company.legal_name || ""} onChange={setC("legal_name")} />
              <Input label="Short name" value={company.short_name} onChange={() => {}} />
              <Input label="Email" type="email" value={company.email || ""} onChange={setC("email")} />
              <Input label="Phone" value={company.phone || ""} onChange={setC("phone")} />
              <Input label="Address" value={company.address || ""} onChange={setC("address")} />
              <div className="flex justify-end md:col-span-3">
                <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save company"}</Button>
              </div>
            </form>
          )}
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="eSSL eTimeTrackLite Integration"
            action={
              <div className="flex items-center gap-2">
                <Badge tone={essl.enabled ? "green" : "neutral"}>{essl.enabled ? "Enabled" : "Disabled"}</Badge>
              </div>
            }
          />
          <form onSubmit={saveEssl} className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
            <Input label="Base URL" value={esslForm.base_url || ""} onChange={setE("base_url")} placeholder="https://rtapi.essl.com" />
            <Input label="Username" value={esslForm.username || ""} onChange={setE("username")} />
            <Input label="Company short name" value={esslForm.company_short_name || ""} onChange={setE("company_short_name")} />
            <Input label="Password (write-only)" type="password" value={esslForm.password || ""} onChange={setE("password")} />
            <Input label="API key (write-only)" type="password" value={esslForm.api_key || ""} onChange={setE("api_key")} />
            <Input label="Timeout (sec)" type="number" value={esslForm.timeout_sec || ""} onChange={setE("timeout_sec")} />
            <Input label="Sync interval (sec)" type="number" value={esslForm.sync_interval_sec || ""} onChange={setE("sync_interval_sec")} />
            <label className="flex items-end gap-2 pb-2 text-sm text-neutral-700">
              <input type="checkbox" checked={essl.enabled} onChange={(e) => setEssl((s) => ({ ...s, enabled: e.target.checked }))} />
              Enable integration
            </label>
            <div className="flex justify-end gap-2 md:col-span-2">
              <Button variant="secondary" type="button" onClick={testEssl} disabled={busy}>Test connection</Button>
              <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save configuration"}</Button>
            </div>
          </form>
        </Card>

        <Card>
          <CardHeader title="Statutory Rules" />
          {rules.length === 0 ? (
            <Empty text="No statutory rules configured" />
          ) : (
            <div className="divide-y divide-neutral-100">
              {rules.map((r) => (
                <div key={r.id} className="flex items-center justify-between px-5 py-3">
                  <div>
                    <div className="text-sm font-medium text-neutral-800">{r.rule_type}</div>
                    <div className="text-xs text-neutral-400">
                      {r.rule_key || ""} · effective {(r.effective_from || "—").slice(0, 10)}
                    </div>
                  </div>
                  <Badge tone="violet">₹{Number(r.value).toLocaleString("en-IN")}</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}