"use client";

import CrudPage from "@/components/CrudPage";

export default function DesignationsPage() {
  return (
    <CrudPage
      title="Designations"
      subtitle="Job titles and levels"
      path="/api/v1/designations"
      fields={[
        { key: "name", label: "Name *", required: true },
        { key: "code", label: "Code" },
        { key: "level", label: "Level" },
        { key: "description", label: "Description" },
      ]}
      renderRow={(item) => (
        <>
          <td data-label="Name" className="px-5 py-3 font-medium text-neutral-800">{String(item.name)}</td>
          <td data-label="Code" className="px-5 py-3 text-neutral-500">{String(item.code || "—")}</td>
          <td data-label="Level" className="px-5 py-3 text-neutral-500">
            {item.level ? `Level ${item.level}` : "—"}
          </td>
        </>
      )}
    />
  );
}