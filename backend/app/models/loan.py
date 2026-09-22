from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import AdvanceStatus, LoanStatus


class EmployeeLoan(PKMixin, TimestampMixin, Base):
    __tablename__ = "employee_loans"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    loan_amount: Mapped[float] = mapped_column(Float, nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    installment_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    number_of_installments: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    paid_installments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outstanding_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    interest_rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[LoanStatus] = mapped_column(
        SAEnum(LoanStatus, name="loan_status"), default=LoanStatus.ACTIVE, nullable=False
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    employee = relationship("Employee", backref="loans")
    installments = relationship("LoanInstallment", backref="loan", cascade="all, delete-orphan")


class LoanInstallment(PKMixin, TimestampMixin, Base):
    __tablename__ = "loan_installments"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    loan_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employee_loans.id"), nullable=False, index=True)
    installment_no: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    paid_in_payroll_period_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("payroll_periods.id"))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)


class SalaryAdvance(PKMixin, TimestampMixin, Base):
    __tablename__ = "salary_advances"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    requested_amount: Mapped[float] = mapped_column(Float, nullable=False)
    approved_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deduction_installments: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deduction_start_month: Mapped[Optional[str]] = mapped_column(String(7))
    status: Mapped[AdvanceStatus] = mapped_column(
        SAEnum(AdvanceStatus, name="advance_status"), default=AdvanceStatus.REQUESTED, nullable=False
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    employee = relationship("Employee", backref="advances")