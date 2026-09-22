from typing import Optional

from pydantic import BaseModel, Field


class AttendanceProcessRequest(BaseModel):
    date: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    employee_id: Optional[str] = None
