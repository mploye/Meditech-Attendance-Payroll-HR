from datetime import date, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from core.timezone import get_zone
from models.shift import Shift, ShiftAssignment


def get_default_shift(db: Session, company_id: str) -> Shift | None:
    """Return the first active default shift for a company, if any."""
    return db.scalar(
        select(Shift)
        .where(
            and_(
                Shift.company_id == company_id,
                Shift.is_default.is_(True),
                Shift.active.is_(True),
            )
        )
        .order_by(Shift.created_at)
        .limit(1)
    )


def get_employee_shift(db: Session, company_id: str, employee_id: str, day: date) -> Shift | None:
    """Resolve the shift active for an employee on a day, falling back to the default shift."""
    assigned = db.scalar(
        select(ShiftAssignment)
        .where(
            and_(
                ShiftAssignment.company_id == company_id,
                ShiftAssignment.employee_id == employee_id,
                or_(
                    ShiftAssignment.effective_from.is_(None),
                    ShiftAssignment.effective_from <= day,
                ),
                or_(
                    ShiftAssignment.effective_to.is_(None),
                    ShiftAssignment.effective_to >= day,
                ),
            )
        )
        .order_by(ShiftAssignment.effective_from.desc())
        .limit(1)
    )
    if assigned is not None:
        shift = db.get(Shift, assigned.shift_id)
        if shift is not None and shift.active:
            return shift
    return get_default_shift(db, company_id)


def resolve_shift_times(
    shift: Shift, day: date, company_timezone: str
) -> tuple[datetime | None, datetime | None]:
    """Return concrete tz-aware shift start/end datetimes in the company timezone."""
    if shift.start_time is None:
        return None, None
    zone = get_zone(company_timezone)
    start = datetime.combine(day, shift.start_time, tzinfo=zone)
    end_day = day + timedelta(days=1) if shift.night_shift else day
    end_time = shift.end_time if shift.end_time is not None else shift.start_time
    end = datetime.combine(end_day, end_time, tzinfo=zone)
    return start, end


def is_working_day(shift: Shift, day: date) -> bool:
    """True when the weekday of `day` is not listed in the shift weekly_off_days."""
    off_days = shift.weekly_off_days or []
    return day.weekday() not in set(off_days)