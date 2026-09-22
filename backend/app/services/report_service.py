import csv
from datetime import date
from pathlib import Path

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from core.errors import NotFoundError
from models.attendance import AttendanceDaily
from models.employee import Employee
from models.enums import AttendanceStatus, PayrollComponentType
from models.loan import EmployeeLoan
from models.payroll import PayrollComponent, PayrollPeriod, PayrollRecord

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPORT_ROOT = _REPO_ROOT / "backend/generated/reports"


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def _employee_full_name(emp: Employee) -> str:
    return f"{emp.first_name} {emp.last_name or ''}".strip()


def _report_path(prefix: str, ext: str) -> Path:
    _REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    return _REPORT_ROOT / f"{prefix}.{ext}"


def _to_csv(rows: list[dict], path: str) -> None:
    """Write list-of-dict rows to a CSV file."""
    fields = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _to_xlsx(rows: list[dict], path: str) -> None:
    """Write list-of-dict rows to an XLSX workbook."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    header = list(rows[0].keys()) if rows else []
    ws.append(header)
    for row in rows:
        ws.append([row.get(col) for col in header])
    wb.save(path)


def _to_pdf_tabular(rows: list[dict], path: str, title: str) -> None:
    """Render list-of-dict rows as a tabular PDF report."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    doc = SimpleDocTemplate(
        path,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 6 * mm)]
    if not rows:
        elements.append(Paragraph("No data", styles["Normal"]))
        doc.build(elements)
        return
    header = list(rows[0].keys())
    data = [[str(h) for h in header]]
    for row in rows:
        data.append([str(row.get(col, "")) for col in header])
    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)


def attendance_daily_rows(
    db: Session,
    company_id: str,
    from_date: date,
    to_date: date,
    format: str = "json",
) -> dict:
    """Export per-day attendance rows for a company across a date range."""
    stmt = (
        select(AttendanceDaily)
        .join(Employee, Employee.id == AttendanceDaily.employee_id)
        .where(
            and_(
                AttendanceDaily.company_id == company_id,
                AttendanceDaily.attendance_date >= from_date,
                AttendanceDaily.attendance_date <= to_date,
            )
        )
        .options(joinedload(AttendanceDaily.employee), joinedload(AttendanceDaily.shift))
        .order_by(AttendanceDaily.attendance_date, Employee.employee_code)
    )
    rows = []
    for rec in db.scalars(stmt):
        shift_name = rec.shift.name if rec.shift is not None else ""
        rows.append(
            {
                "employee_code": rec.employee.employee_code,
                "employee_name": _employee_full_name(rec.employee),
                "date": rec.attendance_date.isoformat(),
                "shift": shift_name,
                "first_in": rec.first_in.isoformat() if rec.first_in else "",
                "last_out": rec.last_out.isoformat() if rec.last_out else "",
                "worked_minutes": rec.worked_minutes,
                "late": rec.late_minutes,
                "early": rec.early_leave_minutes,
                "ot": rec.overtime_minutes,
                "status": rec.status.value,
            }
        )
    path = None
    if format != "json" and rows:
        stamp = f"{from_date.isoformat()}_{to_date.isoformat()}"
        path = _report_path(f"attendance_daily_{stamp}", format)
        if format == "csv":
            _to_csv(rows, str(path))
        elif format == "xlsx":
            _to_xlsx(rows, str(path))
        elif format == "pdf":
            _to_pdf_tabular(rows, str(path), "Attendance Daily Report")
        else:
            path = None
    return {"rows": rows, "path": str(path) if path else None, "format": format}


def attendance_monthly_rows(db: Session, company_id: str, month: int, year: int) -> list:
    """Aggregate per-employee attendance for a calendar month."""
    start = date(year, month, 1)
    last_day = __import__("calendar").monthrange(year, month)[1]
    end = date(year, month, last_day)
    records = list(
        db.scalars(
            select(AttendanceDaily)
            .join(Employee, Employee.id == AttendanceDaily.employee_id)
            .where(
                and_(
                    AttendanceDaily.company_id == company_id,
                    AttendanceDaily.attendance_date >= start,
                    AttendanceDaily.attendance_date <= end,
                )
            )
            .options(joinedload(AttendanceDaily.employee))
        )
    )
    by_employee: dict[str, dict] = {}
    for rec in records:
        emp = rec.employee
        key = emp.id
        bucket = by_employee.setdefault(
            key,
            {
                "employee_code": emp.employee_code,
                "employee_name": _employee_full_name(emp),
                "present": 0,
                "absent": 0,
                "leave": 0,
                "half_day": 0,
                "missing_punch": 0,
                "holiday": 0,
                "weekend": 0,
                "total_work_minutes": 0,
                "late_minutes": 0,
                "ot_minutes": 0,
                "days": 0,
            },
        )
        bucket["days"] += 1
        bucket["total_work_minutes"] += rec.worked_minutes
        bucket["late_minutes"] += rec.late_minutes
        bucket["ot_minutes"] += rec.overtime_minutes
        status = rec.status
        if status == AttendanceStatus.PRESENT:
            bucket["present"] += 1
        elif status == AttendanceStatus.ABSENT:
            bucket["absent"] += 1
        elif status == AttendanceStatus.LEAVE:
            bucket["leave"] += 1
        elif status == AttendanceStatus.HALF_DAY:
            bucket["half_day"] += 1
        elif status == AttendanceStatus.MISSING_PUNCH:
            bucket["missing_punch"] += 1
        elif status == AttendanceStatus.HOLIDAY:
            bucket["holiday"] += 1
        elif status == AttendanceStatus.WEEKEND:
            bucket["weekend"] += 1
    return list(by_employee.values())


def _period_or_404(db: Session, company_id: str, period_id: str) -> PayrollPeriod:
    period = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.id == period_id,
            PayrollPeriod.company_id == company_id,
        )
    )
    if period is None:
        raise NotFoundError("Payroll period")
    return period


def payroll_salary_register_rows(
    db: Session, company_id: str, period_id: str
) -> list:
    """Build a salary register from payroll records and components."""
    _period_or_404(db, company_id, period_id)
    records = list(
        db.scalars(
            select(PayrollRecord)
            .where(PayrollRecord.payroll_period_id == period_id)
            .options(joinedload(PayrollRecord.employee))
        )
    )
    basic_names = {"basic", "basic salary", "basic pay"}
    rows = []
    for rec in records:
        components = {c.name: c.amount for c in list(rec.components)}
        basic = next(
            (amount for name, amount in components.items() if name.strip().lower() in basic_names),
            0.0,
        )
        row = {
            "employee_code": rec.employee.employee_code,
            "employee_name": _employee_full_name(rec.employee),
            "basic": _round2(basic),
            "gross": rec.gross_salary,
            "deductions": rec.total_deductions,
            "net": rec.net_salary,
        }
        row.update({name: _round2(amount) for name, amount in components.items()})
        rows.append(row)
    return rows


def payroll_monthly_rows(db: Session, company_id: str, period_id: str) -> list:
    """Build monthly payroll rows per employee for a period."""
    _period_or_404(db, company_id, period_id)
    records = list(
        db.scalars(
            select(PayrollRecord)
            .where(PayrollRecord.payroll_period_id == period_id)
            .options(joinedload(PayrollRecord.employee))
            .order_by(PayrollRecord.created_at)
        )
    )
    return [
        {
            "employee_code": rec.employee.employee_code,
            "employee_name": _employee_full_name(rec.employee),
            "working_days": rec.working_days,
            "present_days": rec.present_days,
            "leave_days": rec.leave_days,
            "lop_days": rec.lop_days,
            "overtime_minutes": rec.overtime_minutes,
            "gross": rec.gross_salary,
            "deductions": rec.total_deductions,
            "net": rec.net_salary,
            "status": rec.status.value,
        }
        for rec in records
    ]


def deduction_summary_rows(db: Session, company_id: str, period_id: str) -> list:
    """Summarize deductions by component name across a period."""
    _period_or_404(db, company_id, period_id)
    stmt = (
        select(PayrollComponent.name, func.sum(PayrollComponent.amount))
        .where(
            and_(
                PayrollComponent.company_id == company_id,
                PayrollComponent.payroll_record_id.in_(
                    select(PayrollRecord.id).where(PayrollRecord.payroll_period_id == period_id)
                ),
                PayrollComponent.component_type == PayrollComponentType.DEDUCTION,
            )
        )
        .group_by(PayrollComponent.name)
        .order_by(PayrollComponent.name)
    )
    return [{"name": name, "amount": _round2(total)} for name, total in db.execute(stmt).all()]


def _resolve_period_id(
    db: Session, company_id: str, period_id: str | None, month: int | None, year: int | None
) -> str:
    """Resolve a payroll period id from explicit id or month/year."""
    if period_id:
        _period_or_404(db, company_id, period_id)
        return period_id
    if not month or not year:
        raise NotFoundError("Payroll period")
    period = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.company_id == company_id,
            PayrollPeriod.month == month,
            PayrollPeriod.year == year,
        )
    )
    if period is None:
        raise NotFoundError("Payroll period")
    return str(period.id)


def export_report(
    db: Session, company_id: str, report_name: str, rows: list[dict], fmt: str
) -> str | None:
    """Write report rows to a csv/xlsx/pdf file and return the path."""
    if fmt not in ("csv", "xlsx", "pdf") or not rows:
        return None
    path = _report_path(report_name, fmt)
    if fmt == "csv":
        _to_csv(rows, str(path))
    elif fmt == "xlsx":
        _to_xlsx(rows, str(path))
    else:
        _to_pdf_tabular(rows, str(path), report_name.replace("_", " ").title())
    return str(path.resolve())


def loans_report_rows(
    db: Session, company_id: str, employee_id: str | None = None
) -> list:
    """List loan records with employee details for reporting."""
    stmt = (
        select(EmployeeLoan)
        .where(EmployeeLoan.company_id == company_id)
        .options(joinedload(EmployeeLoan.employee))
        .order_by(EmployeeLoan.created_at.desc())
    )
    if employee_id:
        stmt = stmt.where(EmployeeLoan.employee_id == employee_id)
    rows = []
    for loan in db.scalars(stmt):
        rows.append(
            {
                "loan_id": str(loan.id),
                "employee_code": loan.employee.employee_code,
                "employee_name": _employee_full_name(loan.employee),
                "loan_amount": loan.loan_amount,
                "installment_amount": loan.installment_amount,
                "number_of_installments": loan.number_of_installments,
                "paid_installments": loan.paid_installments,
                "outstanding_amount": _round2(loan.outstanding_amount),
                "start_date": loan.start_date.isoformat() if loan.start_date else "",
                "status": loan.status.value,
                "remarks": loan.remarks or "",
            }
        )
    return rows