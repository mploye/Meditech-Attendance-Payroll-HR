from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import MappingSyncStatus


class EmployeeDevice(PKMixin, TimestampMixin, Base):
    __tablename__ = "employee_devices"
    __table_args__ = (
        UniqueConstraint("company_id", "device_id", "device_user_id", name="uq_emp_devices_company_device_user"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(GUID(), ForeignKey("devices.id"), nullable=False, index=True)
    device_user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    face_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fingerprint_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sync_status: Mapped[MappingSyncStatus] = mapped_column(
        SAEnum(MappingSyncStatus, name="mapping_sync_status"), default=MappingSyncStatus.PENDING, nullable=False
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    employee = relationship("Employee", backref="device_mappings")
    device = relationship("Device", backref="employee_mappings")