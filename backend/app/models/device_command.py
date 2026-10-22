from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import GUID, Base, PKMixin, TimestampMixin


class DeviceCommand(PKMixin, TimestampMixin, Base):
    """Persistent server->device command queue for the eSSL ADMS (iclock) channel.

    The device polls ``/iclock/getrequest`` continuously; any command stored
    here for its serial is handed back on the next poll and marked delivered.
    Persisting to the DB (instead of an in-memory dict) means a command survives
    worker restarts / multiple Render instances, so the device is guaranteed to
    receive it. This is what lets us force a device stuck on the ``9999``
    "already-synced" cursor to re-upload its attendance log.
    """

    __tablename__ = "device_commands"

    company_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True, index=True)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
