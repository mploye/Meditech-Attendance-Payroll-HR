from typing import Optional

from pydantic import BaseModel, Field


class EmployeeDeviceMappingRequest(BaseModel):
    device_id: str
    device_user_id: str
