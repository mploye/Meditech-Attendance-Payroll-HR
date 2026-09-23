"use client";

import CrudPage from "@/components/CrudPage";

export default function DepartmentsPage() {
  return (
    <CrudPage
      title="Departments"
      subtitle="Organisational units"
      path="/api/v1/departments"
      fields={[
        { key: "name", label: "Name *", required: true },
        { key: "code", label: "Code" },
        { key: "description", label: "Description" },
      ]}
      renderRow={(item) => (
        <>
          <td data-label="Name" className="px-5 py-3 font-medium text-neutral-800">{String(item.name)}</td>
          <td data-label="Code" className="px-5 py-3 text-neutral-500">{String(item.code || "—")}</td>
          <td data-label="Description" className="px-5 py-3 text-neutral-500">{String(item.description || "—")}</td>
        </>
      )}
    />
  );
}