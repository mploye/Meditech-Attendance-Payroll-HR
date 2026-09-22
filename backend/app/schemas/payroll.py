from typing import Optional

from pydantic import BaseModel


class PayrollPeriodCreate(BaseModel):
    month: int
    year: int
