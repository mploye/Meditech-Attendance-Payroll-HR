from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import EmployeeStatus, EmploymentType


class Employee(PKMixin, TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_code", name="uq_employees_company_code"),
    )

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    gender: Mapped[Optional[str]] = mapped_column(String(20))
    joining_date: Mapped[Optional[date]] = mapped_column(Date)
    resignation_date: Mapped[Optional[date]] = mapped_column(Date)
    department_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("departments.id"), index=True)
    designation_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("designations.id"), index=True)
    manager_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("employees.id"))
    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(EmploymentType, name="employment_type"), default=EmploymentType.FULL_TIME, nullable=False
    )
    work_location: Mapped[Optional[str]] = mapped_column(String(255))
    profile_photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[EmployeeStatus] = mapped_column(
        SAEnum(EmployeeStatus, name="employee_status"), default=EmployeeStatus.ACTIVE, nullable=False, index=True
    )
    aadhaar_no: Mapped[Optional[str]] = mapped_column(String(20))
    pan: Mapped[Optional[str]] = mapped_column(String(20))
    bank_name: Mapped[Optional[str]] = mapped_column(String(100))
    account_number: Mapped[Optional[str]] = mapped_column(String(50))
    ifsc: Mapped[Optional[str]] = mapped_column(String(20))
    account_holder_name: Mapped[Optional[str]] = mapped_column(String(100))

    department = relationship("Department", backref="employees", foreign_keys=[department_id])
    designation = relationship("Designation", backref="employees", foreign_keys=[designation_id])
    manager = relationship(
        "Employee", remote_side="Employee.id", backref="reports", foreign_keys=[manager_id]
    )