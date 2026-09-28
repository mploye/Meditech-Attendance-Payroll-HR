"""Seed the project with 10 employees and last month's (August 2026) full data.

Usage:
    cd backend
    python -m scripts.seed_data

Creates: super admin → company → HR → department, designation, shift, salary structure,
statutory rules, holidays, leave types, then 10 employees with salary, last-month
attendance (daily records), leaves, overtime, a payroll period (calculate → review →
approve → lock), and payslips.
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore")

# Make `app` package importable so `import main` (backend/app/main.py) works.
_backend_app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _backend_app not in sys.path:
    sys.path.insert(0, _backend_app)

# Set env vars before any app import (so settings bind to a SQLite seed DB).
import tempfile
_seed_db = os.path.join(tempfile.gettempdir(), "opencode", "seed_hrms.db")
os.makedirs(os.path.dirname(_seed_db), exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_seed_db.replace(os.sep, '/')}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "seed-jwt-secret-not-for-production"
os.environ["ESSL_MOCK_MODE"] = "true"
os.environ["DEVICE_CONNECTOR_API_KEY"] = "seed-connector-key"
os.environ["APP_ENV"] = "seed"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from models.enums import EventType

# Reset the seed DB on every run for idempotency (delete before import main creates the engine).
if os.path.exists(_seed_db):
    os.remove(_seed_db)

import main

client = TestClient(main.app)
PASS: list[str] = []
FAIL: list[str] = []
LAST_MONTH = 8      # August 2026
LAST_YEAR = 2026


def check(name: str, cond: bool, extra: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {extra}")


def post(path: str, body: dict, headers: dict | None = None) -> dict:
    r = client.post(path, json=body, headers=headers or {})
    check(path, r.status_code == 200, r.text[:120])
    return r.json()["data"]


def get(path: str, headers: dict | None = None) -> dict:
    r = client.get(path, headers=headers or {})
    check(path, r.status_code == 200, r.text[:120])
    return r.json()["data"]


# ── 1. Auth ──────────────────────────────────────────────────────────────────
with client:
    r = client.post(
        "/api/v1/auth/register-super-admin",
        json={"email": "seed@smoke.com", "password": "Seed12345!", "full_name": "Seed Admin"},
    )
    check("register-super-admin", r.status_code == 200)
    r = client.post("/api/v1/auth/login", json={"email": "seed@smoke.com", "password": "Seed12345!"})
    check("login", r.status_code == 200)
    token = r.json()["data"]["access_token"]
    H = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/v1/auth/companies", headers=H, json={
        "company": {"name": "Seed Corp", "short_name": "SKD", "timezone": "Asia/Kolkata", "country": "India"},
        "admin_user": {"email": "hr@seed.com", "password": "Hr123456", "full_name": "HR Manager"},
    })
    check("create-company", r.status_code == 200)
    company_id = r.json()["data"]["company"]["id"]
    r = client.post("/api/v1/auth/login", json={"email": "hr@seed.com", "password": "Hr123456"})
    check("hr-login", r.status_code == 200)
    TH = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

# ── 2. Organisation ──────────────────────────────────────────────────────────
dept = post("/api/v1/departments/", {"name": "Engineering"}, TH)
dept_id = dept["id"]
desig = post("/api/v1/designations/", {"name": "Software Engineer"}, TH)
desig_id = desig["id"]
shift = post("/api/v1/shifts/", {
    "name": "Day Shift", "code": "DAY", "start_time": "09:00", "end_time": "18:00",
    "grace_period_minutes": 10, "minimum_work_minutes": 480, "break_minutes": 60,
    "overtime_enabled": True, "overtime_after_minutes": 60, "is_default": True,
}, TH)
shift_id = shift["id"]
ss = post("/api/v1/salary/structures/", {
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
post("/api/v1/salary/statutory-rules/", {"rule_type": "PF", "rate": 0.12, "threshold": 15000, "maximum": 1800}, TH)
post("/api/v1/holidays/", {"holiday_date": "2026-08-15", "name": "Independence Day", "holiday_type": "NATIONAL"}, TH)
lt = post("/api/v1/leaves/types", {"name": "Annual Leave", "code": "AL", "category": "PAID", "days_per_year": 20}, TH)
lt_id = lt["id"]
post("/api/v1/leaves/balances/init?year=2026", {}, TH)

# ── 3. Create 10 employees ───────────────────────────────────────────────────
first_names = ["Arjun", "Bhavna", "Chetan", "Divya", "Eshan", "Fatima",
               "Ganesh", "Hema", "Irfan", "Jyoti"]
last_names = ["Patel", "Sharma", "Kumar", "Reddy", "Singh", "Ali",
              "Warrier", "Das", "Khan", "Prasad"]
employee_ids: list[str] = []
for i in range(10):
    code = f"EMP{str(i + 1).zfill(3)}"
    fn = first_names[i]
    ln = last_names[i]
    body = {
        "employee_code": code,
        "first_name": fn,
        "last_name": ln,
        "department_id": dept_id,
        "designation_id": desig_id,
        "joining_date": "2026-01-15",
        "employment_type": "FULL_TIME",
        "status": "ACTIVE",
        "phone": f"999999999{i + 1}",
        "salary": {
            "effective_from": "2026-01-01",
            "basic_salary": 20000 + i * 2000,
            "gross_salary": 50000 + i * 5000,
            "salary_structure_id": structure_id,
            "payment_frequency": "MONTHLY",
        },
    }
    r = client.post("/api/v1/employees/", json=body, headers=TH)
    if r.status_code == 200:
        emp = r.json()["data"]
        employee_ids.append(emp["id"])
        check(f"create-employee-{code}", True)
        r2 = client.post(f"/api/v1/employees/{emp['id']}/associate-user", headers=TH,
                         json={"email": f"{fn.lower()}@seed.com", "full_name": f"{fn} {ln}", "password": "Pass123456"})
        check(f"associate-user-{code}", r2.status_code == 200)
    else:
        check(f"create-employee-{code}", False, r.text[:120])

print(f"\nCreated {len(employee_ids)} employees.")

# ── 4. Last month's attendance (August 2026) ────────────────────────────
start = date(LAST_YEAR, LAST_MONTH, 1)
end = date(LAST_YEAR, LAST_MONTH, 31)

# Use TestClient HTTP for attendance to stay consistent with the smoke pattern
# Insert IN/OUT punches via manual endpoint for each employee-day
punch_count = 0
for emp_id in employee_ids:
    d = start
    while d <= end:
        if d.weekday() < 5:  # weekdays only
            for et, ts in [(EventType.IN, "09:00"), (EventType.OUT, "18:00")]:
                body = {
                    "employee_id": emp_id,
                    "event_type": et.value,
                    "timestamp": f"{d.isoformat()}T{ts}:00",
                }
                r = client.post("/api/v1/attendance/manual", json=body, headers=TH)
                if r.status_code == 200:
                    punch_count += 1
                else:
                    check(f"punch-{emp_id}-{d}-{et.value}", False, r.text[:80])
        d += timedelta(days=1)
check("attendance-punches", punch_count > 0, f"{punch_count} punches")

# Process the date range to generate AttendanceDaily records
r = client.post("/api/v1/attendance/process",
                params={"from_date": start.isoformat(), "to_date": end.isoformat()},
                headers=TH)
check("process-attendance-range", r.status_code == 200, r.text[:120])

# ── 5. Leave and overtime for last month ─────────────────────────────────────
for emp_id in employee_ids[:3]:
    r = client.post("/api/v1/leaves/apply", headers=TH, json={
        "employee_id": emp_id, "leave_type_id": lt_id,
        "start_date": "2026-08-15", "end_date": "2026-08-16", "reason": "vacation",
    })
    check(f"leave-{emp_id}", r.status_code == 200)
    lid = r.json()["data"]["id"]
    r = client.post(f"/api/v1/leaves/{lid}/approve", headers=TH, json={})
    check(f"approve-leave-{emp_id}", r.status_code == 200)
for emp_id in employee_ids[:5]:
    r = client.post("/api/v1/overtime/", headers=TH, json={
        "employee_id": emp_id, "date": "2026-08-20", "minutes": 120, "rate": 1.5})
    check(f"overtime-{emp_id}", r.status_code == 200)
    oid = r.json()["data"]["id"]
    r = client.post(f"/api/v1/overtime/{oid}/approve", headers=TH)
    check(f"approve-overtime-{emp_id}", r.status_code == 200)

# ── 6. Payroll period (August 2026) ────────────────────────────────────────
r = client.post("/api/v1/payroll/periods", headers=TH, params={"month": LAST_MONTH, "year": LAST_YEAR})
check("create-payroll-period", r.status_code == 200)
period_id = r.json()["data"]["id"]
r = client.post(f"/api/v1/payroll/periods/{period_id}/calculate", headers=TH)
check("calculate-period", r.status_code == 200)
r = client.post(f"/api/v1/payroll/periods/{period_id}/review", headers=TH)
check("review-period", r.status_code == 200)
r = client.post(f"/api/v1/payroll/periods/{period_id}/approve", headers=TH)
check("approve-period", r.status_code == 200)
r = client.post(f"/api/v1/payroll/periods/{period_id}/lock", headers=TH)
check("lock-period", r.status_code == 200)

# ── 7. Generate payslips ────────────────────────────────────────────
r = client.post(f"/api/v1/payslips/generate?payroll_period_id={period_id}", headers=TH)
check("generate-payslips", r.status_code == 200)
r = client.get("/api/v1/payslips/", headers=TH)
payslips = r.json()["data"]
check("list-payslips", len(payslips) > 0)
payslip_count = len(payslips)
payslip_id = payslips[0]["id"]
r = client.get(f"/api/v1/payslips/{payslip_id}/pdf", headers=TH)
check("payslip-pdf", r.status_code == 200 and "pdf" in r.headers.get("content-type", ""))
r = client.get(f"/api/v1/payslips/{payslip_id}/json", headers=TH)
check("payslip-json", r.status_code == 200)
r = client.get(f"/api/v1/payslips/{payslip_id}/html", headers=TH)
check("payslip-html", r.status_code == 200)
r = client.get(f"/api/v1/payslips/{payslip_id}/text", headers=TH)
check("payslip-text", r.status_code == 200)

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\nPASSED: {len(PASS)}  FAILED: {len(FAIL)}")
if FAIL:
    raise SystemExit(1)
print("Seed complete: 10 employees + August 2026 attendance, payroll, leaves, overtime, payslips.")
