import pytest

from sqlalchemy import func, select

from models.attendance import AttendanceLog
from models.device import Device
from models.employee_device import EmployeeDevice
from models.enums import DeviceProvider, DeviceStatus, DeviceType, EventType


@pytest.fixture()
def env(client, db):
    from tests.conftest import make_company, make_employee

    company = make_company(db)
    emp = make_employee(db, str(company.id), code="A001")
    device = Device(
        company_id=str(company.id),
        name="Orcus Lobby",
        model="AiFace-Orcus",
        serial_number="ORCUS123",
        device_type=DeviceType.FACE_PUNCH,
        ip_address="192.168.1.50",
        port=4370,
        protocol="http",
        provider=DeviceProvider.ESSL,
        status=DeviceStatus.OFFLINE,
    )
    db.add(device)
    db.flush()
    db.add(
        EmployeeDevice(
            company_id=str(company.id),
            employee_id=str(emp.id),
            device_id=str(device.id),
            device_user_id="A001",
        )
    )
    db.commit()
    return {"company": company, "employee": emp, "device": device}


def _push(client, body, sn="ORCUS123"):
    return client.post(
        f"/iclock/cdata?SN={sn}",
        content=body,
        headers={"Content-Type": "text/plain"},
    )


def test_cdata_inserts_log_for_mapped_employee(client, env, db):
    r = _push(client, "USERID=A001\tCHECKTIME=2026-10-12 09:00:00\tCHECKTYPE=I")
    assert r.status_code == 200
    assert r.text == "OK"

    logs = list(db.scalars(select(AttendanceLog)))
    assert len(logs) == 1
    log = logs[0]
    assert log.device_user_id == "A001"
    assert log.event_type == EventType.IN
    assert str(log.employee_id) == str(env["employee"].id)
    assert str(log.device_id) == str(env["device"].id)

    db.refresh(env["device"])
    assert env["device"].status == DeviceStatus.ONLINE


def test_cdata_aspx_path_accepted(client, env, db):
    r = client.post(
        "/iclock/cdata.aspx?SN=ORCUS123",
        content="USERID=A001\tCHECKTIME=2026-10-12 09:00:00\tCHECKTYPE=I",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 200
    assert r.text == "OK"
    assert db.scalar(select(func.count(AttendanceLog.id))) == 1


def test_getrequest_aspx_returns_empty(client):
    r = client.get("/iclock/getrequest.aspx?SN=ORCUS123")
    assert r.status_code == 200
    assert r.text == ""


def test_cdata_unknown_device_rejected(client):
    r = _push(client, "USERID=A001\tCHECKTIME=2026-10-12 09:00:00\tCHECKTYPE=I", sn="UNKNOWN999")
    assert r.status_code == 403


def test_cdata_duplicates_are_deduped(client, env, db):
    body = "USERID=A001\tCHECKTIME=2026-10-12 09:00:00\tCHECKTYPE=I"
    assert _push(client, body).status_code == 200
    assert _push(client, body).status_code == 200

    count = db.scalar(select(func.count(AttendanceLog.id)))
    assert count == 1


def test_cdata_positional_legacy_format(client, env, db):
    r = _push(client, "A001\t2026-10-12 09:00:00\tI")
    assert r.status_code == 200

    logs = list(db.scalars(select(AttendanceLog)))
    assert len(logs) == 1
    assert logs[0].event_type == EventType.IN


def test_cdata_infers_alternating_types(client, env, db):
    body = "\n".join(
        [
            "USERID=A001\tTIME=2026-10-12 09:00:00",
            "USERID=A001\tTIME=2026-10-12 10:10:00",
        ]
    )
    assert _push(client, body).status_code == 200

    logs = list(db.scalars(select(AttendanceLog).order_by(AttendanceLog.event_timestamp)))
    assert len(logs) == 2
    assert [l.event_type for l in logs] == [EventType.IN, EventType.OUT]


def test_handshake_endpoints_respond(client):
    assert client.get("/iclock/getrequest?SN=ORCUS123").status_code == 200
    assert client.post("/iclock/request", content="x").status_code == 200
    assert client.get("/iclock/request?SN=ORCUS123").status_code == 200
    assert client.post("/iclock/devicecmd", content="x").status_code == 200