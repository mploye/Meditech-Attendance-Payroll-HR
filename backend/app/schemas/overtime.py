from typing import Optional

from pydantic import BaseModel, Field


class OvertimeCreateRequest(BaseModel):
    employee_id: str
    date: str
    minutes: int
    rate: Optional[float] = None
    remarks: Optional[str] = None


class OvertimeReviewRequest(BaseModel):
    comment: Optional[str] = None
