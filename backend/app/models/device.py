from datetime import datetime, time
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import DeviceProvider, DeviceStatus, DeviceType


class Device(PKMixin, TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("company_id", "serial_number", name="uq_devices_company_serial"),)

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100))
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False)
    device_type: Mapped[DeviceType] = mapped_column(
        SAEnum(DeviceType, name="device_type"), default=DeviceType.FACE_PUNCH, nullable=False
    )
    location: Mapped[Optional[str]] = mapped_column(String(255))
    ip_address: Mapped[Optional[str]] = mapped_column(String(100))
    port: Mapped[Optional[int]] = mapped_column(Integer)
    protocol: Mapped[Optional[str]] = mapped_column(String(50), default="http")
    provider: Mapped[DeviceProvider] = mapped_column(
        SAEnum(DeviceProvider, name="device_provider"), default=DeviceProvider.ESSL, nullable=False
    )
    status: Mapped[DeviceStatus] = mapped_column(
        SAEnum(DeviceStatus, name="device_status"), default=DeviceStatus.OFFLINE, nullable=False, index=True
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ESSLConfig(PKMixin, TimestampMixin, Base):
    __tablename__ = "essl_config"
    __table_args__ = (UniqueConstraint("company_id", name="uq_essl_config_company"),)

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(500))
    username: Mapped[Optional[str]] = mapped_column(String(255))
    password_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    company_short_name: Mapped[Optional[str]] = mapped_column(String(100))
    timeout_sec: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    sync_interval_sec: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    capabilities: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)