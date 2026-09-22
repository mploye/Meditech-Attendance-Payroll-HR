from datetime import date, time
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, Enum as SAEnum, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin


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
    overtime_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    overtime_after_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    night_shift: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weekly_off_days: Mapped[Optional[list]] = mapped_column(JSON)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ShiftAssignment(PKMixin, TimestampMixin, Base):
    __tablename__ = "shift_assignments"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    shift_id: Mapped[str] = mapped_column(GUID(), ForeignKey("shifts.id"), nullable=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)