"use client";

import CrudPage from "@/components/CrudPage";

export default function HolidaysPage() {
  return (
    <CrudPage
      title="Holidays"
      subtitle="Public / company holidays"
      path="/api/v1/holidays"
      fields={[
        { key: "name", label: "Name *", required: true },
        { key: "holiday_date", label: "Date *", type: "date", required: true },
        { key: "type", label: "Type" },
      ]}
      renderRow={(item) => (
        <>
          <td className="px-5 py-3 font-medium text-neutral-800">{String(item.name)}</td>
          <td className="px-5 py-3 text-neutral-500">{String(String(item.holiday_date || item.date || "").slice(0, 10))}</td>
          <td className="px-5 py-3 text-neutral-500">{String(item.type || "—")}</td>
        </>
      )}
    />
  );
}