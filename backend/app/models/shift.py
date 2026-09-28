from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import BreakStatus, BreakType


class Shift(PKMixin, TimestampMixin, Base):
    __tablename__ = "shifts"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50))
    start_time: Mapped[Optional[time]] = mapped_column(Time)
    end_time: Mapped[Optional[time]] = mapped_column(Time)
    grace_period_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minimum_work_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minimum_shift_hours: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    maximum_shift_hours: Mapped[float] = mapped_column(Float, default=9.0, nullable=False)
    scheduled_break_count: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    scheduled_break_duration: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    overtime_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    overtime_after_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    night_shift: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weekly_off_days: Mapped[Optional[list]] = mapped_column(JSON)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    breaks: Mapped[list["ShiftBreak"]] = relationship(
        "ShiftBreak", back_populates="shift", cascade="all, delete-orphan"
    )

    @property
    def total_scheduled_break_minutes(self) -> int:
        """Configured break budget for the shift.

        Precedence: explicit break templates, then the legacy scalar, then the
        configurable count x per-break duration (never hardcoded). Existing
        shifts keep their `break_minutes` behaviour after the module lands.
        """
        active = [b for b in (self.breaks or []) if b.active]
        if active:
            return sum(int(b.max_duration_minutes or 0) for b in active)
        legacy = int(self.break_minutes or 0)
        if legacy:
            return legacy
        return int(self.scheduled_break_count or 0) * int(self.scheduled_break_duration or 0)


class ShiftAssignment(PKMixin, TimestampMixin, Base):
    __tablename__ = "shift_assignments"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    shift_id: Mapped[str] = mapped_column(GUID(), ForeignKey("shifts.id"), nullable=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)


class ShiftBreak(PKMixin, TimestampMixin, Base):
    """Configured or ad-hoc break slot attached to a shift (scheduled/recurrent).

    Scheduled breaks are re-usable templates (e.g. Morning Break, Lunch, Tea).
    A RESTROOM-type ShiftBreak emits convenience defaults but does not limit
    how many times an employee may take one in a day.
    """

    __tablename__ = "shift_breaks"
    __table_args__ = (
        UniqueConstraint("company_id", "shift_id", "name", name="uq_shift_breaks_company_id_shift_id_name"),
        Index("ix_shift_breaks_company_id", "company_id"),
        Index("ix_shift_breaks_shift_id", "shift_id"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False)
    shift_id: Mapped[str] = mapped_column(GUID(), ForeignKey("shifts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    break_type: Mapped[BreakType] = mapped_column(
        SAEnum(BreakType, name="break_type"), default=BreakType.SCHEDULED, nullable=False
    )
    start_time: Mapped[Optional[time]] = mapped_column(Time)
    max_duration_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    shift = relationship("Shift", back_populates="breaks")
    logs: Mapped[list["BreakLog"]] = relationship("BreakLog", back_populates="scheduled_break")


class BreakLog(PKMixin, TimestampMixin, Base):
    """A single break instance: one start, optional end, and computed duration."""

    __tablename__ = "break_logs"
    __table_args__ = (
        Index("ix_break_logs_company_employee_date", "company_id", "employee_id", "break_date"),
        Index("ix_break_logs_company_id", "company_id"),
        Index("ix_break_logs_employee_id", "employee_id"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False)
    shift_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("shifts.id"))
    scheduled_break_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("shift_breaks.id"))
    break_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    break_type: Mapped[BreakType] = mapped_column(
        SAEnum(BreakType, name="break_type"), default=BreakType.RESTROOM, nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[BreakStatus] = mapped_column(
        SAEnum(BreakStatus, name="break_status"), default=BreakStatus.ACTIVE, nullable=False
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    employee = relationship("Employee", backref="break_logs")
    shift = relationship("Shift")
    scheduled_break = relationship("ShiftBreak", back_populates="logs")