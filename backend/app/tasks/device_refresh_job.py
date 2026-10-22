import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from core.database import SessionLocal
from models.device import Device
from models.device_command import DeviceCommand
from models.enums import DeviceProvider, DeviceStatus

logger = logging.getLogger(__name__)

# Keep the queue bounded: commands that were delivered or confirmed are noise
# after a day, and one that was never even delivered for a week is stale.
CONFIRMED_RETENTION = timedelta(days=1)
UNDELIVERED_RETENTION = timedelta(days=7)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def refresh_devices() -> None:
    """Keep device status honest and clean up the command queue.

    Runs every minute. Status is only ever set to ONLINE by a real request from
    the device (see ``/iclock``); here we downgrade a device that has gone
    quiet. Attendance re-uploads are now triggered from the device's own
    ``getrequest`` poll, so this job no longer has to push commands.
    """
    from api.v1.endpoints.iclock import DEVICE_OFFLINE_AFTER_SEC

    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        devices = db.scalars(select(Device).where(Device.provider == DeviceProvider.ESSL)).all()
        for device in devices:
            seen = _aware(device.last_seen_at)
            quiet = seen is None or (now - seen).total_seconds() > DEVICE_OFFLINE_AFTER_SEC
            if quiet and device.status == DeviceStatus.ONLINE:
                device.status = DeviceStatus.OFFLINE
                logger.info("Device %s marked offline (last seen %s)", device.serial_number, seen)

        db.execute(
            delete(DeviceCommand).where(
                DeviceCommand.created_at < now - CONFIRMED_RETENTION,
                DeviceCommand.confirmed.is_(True) | DeviceCommand.delivered.is_(True),
            )
        )
        db.execute(
            delete(DeviceCommand).where(
                DeviceCommand.delivered.is_(False),
                DeviceCommand.created_at < now - UNDELIVERED_RETENTION,
            )
        )
        db.commit()
    except Exception:
        logger.exception("Device refresh job failed")
        db.rollback()
    finally:
        db.close()
