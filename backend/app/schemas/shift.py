from typing import Optional

from pydantic import BaseModel, Field


class ShiftCreateRequest(BaseModel):
    name: str
    code: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    grace_period_minutes: int = 0
    minimum_work_minutes: int = 0
    break_minutes: int = 0
    overtime_enabled: bool = True
    overtime_after_minutes: int = 60
    is_default: bool = False
    active: bool = True


class ShiftUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    grace_period_minutes: Optional[int] = None
    minimum_work_minutes: Optional[int] = None
    break_minutes: Optional[int] = None
    overtime_enabled: Optional[bool] = None
    overtime_after_minutes: Optional[int] = None
    is_default: Optional[bool] = None
    active: Optional[bool] = None


class ShiftAssignRequest(BaseModel):
    employee_ids: list[str]
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


class ShiftDefaultRequest(BaseModel):
    shift_id: str
