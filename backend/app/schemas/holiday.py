from typing import Optional

from pydantic import BaseModel, Field


class HolidayCreateRequest(BaseModel):
    holiday_date: str
    name: str
    holiday_type: str = "COMPANY"


class HolidayUpdateRequest(BaseModel):
    holiday_date: Optional[str] = None
    name: Optional[str] = None
    holiday_type: Optional[str] = None
