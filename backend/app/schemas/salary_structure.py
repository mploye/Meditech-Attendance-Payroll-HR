from typing import Optional

from pydantic import BaseModel, Field


class SalaryStructureCreateRequest(BaseModel):
    name: str
    code: Optional[str] = None
    payment_frequency: str = "MONTHLY"
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    monthly_gross: float = 0
    active: bool = True


class SalaryStructureUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    payment_frequency: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    monthly_gross: Optional[float] = None
    active: Optional[bool] = None
