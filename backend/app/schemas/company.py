from typing import Optional

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    short_name: str = Field(min_length=1, max_length=50)
    legal_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    pincode: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    gstin: Optional[str] = None
    pan: Optional[str] = None
    statutory_state: Optional[str] = None
    lop_policy: Optional[str] = None
    overtime_enabled: Optional[bool] = None
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    admin_full_name: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    legal_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    timezone: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None


class CompanySettingsUpdate(BaseModel):
    lop_policy: Optional[str] = None
    statutory_state: Optional[str] = None
    timezone: Optional[str] = None
    overtime_enabled: Optional[bool] = None
