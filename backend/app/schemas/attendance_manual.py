from typing import Optional

from pydantic import BaseModel, Field


class ManualLog(BaseModel):
    employee_id: str
    event_type: str = "IN"
    timestamp: Optional[str] = None
    remarks: Optional[str] = None
    device_id: Optional[str] = None
