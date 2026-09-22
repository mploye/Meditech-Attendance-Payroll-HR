from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import Role


class User(PKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    company_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("companies.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="role"), default=Role.EMPLOYEE, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    employee_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("employees.id"))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    company = relationship("Company", backref="users")
    employee = relationship("Employee", backref="user", remote_side="Employee.id", foreign_keys=[employee_id])