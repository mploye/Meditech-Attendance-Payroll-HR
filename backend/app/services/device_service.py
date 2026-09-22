import asyncio
import logging

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.errors import ValidationError
from models.device import Device
from models.enums import DeviceProvider, DeviceStatus
from services.sync_service import SyncService, get_essl_service

logger = logging.getLogger(__name__)

_DEVICE_FIELDS = {
    "name",
    "model",
    "serial_number",
    "device_type",
    "location",
    "ip_address",
    "port",
    "protocol",
    "provider",
    "status",
}


def create_device(db: Session, company_id: str, data: dict) -> Device:
    """Create a device for a company from validated input data."""
    name = str(data.get("name") or "").strip()
    serial_number = str(data.get("serial_number") or "").strip()
    if not name or not serial_number:
        raise ValidationError("name and serial_number are required")
    fields = {k: v for k, v in data.items() if k in _DEVICE_FIELDS}
    device = Device(company_id=company_id, **fields)
    db.add(device)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValidationError("a device with this serial number already exists")
    db.refresh(device)
    return device


def test_device_connection(db: Session, device: Device) -> dict:
    """Test connectivity with the device provider or return a simulated result."""
    if device.provider == DeviceProvider.ESSL:
        service = get_essl_service(db, device.company_id)
        if service is None:
            return {"success": False, "status": device.status.value, "message": "ESSL provider not configured"}
        try:
            result = asyncio.run(service.test_device_connection(device))
        except Exception as exc:
            logger.exception("Device connection test failed")
            result = {"success": False, "status": device.status.value, "message": str(exc)}
        result.setdefault("status", device.status.value)
        return result
    return {"success": True, "status": device.status.value, "message": "simulated"}


def list_devices(
    db: Session,
    company_id: str,
    search: str | None = None,
    status: DeviceStatus | str | None = None,
) -> list[Device]:
    """List devices for a company with optional search text and status filter."""
    if isinstance(status, str):
        status = DeviceStatus(status)
    stmt = select(Device).where(Device.company_id == company_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Device.name.ilike(like), Device.serial_number.ilike(like)))
    if status is not None:
        stmt = stmt.where(Device.status == status)
    return list(db.scalars(stmt.order_by(Device.created_at)))


def sync_device_now(db: Session, device: Device) -> dict:
    """Trigger an immediate manual sync for a single device."""
    return SyncService(db).run_manual_sync(device.company_id, device.id)