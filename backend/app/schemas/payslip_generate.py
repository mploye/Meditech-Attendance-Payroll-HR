from typing import Optional

from pydantic import BaseModel, Field


class PayslipGenerateRequest(BaseModel):
    payroll_period_id: str
