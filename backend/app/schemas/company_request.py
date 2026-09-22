"""Request schemas for company create / update operations."""

from pydantic import BaseModel, Field


class CompanyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    short_name: str = Field(..., min_length=1, max_length=50)
    legal_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field("India", max_length=80)
    pincode: str | None = Field(None, max_length=20)
    timezone: str | None = Field("Asia/Kolkata", max_length=50)
    gstin: str | None = Field(None, max_length=50)
    pan: str | None = Field(None, max_length=50)
    statutory_state: str | None = Field(None, max_length=100)


class CompanyUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    short_name: str | None = Field(None, min_length=1, max_length=50)
    legal_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=80)
    pincode: str | None = Field(None, max_length=20)
    timezone: str | None = Field(None, max_length=50)
    gstin: str | None = Field(None, max_length=50)
    pan: str | None = Field(None, max_length=50)
    statutory_state: str | None = Field(None, max_length=100)


class CompanySettingsRequest(BaseModel):
    lop_policy: str | None = Field(None, max_length=30)
    statutory_state: str | None = Field(None, max_length=100)
    timezone: str | None = Field(None, max_length=50)
    overtime_enabled: bool | None = None