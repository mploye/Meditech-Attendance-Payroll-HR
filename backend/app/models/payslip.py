from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin
from models.enums import PayslipStatus


class Payslip(PKMixin, Base):
    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint("company_id", "payroll_record_id", "employee_id", name="uq_payslips_record_emp"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    payroll_record_id: Mapped[str] = mapped_column(GUID(), ForeignKey("payroll_records.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    payroll_period_id: Mapped[str] = mapped_column(GUID(), ForeignKey("payroll_periods.id"), nullable=False, index=True)
    gross: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_deductions: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    net: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[PayslipStatus] = mapped_column(
        SAEnum(PayslipStatus, name="payslip_status"), default=PayslipStatus.GENERATED, nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    payroll_record = relationship("PayrollRecord", backref="payslip")
    employee = relationship("Employee", backref="payslips")
    period = relationship("PayrollPeriod", backref="payslips")