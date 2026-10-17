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
    _probe(db, request, "cdata", sn=serial, body=body)
    device = _device_for_serial(db, serial)
    if device is None:
        logger.warning("iclock push from unknown device SN=%s", serial)
        return PlainTextResponse("Error: device not registered", status_code=403)

    company_id = str(device.company_id)
    company_tz = get_zone(_company_timezone(db, company_id))

    inserted = duplicates = failed = 0
    last_type: dict[str, Optional[EventType]] = {}
    for record in records:
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
        "iclock push SN=%s: received=%d inserted=%d dup=%d failed=%d",
        serial,
        len(records),
        inserted,
        duplicates,
        failed,
    )
    return PlainTextResponse("OK")


@router.api_route("/iclock/getrequest", methods=["GET", "POST"], include_in_schema=False)
@router.api_route("/iclock/getrequest.aspx", methods=["GET", "POST"], include_in_schema=False)
def iclock_getrequest(request: Request, db: Session = Depends(get_db)):
    """Command channel probe. Empty response = no pending commands for the device.

    eSSL Orcus firmware calls ``/iclock/getrequest.aspx?SN=...`` every ~30s.
    We must return an EMPTY body (not "OK") or the device treats it as a
    pending command and may stall its punch upload.
    """
    sn = request.query_params.get("SN") or request.query_params.get("sn")
    _probe(db, request, "getrequest", sn=sn)
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