from typing import Optional

from pydantic import BaseModel, Field


class LeaveTypeCreateRequest(BaseModel):
    name: str
    code: Optional[str] = None
    category: Optional[str] = "PAID"
    days_per_year: float = 0
    requires_approval: bool = True


class LeaveTypeUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    days_per_year: Optional[float] = None
    requires_approval: Optional[bool] = None


class LeaveApplyRequest(BaseModel):
    employee_id: str
    leave_type_id: str
    start_date: str
    end_date: str
    reason: Optional[str] = None
    is_half_day: bool = False


class LeaveDecisionRequest(BaseModel):
    comment: Optional[str] = None
