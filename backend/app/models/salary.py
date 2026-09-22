from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, Enum as SAEnum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import CalculationType, SalaryComponentType, SalaryFrequency, StatutoryRuleType


class SalaryStructure(PKMixin, TimestampMixin, Base):
    __tablename__ = "salary_structures"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50))
    payment_frequency: Mapped[SalaryFrequency] = mapped_column(
        SAEnum(SalaryFrequency, name="salary_frequency"), default=SalaryFrequency.MONTHLY, nullable=False
    )
    effective_from: Mapped[Optional[date]] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    monthly_gross: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    components = relationship(
        "SalaryStructureComponent", backref="structure", cascade="all, delete-orphan", order_by="SalaryStructureComponent.sort_order"
    )


class SalaryStructureComponent(PKMixin, TimestampMixin, Base):
    __tablename__ = "salary_structure_components"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    salary_structure_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("salary_structures.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    component_type: Mapped[SalaryComponentType] = mapped_column(
        SAEnum(SalaryComponentType, name="salary_component_type"), default=SalaryComponentType.EARNING, nullable=False
    )
    calculation_type: Mapped[CalculationType] = mapped_column(
        SAEnum(CalculationType, name="calculation_type"), default=CalculationType.FIXED, nullable=False
    )
    value: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    formula: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class EmployeeSalary(PKMixin, TimestampMixin, Base):
    """Salary history. Never overwrite; expire by effective_to."""

    __tablename__ = "employee_salary"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    salary_structure_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("salary_structures.id"))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    basic_salary: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    gross_salary: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    payment_frequency: Mapped[SalaryFrequency] = mapped_column(
        SAEnum(SalaryFrequency, name="salary_frequency"), default=SalaryFrequency.MONTHLY, nullable=False
    )
    bank_name: Mapped[Optional[str]] = mapped_column(String(100))
    account_number: Mapped[Optional[str]] = mapped_column(String(50))
    ifsc: Mapped[Optional[str]] = mapped_column(String(20))
    account_holder_name: Mapped[Optional[str]] = mapped_column(String(100))

    employee = relationship("Employee", backref="salary_history")
    structure = relationship("SalaryStructure", backref="employee_salaries")


class StatutoryRule(PKMixin, TimestampMixin, Base):
    __tablename__ = "statutory_rules"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    rule_type: Mapped[StatutoryRuleType] = mapped_column(
        SAEnum(StatutoryRuleType, name="statutory_rule_type"), nullable=False, index=True
    )
    region: Mapped[Optional[str]] = mapped_column(String(100))
    employee_category: Mapped[Optional[str]] = mapped_column(String(100))
    effective_from: Mapped[Optional[date]] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    threshold: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    maximum: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    calculation_method: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)