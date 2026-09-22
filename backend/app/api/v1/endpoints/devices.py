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
    return success_response([orm_to_dict(d) for d in devices])


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