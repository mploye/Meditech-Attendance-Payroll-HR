"""Deploy 10 employees + August 2026 full data to the live HRMS backend.

Usage:
    cd backend
    python -m scripts.deploy_live

Idempotent: checks for existing resources before creating them.
Uses async httpx for fast parallel attendance punches.
"""

import asyncio
import os
import sys
import warnings

warnings.filterwarnings("ignore")

# Make `app` package importable.
_backend_app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _backend_app not in sys.path:
    sys.path.insert(0, _backend_app)

from datetime import date, timedelta

import httpx
from models.enums import EventType

BASE = "https://hrms-api-4trx.onrender.com"
LAST_MONTH = 8
LAST_YEAR = 2026
PASS: list[str] = []
FAIL: list[str] = []
SEM = asyncio.Semaphore(30)


def check(name: str, cond: bool, extra: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {extra}")


async def request(client: httpx.AsyncClient, method: str, path: str,
                  json_body: dict | None = None, params: dict | None = None,
                  headers: dict | None = None, timeout: float = 15) -> dict:
    async with SEM:
        r = await client.request(method, BASE + path, json=json_body,
                                  params=params, headers=headers, timeout=timeout)
        check(f"{method} {path}", r.status_code == 200, r.text[:120])
        data = r.json()
        return data.get("data", data) if isinstance(data, dict) else data


async def post(client: httpx.AsyncClient, path: str, body: dict,
               headers: dict) -> dict:
    return await request(client, "POST", path, json_body=body, headers=headers)


async def get(client: httpx.AsyncClient, path: str, params: dict | None = None,
              headers: dict | None = None) -> dict:
    return await request(client, "GET", path, params=params, headers=headers)


def find_in_list(list_data: list[dict], **criteria) -> dict | None:
    for item in list_data:
        if all(item.get(k) == v for k, v in criteria.items()):
            return item
    return None


def find_in_response(data, **criteria):
    items = data.get("items") if isinstance(data, dict) else data
    if isinstance(items, list):
        return find_in_list(items, **criteria)
    return None


def find_period(periods, month: int, year: int) -> dict | None:
    """Find a period by month/year — handles both dict and list responses."""
    items = periods.get("items") if isinstance(periods, dict) else periods
    if isinstance(items, list):
        for p in items:
            if p.get("month") == month and p.get("year") == year:
                return p
    return None


async def main() -> None:
    client = httpx.AsyncClient(timeout=15, limits=httpx.Limits(max_connections=50))

    try:
        # ── 1. Auth ──────────────────────────────────
        login = await post(client, "/api/v1/auth/login",
                           {"email": "hr.genetics@gmail.com", "password": "Admin@12345"}, {})
        token = login["access_token"]
        H = {"Authorization": f"Bearer {token}"}
        hr_login = await post(client, "/api/v1/auth/login",
                              {"email": "admin@geneticsmeditech.com", "password": "Company@12345"}, {})
        TH = {"Authorization": f"Bearer {hr_login['access_token']}"}
        print(f"Logged in as super-admin and HR.")

        # ── 2. Organisation (idempotent) ──────────
        depts = await get(client, "/api/v1/departments/", params={}, headers=TH)
        dept = find_in_list(depts, name="Engineering")
        if dept:
            dept_id = dept["id"]
            check("department-Engineering (exists)", True)
        else:
            dept = await post(client, "/api/v1/departments/", {"name": "Engineering"}, TH)
            dept_id = dept["id"]
            check("department-Engineering (created)", True)

        desigs = await get(client, "/api/v1/designations/", params={}, headers=TH)
        desig = find_in_list(desigs, name="Software Engineer")
        if desig:
            desig_id = desig["id"]
            check("designation-Software Engineer (exists)", True)
        else:
            desig = await post(client, "/api/v1/designations/", {"name": "Software Engineer"}, TH)
            desig_id = desig["id"]
            check("designation-Software Engineer (created)", True)

        shifts = await get(client, "/api/v1/shifts/", params={}, headers=TH)
        shift = find_in_list(shifts, name="Day Shift")
        if shift:
            shift_id = shift["id"]
            check("shift-Day Shift (exists)", True)
        else:
            shift = await post(client, "/api/v1/shifts/", {
                "name": "Day Shift", "code": "DAY", "start_time": "09:00", "end_time": "18:00",
                "grace_period_minutes": 10, "minimum_work_minutes": 480, "break_minutes": 60,
                "overtime_enabled": True, "overtime_after_minutes": 60, "is_default": True,
            }, TH)
            shift_id = shift["id"]
            check("shift-Day Shift (created)", True)

        structures = await get(client, "/api/v1/salary/structures", params={}, headers=TH)
        ss = find_in_list(structures, name="Standard")
        if ss:
            structure_id = ss["id"]
            check("salary-structure-Standard (exists)", True)
        else:
            ss = await post(client, "/api/v1/salary/structures", {
                "name": "Standard", "payment_frequency": "MONTHLY", "monthly_gross": 50000,
                "effective_from": "2026-01-01",
                "components": [
                    {"name": "Basic", "component_type": "EARNING", "calculation_type": "PERCENTAGE_OF_GROSS", "value": 0.4},
                    {"name": "HRA", "component_type": "EARNING", "calculation_type": "PERCENTAGE_OF_BASIC", "value": 0.5},
                    {"name": "Special Allowance", "component_type": "EARNING", "calculation_type": "FIXED", "value": 10000},
                    {"name": "PF", "component_type": "DEDUCTION", "calculation_type": "PERCENTAGE_OF_BASIC", "value": 0.12},
                ],
            }, TH)
            structure_id = ss["id"]
            check("salary-structure-Standard (created)", True)

        await post(client, "/api/v1/salary/statutory-rules",
                   {"rule_type": "PF", "rate": 0.12, "threshold": 15000, "maximum": 1800}, TH)
        check("statutory-rules-PF", True)
        try:
            await post(client, "/api/v1/holidays/",
                       {"holiday_date": "2026-08-15", "name": "Independence Day", "holiday_type": "NATIONAL"}, TH)
        except Exception:
            pass
        check("holiday-Independence Day", True)

        lt = await get(client, "/api/v1/leaves/types", params={}, headers=TH)
        lt_item = find_in_list(lt, code="AL")
        if lt_item:
            lt_id = lt_item["id"]
            check("leave-type-Annual Leave (exists)", True)
        else:
            lt = await post(client, "/api/v1/leaves/types",
                            {"name": "Annual Leave", "code": "AL", "category": "PAID", "days_per_year": 20}, TH)
            lt_id = lt["id"]
            check("leave-type-Annual Leave (created)", True)
        await post(client, "/api/v1/leaves/balances/init?year=2026", {}, TH)
        check("leave-balances-init", True)

        # ── 3. Create 10 employees (idempotent) ──
        first_names = ["Arjun", "Bhavna", "Chetan", "Divya", "Eshan", "Fatima",
                       "Ganesh", "Hema", "Irfan", "Jyoti"]
        last_names = ["Patel", "Sharma", "Kumar", "Reddy", "Singh", "Ali",
                      "Warrier", "Das", "Khan", "Prasad"]
        employee_ids: list[str] = []
        for i in range(10):
            code = f"EMP{str(i + 1).zfill(3)}"
            fn = first_names[i]
            ln = last_names[i]
            emp_res = await get(client, "/api/v1/employees/",
                                  params={"employee_code": code}, headers=TH)
            existing = find_in_response(emp_res, employee_code=code)
            if existing:
                employee_ids.append(existing["id"])
                check(f"employee-{code} (exists)", True)
                continue
            body = {
                "employee_code": code, "first_name": fn, "last_name": ln,
                "department_id": dept_id, "designation_id": desig_id,
                "joining_date": "2026-01-15", "employment_type": "FULL_TIME",
                "status": "ACTIVE", "phone": f"999999999{i + 1}",
                "salary": {
                    "effective_from": "2026-01-01", "basic_salary": 20000 + i * 2000,
                    "gross_salary": 50000 + i * 5000, "salary_structure_id": structure_id,
                    "payment_frequency": "MONTHLY",
                },
            }
            r = await request(client, "POST", "/api/v1/employees/", json_body=body, headers=TH, timeout=15)
            if isinstance(r, dict) and "id" in r:
                emp_id = r["id"]
                employee_ids.append(emp_id)
                check(f"employee-{code} (created)", True)
                r2 = await request(client, "POST", f"/api/v1/employees/{emp_id}/associate-user",
                                   json_body={"email": f"{fn.lower()}@seed.com",
                                   "full_name": f"{fn} {ln}", "password": "Pass123456"},
                                   headers=TH, timeout=15)
                check(f"associate-user-{code}", isinstance(r2, dict))
            else:
                check(f"employee-{code}", False)
        print(f"\n{len(employee_ids)} employees ready.")

        # ── 4. Last month's attendance (August 2026) ──
        start = date(LAST_YEAR, LAST_MONTH, 1)
        end = date(LAST_YEAR, LAST_MONTH, 31)
        async def add_punch(emp_id: str, d: date, et: EventType) -> int:
            r = await request(client, "POST", "/api/v1/attendance/manual",
                              json_body={"employee_id": emp_id, "event_type": et.value,
                                         "timestamp": f"{d.isoformat()}T{'09:00' if et == EventType.IN else '18:00'}"},
                              headers=TH, timeout=10)
            return 1 if isinstance(r, dict) else 0
        tasks = []
        for emp_id in employee_ids:
            d = start
            while d <= end:
                if d.weekday() < 5:
                    tasks.append(add_punch(emp_id, d, EventType.IN))
                    tasks.append(add_punch(emp_id, d, EventType.OUT))
                d += timedelta(days=1)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        punch_count = sum(1 for r in results if isinstance(r, int))
        check("attendance-punches", punch_count > 0, f"{punch_count} punches")
        r = await request(client, "POST", "/api/v1/attendance/process",
                          params={"from_date": start.isoformat(), "to_date": end.isoformat()},
                          headers=TH, timeout=120)
        check("process-attendance-range", r is not None)

        # ── 5. Leave and overtime ──────────────────
        for emp_id in employee_ids[:3]:
            r = await request(client, "POST", "/api/v1/leaves/apply",
                              json_body={"employee_id": emp_id, "leave_type_id": lt_id,
                                         "start_date": "2026-08-15", "end_date": "2026-08-16", "reason": "vacation"},
                              headers=TH, timeout=10)
            check(f"leave-{emp_id}", isinstance(r, dict))
            lid = r.get("id") if isinstance(r, dict) else None
            if lid:
                r = await request(client, "POST", f"/api/v1/leaves/{lid}/approve",
                                  json_body={}, headers=TH, timeout=10)
                check(f"approve-leave-{emp_id}", isinstance(r, dict))
        for emp_id in employee_ids[:5]:
            r = await request(client, "POST", "/api/v1/overtime/",
                              json_body={"employee_id": emp_id, "date": "2026-08-20", "minutes": 120, "rate": 1.5},
                              headers=TH, timeout=10)
            check(f"overtime-{emp_id}", isinstance(r, dict))
            oid = r.get("id") if isinstance(r, dict) else None
            if oid:
                r = await request(client, "POST", f"/api/v1/overtime/{oid}/approve",
                                  json_body={}, headers=TH, timeout=10)
                check(f"approve-overtime-{emp_id}", isinstance(r, dict))

        # ── 6. Payroll period (idempotent) ────────
        periods_data = await get(client, "/api/v1/payroll/periods",
                                  params={"month": LAST_MONTH, "year": LAST_YEAR}, headers=TH)
        existing_period = find_period(periods_data, LAST_MONTH, LAST_YEAR)
        if existing_period:
            period_id = existing_period["id"]
            check("payroll-period-August-2026 (exists)", True)
        else:
            r = await request(client, "POST", "/api/v1/payroll/periods",
                              params={"month": LAST_MONTH, "year": LAST_YEAR}, headers=TH, timeout=15)
            check("create-payroll-period", isinstance(r, dict))
            period_id = r["id"] if isinstance(r, dict) else None

        # If existing period was already processed (locked), skip calculate/review/approve/lock
        if existing_period and existing_period.get("status") == "LOCKED":
            check("payroll-period already LOCKED — skipping recalculation", True)
        else:
            r = await request(client, "POST", f"/api/v1/payroll/periods/{period_id}/calculate", headers=TH, timeout=30)
            check("calculate-period", r is not None)
            r = await request(client, "POST", f"/api/v1/payroll/periods/{period_id}/review", headers=TH, timeout=15)
            check("review-period", r is not None)
            r = await request(client, "POST", f"/api/v1/payroll/periods/{period_id}/approve", headers=TH, timeout=15)
            check("approve-period", r is not None)
            r = await request(client, "POST", f"/api/v1/payroll/periods/{period_id}/lock", headers=TH, timeout=15)
            check("lock-period", r is not None)

        # ── 7. Generate payslips ──────────────────
        r = await request(client, "POST", f"/api/v1/payslips/generate?payroll_period_id={period_id}",
                          headers=TH, timeout=30)
        check("generate-payslips", r is not None)
        gen = r if isinstance(r, dict) else {}
        print(f"  generate result: {gen}")
        payslips = await get(client, "/api/v1/payslips/", params={}, headers=TH)
        check("list-payslips", len(payslips) > 0, f"count={len(payslips)}")
        if isinstance(payslips, list) and payslips:
            payslip_id = payslips[0]["id"]
            for fmt in ["pdf", "json", "html", "text"]:
                r = await request(client, "GET", f"/api/v1/payslips/{payslip_id}/{fmt}", headers=TH, timeout=30)
                check(f"payslip-{fmt}", r is not None)
        else:
            check("payslip-format", False, "no payslips found")

    finally:
        await client.aclose()

    print(f"\nPASSED: {len(PASS)}  FAILED: {len(FAIL)}")
    if FAIL:
        raise SystemExit(1)
    print("Live deploy complete: 10 employees + August 2026 data on", BASE)


if __name__ == "__main__":
    asyncio.run(main())
