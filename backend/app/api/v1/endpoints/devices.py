from fastapi import APIRouter, Depends

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.attendance import AttendanceLog, DeviceSyncLog
from models.device import Device
from models.enums import DeviceStatus
from models.user import User
from services import device_service, sync_service

router = APIRouter()


def _get_device(db, cid: str, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None or str(device.company_id) != cid:
        raise NotFoundError("Device")
    return device


@router.get("/")
def list_devices(
    search: str | None = None,
    status: str | None = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "devices.view")
    cid = resolve_company_id(user)
    dev_status = DeviceStatus(status) if status else None
    devices = device_service.list_devices(db, cid, search, dev_status)

    from datetime import timezone
    from zoneinfo import ZoneInfo

    from sqlalchemy import func, select

    clocks = dict(
        db.execute(
            select(AttendanceLog.device_id, func.max(AttendanceLog.event_timestamp))
            .where(AttendanceLog.company_id == cid)
            .group_by(AttendanceLog.device_id)
        ).all()
    )

    data = []
    for device in devices:
        item = orm_to_dict(device)
        last = clocks.get(device.id)
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            try:
                tz = ZoneInfo(device.timezone or "Asia/Kolkata")
            except Exception:
                tz = timezone.utc
            item["last_punch_clock"] = last.astimezone(tz).isoformat()
        else:
            item["last_punch_clock"] = None
        # A drift reading is only meaningful right after a real-time punch.
        last_punch = device.last_punch_at
        if last_punch is None or (datetime.now(timezone.utc) - last_punch).total_seconds() > 1800:
            item["clock_drift_minutes"] = None
        data.append(item)
    return success_response(data)


@router.post("/")
def create_device(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.create")
    cid = resolve_company_id(user)
    device = device_service.create_device(db, cid, body)
    return success_response(orm_to_dict(device))


@router.get("/{device_id}")
def get_device(device_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.view")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(_get_device(db, cid, device_id)))


@router.patch("/{device_id}")
def update_device(device_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.edit")
    cid = resolve_company_id(user)
    device = _get_device(db, cid, device_id)
    allowed = {"name", "model", "serial_number", "device_type", "location", "ip_address", "port", "protocol", "provider", "status"}
    for key, value in body.items():
        if key in allowed:
            if key == "device_type" and isinstance(value, str):
                from models.enums import DeviceType

                value = DeviceType(value)
            if key == "provider" and isinstance(value, str):
                from models.enums import DeviceProvider

                value = DeviceProvider(value)
            if key == "status" and isinstance(value, str):
                value = DeviceStatus(value)
            setattr(device, key, value)
    db.commit()
    db.refresh(device)
    return success_response(orm_to_dict(device))


@router.delete("/{device_id}")
def delete_device(device_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.delete")
    cid = resolve_company_id(user)
    device = _get_device(db, cid, device_id)
    device.status = DeviceStatus.DISABLED
    db.commit()
    return success_response({"deleted": True})


@router.post("/{device_id}/test")
def test_connection(device_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.test")
    cid = resolve_company_id(user)
    device = _get_device(db, cid, device_id)
    return success_response(device_service.test_device_connection(db, device))


@router.post("/{device_id}/sync")
def sync_now(device_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.sync")
    cid = resolve_company_id(user)
    device = _get_device(db, cid, device_id)
    result = device_service.sync_device_now(db, device)
    db.commit()
    return success_response(result)


@router.post("/{device_id}/pull-data")
def pull_data(device_id: str, body: dict | None = None, user: User = Depends(get_current_user), db=Depends(get_db)):
    """Queue ADMS data-query commands so a connected device uploads its data.

    The device polls /iclock/getrequest and executes queued commands, then
    POSTs the results to /iclock/cdata. Used to fetch enrolled users and
    historical attendance (e.g. a full month) without local CSV exports.
    """
    ensure_perm(user, "devices.sync")
    cid = resolve_company_id(user)
    device = _get_device(db, cid, device_id)
    from api.v1.endpoints.iclock import queue_command

    body = body or {}
    start = body.get("start")
    end = body.get("end")
    want_users = bool(body.get("users", True))
    want_attendance = bool(body.get("attendance", True))
    resync = bool(body.get("resync", False))

    queued: list[str] = []
    if resync:
        # ZKTeco/eSSL: DATA UPDATE ATTLOG re-marks every stored attendance
        # record as "not yet uploaded", forcing the device to re-push its
        # entire log on the next sync even when its local Stamp is 9999.
        cmd = "DATA UPDATE ATTLOG"
        queue_command(device.serial_number, cmd)
        queued.append(cmd)
    if want_users:
        cmd = "DATA QUERY USERINFO"
        queue_command(device.serial_number, cmd)
        queued.append(cmd)
    if want_attendance and start and end:
        cmd = f"DATA QUERY ATTLOG StartTime={start} 00:00:00\tEndTime={end} 23:59:59"
        queue_command(device.serial_number, cmd)
        queued.append(cmd)

    return success_response(
        {
            "device": device.serial_number,
            "queued": queued,
            "note": "Commands run on the device's next poll (within ~10s). Watch /iclock/cdata hits.",
        }
    )


@router.post("/{device_id}/set-time")
def set_device_time(device_id: str, body: dict | None = None, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.edit")
    cid = resolve_company_id(user)
    device = _get_device(db, cid, device_id)
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from api.v1.endpoints.iclock import queue_command
    from core.errors import ValidationError

    tz_name = device.timezone or "Asia/Kolkata"
    try:
        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now = datetime.now()

    raw = (body or {}).get("datetime")
    if raw:
        text = str(raw).strip().replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                target = datetime.strptime(text, fmt)
                break
            except ValueError:
                target = None
        if target is None:
            raise ValidationError("datetime must be YYYY-MM-DD HH:MM:SS")
    else:
        target = now

    cmd = f"SET OPTION DateTime={target.strftime('%Y-%m-%d %H:%M:%S')}"
    offset = target.replace(tzinfo=ZoneInfo(tz_name)).utcoffset()
    hours = (offset.total_seconds() / 3600) if offset is not None else 0
    tz_value = f"{hours:g}"
    tz_cmd = f"SET OPTION TimeZone={tz_value}"
    queue_command(device.serial_number, tz_cmd)
    queue_command(device.serial_number, cmd)
    return success_response(
        {
            "queued": [tz_cmd, cmd],
            "device_time": target.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": tz_name,
            "message": (
                f"Sent timezone {tz_value} and time {target.strftime('%d %b %Y %I:%M:%S %p')} to the device. "
                "If the terminal firmware ignores remote clock changes, set it once on the device keypad "
                "(Menu → Date/Time); the server will keep correcting stored punches in the meantime."
            ),
        }
    )


@router.post("/{device_id}/get-time")
def get_device_time(device_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.view")
    cid = resolve_company_id(user)
    device = _get_device(db, cid, device_id)
    from api.v1.endpoints.iclock import queue_command
    cmd = "GET TIME"
    queue_command(device.serial_number, cmd)
    return success_response({"queued": cmd})


@router.get("/{device_id}/sync-logs")
def sync_logs(device_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.view")
    cid = resolve_company_id(user)
    _get_device(db, cid, device_id)
    from sqlalchemy import select

    rows = list(db.scalars(select(DeviceSyncLog).where(DeviceSyncLog.device_id == device_id).order_by(DeviceSyncLog.started_at.desc()).limit(50)))
    return success_response([orm_to_dict(r) for r in rows])


@router.get("/{device_id}/logs")
def device_logs(
    device_id: str,
    from_date=None,
    to_date=None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    cid = resolve_company_id(user)
    _get_device(db, cid, device_id)
    from sqlalchemy import select

    stmt = select(AttendanceLog).where(AttendanceLog.device_id == device_id)
    rows = list(db.scalars(stmt.order_by(AttendanceLog.event_timestamp.desc()).limit(200)))
    return success_response([orm_to_dict(r) for r in rows])