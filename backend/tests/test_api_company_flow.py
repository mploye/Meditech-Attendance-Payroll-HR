def test_company_lifecycle(client, superadmin, company):
    cid = company["company_id"]

    r = client.get("/api/v1/companies", headers=company["headers"])
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["data"]]
    assert cid in ids

    r = client.patch(
        f"/api/v1/companies/{cid}",
        headers=company["headers"],
        json={"name": "Acme Renamed"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Acme Renamed"


def test_department_crud_and_scoping(client, superadmin, company):
    H = company["headers"]
    r = client.post("/api/v1/departments/", headers=H, json={"name": "Engineering"})
    assert r.status_code == 200, r.text
    dept_id = r.json()["data"]["id"]

    r = client.patch(f"/api/v1/departments/{dept_id}", headers=H, json={"name": "Platform"})
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Platform"

    r = client.delete(f"/api/v1/departments/{dept_id}", headers=H)
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] is True


def test_hr_admin_cannot_see_other_companys_employees(client, superadmin, company):
    # Create a second company so the HR admin cannot access its data.
    second = client.post(
        "/api/v1/auth/companies",
        headers=superadmin["headers"],
        json={
            "company": {"name": "Beta Corp", "short_name": "BETA", "country": "India"},
            "admin_user": {"email": "hr2@example.com", "password": "Hr123456", "full_name": "HR2"},
        },
    )
    assert second.status_code == 200
    other_company_id = second.json()["data"]["company"]["id"]

    # HR of the first company must not be able to read the second company's employees.
    r = client.get(
        "/api/v1/employees/",
        headers=company["headers"],
        params={"company_id": other_company_id},
    )
    assert r.status_code in (200, 403)
    if r.status_code == 200:
        for emp in r.json()["data"]["items"]:
            assert str(emp["company_id"]) != other_company_id or company["company_id"] == other_company_id


def test_employee_create_with_salary(client, company):
    H = company["headers"]
    dept = client.post("/api/v1/departments/", headers=H, json={"name": "Engineering"})
    dept_id = dept.json()["data"]["id"]

    structure = client.post(
        "/api/v1/salary/structures",
        headers=H,
        json={
            "name": "Standard",
            "code": "STD",
            "payment_frequency": "MONTHLY",
            "effective_from": "2024-01-01",
            "monthly_gross": 50000,
            "components": [
                {"name": "Basic", "component_type": "EARNING", "calculation_type": "FIXED", "value": 40000}
            ],
        },
    )
    assert structure.status_code == 200, structure.text
    structure_id = structure.json()["data"]["id"]

    emp = client.post(
        "/api/v1/employees/",
        headers=H,
        json={
            "employee_code": "E001",
            "first_name": "Alice",
            "last_name": "Doe",
            "department_id": dept_id,
            "employment_type": "FULL_TIME",
            "salary": {
                "effective_from": "2024-01-01",
                "salary_structure_id": structure_id,
                "gross_salary": 50000,
                "basic_salary": 40000,
            },
        },
    )
    assert emp.status_code == 200, emp.text
    emp_id = emp.json()["data"]["id"]

    salary = client.get(f"/api/v1/employees/{emp_id}/salary", headers=H)
    assert salary.status_code == 200
    history = salary.json()["data"]
    assert history and history[0]["gross_salary"] == 50000


def test_payroll_workflow_api(client, company):
    H = company["headers"]
    structure = client.post(
        "/api/v1/salary/structures",
        headers=H,
        json={
            "name": "Standard",
            "code": "STD",
            "payment_frequency": "MONTHLY",
            "monthly_gross": 50000,
            "components": [
                {"name": "Basic", "component_type": "EARNING", "calculation_type": "FIXED", "value": 40000},
                {"name": "HRA", "component_type": "EARNING", "calculation_type": "PERCENTAGE_OF_BASIC", "value": 0.5},
            ],
        },
    )
    structure_id = structure.json()["data"]["id"]
    client.post(
        "/api/v1/employees/",
        headers=H,
        json={
            "employee_code": "P001",
            "first_name": "Bob",
            "employment_type": "FULL_TIME",
            "salary": {
                "effective_from": "2024-01-01",
                "salary_structure_id": structure_id,
                "gross_salary": 50000,
                "basic_salary": 40000,
            },
        },
    )

    period = client.post("/api/v1/payroll/periods", headers=H, json={"month": 1, "year": 2024})
    assert period.status_code == 200, period.text
    period_id = period.json()["data"]["id"]

    dup = client.post("/api/v1/payroll/periods", headers=H, json={"month": 1, "year": 2024})
    assert dup.status_code == 409

    calc = client.post(f"/api/v1/payroll/periods/{period_id}/calculate", headers=H)
    assert calc.status_code == 200, calc.text
    assert calc.json()["data"]["employees_processed"] == 1

    rev = client.post(f"/api/v1/payroll/periods/{period_id}/review", headers=H)
    assert rev.json()["data"]["status"] == "REVIEW"

    appr = client.post(f"/api/v1/payroll/periods/{period_id}/approve", headers=H)
    assert appr.json()["data"]["status"] == "APPROVED"

    lock = client.post(f"/api/v1/payroll/periods/{period_id}/lock", headers=H)
    assert lock.json()["data"]["status"] == "LOCKED"

    records = client.get(f"/api/v1/payroll/periods/{period_id}/records", headers=H)
    items = records.json()["data"]
    assert len(items) == 1
    assert items[0]["net_salary"] > 0
