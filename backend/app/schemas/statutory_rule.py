from typing import Optional

from pydantic import BaseModel, Field


class StatutoryRuleUpsertRequest(BaseModel):
    rule_type: str
    region: Optional[str] = None
    employee_category: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    threshold: float = 0
    rate: float = 0
    maximum: float = 0
    calculation_method: Optional[str] = None
    status: bool = True
