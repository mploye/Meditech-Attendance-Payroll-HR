from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import OvertimeStatus

from sqlalchemy import Integer


class OvertimeRecord(PKMixin, TimestampMixin, Base):
    __tablename__ = "overtime_records"

    company_id: Mapped[str] = mapped_column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(GUID(), ForeignKey("employees.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[OvertimeStatus] = mapped_column(
        SAEnum(OvertimeStatus, name="overtime_status"), default=OvertimeStatus.PENDING, nullable=False
    )
    approved_by: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    employee = relationship("Employee", backref="overtime_records")