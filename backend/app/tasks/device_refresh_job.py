import logging
from datetime import datetime, timezone

from sqlalchemy import select

from core.database import SessionLocal
from models.device import Device
from models.enums import DeviceStatus, DeviceProvider

logger = logging.getLogger(__name__)


def refresh_devices() -> None:
    """Push every registered ADMS device to re-upload its attendance log.

    Runs every minute. The device polls /iclock/getrequest continuously, so the
    command is delivered within seconds and the device POSTs its stored punches
    back to /iclock/cdata. This is what keeps attendance fresh ~every minute
    without any manual action, even if a device cursor drifted to the "9999
    already-synced" sentinel and silently stopped uploading.
    """
    from api.v1.endpoints.iclock import ATTLOG_REUPLOAD_CMD, queue_command

    db = SessionLocal()
    try:
        devices = db.scalars(
            select(Device).where(Device.provider == DeviceProvider.ESSL)
        ).all()
        for device in devices:
            try:
                queue_command(
                    device.serial_number,
                    ATTLOG_REUPLOAD_CMD,
                    company_id=str(device.company_id),
                )
                # A device is considered online until it misses several polls.
                if device.status != DeviceStatus.ONLINE:
                    device.status = DeviceStatus.ONLINE
            except Exception:
                logger.exception("Failed to queue refresh for device %s", device.serial_number)
        db.commit()
    except Exception:
        logger.exception("Device refresh job failed")
    finally:
        db.close()
