import calendar
from typing import Optional

from models.company import Company
from models.enums import LOPPolicy


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def daily_rate(
    company: Company,
    gross_salary: float,
    month: int,
    year: int,
    working_days: int | None = None,
) -> float:
    """Return the per-day value of a monthly gross salary under the company LOP policy."""
    gross = float(gross_salary or 0)
    if company.lop_policy == LOPPolicy.CALENDAR_DAYS:
        days = calendar.monthrange(year, month)[1]
        return _round2(gross / days) if days else 0.0
    if company.lop_policy == LOPPolicy.WORKING_DAYS:
        days = working_days or calendar.monthrange(year, month)[1]
        return _round2(gross / days) if days else 0.0
    return _round2(gross / 30)


def lop_amount(
    company: Company,
    gross_salary: float,
    lop_days: float,
    month: int,
    year: int,
    working_days: Optional[int] = None,
) -> float:
    """Return the pay deduction for unpaid leave days in a period."""
    rate = daily_rate(company, gross_salary, month, year, working_days)
    return _round2(rate * float(lop_days or 0))