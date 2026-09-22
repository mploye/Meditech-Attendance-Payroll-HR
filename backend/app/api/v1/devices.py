"""Device endpoints under /devices."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import NotFoundError, success_response
from models.attendance import AttendanceLog, DeviceSyncLog
from models.device import Device
from models.user import User
from schemas.device import DeviceCreateRequest, DeviceUpdateRequest
from services import device_service

router = APIRouter(prefix="/devices", tags=["devices"])


def _get_device(db: Session, company_id: str, device_id: str) -> Device:
    device = db.scalar(
        select(Device).where(Device.id == device_id, Device.company_id == company_id)
    )
    if device is None:
        raise NotFoundError("Device")
    return device


@router.get("")
def list_devices(
    search: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.view")
    scope = company_scope(user=user)
    rows = device_service.list_devices(db, scope, search=search, status=status)
    return success_response(orm_to_dict(rows))


@router.post("")
def create_device(
    payload: DeviceCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.create")
    scope = company_scope(user=user)
    device = device_service.create_device(db, scope, payload.model_dump(exclude_unset=True))
    return success_response(orm_to_dict(device))


@router.get("/{device_id}")
def get_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.view")
    scope = company_scope(user=user)
    return success_response(orm_to_dict(_get_device(db, scope, device_id)))


@router.patch("/{device_id}")
def update_device(
    device_id: str,
    payload: DeviceUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.edit")
    scope = company_scope(user=user)
    device = _get_device(db, scope, device_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if hasattr(device, key):
            setattr(device, key, value)
    db.commit()
    db.refresh(device)
    return success_response(orm_to_dict(device))


@router.delete("/{device_id}")
def delete_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.delete")
    scope = company_scope(user=user)
    device = _get_device(db, scope, device_id)
    db.delete(device)
    db.commit()
    return success_response({"message": "deleted"})


@router.post("/{device_id}/test")
def test_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.test")
    scope = company_scope(user=user)
    device = _get_device(db, scope, device_id)
    return success_response(device_service.test_device_connection(db, device))


@router.post("/{device_id}/sync")
def sync_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.sync")
    scope = company_scope(user=user)
    device = _get_device(db, scope, device_id)
    result = device_service.sync_device_now(db, device)
    return success_response(result)


@router.get("/{device_id}/sync-logs")
def device_sync_logs(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.view")
    scope = company_scope(user=user)
    _get_device(db, scope, device_id)
    logs = list(
        db.scalars(
            select(DeviceSyncLog)
            .where(DeviceSyncLog.company_id == scope, DeviceSyncLog.device_id == device_id)
            .order_by(DeviceSyncLog.started_at.desc())
            .limit(100)
        )
    )
    return success_response(orm_to_dict(logs))


@router.get("/{device_id}/logs")
def device_logs(
    device_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    scope = company_scope(user=user)
    _get_device(db, scope, device_id)
    stmt = select(AttendanceLog).where(
        AttendanceLog.company_id == scope, AttendanceLog.device_id == device_id
    )
    total = len(list(db.scalars(stmt)))
    rows = list(
        db.scalars(stmt.order_by(AttendanceLog.event_timestamp.desc()).offset((page - 1) * page_size).limit(page_size))
    )
    return success_response(
        {"items": orm_to_dict(rows), "total": total, "page": page, "page_size": page_size}
    )