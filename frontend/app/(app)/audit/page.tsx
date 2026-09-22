"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Alert, Badge, Button, Card, Empty, Input, PageHeader, statusTone } from "@/components/ui";

type Log = {
  id: string;
  action: string;
  entity_type?: string;
  entity_id?: string;
  user_id?: string;
  created_at: string;
  ip_address?: string;
  new_value?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
};

export default function AuditPage() {
  const [rows, setRows] = useState<Log[]>([]);
  const [total, setTotal] = useState(0);
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [pageSize] = useState(50);

  const load = async (p: number) => {
    setError("");
    try {
      const data = await api.get<{ items: Log[]; total: number }>("/api/v1/audit/logs", {
        action: action || undefined,
        entity_type: entityType || undefined,
        page: p,
        page_size: pageSize,
      });
      setRows(data.items);
      setTotal(data.total);
      setPage(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit logs");
      setRows([]);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(1), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, entityType]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <PageHeader title="Audit Logs" subtitle={`${total} events`} />
      <Alert kind="error" message={error} />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-neutral-100 px-5 py-3">
          <Input placeholder="Filter by action" value={action} onChange={setAction} className="w-56" />
          <Input placeholder="Entity type" value={entityType} onChange={setEntityType} className="w-56" />
        </div>
        {rows.length === 0 ? (
          <Empty text="No audit events" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-100 text-xs uppercase text-neutral-400">
                <tr>
                  <th className="px-5 py-3 font-medium">When</th>
                  <th className="px-5 py-3 font-medium">Action</th>
                  <th className="px-5 py-3 font-medium">Entity</th>
                  <th className="px-5 py-3 font-medium">User</th>
                  <th className="px-5 py-3 font-medium">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-3 text-xs text-neutral-400">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-3">
                      <Badge tone={statusTone(String(r.action.includes("delete") ? "DELETED" : r.action.includes("approve") ? "APPROVED" : "GENERATED"))}>
                        {r.action}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 text-neutral-500">
                      {r.entity_type || "—"}
                      {r.entity_id ? <div className="text-[10px] text-neutral-400">{r.entity_id.slice(0, 12)}</div> : null}
                    </td>
                    <td className="px-5 py-3 text-neutral-500">{r.user_id ? r.user_id.slice(0, 8) : "system"}</td>
                    <td className="max-w-[300px] truncate px-5 py-3 text-xs text-neutral-500">
                      {JSON.stringify(r.new_value ?? r.metadata ?? {})}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-neutral-100 px-5 py-3">
            <span className="text-xs text-neutral-400">
              Page {page} of {totalPages} · {total} events
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => load(page - 1)} disabled={page <= 1}>
                Prev
              </Button>
              <Button variant="secondary" onClick={() => load(page + 1)} disabled={page >= totalPages}>
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}