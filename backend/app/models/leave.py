from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import HolidayType, LeaveStatus, LeaveTypeCategory


class LeaveType(PKMixin, TimestampMixin, Base):
    __tablename__ = "leave_types"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50))
    category: Mapped[LeaveTypeCategory] = mapped_column(
        SAEnum(LeaveTypeCategory, name="leave_type_category"), default=LeaveTypeCategory.PAID, nullable=False
    )
    days_per_year: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    carry_forward_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LeaveBalance(PKMixin, TimestampMixin, Base):
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_id", "leave_type_id", "year", name="uq_leave_balances"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    leave_type_id: Mapped[str] = mapped_column(GUID(), ForeignKey("leave_types.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    entitled_days: Mapped[float] = mapped_column(default=0, nullable=False)
    used_days: Mapped[float] = mapped_column(default=0, nullable=False)
    pending_days: Mapped[float] = mapped_column(default=0, nullable=False)
    remaining_days: Mapped[float] = mapped_column(default=0, nullable=False)


class LeaveRequest(PKMixin, TimestampMixin, Base):
    __tablename__ = "leave_requests"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    leave_type_id: Mapped[str] = mapped_column(GUID(), ForeignKey("leave_types.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[float] = mapped_column(default=0, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[LeaveStatus] = mapped_column(
        SAEnum(LeaveStatus, name="leave_status"), default=LeaveStatus.PENDING, nullable=False, index=True
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[Optional[str]] = mapped_column(Text)
    is_half_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    employee = relationship("Employee", backref="leave_requests")
    leave_type = relationship("LeaveType", backref="requests")


class Holiday(PKMixin, TimestampMixin, Base):
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("company_id", "holiday_date", name="uq_holidays_company_date"),)

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    holiday_type: Mapped[HolidayType] = mapped_column(
        SAEnum(HolidayType, name="holiday_type"), default=HolidayType.COMPANY, nullable=False
    )