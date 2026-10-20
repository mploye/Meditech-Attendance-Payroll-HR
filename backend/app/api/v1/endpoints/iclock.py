"""Inbound eSSL/ZKTeco ADMS push receiver.

eSSL devices (AiFace-Orcus, etc.) can only hold ONE cloud/ADMS server address.
Point that address at this FastAPI app (e.g. https://hrms-api-4trx.onrender.com)
and the device will POST every punch to ``/iclock/cdata`` over HTTPS. The device
talks the ZKTeco ``/iclock`` protocol family, so the handshake endpoints are
implemented as well. No API header is possible from the device menu; the device
serial (``SN``) is verified against registered entries instead.

Punch lines arrive as newline/TAB separated ``KEY=VALUE`` records (e.g.
``USERID=101\tCHECKTIME=2026-10-12 09:00:00\tCHECKTYPE=I``). Both the tabular
eSSL format and the legacy positional ZKTeco ATTLOG format are accepted.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from core.timezone import get_zone
from models.audit import AuditLog
from models.device import Device
from models.enums import DeviceStatus, EventType, LogSource
from services import attendance_service

logger = logging.getLogger(__name__)

router = APIRouter()

# --- ADMS server->device command queue -------------------------------------
# The device polls /iclock/getrequest continuously; to pull data we queue a
# command for its serial and hand it back on the next poll. Single worker
# deployment (WEB_CONCURRENCY=1), so a process-local queue is sufficient.
_cmd_lock = threading.Lock()
_cmd_queue: dict[str, list[str]] = {}
_cmd_counter = {"n": 0}


def queue_command(sn: str, command: str) -> None:
    sn = (sn or "").strip()
    if not sn:
        return
    with _cmd_lock:
        _cmd_queue.setdefault(sn, []).append(command)


def _pop_command(sn: str) -> Optional[str]:
    with _cmd_lock:
        queue = _cmd_queue.get(sn)
        if queue:
            return queue.pop(0)
    return None


def _next_cmd_id() -> int:
    with _cmd_lock:
        _cmd_counter["n"] += 1
        return _cmd_counter["n"]



def _probe(db: Session, request: Request, endpoint: str, sn=None, body=""):
    """Persist every /iclock hit so we can see device connectivity in the DB.

    Render's log API only surfaces build/startup logs, so we record probes to
    the (already existing) audit_logs table instead. This catches hits from
    unknown serials too, which is how we diagnose a device pushing with the
    wrong SN.
    """
    try:
        client = request.client.host if request.client else None
        db.add(
            AuditLog(
                action="iclock_probe",
                entity_type="iclock",
                new_value={
                    "endpoint": endpoint,
                    "sn": sn,
                    "method": request.method,
                    "query": dict(request.query_params),
                    "client": client,
                    "body": (body or "")[:500],
                },
                ip_address=client,
                user_agent=request.headers.get("user-agent"),
            )
        )
        db.commit()
    except Exception:  # pragma: no cover - diagnostic only
        try:
            db.rollback()
        except Exception:
            pass

_CHECKTYPE_MAP = {
    "I": EventType.IN,
    "O": EventType.OUT,
    "IN": EventType.IN,
    "OUT": EventType.OUT,
    "CHECKIN": EventType.IN,
    "CHECKOUT": EventType.OUT,
    "CHECK_IN": EventType.IN,
    "CHECK_OUT": EventType.OUT,
    "PUNCHIN": EventType.IN,
    "PUNCHOUT": EventType.OUT,
    "0": EventType.IN,  # ZKTeco ATTLOG status 0 = check-in
    "1": EventType.OUT,  # ZKTeco ATTLOG status 1 = check-out
}


def _parse_timestamp(value: str):
    """Parse a device timestamp (naive local time) into a tz-aware UTC datetime."""
    text = (value or "").strip()
    if not text:
        return None
    text = text.replace("T", " ").replace("/", "-")
    if text.endswith("Z"):
        text = text[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_records(body: str) -> list[dict]:
    """Split the raw push body into KEY=VALUE record dicts."""
    records: list[dict] = []
    for line in body.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        tokens = line.split("\t")
        if len(tokens) == 1:
            tokens = line.split("&")
        record: dict[str, str] = {}
        position = 0
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if "=" in token:
                key, _, value = token.partition("=")
                record[key.strip().upper()] = value.strip()
            else:
                if position == 0:
                    record["USERID"] = token
                elif position == 1:
                    record["CHECKTIME"] = token
                elif position == 2:
                    record["CHECKTYPE"] = token
                position += 1
        if record:
            records.append(record)
    return records


def _canonical_records(records: list[dict]) -> list[dict]:
    """Normalise eSSL ADMS field names to the canonical USERID/CHECKTIME/CHECKTYPE."""
    for record in records:
        if "USERID" not in record:
            for alias in ("PIN", "USER_ID", "ENROLLID", "ENROLL_ID", "EMPID"):
                if alias in record:
                    record["USERID"] = record[alias]
                    break
        if "CHECKTIME" not in record:
            for alias in ("DATETIME", "TIME", "PUNCHTIME", "CHECK_TIME"):
                if alias in record:
                    record["CHECKTIME"] = record[alias]
                    break
        if "CHECKTYPE" not in record:
            for alias in ("STATUS", "STATE", "ATT", "VERIFY"):
                if alias in record:
                    record["CHECKTYPE"] = record[alias]
                    break
    return records


def _record_event_type(record: dict) -> Optional[EventType]:
    for key in ("CHECKTYPE", "ATT", "STATUS", "EVENT_TYPE", "TYPE", "STATE"):
        value = record.get(key)
        if value is None:
            continue
        mapped = _CHECKTYPE_MAP.get(value.strip().upper())
        if mapped is not None:
            return mapped
    return None


def _device_for_serial(db: Session, serial: str) -> Optional[Device]:
    """Find the most recently active device row for a serial number."""
    serial = (serial or "").strip()
    if not serial:
        return None
    return db.scalar(
        select(Device)
        .where(Device.serial_number == serial, Device.status != DeviceStatus.DISABLED)
        .order_by(Device.updated_at.desc())
        .limit(1)
    )


def _resolve_device_employee(db: Session, company_id: str, device_id: str, device_user_id: str) -> Optional[str]:
    from models.employee_device import EmployeeDevice

    mapping = db.scalar(
        select(EmployeeDevice).where(
            EmployeeDevice.company_id == company_id,
            EmployeeDevice.device_id == device_id,
            EmployeeDevice.device_user_id == device_user_id,
        )
    )
    return str(mapping.employee_id) if mapping is not None else None


def _split_user_and_punch(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Separate user-info records from punch records in a mixed ADMS push.

    eSSL firmware sends user info as ``USER PIN=1\tName=DEEPAK.K\tGrp=1...``
    (often embedded in a ``BIODATA`` push alongside biometric templates).
    Punch records carry a ``CHECKTIME``/``DateTime``.
    """
    users: list[dict] = []
    punches: list[dict] = []
    for record in records:
        pin = record.get("USER PIN") or record.get("PIN") or record.get("USERID")
        name = record.get("NAME") or record.get("USERNAME")
        if name and pin:
            users.append({"PIN": str(pin).strip(), "NAME": str(name).strip()})
        elif record.get("CHECKTIME") or record.get("DATETIME"):
            punches.append(record)
    return users, punches


def _create_employees_from_users(db: Session, device: Device, users: list[dict]) -> int:
    """Create employees + device mappings for users reported by the device.

    Employees are keyed by ``employee_code = E<PIN>`` (idempotent); the display
    name comes from the device's ``Name`` field.
    """
    from models.employee import Employee
    from models.employee_device import EmployeeDevice

    company_id = str(device.company_id)
    device_id = str(device.id)
    created = 0
    for user in users:
        pin = (user.get("PIN") or "").strip()
        if not pin:
            continue
        name = (user.get("NAME") or "").strip() or f"User {pin}"

        employee = db.scalar(
            select(Employee).where(
                Employee.company_id == company_id,
                Employee.employee_code == f"E{pin}",
            )
        )
        if employee is None:
            parts = name.split(" ", 1)
            employee = Employee(
                company_id=company_id,
                employee_code=f"E{pin}",
                first_name=parts[0][:100] or f"E{pin}",
                last_name=(parts[1][:100] if len(parts) > 1 else None),
            )
            db.add(employee)
            db.flush()
            created += 1

        mapping = db.scalar(
            select(EmployeeDevice).where(
                EmployeeDevice.company_id == company_id,
                EmployeeDevice.device_id == device_id,
                EmployeeDevice.device_user_id == pin,
            )
        )
        if mapping is None:
            db.add(
                EmployeeDevice(
                    company_id=company_id,
                    employee_id=str(employee.id),
                    device_id=device_id,
                    device_user_id=pin,
                )
            )
    db.commit()
    logger.info("iclock USERINFO SN=%s: users=%d new_employees=%d", device.serial_number, len(users), created)
    return created


def _option_response(sn: str) -> str:
    """ZKTeco/eSSL ADMS registration/config handshake reply.

    The device calls ``GET /iclock/cdata.aspx?SN=...&options=all&pushver=...``
    on connect. It will NOT upload punches until it receives a ``GET OPTION
    FROM: <sn>`` block. ``Realtime=1`` enables instant push; the ``Trans*``
    values make it report attendance immediately.
    """
    lines = [
        f"GET OPTION FROM: {sn}",
        "Stamp=0",
        "OpStamp=0",
        "ErrorDelay=30",
        "Delay=10",
        "TransTimes=00:00;14:05",
        "TransInterval=1",
        "TransFlag=1111000000",
        "TimeZone=5.5",
        "Realtime=1",
        "Encrypt=None",
    ]
    return "\r\n".join(lines) + "\r\n"


@router.api_route("/iclock/cdata", methods=["GET"], include_in_schema=False)
@router.api_route("/iclock/cdata.aspx", methods=["GET"], include_in_schema=False)
def iclock_cdata_options(request: Request, db: Session = Depends(get_db)):
    """ADMS registration handshake: reply with the device config block."""
    params = request.query_params
    sn = params.get("SN") or params.get("sn") or ""
    _probe(db, request, "cdata-options", sn=sn)
    return PlainTextResponse(_option_response(sn))


@router.post("/iclock/cdata", include_in_schema=False)
@router.post("/iclock/cdata.aspx", include_in_schema=False)
async def iclock_cdata(request: Request, db: Session = Depends(get_db)):
    """Receive the device's punch push stream and persist raw attendance logs.

    eSSL Orcus firmware posts to ``/iclock/cdata.aspx`` (with the ``.aspx``
    suffix); other ZKTeco firmware uses ``/iclock/cdata``. Both are accepted.
    """
    body = (await request.body()).decode("utf-8", errors="ignore")
    records = _parse_records(body)
    logger.info(
        "iclock/cdata HIT client=%s query=%s body=%r",
        request.client.host if request.client else "?",
        dict(request.query_params),
        body[:400],
    )

    params = request.query_params
    serial = params.get("SN") or params.get("sn") or params.get("serial") or (records[0].get("SN") if records else None)
    table = (params.get("table") or params.get("Table") or "").strip().upper()
    _probe(db, request, f"cdata:{table or 'ATTLOG'}", sn=serial, body=body)
    device = _device_for_serial(db, serial)
    if device is None:
        logger.warning("iclock push from unknown device SN=%s", serial)
        return PlainTextResponse("Error: device not registered", status_code=403)

    records = _canonical_records(records)

    user_records, punch_records = _split_user_and_punch(records)
    if user_records:
        _create_employees_from_users(db, device, user_records)

    company_id = str(device.company_id)
    company_tz = get_zone(_company_timezone(db, company_id))

    inserted = duplicates = failed = 0
    last_type: dict[str, Optional[EventType]] = {}
    for record in punch_records:
        device_user_id = str(record.get("USERID") or "").strip()
        time_value = record.get("CHECKTIME") or record.get("TIME") or record.get("DATETIME")
        naive_ts = _parse_timestamp(time_value) if time_value else None
        if not device_user_id or naive_ts is None:
            failed += 1
            continue

        event_type = _record_event_type(record)
        if event_type is None:
            prev = last_type.get(device_user_id)
            event_type = EventType.OUT if prev == EventType.IN else EventType.IN
        last_type[device_user_id] = event_type

        aware_ts = naive_ts.replace(tzinfo=company_tz).astimezone(timezone.utc)
        employee_id = _resolve_device_employee(db, company_id, str(device.id), device_user_id)
        if employee_id is None:
            failed += 1
            continue

        result = attendance_service.insert_raw_log(
            db,
            company_id=company_id,
            device_id=str(device.id),
            employee_id=employee_id,
            device_user_id=device_user_id,
            event_timestamp=aware_ts,
            event_type=event_type,
            source=LogSource.DEVICE,
            raw_payload=record,
        )
        if result.inserted:
            inserted += 1
        else:
            duplicates += 1

    device.last_seen_at = datetime.now(timezone.utc)
    device.status = DeviceStatus.ONLINE
    db.commit()
    logger.info(
        "iclock push SN=%s: received=%d inserted=%d dup=%d failed=%d users=%d",
        serial,
        len(punch_records),
        inserted,
        duplicates,
        failed,
        len(user_records),
    )
    return PlainTextResponse("OK")


@router.api_route("/iclock/getrequest", methods=["GET", "POST"], include_in_schema=False)
@router.api_route("/iclock/getrequest.aspx", methods=["GET", "POST"], include_in_schema=False)
def iclock_getrequest(request: Request, db: Session = Depends(get_db)):
    """Command channel probe. Empty response = no pending commands for the device.

    eSSL Orcus firmware calls ``/iclock/getrequest.aspx?SN=...`` every ~7s.
    If a server->device command is queued for this serial we return it as
    ``C:<id>:<command>``; otherwise an EMPTY body means "nothing to do".
    """
    sn = request.query_params.get("SN") or request.query_params.get("sn")
    command = _pop_command(sn) if sn else None
    _probe(db, request, "getrequest", sn=sn, body=command or "")
    if command:
        return PlainTextResponse(f"C:{_next_cmd_id()}:{command}")
    return PlainTextResponse("")


@router.post("/iclock/request", include_in_schema=False)
def iclock_request(request: Request, db: Session = Depends(get_db)):
    """Device posts its status here; acknowledge."""
    _probe(db, request, "request")
    return PlainTextResponse("OK")


@router.get("/iclock/request", include_in_schema=False)
def iclock_request_get(request: Request, db: Session = Depends(get_db)):
    _probe(db, request, "request")
    return PlainTextResponse("OK")


@router.post("/iclock/devicecmd", include_in_schema=False)
def iclock_devicecmd(request: Request, db: Session = Depends(get_db)):
    """Device confirms it executed a command; acknowledge."""
    _probe(db, request, "devicecmd")
    return PlainTextResponse("OK")


@router.api_route("/iclock/{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def iclock_catchall(rest: str, request: Request, db: Session = Depends(get_db)):
    """Diagnostic catch-all: record any /iclock path we didn't implement, ack with OK."""
    body = ""
    if request.method == "POST":
        body = (await request.body()).decode("utf-8", errors="ignore")
    _probe(db, request, f"catchall:{rest}", body=body)
    return PlainTextResponse("OK")



def _company_timezone(db: Session, company_id: str) -> str:
    from core.config import settings
    from models.company import Company

    tz = db.scalar(select(Company.timezone).where(Company.id == company_id))
    return tz or settings.DEFAULT_TIMEZONE