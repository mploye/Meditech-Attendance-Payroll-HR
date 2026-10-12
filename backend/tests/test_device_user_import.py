import io

from services import device_user_import


def test_device_user_import_parses_etimetracklite_csv(db, company, client):
    # prepare device
    from models.device import Device
    dev = Device(company_id=company["company_id"], name="Orcus", serial_number="RAG-TEST-123", device_type="FACE_PUNCH", provider="ESSL")
    db.add(dev)
    db.commit()
    db.refresh(dev)

    csv_text = "SNo,User ID,Bio User ID,User Name,Department,Designation,Gender,Join Date,Mobile,Email,Is Manager\n" \
               "1,1001,1001,John Doe,IT,Engineer,M,01/01/2024,9999999999,john.doe@test.com,No\n" \
               "2,1002,1002,Jane Smith,HR,Manager,F,15/02/2024,8888888888,jane.smith@test.com,No\n"
    content = csv_text.encode("utf-8")

    res = device_user_import.import_device_users(db, company["company_id"], str(dev.id), content, create_accounts=False)
    assert res["created"] == 2
    assert res["mapped"] == 2
    assert len(res["errors"]) == 0

    # via API
    with io.BytesIO(content) as f:
        r = client.post(
            "/api/v1/imports/device-users",
            data={
                "device_id": str(dev.id),
                "create_accounts": "false",
            },
            files={"file": ("users.csv", f, "text/csv")},
            headers=company["headers"],
        )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["mapped"] == 2

    r2 = client.get(f"/api/v1/imports/device-users/{dev.id}", headers=company["headers"])
    assert r2.status_code == 200, r2.text
    assert len(r2.json()["data"]) == 2
