import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

PASS = []
FAIL = []


def check(name, cond, extra=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {extra}")


with client:
    r = client.post(
        "/api/v1/auth/register-super-admin",
        json={"email": "smoke@example.com", "password": "Admin123!", "full_name": "Smoke Admin"},
    )
    check("register-super-admin", r.status_code == 200)

    r = client.post("/api/v1/auth/login", json={"email": "smoke@example.com", "password": "Admin123!"})
    check("login", r.status_code == 200, r.text)
    token = r.json()["data"]["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/v1/auth/companies", headers=H, json={
        "company": {"name": "Smoke Corp", "short_name": "SMK", "timezone": "Asia/Kolkata",
                    "country": "India"},
        "admin_user": {"email": "hr@smoke.com", "password": "Hr123456", "full_name": "HR Manager"},
    })
    check("create-company", r.status_code == 200, r.text)
    company_id = r.json()["data"]["company"]["id"]

    hr = client.post("/api/v1/auth/login", json={"email": "hr@smoke.com", "password": "Hr123456"})
    check("hr-login", hr.status_code == 200, hr.text)
    TH = {"Authorization": f"Bearer {hr.json()['data']['access_token']}"}

    r = client.post("/api/v1/departments/", headers=TH, json={"name": "Engineering"})
    check("create-department", r.status_code == 200, r.text)
    dept_id = r.json()["data"]["id"]

    r = client.post("/api/v1/designations/", headers=TH, json={"name": "Software Engineer"})
    check("create-designation", r.status_code == 200, r.text)
    desig_id = r.json()["data"]["id"]

    r = client.post("/api/v1/shifts/", headers=TH, json={
        "name": "Day Shift", "code": "DAY", "start_time": "09:00", "end_time": "18:00",
        "grace_period_minutes": 10, "minimum_work_minutes": 480, "break_minutes": 60,
        "overtime_enabled": True, "overtime_after_minutes": 60, "is_default": True,
    })
    check("create-shift", r.status_code == 200, r.text)
    shift_id = r.json()["data"]["id"]

    r = client.post("/api/v1/salary/structures/", headers=TH, json={
        "name": "Standard", "payment_frequency": "MONTHLY", "monthly_gross": 50000,
        "effective_from": "2026-01-01",
        "components": [
            {"name": "Basic", "component_type": "EARNING", "calculation_type": "PERCENTAGE_OF_GROSS", "value": 0.4},
            {"name": "HRA", "component_type": "EARNING", "calculation_type": "PERCENTAGE_OF_BASIC", "value": 0.5},
            {"name": "Special Allowance", "component_type": "EARNING", "calculation_type": "FIXED", "value": 10000},
            {"name": "PF", "component_type": "DEDUCTION", "calculation_type": "PERCENTAGE_OF_BASIC", "value": 0.12},
        ],
    })
    check("create-salary-structure", r.status_code == 200, r.text)
    structure_id = r.json()["data"]["id"]

    r = client.post(f"/api/v1/salary/structures/{structure_id}/simulate", headers=TH, json={"basic_salary": 20000})
    check("simulate-structure", r.status_code == 200, r.text)

    r = client.post("/api/v1/employees/", headers=TH, json={
        "employee_code": "EMP001", "first_name": "John", "last_name": "Doe",
        "department_id": dept_id, "designation_id": desig_id,
        "joining_date": "2026-01-01", "employment_type": "FULL_TIME",
        "status": "ACTIVE", "phone": "9898989898",
        "salary": {"effective_from": "2026-01-01", "basic_salary": 20000, "gross_salary": 50000,
                   "salary_structure_id": structure_id, "payment_frequency": "MONTHLY"},
    })
    check("create-employee", r.status_code == 200, r.text)
    emp_id = r.json()["data"]["id"]

    r = client.post("/api/v1/employees/", headers=TH, json={
        "employee_code": "EMP002", "first_name": "Jane", "last_name": "Roe",
        "department_id": dept_id, "designation_id": desig_id,
        "joining_date": "2026-01-01", "employment_type": "FULL_TIME",
        "status": "ACTIVE", "phone": "9797979797",
        "salary": {"effective_from": "2026-01-01", "basic_salary": 18000, "gross_salary": 45000,
                   "salary_structure_id": structure_id, "payment_frequency": "MONTHLY"},
    })
    check("create-employee-2", r.status_code == 200, r.text)
    emp2_id = r.json()["data"]["id"]

    r = client.post("/api/v1/employees/" + emp_id + "/associate-user", headers=TH,
                    json={"email": "john@smoke.com", "full_name": "John Doe", "password": "John123456"})
    check("associate-user", r.status_code == 200, r.text)
    check("org-user-company-scoped", "company_id" in r.json()["data"])

    r = client.post("/api/v1/salary/statutory-rules/", headers=TH, json={
        "rule_type": "PF", "rate": 0.12, "threshold": 15000, "maximum": 1800,
    })
    check("create-statutory-rule", r.status_code == 200, r.text)

    r = client.post("/api/v1/holidays/", headers=TH, json={"holiday_date": "2026-01-26", "name": "Republic Day", "holiday_type": "NATIONAL"})
    check("create-holiday", r.status_code == 200, r.text)

    r = client.post("/api/v1/leaves/types", headers=TH, json={"name": "Annual Leave", "code": "AL", "category": "PAID", "days_per_year": 20})
    check("create-leave-type", r.status_code == 200, r.text)
    lt_id = r.json()["data"]["id"]

    r = client.post("/api/v1/leaves/balances/init?year=2026", headers=TH)
    check("init-leave-balances", r.status_code == 200, r.text)
    r = client.get("/api/v1/leaves/balances?year=2026", headers=TH)
    check("list-leave-balances", r.status_code == 200 and len(r.json()["data"]) > 0)

    r = client.post("/api/v1/leaves/apply", headers=TH, json={
        "employee_id": emp_id, "leave_type_id": lt_id, "start_date": "2026-03-02", "end_date": "2026-03-04", "reason": "vacation",
    })
    check("apply-leave", r.status_code == 200, r.text)
    leave_id = r.json()["data"]["id"]

    r = client.post(f"/api/v1/leaves/{leave_id}/approve", headers=TH, json={})
    check("approve-leave", r.status_code == 200, r.text)

    r = client.post("/api/v1/overtime/", headers=TH, json={"employee_id": emp_id, "date": "2026-03-05", "minutes": 120, "rate": 1.5})
    check("create-overtime", r.status_code == 200, r.text)
    ot_id = r.json()["data"]["id"]
    r = client.post(f"/api/v1/overtime/{ot_id}/approve", headers=TH)
    check("approve-overtime", r.status_code == 200, r.text)

    r = client.post("/api/v1/payroll/periods?month=3&year=2026", headers=TH)
    check("create-payroll-period", r.status_code == 200, r.text)
    period_id = r.json()["data"]["id"]

    r = client.post(f"/api/v1/payroll/periods/{period_id}/calculate", headers=TH)
    check("calculate-period", r.status_code == 200, r.text)
    r = client.get(f"/api/v1/payroll/periods/{period_id}/records", headers=TH)
    check("period-records", r.status_code == 200 and len(r.json()["data"]) == 2, r.text)

    r = client.post(f"/api/v1/payroll/periods/{period_id}/review", headers=TH)
    check("review-period", r.status_code == 200, r.text)
    r = client.post(f"/api/v1/payroll/periods/{period_id}/approve", headers=TH)
    check("approve-period", r.status_code == 200, r.text)
    r = client.post(f"/api/v1/payroll/periods/{period_id}/lock", headers=TH)
    check("lock-period", r.status_code == 200, r.text)

    r = client.post(f"/api/v1/payslips/generate?payroll_period_id={period_id}", headers=TH)
    check("generate-payslips", r.status_code == 200, r.text)
    r = client.get("/api/v1/payslips/", headers=TH)
    check("list-payslips", r.status_code == 200 and len(r.json()["data"]) == 2, r.text)
    payslip_id = r.json()["data"][0]["id"]
    r = client.get(f"/api/v1/payslips/{payslip_id}/pdf", headers=TH)
    check("payslip-pdf", r.status_code == 200 and r.headers.get("content-type") == "application/pdf", r.text[:200])

    r = client.get(f"/api/v1/reports/attendance/daily?from_date=2026-03-01&to_date=2026-03-31", headers=TH)
    check("report-attendance-daily", r.status_code == 200, r.text[:300])
    r = client.get(f"/api/v1/reports/payroll/salary-register?payroll_period_id={period_id}&format=csv", headers=TH)
    check("report-salary-register-csv", r.status_code == 200 and "text/csv" in r.headers.get("content-type", ""), r.text[:200])

    r = client.post("/api/v1/loans/", headers=TH, json={
        "employee_id": emp_id, "loan_amount": 100000, "installment_amount": 10000,
        "number_of_installments": 10, "start_date": "2026-01-15", "remarks": "bike loan",
    })
    check("create-loan", r.status_code == 200, r.text)
    loan_id = r.json()["data"]["id"]
    r = client.post(f"/api/v1/loans/{loan_id}/pay", headers=TH, json={})
    check("pay-loan-installment", r.status_code == 200, r.text)

    r = client.get(f"/api/v1/reports/loans?format=xlsx", headers=TH)
    check("report-loans-xlsx", r.status_code == 200 and "spreadsheet" in r.headers.get("content-type", ""), r.text[:200])

    r = client.get("/api/v1/dashboard/summary", headers=TH)
    check("dashboard-summary", r.status_code == 200, r.text[:300])

    r = client.get("/api/v1/audit/", headers=TH)
    check("audit-logs", r.status_code == 200, r.text[:300])

    r = client.get("/api/v1/integrations/essl/config", headers=TH)
    check("essl-config", r.status_code == 200, r.text[:200])

    r = client.post("/api/v1/integrations/essl/test", headers=TH)
    check("essl-test-mock", r.status_code == 200, r.text[:300])

    r = client.post("/api/v1/devices/", headers=TH, json={
        "name": "Front Door", "device_type": "FACE_PUNCH", "provider": "ESSL",
        "serial_number": "SN123", "model": "eTimeTrackLite", "ip_address": "192.168.1.10",
    })
    check("create-device", r.status_code == 200, r.text)
    device_id = r.json()["data"]["id"]

    r = client.post(f"/api/v1/employees/{emp_id}/devices", headers=TH, json={"device_id": device_id, "device_user_id": "EMP001"})
    check("map-employee-device", r.status_code == 200, r.text)

    r = client.get(f"/api/v1/shifts/{shift_id}", headers=TH)
    check("get-shift", r.status_code == 200, r.text[:200])

    r = client.get("/api/v1/companies/" + company_id, headers=TH)
    check("get-company", r.status_code == 200, r.text[:200])

    print()
    print(f"PASSED: {len(PASS)}  FAILED: {len(FAIL)}")
    if FAIL:
        raise SystemExit(1)