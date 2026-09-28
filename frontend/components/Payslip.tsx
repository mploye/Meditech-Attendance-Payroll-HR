interface PayrollComponent {
  name: string;
  amount: number;
}

interface PayslipProps {
  company: {
    name: string;
    address: string;
    logoUrl?: string;
  };
  employee: {
    employeeId: string;
    name: string;
    department: string;
  };
  attendance: {
    workingDays: number;
    presentDays: number;
    leaveDays: number;
    lopDays: number;
    overtimeMinutes: number;
  };
  month: string;
  year: number;
  earnings: PayrollComponent[];
  deductions: PayrollComponent[];
}

export function Payslip({
  company,
  employee,
  attendance,
  month,
  year,
  earnings,
  deductions,
}: PayslipProps) {

  const grossSalary = earnings.reduce(
    (total, item) => total + Number(item.amount),
    0
  );

  const totalDeductions = deductions.reduce(
    (total, item) => total + Number(item.amount),
    0
  );

  const netPay = grossSalary - totalDeductions;

  const money = (amount: number) =>
    amount.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  return (
    <div className="mx-auto w-[210mm] min-h-[297mm] bg-white p-[15mm] text-gray-800">

      {/* HEADER */}
      <div className="flex items-center justify-between border-b-2 border-green-700 pb-4">

        <div className="flex items-center gap-4">
          {company.logoUrl && (
            <img
              src={company.logoUrl}
              alt="Company Logo"
              className="h-16 w-16 object-contain"
            />
          )}

          <div>
            <h1 className="text-xl font-bold">
              {company.name}
            </h1>

            <p className="max-w-[350px] text-sm text-gray-600">
              {company.address}
            </p>
          </div>
        </div>

        <h2 className="text-xl font-bold">
          Payslip - {month} {year}
        </h2>

      </div>

      {/* EMPLOYEE DETAILS */}
      <section className="mt-6 overflow-hidden rounded-lg border border-green-200">

        <div className="bg-green-50 px-4 py-2">
          <h2 className="font-bold text-green-800">
            Employee Details
          </h2>
        </div>

        <div className="grid grid-cols-2 gap-3 p-4 text-sm">

          <div>
            <span className="text-gray-500">Employee ID</span>
            <p className="font-bold">{employee.employeeId}</p>
          </div>

          <div>
            <span className="text-gray-500">Employee Name</span>
            <p className="font-bold">{employee.name}</p>
          </div>

          <div>
            <span className="text-gray-500">Department</span>
            <p className="font-bold">{employee.department}</p>
          </div>

        </div>
      </section>

      {/* WORKING DETAILS */}
      <section className="mt-5 overflow-hidden rounded-lg border border-green-200">

        <div className="bg-green-50 px-4 py-2">
          <h2 className="font-bold text-green-800">
            Working Details
          </h2>
        </div>

        <div className="grid grid-cols-2 gap-3 p-4 text-sm">

          <div>
            <span className="text-gray-500">Period</span>
            <p className="font-bold">
              {month} {year}
            </p>
          </div>

          <div>
            <span className="text-gray-500">Working Days</span>
            <p className="font-bold">{attendance.workingDays}</p>
          </div>

          <div>
            <span className="text-gray-500">Present Days</span>
            <p className="font-bold">{attendance.presentDays}</p>
          </div>

          <div>
            <span className="text-gray-500">Leave Days</span>
            <p className="font-bold">{attendance.leaveDays}</p>
          </div>

          <div>
            <span className="text-gray-500">LOP Days</span>
            <p className="font-bold">{attendance.lopDays}</p>
          </div>

          <div>
            <span className="text-gray-500">Overtime Minutes</span>
            <p className="font-bold">
              {attendance.overtimeMinutes}
            </p>
          </div>

        </div>
      </section>

      {/* EARNINGS */}
      <section className="mt-5 overflow-hidden rounded-lg border border-green-200">

        <div className="flex justify-between bg-green-800 px-4 py-2 font-bold text-white">
          <span>Earnings</span>
          <span>Amount</span>
        </div>

        <div className="p-4">

          {earnings.map((item) => (
            <div
              key={item.name}
              className="flex justify-between border-b border-gray-100 py-2 text-sm last:border-0"
            >
              <span>{item.name}</span>

              <span>
                {money(item.amount)}
              </span>
            </div>
          ))}

        </div>
      </section>

      {/* DEDUCTIONS */}
      <section className="mt-5 overflow-hidden rounded-lg border border-green-200">

        <div className="flex justify-between bg-green-800 px-4 py-2 font-bold text-white">
          <span>Deductions</span>
          <span>Amount</span>
        </div>

        <div className="p-4">

          {deductions.map((item) => (
            <div
              key={item.name}
              className="flex justify-between border-b border-gray-100 py-2 text-sm last:border-0"
            >
              <span>{item.name}</span>

              <span>
                {money(item.amount)}
              </span>
            </div>
          ))}

        </div>
      </section>

      {/* SUMMARY */}
      <section className="mt-5 rounded-lg border border-green-300 bg-green-50 p-4">

        <div className="flex justify-between py-2 font-bold">
          <span>Gross Salary</span>
          <span>{money(grossSalary)}</span>
        </div>

        <div className="flex justify-between py-2 font-bold">
          <span>Total Deductions</span>
          <span>{money(totalDeductions)}</span>
        </div>

        <div className="mt-2 flex justify-between border-t-2 border-green-300 pt-3 text-lg font-bold text-green-800">
          <span>Net Pay</span>
          <span>{money(netPay)}</span>
        </div>

      </section>

    </div>
  );
}
