from typing import Optional

from pydantic import BaseModel, Field


class LoanCreateRequest(BaseModel):
    employee_id: str
    loan_amount: float
    installment_amount: float
    number_of_installments: int
    start_date: Optional[str] = None
    interest_rate: float = 0
    remarks: Optional[str] = None


class AdvanceCreateRequest(BaseModel):
    employee_id: str
    requested_amount: float
    deduction_installments: int = 1
    deduction_start_month: Optional[str] = None
    remarks: Optional[str] = None


class AdvanceApproveRequest(BaseModel):
    approved_amount: Optional[float] = None
