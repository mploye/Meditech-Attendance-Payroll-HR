def _create_shift(client, headers, name):
    r = client.post(
        "/api/v1/shifts/",
        headers=headers,
        json={"name": name, "start_time": "09:00", "end_time": "18:00"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _create_employee(client, headers, code):
    r = client.post(
        "/api/v1/employees/",
        headers=headers,
        json={
            "employee_code": code,
            "first_name": f"Emp {code}",
            "last_name": "Test",
            "status": "ACTIVE",
            "employment_type": "FULL_TIME",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_assign_list_and_unassign_employees(client, company):
    headers = company["headers"]
    shift = _create_shift(client, headers, "Morning")
    e1 = _create_employee(client, headers, "E101")
    e2 = _create_employee(client, headers, "E102")

    r = client.post(
        f"/api/v1/shifts/{shift['id']}/assign",
        headers=headers,
        json={"employee_ids": [e1["id"], e2["id"]], "effective_from": "2026-10-01"},
    )
    assert r.status_code == 200, r.text
    assert set(r.json()["data"]["assigned"]) == {e1["id"], e2["id"]}

    rows = client.get(f"/api/v1/shifts/{shift['id']}/assignments", headers=headers).json()["data"]
    assert {row["employee_code"] for row in rows} == {"E101", "E102"}
    assert all(row["effective_from"] == "2026-10-01" for row in rows)
    assert all(row["employee_name"] for row in rows)

    client.post(
        f"/api/v1/shifts/{shift['id']}/assign",
        headers=headers,
        json={"employee_ids": [e1["id"], e1["id"]], "effective_from": "2026-10-05"},
    )
    rows = client.get(f"/api/v1/shifts/{shift['id']}/assignments", headers=headers).json()["data"]
    assert len(rows) == 2
    assert next(row for row in rows if row["employee_code"] == "E101")["effective_from"] == "2026-10-05"

    target = next(row for row in rows if row["employee_code"] == "E102")
    removed = client.delete(
        f"/api/v1/shifts/{shift['id']}/assignments/{target['id']}", headers=headers
    )
    assert removed.status_code == 200, removed.text
    rows = client.get(f"/api/v1/shifts/{shift['id']}/assignments", headers=headers).json()["data"]
    assert [row["employee_code"] for row in rows] == ["E101"]


def test_reassign_closes_previous_assignment(client, company):
    headers = company["headers"]
    shift_a = _create_shift(client, headers, "Shift A")
    shift_b = _create_shift(client, headers, "Shift B")
    emp = _create_employee(client, headers, "E201")

    first = client.post(
        f"/api/v1/shifts/{shift_a['id']}/assign",
        headers=headers,
        json={"employee_ids": [emp["id"]]},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/shifts/{shift_b['id']}/assign",
        headers=headers,
        json={"employee_ids": [emp["id"]], "effective_from": "2026-10-10"},
    )
    assert second.status_code == 200, second.text

    old_rows = client.get(f"/api/v1/shifts/{shift_a['id']}/assignments", headers=headers).json()["data"]
    assert len(old_rows) == 1
    assert old_rows[0]["effective_to"] is not None

    new_rows = client.get(f"/api/v1/shifts/{shift_b['id']}/assignments", headers=headers).json()["data"]
    assert len(new_rows) == 1
    assert new_rows[0]["effective_to"] is None


def test_assign_requires_employee_ids(client, company):
    headers = company["headers"]
    shift = _create_shift(client, headers, "Empty")

    r = client.post(f"/api/v1/shifts/{shift['id']}/assign", headers=headers, json={"employee_ids": []})
    assert r.status_code == 422, r.text
