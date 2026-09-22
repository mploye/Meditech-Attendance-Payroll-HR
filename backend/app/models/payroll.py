from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import PayrollComponentType, PayrollPeriodStatus, PayrollRecordStatus


class PayrollPeriod(PKMixin, TimestampMixin, Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (UniqueConstraint("company_id", "month", "year", name="uq_payroll_periods_company_month_year"),)

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PayrollPeriodStatus] = mapped_column(
        SAEnum(PayrollPeriodStatus, name="payroll_period_status"), default=PayrollPeriodStatus.DRAFT, nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    records = relationship("PayrollRecord", backref="period", cascade="all, delete-orphan")


class PayrollRecord(PKMixin, TimestampMixin, Base):
    __tablename__ = "payroll_records"
    __table_args__ = (
        UniqueConstraint("company_id", "payroll_period_id", "employee_id", name="uq_payroll_records_period_emp"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    payroll_period_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("payroll_periods.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    working_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    present_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leave_days: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    absent_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lop_days: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gross_salary: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_deductions: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    net_salary: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[PayrollRecordStatus] = mapped_column(
        SAEnum(PayrollRecordStatus, name="payroll_record_status"), default=PayrollRecordStatus.DRAFT, nullable=False
    )

    employee = relationship("Employee", backref="payroll_records")
    components = relationship(
        "PayrollComponent", backref="record", cascade="all, delete-orphan", order_by="PayrollComponent.sort_order"
    )


class PayrollComponent(PKMixin, Base):
    __tablename__ = "payroll_components"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    payroll_record_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("payroll_records.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    component_type: Mapped[PayrollComponentType] = mapped_column(
        SAEnum(PayrollComponentType, name="payroll_component_type"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    is_statutory: Mapped[bool] = mapped_column(default=False, nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50))
    reference_id: Mapped[Optional[str]] = mapped_column(GUID())
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)