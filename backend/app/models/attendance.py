from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin, utcnow
from models.enums import AttendanceStatus, EventType, LogSource, SyncLogStatus


class AttendanceLog(PKMixin, Base):
    """Raw device transaction. Immutable."""

    __tablename__ = "attendance_logs"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_attendance_logs_idempotency"),
        Index("ix_attendance_logs_company_device_time", "company_id", "device_id", "event_timestamp"),
        Index("ix_attendance_logs_company_employee_time", "company_id", "employee_id", "event_timestamp"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("devices.id"), index=True)
    employee_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("employees.id"), index=True)
    device_user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(SAEnum(EventType, name="event_type"), default=EventType.UNKNOWN, nullable=False)
    source: Mapped[LogSource] = mapped_column(SAEnum(LogSource, name="log_source"), default=LogSource.ESSL, nullable=False)
    external_event_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    employee = relationship("Employee", backref="attendance_logs")
    device = relationship("Device", backref="attendance_logs")


class AttendanceDaily(PKMixin, TimestampMixin, Base):
    __tablename__ = "attendance_daily"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_id", "attendance_date", name="uq_attendance_daily_emp_date"),
        Index("ix_attendance_daily_company_status_date", "company_id", "status", "attendance_date"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("shifts.id"))
    first_in: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, name="attendance_status"), default=AttendanceStatus.PRESENT, nullable=False
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    employee = relationship("Employee", backref="daily_attendance")
    shift = relationship("Shift", backref="daily_attendance")


class DeviceSyncLog(PKMixin, Base):
    __tablename__ = "device_sync_logs"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("devices.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    records_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_duplicate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[SyncLogStatus] = mapped_column(
        SAEnum(SyncLogStatus, name="sync_log_status"), default=SyncLogStatus.SUCCESS, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)


class Synchronization:
    """Tag object; keeps module import name unambiguous."""

    pass