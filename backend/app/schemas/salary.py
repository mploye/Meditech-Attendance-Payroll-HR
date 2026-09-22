from typing import Optional

from pydantic import BaseModel


class SalarySetRequest(BaseModel):
    effective_from: str
    basic_salary: Optional[float] = None
    gross_salary: Optional[float] = None
    salary_structure_id: Optional[str] = None
    payment_frequency: Optional[str] = None
    effective_to: Optional[str] = None
