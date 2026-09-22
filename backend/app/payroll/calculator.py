from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from core.errors import ValidationError
from models.attendance import AttendanceDaily
from models.company import Company
from models.employee import Employee
from models.enums import (
    AttendanceStatus,
    CalculationType,
    EmployeeStatus,
    OvertimeStatus,
    PayrollComponentType,
    SalaryComponentType,
    StatutoryRuleType,
)
from models.leave import LeaveRequest
from models.overtime import OvertimeRecord
from models.payroll import PayrollPeriod
from models.salary import EmployeeSalary, SalaryStructure, SalaryStructureComponent
from services import shift_service

from payroll import lop, statutory


@dataclass
class CalcComponent:
    name: str
    component_type: PayrollComponentType
    amount: float
    is_statutory: bool = False
    reference_type: str | None = None
    reference_id: str | None = None
    sort_order: int = 0


@dataclass
class AttendanceSummary:
    working_days: int = 0
    present_days: int = 0
    leave_days: float = 0.0
    absent_days: int = 0
    lop_days: float = 0.0
    overtime_minutes: int = 0
    overtime_amount: float = 0.0


@dataclass
class PayrollCalcResult:
    employee_id: str
    attendance: AttendanceSummary
    components: list[CalcComponent] = field(default_factory=list)
    gross_salary: float = 0.0
    total_deductions: float = 0.0
    net_salary: float = 0.0


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def _eval_formula(expr: str | None, basic: float, gross: float) -> float:
    """Safely evaluate a simple arithmetic salary formula, returning 0 on failure."""
    if not expr:
        return 0.0
    try:
        return float(eval(expr, {"__builtins__": {}}, {"basic": basic, "gross": gross}))
    except Exception:
        return 0.0


def _component_type(component_type: SalaryComponentType) -> PayrollComponentType:
    return PayrollComponentType(component_type.value)


def compute_structure_components(
    structure: SalaryStructure, basic_salary: float
) -> list[CalcComponent]:
    """Compute a salary structure's components to CalcComponent rows."""
    basic = float(basic_salary or 0)
    out: list[CalcComponent] = []
    deferred: list[SalaryStructureComponent] = []
    for comp in structure.components or []:
        amount = 0.0
        ctype = comp.calculation_type
        if ctype == CalculationType.FIXED:
            amount = _round2(comp.value)
            out.append(
                CalcComponent(
                    name=comp.name,
                    component_type=_component_type(comp.component_type),
                    amount=amount,
                    sort_order=int(comp.sort_order or 0),
                )
            )
        elif ctype == CalculationType.PERCENTAGE_OF_BASIC:
            amount = _round2(float(comp.value or 0) / 100 * basic)
            out.append(
                CalcComponent(
                    name=comp.name,
                    component_type=_component_type(comp.component_type),
                    amount=amount,
                    sort_order=int(comp.sort_order or 0),
                )
            )
        else:
            deferred.append(comp)
    provisional_gross = basic + sum(
        c.amount for c in out if c.component_type == PayrollComponentType.EARNING
    )
    for comp in deferred:
        if comp.calculation_type == CalculationType.PERCENTAGE_OF_GROSS:
            amount = _round2(float(comp.value or 0) / 100 * provisional_gross)
        else:
            amount = _round2(_eval_formula(comp.formula, basic, provisional_gross))
        out.append(
            CalcComponent(
                name=comp.name,
                component_type=_component_type(comp.component_type),
                amount=amount,
                sort_order=int(comp.sort_order or 0),
            )
        )
    return out


def _active_salary(
    db: Session, company_id: str, employee_id: str, as_on: date
) -> EmployeeSalary | None:
    """Return the salary effective for an employee on a date, or None."""
    return db.scalar(
        select(EmployeeSalary)
        .where(
            and_(
                EmployeeSalary.company_id == company_id,
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.effective_from <= as_on,
                or_(
                    EmployeeSalary.effective_to.is_(None),
                    EmployeeSalary.effective_to >= as_on,
                ),
            )
        )
        .order_by(EmployeeSalary.effective_from.desc())
        .limit(1)
    )


def _resolve_active_salary(db: Session, company_id: str, employee_id: str, as_on: date):
    """Try employee_service.active_salary, falling back to a direct query."""
    try:
        from services import employee_service

        fn = getattr(employee_service, "active_salary", None)
        if callable(fn):
            return fn(db, company_id, employee_id, as_on)
    except Exception:
        pass
    return _active_salary(db, company_id, employee_id, as_on)


def _holidays_between(db: Session, company_id: str, start: date, end: date) -> list[date]:
    """Return holiday dates for a company within a range."""
    from models.leave import Holiday

    return list(
        db.scalars(
            select(Holiday.holiday_date).where(
                and_(
                    Holiday.company_id == company_id,
                    Holiday.holiday_date >= start,
                    Holiday.holiday_date <= end,
                )
            )
        )
    )


def _resolve_holidays(db: Session, company_id: str, start: date, end: date) -> list[date]:
    """Try holiday_service.holidays_between, falling back to a direct query."""
    try:
        from services import holiday_service

        fn = getattr(holiday_service, "holidays_between", None)
        if callable(fn):
            result = fn(db, company_id, start, end)
            if result is not None:
                return [d if not isinstance(d, date) else d for d in result]
    except Exception:
        pass
    return _holidays_between(db, company_id, start, end)


def _approved_leave_days_between(
    db: Session, company_id: str, employee_id: str, start: date, end: date
) -> float:
    """Count approved leave days overlapping a date range for an employee."""
    from models.enums import LeaveStatus

    requests = list(
        db.scalars(
            select(LeaveRequest).where(
                and_(
                    LeaveRequest.company_id == company_id,
                    LeaveRequest.employee_id == employee_id,
                    LeaveRequest.status == LeaveStatus.APPROVED,
                    LeaveRequest.start_date <= end,
                    LeaveRequest.end_date >= start,
                )
            )
        )
    )
    total = 0.0
    for req in requests:
        overlap = (min(req.end_date, end) - max(req.start_date, start)).days + 1
        overlap = max(0, overlap)
        total += overlap * (0.5 if req.is_half_day else 1.0)
    return total


def _resolve_leave_days(
    db: Session, company_id: str, employee_id: str, start: date, end: date
) -> float:
    """Try leave_service.approved_leave_days_between, falling back to a direct query."""
    try:
        from services import leave_service

        fn = getattr(leave_service, "approved_leave_days_between", None)
        if callable(fn):
            return float(fn(db, company_id, employee_id, start, end) or 0)
    except Exception:
        pass
    return _approved_leave_days_between(db, company_id, employee_id, start, end)


def _overtime_records_between(
    db: Session, company_id: str, employee_id: str, start: date, end: date
) -> list[OvertimeRecord]:
    """Return approved overtime records for an employee within a range."""
    return list(
        db.scalars(
            select(OvertimeRecord).where(
                and_(
                    OvertimeRecord.company_id == company_id,
                    OvertimeRecord.employee_id == employee_id,
                    OvertimeRecord.date >= start,
                    OvertimeRecord.date <= end,
                    OvertimeRecord.status == OvertimeStatus.APPROVED,
                )
            )
        )
    )


def _overtime_summary(
    db: Session,
    company_id: str,
    employee_id: str,
    start: date,
    end: date,
    company: Company,
    period: PayrollPeriod,
) -> tuple[int, float]:
    """Return (approved_ot_minutes, ot_amount) for an employee in a range."""
    try:
        from services import overtime_service

        fn = getattr(overtime_service, "approved_overtime_minutes_between", None)
        if callable(fn):
            minutes = int(fn(db, company_id, employee_id, start, end) or 0)
            total_amount = 0.0
        else:
            minutes, total_amount = 0, 0.0
    except Exception:
        fn = None
        minutes = 0
        total_amount = 0.0
    if fn is None:
        records = _overtime_records_between(db, company_id, employee_id, start, end)
        minutes = sum(int(r.minutes or 0) for r in records)
        total_amount = sum(
            float(r.amount or 0)
            for r in records
            if float(r.amount or 0) > 0
        )
        records_without_amount = [r for r in records if not float(r.amount or 0)]
        if records_without_amount:
            salary = _resolve_active_salary(db, company_id, employee_id, period.end_date)
            gross = float(salary.gross_salary if salary is not None else 0)
            rate = lop.daily_rate(company, gross, period.month, period.year, None)
            fallback = sum(float(r.minutes or 0) / 60 * rate for r in records_without_amount)
            total_amount += fallback
        return minutes, _round2(total_amount)
    records = _overtime_records_between(db, company_id, employee_id, start, end)
    total_amount = sum(float(r.amount or 0) for r in records if float(r.amount or 0) > 0)
    records_without_amount = [r for r in records if not float(r.amount or 0)]
    if records_without_amount:
        salary = _resolve_active_salary(db, company_id, employee_id, period.end_date)
        gross = float(salary.gross_salary if salary is not None else 0)
        rate = lop.daily_rate(company, gross, period.month, period.year, None)
        fallback = sum(float(r.minutes or 0) / 60 * rate for r in records_without_amount)
        total_amount += fallback
    return minutes, _round2(total_amount)


def attendance_summary(
    db: Session,
    company_id: str,
    employee_id: str,
    period: PayrollPeriod,
    *,
    holidays: list[date],
    weekly_off_days: list[int],
    company: Company,
) -> AttendanceSummary:
    """Aggregate attendance metrics for an employee across a payroll period."""
    holiday_set = set(holidays or [])
    off_set = set(weekly_off_days or [])
    total_days = (period.end_date - period.start_date).days + 1
    weekend_days = sum(
        1
        for offset in range(total_days)
        if (period.start_date + timedelta(days=offset)).weekday() in off_set
    )
    working_days = max(0, total_days - weekend_days)

    rows = list(
        db.scalars(
            select(AttendanceDaily).where(
                and_(
                    AttendanceDaily.company_id == company_id,
                    AttendanceDaily.employee_id == employee_id,
                    AttendanceDaily.attendance_date >= period.start_date,
                    AttendanceDaily.attendance_date <= period.end_date,
                )
            )
        )
    )
    present_days = sum(1 for r in rows if r.status == AttendanceStatus.PRESENT)
    absent_days = sum(
        1
        for r in rows
        if r.status == AttendanceStatus.ABSENT
        and r.attendance_date.weekday() not in off_set
        and r.attendance_date not in holiday_set
    )

    leave_days = _resolve_leave_days(db, company_id, employee_id, period.start_date, period.end_date)
    lop_days = max(0.0, absent_days - leave_days)

    overtime_minutes, overtime_amount = _overtime_summary(
        db, company_id, employee_id, period.start_date, period.end_date, company, period
    )
    return AttendanceSummary(
        working_days=working_days,
        present_days=present_days,
        leave_days=_round2(leave_days),
        absent_days=absent_days,
        lop_days=_round2(lop_days),
        overtime_minutes=overtime_minutes,
        overtime_amount=overtime_amount,
    )


def _first_due_loan_id(
    db: Session, company_id: str, employee_id: str, period: PayrollPeriod
) -> str | None:
    """Return the loan id with the earliest pending due installment for an employee."""
    from models.loan import EmployeeLoan, LoanInstallment

    row = db.execute(
        select(LoanInstallment.loan_id)
        .join(EmployeeLoan, EmployeeLoan.id == LoanInstallment.loan_id)
        .where(
            and_(
                EmployeeLoan.company_id == company_id,
                EmployeeLoan.employee_id == employee_id,
                LoanInstallment.status == "PENDING",
                LoanInstallment.due_date <= period.end_date,
            )
        )
        .order_by(LoanInstallment.due_date)
        .limit(1)
    ).first()
    return str(row[0]) if row is not None else None


def calculate_employee(
    db: Session,
    company_id: str,
    period: PayrollPeriod,
    employee: Employee,
) -> PayrollCalcResult:
    """Compute the full payroll breakdown for one employee in a period."""
    salary = _resolve_active_salary(db, company_id, employee.id, period.end_date)
    if salary is None:
        raise ValidationError(f"No active salary for {employee.employee_code}")

    if salary.structure is not None:
        components = compute_structure_components(salary.structure, salary.basic_salary)
    else:
        components = [
            CalcComponent(
                name="Basic salary",
                component_type=PayrollComponentType.EARNING,
                amount=_round2(salary.basic_salary),
                sort_order=0,
            )
        ]

    holidays = _resolve_holidays(db, company_id, period.start_date, period.end_date)
    shift = shift_service.get_employee_shift(db, company_id, employee.id, period.start_date)
    weekly_off = list(shift.weekly_off_days or []) if shift is not None else []
    company = db.get(Company, company_id)

    attendance = attendance_summary(
        db,
        company_id,
        employee.id,
        period,
        holidays=holidays,
        weekly_off_days=weekly_off,
        company=company,
    )

    earnings = [c for c in components if c.component_type == PayrollComponentType.EARNING]
    deductions = [c for c in components if c.component_type == PayrollComponentType.DEDUCTION]
    deduction_extras: list[CalcComponent] = []

    lop_value = lop.lop_amount(
        company,
        salary.gross_salary,
        attendance.lop_days,
        period.month,
        period.year,
        attendance.working_days,
    )
    if lop_value > 0:
        deduction_extras.append(
            CalcComponent(
                name="Loss of Pay",
                component_type=PayrollComponentType.DEDUCTION,
                amount=lop_value,
                is_statutory=False,
                sort_order=0,
            )
        )

    defaults = statutory.statutory_defaults(company)
    pf_rule = statutory.resolve_rules(db, company_id, StatutoryRuleType.PF)
    esi_rule = statutory.resolve_rules(db, company_id, StatutoryRuleType.ESI)
    pt_rule = statutory.resolve_rules(db, company_id, StatutoryRuleType.PT)
    tds_rule = statutory.resolve_rules(db, company_id, StatutoryRuleType.TDS)

    pf_base = max(salary.basic_salary, min(salary.gross_salary, float(defaults["pf_threshold"])))
    pf = statutory.calculate_pf(pf_base, pf_rule, defaults)
    esi_employee, _esi_employer = statutory.calculate_esi(salary.gross_salary, esi_rule, defaults)
    pt = statutory.calculate_pt(salary.gross_salary, company.statutory_state, pt_rule)
    tds = statutory.calculate_tds(salary.gross_salary * 12, tds_rule)
    deduction_extras.extend(
        [
            CalcComponent(
                name="PF",
                component_type=PayrollComponentType.DEDUCTION,
                amount=pf,
                is_statutory=True,
                sort_order=10,
            ),
            CalcComponent(
                name="ESI",
                component_type=PayrollComponentType.DEDUCTION,
                amount=esi_employee,
                is_statutory=True,
                sort_order=11,
            ),
            CalcComponent(
                name="Professional Tax",
                component_type=PayrollComponentType.DEDUCTION,
                amount=pt,
                is_statutory=True,
                sort_order=12,
            ),
            CalcComponent(
                name="TDS",
                component_type=PayrollComponentType.DEDUCTION,
                amount=tds,
                is_statutory=True,
                sort_order=13,
            ),
        ]
    )

    try:
        from services import loan_service

        loan_emi = float(loan_service.due_instalment_amount(db, company_id, employee.id, period) or 0)
    except Exception:
        loan_emi = 0.0
    if loan_emi > 0:
        loan_id = _first_due_loan_id(db, company_id, employee.id, period)
        deduction_extras.append(
            CalcComponent(
                name="Loan EMI",
                component_type=PayrollComponentType.DEDUCTION,
                amount=_round2(loan_emi),
                is_statutory=False,
                reference_type="loan",
                reference_id=loan_id,
                sort_order=20,
            )
        )

    try:
        from services import advance_service

        advance_ded = float(
            advance_service.approved_advance_deduction(db, company_id, employee.id, period) or 0
        )
    except Exception:
        advance_ded = 0.0
    if advance_ded > 0:
        deduction_extras.append(
            CalcComponent(
                name="Salary Advance",
                component_type=PayrollComponentType.DEDUCTION,
                amount=_round2(advance_ded),
                is_statutory=False,
                reference_type="advance",
                sort_order=21,
            )
        )

    overtime_earning: CalcComponent | None = None
    if company.overtime_enabled and attendance.overtime_amount > 0:
        overtime_earning = CalcComponent(
            name="Overtime",
            component_type=PayrollComponentType.EARNING,
            amount=attendance.overtime_amount,
            is_statutory=False,
            sort_order=30,
        )
        earnings.append(overtime_earning)

    gross_salary = _round2(sum(c.amount for c in earnings))
    total_deductions = _round2(sum(c.amount for c in deductions) + sum(c.amount for c in deduction_extras))
    net_salary = _round2(gross_salary - total_deductions)

    all_components = list(components)
    all_components.extend(deduction_extras)
    if overtime_earning is not None:
        all_components.append(overtime_earning)

    return PayrollCalcResult(
        employee_id=employee.id,
        attendance=attendance,
        components=all_components,
        gross_salary=gross_salary,
        total_deductions=total_deductions,
        net_salary=net_salary,
    )