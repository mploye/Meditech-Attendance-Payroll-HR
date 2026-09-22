from typing import Optional

from pydantic import BaseModel, Field


class AttendanceCorrectionRequest(BaseModel):
    first_in: Optional[str] = None
    last_out: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None
