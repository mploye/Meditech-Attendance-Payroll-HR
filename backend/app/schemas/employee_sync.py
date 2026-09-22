from typing import Optional

from pydantic import BaseModel, Field


class EmployeeSyncRequest(BaseModel):
    device_id: Optional[str] = None
    all_devices: bool = False
