from typing import Optional

from pydantic import BaseModel, Field


class AttendanceSyncRequest(BaseModel):
    device_id: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
