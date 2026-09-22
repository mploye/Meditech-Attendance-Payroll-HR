from typing import Optional

from pydantic import BaseModel, Field


class DeviceCreateRequest(BaseModel):
    name: str
    serial_number: str
    model: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    provider: Optional[str] = None
    status: Optional[str] = None


class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    status: Optional[str] = None
