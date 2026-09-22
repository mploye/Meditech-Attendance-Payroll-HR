import calendar
from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from models.attendance import AttendanceDaily
from models.device import Device
from models.employee import Employee
from models.enums import (
    AttendanceStatus,
    DeviceStatus,
    EmployeeStatus,
    LeaveStatus,
    OvertimeStatus,
    PayrollPeriodStatus,
)
from models.leave import LeaveRequest
from models.overtime import OvertimeRecord
from models.payroll import PayrollPeriod, PayrollRecord


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def _latest_monthends(months: int, today: date) -> list[tuple[int, int]]:
    """Return (year, month) pairs for the trailing N calendar months, oldest first."""
    pairs: list[tuple[int, int]] = []
    year, month = today.year, today.month
    for _ in range(months):
        pairs.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(pairs))


def summary(db: Session, company_id: str, day: date) -> dict:
    """Return dashboard headline metrics for a company on a given day."""
    total_employees = db.scalar(
        select(func.count(Employee.id)).where(
            Employee.company_id == company_id,
            Employee.status == EmployeeStatus.ACTIVE,
        )
    )
    present_today = db.scalar(
        select(func.count(AttendanceDaily.id)).where(
            AttendanceDaily.company_id == company_id,
            AttendanceDaily.attendance_date == day,
            AttendanceDaily.status == AttendanceStatus.PRESENT,
        )
    )
    absent_today = db.scalar(
        select(func.count(AttendanceDaily.id)).where(
            AttendanceDaily.company_id == company_id,
            AttendanceDaily.attendance_date == day,
            AttendanceDaily.status == AttendanceStatus.ABSENT,
        )
    )
    on_leave = db.scalar(
        select(func.count(LeaveRequest.id)).where(
            and_(
                LeaveRequest.company_id == company_id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date <= day,
                LeaveRequest.end_date >= day,
            )
        )
    )
    late_today = db.scalar(
        select(func.count(AttendanceDaily.id)).where(
            and_(
                AttendanceDaily.company_id == company_id,
                AttendanceDaily.attendance_date == day,
                AttendanceDaily.late_minutes > 0,
            )
        )
    )
    overtime_employees = db.scalar(
        select(func.count(OvertimeRecord.id)).where(
            and_(
                OvertimeRecord.company_id == company_id,
                OvertimeRecord.date == day,
                OvertimeRecord.status.in_(
                    [OvertimeStatus.PENDING, OvertimeStatus.APPROVED]
                ),
            )
        )
    )
    pending_leaves = db.scalar(
        select(func.count(LeaveRequest.id)).where(
            LeaveRequest.company_id == company_id,
            LeaveRequest.status == LeaveStatus.PENDING,
        )
    )
    pending_payroll = db.scalar(
        select(func.count(PayrollPeriod.id)).where(
            PayrollPeriod.company_id == company_id,
            PayrollPeriod.status.in_(
                [
                    PayrollPeriodStatus.DRAFT,
                    PayrollPeriodStatus.CALCULATING,
                    PayrollPeriodStatus.REVIEW,
                ]
            ),
        )
    )
    latest_period = db.scalar(
        select(PayrollPeriod)
        .where(PayrollPeriod.company_id == company_id)
        .order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc())
        .limit(1)
    )
    payroll_amount = 0.0
    if latest_period is not None:
        total = db.scalar(
            select(func.coalesce(func.sum(PayrollRecord.net_salary), 0.0)).where(
                PayrollRecord.payroll_period_id == latest_period.id
            )
        )
        payroll_amount = _round2(total or 0)

    onlines = db.scalar(
        select(func.count(Device.id)).where(
            Device.company_id == company_id,
            Device.status == DeviceStatus.ONLINE,
        )
    )
    offlines = db.scalar(
        select(func.count(Device.id)).where(
            Device.company_id == company_id,
            Device.status == DeviceStatus.OFFLINE,
        )
    )
    return {
        "total_employees": int(total_employees or 0),
        "present_today": int(present_today or 0),
        "absent_today": int(absent_today or 0),
        "on_leave": int(on_leave or 0),
        "late_today": int(late_today or 0),
        "overtime_employees": int(overtime_employees or 0),
        "pending_leaves": int(pending_leaves or 0),
        "pending_payroll": int(pending_payroll or 0),
        "payroll_amount": payroll_amount,
        "devices_online": int(onlines or 0),
        "devices_offline": int(offlines or 0),
    }


def attendance_trend(db: Session, company_id: str, days: int = 14) -> list:
    """Return daily present/absent/leave counts for the trailing N days."""
    today = date.today()
    start = today - timedelta(days=max(1, int(days)) - 1)
    rows = list(
        db.scalars(
            select(AttendanceDaily).where(
                and_(
                    AttendanceDaily.company_id == company_id,
                    AttendanceDaily.attendance_date >= start,
                    AttendanceDaily.attendance_date <= today,
                )
            )
        )
    )
    counts: dict[date, dict[str, int]] = {}
    for rec in rows:
        bucket = counts.setdefault(rec.attendance_date, {"present": 0, "absent": 0, "leave": 0})
        if rec.status == AttendanceStatus.PRESENT:
            bucket["present"] += 1
        elif rec.status == AttendanceStatus.ABSENT:
            bucket["absent"] += 1
        elif rec.status == AttendanceStatus.LEAVE:
            bucket["leave"] += 1
    trend = []
    current = start
    while current <= today:
        bucket = counts.get(current, {"present": 0, "absent": 0, "leave": 0})
        trend.append({"date": current.isoformat(), **bucket})
        current += timedelta(days=1)
    return trend


def payroll_trend(db: Session, company_id: str, months: int = 6) -> list:
    """Return gross/deductions/net totals per period for the trailing N months."""
    pairs = _latest_monthends(months, date.today())
    result = []
    for year, month in pairs:
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)
        period = db.scalar(
            select(PayrollPeriod).where(
                and_(
                    PayrollPeriod.company_id == company_id,
                    PayrollPeriod.start_date >= start,
                    PayrollPeriod.end_date <= end,
                )
            )
        )
        gross = deductions = net = 0.0
        status = None
        if period is not None:
            totals = db.execute(
                select(
                    func.coalesce(func.sum(PayrollRecord.gross_salary), 0.0),
                    func.coalesce(func.sum(PayrollRecord.total_deductions), 0.0),
                    func.coalesce(func.sum(PayrollRecord.net_salary), 0.0),
                ).where(PayrollRecord.payroll_period_id == period.id)
            ).one()
            gross, deductions, net = (float(v or 0) for v in totals)
            status = period.status.value
        result.append(
            {
                "period": f"{year}-{month:02d}",
                "gross": _round2(gross),
                "deductions": _round2(deductions),
                "net": _round2(net),
                "status": status,
            }
        )
    return result


def department_attendance(
    db: Session, company_id: str, start_date: date, end_date: date
) -> list:
    """Aggregate attendance productivity by department across a date range."""
    from models.organization import Department

    rows = list(
        db.execute(
            select(Department.name, AttendanceDaily)
            .join(
                Employee,
                and_(
                    Employee.company_id == company_id,
                    Employee.department_id == Department.id,
                ),
            )
            .join(AttendanceDaily, AttendanceDaily.employee_id == Employee.id)
            .where(
                and_(
                    AttendanceDaily.company_id == company_id,
                    AttendanceDaily.attendance_date >= start_date,
                    AttendanceDaily.attendance_date <= end_date,
                )
            )
        ).all()
    )
    buckets: dict[str, dict] = {}
    for dept_name, rec in rows:
        key = dept_name or "Unassigned"
        bucket = buckets.setdefault(key, {"department": key, "present_days": 0, "late_count": 0})
        if rec.status == AttendanceStatus.PRESENT:
            bucket["present_days"] += 1
        if rec.late_minutes > 0:
            bucket["late_count"] += 1
    return [buckets[k] for k in sorted(buckets)]


def employee_growth(db: Session, company_id: str, months: int = 6) -> list:
    """Return monthly joiner counts and cumulative headcount for the trailing N months."""
    pairs = _latest_monthends(months, date.today())
    result = []
    cumulative = 0
    for year, month in pairs:
        last_day = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day)
        joins = db.scalar(
            select(func.count(Employee.id)).where(
                and_(
                    Employee.company_id == company_id,
                    Employee.joining_date.isnot(None),
                    Employee.joining_date <= month_end,
                    Employee.joining_date >= date(year, month, 1),
                )
            )
        )
        cumulative += int(joins or 0)
        result.append(
            {
                "month": f"{year}-{month:02d}",
                "joins": int(joins or 0),
                "total": cumulative,
            }
        )
    return result