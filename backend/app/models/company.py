from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import GUID, Base, PKMixin, TimestampMixin
from models.enums import LOPPolicy

from sqlalchemy import JSON


class Company(PKMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100), default="India")
    pincode: Mapped[Optional[str]] = mapped_column(String(20))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    gstin: Mapped[Optional[str]] = mapped_column(String(50))
    pan: Mapped[Optional[str]] = mapped_column(String(20))
    statutory_state: Mapped[Optional[str]] = mapped_column(String(100))
    lop_policy: Mapped[LOPPolicy] = mapped_column(
        SAEnum(LOPPolicy, name="lop_policy"), default=LOPPolicy.WORKING_DAYS, nullable=False
    )
    overtime_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


def default_json_store() -> dict:
    return {}