from typing import Optional

from pydantic import BaseModel, Field


class AdvanceCreate(BaseModel):
    employee_id: str
    requested_amount: float = Field(gt=0)
    deduction_installments: int = 1
    deduction_start_month: Optional[str] = None
    remarks: Optional[str] = None


class AdvanceApprove(BaseModel):
    approved_amount: Optional[float] = None
