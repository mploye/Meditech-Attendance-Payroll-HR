import calendar
from pathlib import Path

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from core.errors import NotFoundError
from models.enums import PayrollRecordStatus, PayslipStatus
from models.payroll import PayrollRecord
from models.payslip import Payslip
from models.company import Company

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATION_ROOT = _REPO_ROOT / "backend/generated"
_PAYSLIP_DIR = _GENERATION_ROOT / "payslips"
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_COMPANY_LOGO = _STATIC_DIR / "company_logo.png"


def _company_address(company: Company) -> str:
    """Render a readable address block from the company profile fields."""
    if company.address:
        return company.address
    parts = [part for part in (company.city, company.state, company.pincode) if part]
    return ", ".join(parts) if parts else ""


def _company_header(company: Company) -> "Table":
    """Return a payslip header table with the company logo, name and address."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, Table, TableStyle

    left: list = []
    if _COMPANY_LOGO.exists():
        left.append(Image(str(_COMPANY_LOGO), width=18 * mm, height=None))

    name = company.legal_name or company.name
    address = _company_address(company)
    title_style = ParagraphStyle(
        "CompanyTitle",
        parent=ParagraphStyle("Normal"),
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor="#1f2937",
        spaceAfter=2,
    )
    addr_style = ParagraphStyle(
        "CompanyAddress",
        parent=ParagraphStyle("Normal"),
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor="#4b5563",
    )
    right = [Paragraph(name, title_style)]
    if address:
        right.append(Paragraph(address.replace(", ", ",<br/>"), addr_style))

    rows = []
    if left:
        rows = [[left[0], right]]
    else:
        rows = [[right]]

    header = Table(rows, colWidths=[22 * mm, 138 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return header


def _ensure_dirs(source: Payslip) -> Path:
    output = _PAYSLIP_DIR
    output.mkdir(parents=True, exist_ok=True)
    return output


def _period_label(source: Payslip) -> str:
    period = source.period
    return f"{calendar.month_name[period.month]} {period.year}"


def _employee_display(source: Payslip) -> tuple[str, str, str, str]:
    emp = source.employee
    name = f"{emp.first_name} {emp.last_name or ''}".strip()
    department = emp.department.name if emp.department is not None else ""
    designation = emp.designation.name if emp.designation is not None else ""
    return emp.employee_code, name, department, designation


def _payslip_elements(source: Payslip, record: PayrollRecord, company: Company) -> list:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    emp_code, emp_name, department, designation = _employee_display(source)
    period_label = _period_label(source)

    header = _company_header(company)

    info_rows = [
        ["Employee ID", emp_code],
        ["Employee Name", emp_name],
        ["Department", department],
        ["Designation", designation],
        ["Period", period_label],
    ]
    attendance = source.payroll_record
    info_rows.extend(
        [
            ["Working Days", str(attendance.working_days)],
            ["Present Days", str(attendance.present_days)],
            ["Leave Days", str(attendance.leave_days)],
            ["LOP Days", str(attendance.lop_days)],
            ["Overtime Minutes", str(attendance.overtime_minutes)],
        ]
    )
    info = Table([[k, v] for k, v in info_rows], colWidths=[45 * mm, 115 * mm])
    info.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    earnings = [c for c in record.components if c.component_type.value == "EARNING"]
    deductions = [c for c in record.components if c.component_type.value == "DEDUCTION"]
    earn_table = Table(
        [["Earnings", "Amount"],
         *[[c.name, f"{c.amount:.2f}"] for c in earnings]],
        colWidths=[120 * mm, 40 * mm],
    )
    earn_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    ded_table = Table(
        [["Deductions", "Amount"],
         *[[c.name, f"{c.amount:.2f}"] for c in deductions]],
        colWidths=[120 * mm, 40 * mm],
    )
    ded_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    summary = Table(
        [
            ["Gross Salary", f"{source.gross:.2f}"],
            ["Total Deductions", f"{source.total_deductions:.2f}"],
            ["Net Pay", f"{source.net:.2f}"],
        ],
        colWidths=[80 * mm, 40 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 2), (-1, 2), colors.lightgreen),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    return [
        header,
        Spacer(1, 2 * mm),
        Paragraph(
            f"<b>Payslip - {period_label}</b>",
            ParagraphStyle(
                "PayslipSubtitle",
                parent=ParagraphStyle("Normal"),
                fontName="Helvetica-Bold",
                fontSize=12,
                textColor="#374151",
            ),
        ),
        Spacer(1, 4 * mm),
        info,
        Spacer(1, 4 * mm),
        earn_table,
        Spacer(1, 3 * mm),
        ded_table,
        Spacer(1, 4 * mm),
        summary,
    ]


def build_payslip_pdf(db: Session, payslip: Payslip) -> str:
    """Render a payslip PDF and return its absolute file path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    output_dir = _ensure_dirs(payslip)
    emp_code, _name, _dept, _desig = _employee_display(payslip)
    filename = f"{payslip.period.year}-{payslip.period.month:02d}-{emp_code}.pdf"
    filepath = output_dir / filename
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    record = payslip.payroll_record
    company = db.get(Company, payslip.company_id)
    doc.build(_payslip_elements(payslip, record, company))
    return str(filepath.resolve())


def generate_for_period(db: Session, company_id: str, period_id: str) -> dict:
    """Generate or regenerate payslips for all payable records in a period."""
    from models.payroll import PayrollPeriod

    period = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.id == period_id,
            PayrollPeriod.company_id == company_id,
        )
    )
    if period is None:
        raise NotFoundError("Payroll period")
    records = list(
        db.scalars(
            select(PayrollRecord)
            .where(PayrollRecord.payroll_period_id == period.id)
            .options(joinedload(PayrollRecord.employee))
        )
    )
    generated = 0
    skipped = 0
    failures: list[str] = []
    for record in records:
        if record.status not in (
            PayrollRecordStatus.APPROVED,
            PayrollRecordStatus.LOCKED,
        ):
            skipped += 1
            continue
        try:
            with db.begin_nested():
                existing = db.scalar(
                    select(Payslip).where(
                        Payslip.company_id == company_id,
                        Payslip.payroll_record_id == record.id,
                        Payslip.employee_id == record.employee_id,
                    )
                )
                if existing is None:
                    slip = Payslip(
                        company_id=company_id,
                        payroll_record_id=record.id,
                        employee_id=record.employee_id,
                        payroll_period_id=period.id,
                        gross=record.gross_salary,
                        total_deductions=record.total_deductions,
                        net=record.net_salary,
                        status=PayslipStatus.GENERATED,
                    )
                    db.add(slip)
                    db.flush()
                    slip.pdf_path = build_payslip_pdf(db, slip)
                else:
                    existing.gross = record.gross_salary
                    existing.total_deductions = record.total_deductions
                    existing.net = record.net_salary
                    existing.status = PayslipStatus.GENERATED
                    existing.pdf_path = build_payslip_pdf(db, existing)
                generated += 1
        except Exception as exc:
            code = record.employee.employee_code if record.employee is not None else str(record.employee_id)
            failures.append(f"{code}: {exc}")
    db.commit()
    return {
        "period_id": period_id,
        "generated": generated,
        "skipped": skipped,
        "failures": failures,
    }


def list_payslips(
    db: Session,
    company_id: str,
    payroll_period_id: str | None = None,
    employee_id: str | None = None,
) -> list[Payslip]:
    """List payslips for a company with optional period/employee filters."""
    stmt = (
        select(Payslip)
        .where(Payslip.company_id == company_id)
        .options(joinedload(Payslip.employee))
    )
    if payroll_period_id:
        stmt = stmt.where(Payslip.payroll_period_id == payroll_period_id)
    if employee_id:
        stmt = stmt.where(Payslip.employee_id == employee_id)
    return list(db.scalars(stmt.order_by(Payslip.generated_at.desc())))


def get_payslip(db: Session, company_id: str, payslip_id: str) -> Payslip:
    """Return a single payslip scoped to a company."""
    slip = db.scalar(
        select(Payslip).where(
            Payslip.id == payslip_id,
            Payslip.company_id == company_id,
        )
    )
    if slip is None:
        raise NotFoundError("Payslip")
    return slip


def mark_downloaded(db: Session, payslip: Payslip) -> Payslip:
    """Mark a payslip as downloaded."""
    payslip.status = PayslipStatus.DOWNLOADED
    db.commit()
    db.refresh(payslip)
    return payslip


def employee_payslips(
    db: Session,
    company_id: str,
    employee_id: str,
    month: int | None = None,
    year: int | None = None,
) -> list[Payslip]:
    """List an employee's payslips with optional month/year filtering."""
    from models.payroll import PayrollPeriod

    stmt = (
        select(Payslip)
        .join(PayrollPeriod, PayrollPeriod.id == Payslip.payroll_period_id)
        .where(
            and_(
                Payslip.company_id == company_id,
                Payslip.employee_id == employee_id,
            )
        )
    )
    if year:
        stmt = stmt.where(PayrollPeriod.year == year)
    if month:
        stmt = stmt.where(PayrollPeriod.month == month)
    return list(db.scalars(stmt.order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc())))