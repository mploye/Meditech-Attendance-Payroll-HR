from typing import Optional

from pydantic import BaseModel, Field


class EmployeeSalaryUpsertRequest(BaseModel):
    effective_from: str
    effective_to: Optional[str] = None
    salary_structure_id: Optional[str] = None
    basic_salary: float = 0
    gross_salary: float = 0
    payment_frequency: str = "MONTHLY"
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    account_holder_name: Optional[str] = None
