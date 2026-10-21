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


def test_getrequest_returns_queued_command(client, env):
    from api.v1.endpoints.iclock import queue_command

    queue_command("ORCUS123", "DATA QUERY USERINFO")
    r = client.get("/iclock/getrequest.aspx?SN=ORCUS123")
    assert r.status_code == 200
    assert "DATA QUERY USERINFO" in r.text
    assert r.text.startswith("C:")
    # command is consumed once
    assert client.get("/iclock/getrequest.aspx?SN=ORCUS123").text == ""


def test_userinfo_creates_employee_and_mapping(client, env, db):
    from sqlalchemy import select

    from models.employee import Employee
    from models.employee_device import EmployeeDevice

    r = client.post(
        "/iclock/cdata.aspx?SN=ORCUS123&table=USERINFO",
        content="PIN=7\tName=Jane Doe\tPri=0\tGrp=1",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 200
    emp = db.scalar(select(Employee).where(Employee.employee_code == "E7"))
    assert emp is not None
    assert emp.first_name == "Jane"
    mapping = db.scalar(select(EmployeeDevice).where(EmployeeDevice.device_user_id == "7"))
    assert mapping is not None
    assert str(mapping.employee_id) == str(emp.id)


def test_attlog_pin_alias_ingested(client, env, db):
    from models.attendance import AttendanceLog

    r = client.post(
        "/iclock/cdata.aspx?SN=ORCUS123&table=ATTLOG",
        content="PIN=A001\tDateTime=2026-10-12 09:00:00\tStatus=0",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 200
    logs = list(db.scalars(select(AttendanceLog)))
    assert len(logs) == 1
    assert logs[0].device_user_id == "A001"
    assert logs[0].event_type == EventType.IN


def test_biodata_user_lines_create_employees(client, env, db):
    from sqlalchemy import select

    from models.employee import Employee
    from models.employee_device import EmployeeDevice

    body = (
        "BIODATA Pin=1\tNo=0\tIndex=0\tValid=1\tType=9\tTmp=AAAA\n"
        "USER PIN=1\tName=DEEPAK.K\tPri=14\tGrp=1\tVerify=-1\n"
        "USER PIN=2\tName=SAKTHIVEL\tPri=0\tGrp=1\tVerify=0\n"
    )
    r = client.post(
        "/iclock/cdata.aspx?SN=ORCUS123&table=BIODATA",
        content=body,
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 200
    emp1 = db.scalar(select(Employee).where(Employee.employee_code == "E1"))
    emp2 = db.scalar(select(Employee).where(Employee.employee_code == "E2"))
    assert emp1 is not None and emp1.first_name == "DEEPAK.K"
    assert emp2 is not None and emp2.first_name == "SAKTHIVEL"
    pins = set(db.scalars(select(EmployeeDevice.device_user_id)))
    assert {"1", "2"} <= pins


def test_cdata_get_returns_option_block(client):
    r = client.get(
        "/iclock/cdata.aspx?SN=ORCUS123&options=all&pushver=2.4.1&DeviceType=att"
    )
    assert r.status_code == 200
    assert r.text.startswith("GET OPTION FROM: ORCUS123")
    assert "Realtime=1" in r.text
    assert "Stamp=0" in r.text
    assert "OpStamp=0" in r.text


def test_option_response_forces_full_resend_by_default():
    from api.v1.endpoints.iclock import _option_response

    text = _option_response("ORCUS123")
    assert "Stamp=0" in text
    assert "OpStamp=0" in text


def test_resync_command_is_queued_for_serial():
    from api.v1.endpoints.iclock import _pop_command, queue_command

    queue_command("ORCUS123", "DATA UPDATE ATTLOG")
    assert _pop_command("ORCUS123") == "DATA UPDATE ATTLOG"
    assert _pop_command("ORCUS123") is None


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