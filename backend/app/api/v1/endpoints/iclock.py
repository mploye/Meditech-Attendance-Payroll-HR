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
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from core.database import SessionLocal
from core.timezone import get_zone
from models.audit import AuditLog
from models.device import Device
from models.device_command import DeviceCommand
from models.enums import DeviceStatus, EventType, LogSource
from services import attendance_service

logger = logging.getLogger(__name__)

router = APIRouter()

# --- ADMS server->device command queue (persistent, DB-backed) --------------
# The device polls /iclock/getrequest continuously; to pull data we store a
# command for its serial and hand it back on the next poll. The queue lives in
# the DB (device_commands) rather than process memory so a command survives
# worker restarts / multiple Render instances, guaranteeing delivery.
#
# Attendance re-upload command. Sent whenever the server wants the device to
# re-push its stored attendance log (e.g. the device cursor drifted to the
# "9999 already-synced" sentinel and stopped uploading).
ATTLOG_REUPLOAD_CMD = "DATA UPDATE ATTLOG"
# How long the device may go without pushing punch data before we ask again.
# The terminal polls getrequest every ~5s, so 15s keeps delivery within
# ~5-20s while still bounding how often a full re-upload is requested.
ATTLOG_REUPLOAD_INTERVAL_SEC = 15
# A device that has not polled for this long is treated as offline.
DEVICE_OFFLINE_AFTER_SEC = 180
# Serialises immediate attendance recomputation so concurrent pushes from
# multiple devices cannot race on the same daily rows.
_PROCESS_LOCK = threading.Lock()


def queue_command(sn: str, command: str, company_id: Optional[str] = None) -> None:
    """Persist a pending server->device command for the given serial number.

    De-duplicates only against a command that is still "in flight" (undelivered,
    or delivered within the last few minutes). An old delivered-but-never-
    confirmed command does NOT block a fresh one, so the recurring refresh job
    keeps prodding a device that drops an acknowledgement.
    """
    sn = (sn or "").strip()
    if not sn or not command:
        return
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        existing = db.scalar(
            select(DeviceCommand).where(
                DeviceCommand.serial_number == sn,
                DeviceCommand.command == command,
                DeviceCommand.confirmed.is_(False),
                (DeviceCommand.delivered.is_(False)) | (DeviceCommand.delivered_at >= cutoff),
            )
        )
        if existing is not None:
            return
        db.add(DeviceCommand(serial_number=sn, command=command, company_id=company_id))
        db.commit()
    finally:
        db.close()


def _pop_command(db: Session, sn: str) -> Optional[str]:
    """Return the oldest undelivered command for this serial, marking it sent."""
    if not sn:
        return None
    cmd = db.scalar(
        select(DeviceCommand)
        .where(
            DeviceCommand.serial_number == sn,
            DeviceCommand.delivered.is_(False),
        )
        .order_by(DeviceCommand.created_at)
    )
    if cmd is None:
        return None
    cmd.delivered = True
    cmd.delivered_at = datetime.now(timezone.utc)
    cmd.attempts = (cmd.attempts or 0) + 1
    db.commit()
    return cmd.command


def _confirm_commands(db: Session, sn: str) -> None:
    """Mark all delivered-but-unconfirmed commands for this serial as confirmed."""
    if not sn:
        return
    for cmd in db.scalars(
        select(DeviceCommand).where(
            DeviceCommand.serial_number == sn,
            DeviceCommand.confirmed.is_(False),
        )
    ):
        cmd.confirmed = True
    db.commit()


def _last_attlog_at(db: Session, sn: str) -> Optional[datetime]:
    """Latest ATTLOG punch-push time for a serial, from the iclock probe trail.

    Probes are stored in audit_logs with new_value['endpoint'] == 'cdata:ATTLOG'.
    """
    rows = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.action == "iclock_probe",
            AuditLog.entity_type == "iclock",
            AuditLog.created_at >= datetime.now(timezone.utc) - timedelta(hours=6),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    )
    for row in rows:
        value = row.new_value
        if isinstance(value, str):
            try:
                import json

                value = json.loads(value)
            except Exception:
                continue
        if not isinstance(value, dict):
            continue
        if value.get("endpoint") == "cdata:ATTLOG" and (not sn or value.get("sn") == sn):
            return row.created_at
    return None


def _cmd_counter() -> int:
    """Monotonic-ish command id for the ``C:<id>:<cmd>`` reply envelope."""
    return int(datetime.now(timezone.utc).timestamp())


_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def _parse_device_info(info: str) -> dict:
    """Best-effort parse of the ``INFO=`` blob on ``/iclock/getrequest``.

    Observed on the AiFace-Orcus:
    ``ZAM70-NF24HE-Ver3.8.4,12,13,2093,192.168.1.36,10,40,...``
    Field meanings vary by firmware, so only fields we can identify safely are
    extracted; the raw string is kept for diagnostics.
    """
    text = (info or "").strip()
    if not text:
        return {}
    parts = [part.strip() for part in text.split(",")]
    result: dict = {"raw": text, "fields": parts}
    for part in parts:
        if _IPV4_RE.match(part):
            result["ip"] = part
            break
    return result


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _request_attlog_if_stale(db: Session, device: "Device") -> None:
    """Ask a polling device to upload attendance when it has gone quiet.

    Called on every ``getrequest`` (the terminal polls every ~5s). The
    in-flight guard means we only send one command at a time, so this does not
    flood the device; a full re-upload is therefore requested at most once per
    ATTLOG_REUPLOAD_INTERVAL_SEC. This replaces the old 60-second background
    delay and normally delivers punches within ~5-20 seconds.
    """
    now = datetime.now(timezone.utc)
    last_push = _aware(device.last_punch_at)
    if last_push is not None and (now - last_push).total_seconds() <= ATTLOG_REUPLOAD_INTERVAL_SEC:
        return

    cutoff = now - timedelta(minutes=2)
    in_flight = db.scalar(
        select(DeviceCommand.id).where(
            DeviceCommand.serial_number == device.serial_number,
            DeviceCommand.confirmed.is_(False),
            (DeviceCommand.delivered.is_(False)) | (DeviceCommand.delivered_at >= cutoff),
        )
    )
    if in_flight is not None:
        return

    queue_command(
        device.serial_number,
        ATTLOG_REUPLOAD_CMD,
        company_id=str(device.company_id),
    )


def _device_zone(device: "Device", company_tz: str):
    """Timezone the device's wall-clock timestamps are expressed in."""
    return get_zone(device.timezone or company_tz)


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


def _option_response(sn: str, stamp: str = "0", op_stamp: str = "0") -> str:
    """ZKTeco/eSSL ADMS registration/config handshake reply.

    The device calls ``GET /iclock/cdata.aspx?SN=...&options=all&pushver=...``
    on connect. It will NOT upload punches until it receives a ``GET OPTION
    FROM: <sn>`` block. ``Realtime=1`` enables instant push; the ``Trans*``
    values make it report attendance immediately.

    ``Stamp``/``OpStamp`` are the server's acknowledged cursors. Returning a
    value LOWER than the device's own cursor forces it to re-upload records
    after that point; returning ``0`` requests a full resend. We default to 0
    so a device that has drifted to the ``9999`` "synced" sentinel re-pushes
    its whole attendance log on the next handshake.
    """
    lines = [
        f"GET OPTION FROM: {sn}",
        f"Stamp={stamp}",
        f"OpStamp={op_stamp}",
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
    """ADMS registration handshake: reply with the device config block.

    Every handshake also (re)queues an attendance re-upload unless an ATTLOG
    push arrived very recently. This self-heals devices whose cursor has drifted
    to the "9999 already-synced" sentinel and silently stopped uploading.
    """
    params = request.query_params
    sn = params.get("SN") or params.get("sn") or ""
    _probe(db, request, "cdata-options", sn=sn)

    device = _device_for_serial(db, sn)
    if device is not None:
        device.last_seen_at = datetime.now(timezone.utc)
        device.status = DeviceStatus.ONLINE
        db.commit()

    last_push = _aware(device.last_punch_at) if device is not None else None
    if last_push is None:
        last_push = _last_attlog_at(db, sn)
    stale = last_push is None or (datetime.now(timezone.utc) - last_push).total_seconds() > ATTLOG_REUPLOAD_INTERVAL_SEC
    has_pending = db.scalar(
        select(DeviceCommand.id).where(
            DeviceCommand.serial_number == sn,
            DeviceCommand.confirmed.is_(False),
        )
    )
    if sn and stale and has_pending is None:
        queue_command(sn, ATTLOG_REUPLOAD_CMD, company_id=str(device.company_id) if device else None)

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
    company_tz_name = _company_timezone(db, company_id)
    device_tz = _device_zone(device, company_tz_name)

    inserted = duplicates = failed = 0
    newest_device_ts: Optional[datetime] = None
    last_type: dict[str, Optional[EventType]] = {}
    for record in punch_records:
        device_user_id = str(record.get("USERID") or "").strip()
        time_value = record.get("CHECKTIME") or record.get("TIME") or record.get("DATETIME")
        naive_ts = _parse_timestamp(time_value) if time_value else None
        if not device_user_id or naive_ts is None:
            failed += 1
            continue
        if newest_device_ts is None or naive_ts > newest_device_ts:
            newest_device_ts = naive_ts

        event_type = _record_event_type(record)
        if event_type is None:
            prev = last_type.get(device_user_id)
            event_type = EventType.OUT if prev == EventType.IN else EventType.IN
        last_type[device_user_id] = event_type

        aware_ts = naive_ts.replace(tzinfo=device_tz).astimezone(timezone.utc)
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

    now = datetime.now(timezone.utc)
    device.last_seen_at = now
    device.status = DeviceStatus.ONLINE
    if newest_device_ts is not None:
        device.last_punch_at = now
        # Device clock vs company-local wall clock: a large gap silently shifts
        # every punch and corrupts payroll, so record it for the UI to surface.
        # Only a real-time push gives a usable clock reading. Bulk re-uploads
        # of older logs would otherwise look like hours of drift.
        local_now = now.astimezone(device_tz).replace(tzinfo=None)
        gap_minutes = int(round((newest_device_ts - local_now).total_seconds() / 60))
        if abs(gap_minutes) <= 15:
            device.clock_drift_minutes = gap_minutes
    db.commit()
    if serial:
        _confirm_commands(db, serial)
    logger.info(
        "iclock push SN=%s: received=%d inserted=%d dup=%d failed=%d users=%d drift=%s min",
        serial,
        len(punch_records),
        inserted,
        duplicates,
        failed,
        len(user_records),
        device.clock_drift_minutes,
    )
    if inserted:
        _process_company_today(company_id)
    return PlainTextResponse("OK")


def _process_company_today(company_id: str) -> None:
    """Recompute today's attendance rows right after punches arrive."""
    if not _PROCESS_LOCK.acquire(blocking=False):
        return
    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).astimezone(get_zone(_company_timezone(db, company_id))).date()
        attendance_service.process_range(db, company_id, today, today)
        logger.info("Immediate attendance processing for company %s (%s) done", company_id, today)
    except Exception:
        logger.exception("Immediate attendance processing failed for company %s", company_id)
    finally:
        db.close()
        _PROCESS_LOCK.release()


@router.api_route("/iclock/getrequest", methods=["GET", "POST"], include_in_schema=False)
@router.api_route("/iclock/getrequest.aspx", methods=["GET", "POST"], include_in_schema=False)
def iclock_getrequest(request: Request, db: Session = Depends(get_db)):
    """Command channel probe and fast attendance trigger.

    The terminal polls this endpoint every ~5s. Besides returning any queued
    command, the poll doubles as a heartbeat: when the device has not pushed
    punch data for ATTLOG_REUPLOAD_INTERVAL_SEC we ask it to upload now. That
    removes the old 60-second background lag, so punches normally reach the
    portal within ~5-20 seconds.
    """
    params = request.query_params
    sn = params.get("SN") or params.get("sn")
    info = _parse_device_info(params.get("INFO") or params.get("info") or "")

    device = _device_for_serial(db, sn) if sn else None
    if device is not None:
        device.last_seen_at = datetime.now(timezone.utc)
        device.status = DeviceStatus.ONLINE
        if info.get("ip"):
            device.ip_address = info["ip"]
        db.commit()
        _request_attlog_if_stale(db, device)

    command = _pop_command(db, sn) if sn else None
    _probe(db, request, "getrequest", sn=sn, body=command or info.get("raw", ""))
    if command:
        return PlainTextResponse(f"C:{_cmd_counter()}:{command}")
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
@router.post("/iclock/devicecmd.aspx", include_in_schema=False)
async def iclock_devicecmd(request: Request, db: Session = Depends(get_db)):
    """Device confirms it executed a command; acknowledge and clear the queue."""
    body = (await request.body()).decode("utf-8", errors="ignore")
    _probe(db, request, "devicecmd", body=body)
    # The serial may be in the query string OR in the confirmation body
    # (e.g. "SN=RAG...&CMD=DATA UPDATE ATTLOG"). Resolve it from either.
    sn = request.query_params.get("SN") or request.query_params.get("sn")
    if not sn and body:
        for token in body.replace("\r", "").replace("\n", "&").split("&"):
            if token.upper().startswith("SN="):
                sn = token.partition("=")[2].strip()
                break
    if sn:
        _confirm_commands(db, sn)
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