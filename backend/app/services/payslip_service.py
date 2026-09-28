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
    """Return a branded payslip header with company logo, name and address."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, Table, TableStyle
    from reportlab.lib import colors

    left: list = []
    if _COMPANY_LOGO.exists():
        left.append(Image(str(_COMPANY_LOGO), width=24 * mm, height=None))

    name = company.legal_name or company.name
    address = _company_address(company)
    title_style = ParagraphStyle(
        "CompanyTitle", parent=ParagraphStyle("Normal"),
        fontName="Helvetica-Bold", fontSize=18, leading=21,
        textColor="#ffffff", spaceAfter=1,
    )
    addr_style = ParagraphStyle(
        "CompanyAddress", parent=ParagraphStyle("Normal"),
        fontName="Helvetica", fontSize=9, leading=12,
        textColor="#dbeafe",
    )
    right = [Paragraph(name, title_style)]
    if address:
        right.append(Paragraph(address.replace(", ", ",<br/>"), addr_style))

    rows = []
    if left:
        rows = [[left[0], right]]
    else:
        rows = [[right]]

    header = Table(rows, colWidths=[30 * mm, 130 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2563eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 8),
        ("RIGHTPADDING", (1, 0), (1, 0), 12),
        ("LEFTPADDING", (1, 0), (1, 0), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
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


def _payslip_summary(source: Payslip, record: "PayrollRecord") -> dict[str, object]:
    """Return plain-data summary used by HTML/JSON/Text builders."""
    emp_code, emp_name, department, designation = _employee_display(source)
    period_label = _period_label(source)
    attendance = source.payroll_record
    earnings = [c for c in record.components if c.component_type.value == "EARNING"]
    deductions = [c for c in record.components if c.component_type.value == "DEDUCTION"]
    return {
        "employee_code": emp_code,
        "employee_name": emp_name,
        "department": department,
        "designation": designation,
        "period": period_label,
        "working_days": attendance.working_days,
        "present_days": attendance.present_days,
        "leave_days": attendance.leave_days,
        "lop_days": attendance.lop_days,
        "overtime_minutes": attendance.overtime_minutes,
        "earnings": [{"name": c.name, "amount": round(float(c.amount), 2)} for c in earnings],
        "deductions": [{"name": c.name, "amount": round(float(c.amount), 2)} for c in deductions],
        "gross": round(float(source.gross), 2),
        "total_deductions": round(float(source.total_deductions), 2),
        "net": round(float(source.net), 2),
    }


def build_payslip_html(db: Session, payslip: Payslip) -> str:
    """Render the payslip as a self-contained HTML document (AI-readable)."""
    from models.company import Company
    record = payslip.payroll_record
    company = db.get(Company, payslip.company_id)
    s = _payslip_summary(payslip, record)
    emp = payslip.employee
    comp_name = (company.legal_name or company.name) if company else "Company"
    rows = "".join(f"<tr><td>{e['name']}</td><td>₹{e['amount']:,.2f}</td></tr>" for e in s["earnings"])
    drows = "".join(f"<tr><td>{e['name']}</td><td>₹{e['amount']:,.2f}</td></tr>" for e in s["deductions"])
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Payslip - {s['employee_code']} - {s['period']}</title><style>body{{font-family:Helvetica,Arial,sans-serif;max-width:800px;margin:24px auto;color:#1f2937}}header{{background:#2563eb;color:#fff;padding:16px 20px;border-radius:8px}}header h1{{margin:0;font-size:20px}}header p{{margin:4px 0 0;color:#dbeafe;font-size:11px}}.banner{{background:#1e40af;color:#fff;text-align:center;font-size:20px;font-weight:bold;padding:10px;margin:12px 0;border-radius:4px}}.box{{display:flex;gap:16px;margin:12px 0}}.box table{{width:100%;border-collapse:collapse}}.box td{{padding:5px 8px;border:1px solid #cbd5e1;font-size:13px}}.box td.k{{background:#f1f5f9;font-weight:bold;width:40%}}.att{{display:flex;gap:16px}}.att table{{width:100%;border-collapse:collapse}}.att td{{padding:4px 8px;border:1px solid #cbd5e1;font-size:13px}}.att td.k{{background:#f1f5f9;font-weight:bold;width:50%}}.comp-table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}}.comp-table th{{background:#2563eb;color:#fff;padding:6px 8px;border:1px solid #2563eb}}.comp-table td{{padding:5px 8px;border:1px solid #e2e8f0}}.comp-table tr:last-child td{{background:#e0e7ff;font-weight:bold}}.summary{{margin-top:16px;font-size:14px}}.summary table{{width:100%;border-collapse:collapse}}.summary td{{padding:6px 8px;border:1px solid #cbd5e1}}.summary tr:last-child td{{background:#dcfce7;font-weight:bold;color:#166534}}.footer{{margin-top:16px;font-size:11px;color:#94a3b8}}</style></head><body><header><h1>{comp_name}</h1><p>{company.address if company and company.address else ""}</p></header><div class="banner">PAYSLIP</div><div class="box"><table><tr><td class="k">Employee</td><td>{s['employee_code']} — {s['employee_name']}</td></tr><tr><td class="k">Department</td><td>{s['department']} — {s['designation']}</td></tr><tr><td class="k">Period</td><td>{s['period']}</td></tr></table><table><tr><td class="k">Working</td><td>{s['working_days']}</td></tr><tr><td class="k">Present</td><td>{s['present_days']}</td></tr><tr><td class="k">Leave</td><td>{s['leave_days']}</td></tr><tr><td class="k">LOP</td><td>{s['lop_days']}</td></tr><tr><td class="k">Overtime</td><td>{s['overtime_minutes']} min</td></tr></table></div><div class="comp-table"><table><tr><th>Description</th><th>Amount (₹)</th><th>Type</th></tr>{rows}{drows}</table></div><div class="summary"><table><tr><td>Gross Salary</td><td>₹{s['gross']:,.2f}</td></tr><tr><td>Total Deductions</td><td>₹{s['total_deductions']:,.2f}</td></tr><tr><td>Net Pay</td><td>₹{s['net']:,.2f}</td></tr></table></div><div class="footer">Generated: {payslip.generated_at.isoformat() if payslip.generated_at else 'N/A'} | ID: {payslip.id} | Status: {payslip.status.value if payslip.status else 'N/A'}</div></body></html>"""


def build_payslip_json(db: Session, payslip: Payslip) -> dict[str, object]:
    """Return payslip data as a JSON-serializable dict (AI-readable)."""
    from models.company import Company
    record = payslip.payroll_record
    company = db.get(Company, payslip.company_id)
    s = _payslip_summary(payslip, record)
    return {
        "document_type": "payslip",
        "company": company.name if company else None,
        "employee": {"code": s["employee_code"], "name": s["employee_name"], "department": s["department"], "designation": s["designation"]},
        "period": s["period"],
        "attendance": {"working_days": s["working_days"], "present_days": s["present_days"], "leave_days": s["leave_days"], "lop_days": s["lop_days"], "overtime_minutes": s["overtime_minutes"]},
        "earnings": s["earnings"],
        "deductions": s["deductions"],
        "gross_salary": s["gross"],
        "total_deductions": s["total_deductions"],
        "net_pay": s["net"],
        "generated_at": payslip.generated_at.isoformat() if payslip.generated_at else None,
        "status": payslip.status.value if payslip.status else None,
        "payslip_id": str(payslip.id),
    }


def build_payslip_text(payslip: Payslip) -> str:
    """Return payslip data as plain text (AI-readable)."""
    s = _payslip_summary(payslip, payslip.payroll_record)
    lines = [
        f"PAYSLEET — {s['employee_name']} ({s['employee_code']})",
        f"Period: {s['period']} | Dept: {s['department']} | Designation: {s['designation']}",
        "-" * 50, "ATTENDANCE",
        f"  Working Days : {s['working_days']}", f"  Present Days : {s['present_days']}",
        f"  Leave Days   : {s['leave_days']}", f"  LOP Days     : {s['lop_days']}",
        f"  Overtime     : {s['overtime_minutes']} min",
        "-" * 50, "EARNINGS",
    ]
    for e in s["earnings"]:
        lines.append(f"  {e['name']:<30} ₹{e['amount']:>12,.2f}")
    lines.append("-" * 50 + "\nDEDUCTIONS")
    for e in s["deductions"]:
        lines.append(f"  {e['name']:<30} ₹{e['amount']:>12,.2f}")
    lines.append("-" * 50)
    lines.extend([f"  {'GROSS SALARY':<30} ₹{s['gross']:>12,.2f}", f"  {'TOTAL DEDUCTIONS':<30} ₹{s['total_deductions']:>12,.2f}", f"  {'NET PAY':<30} ₹{s['net']:>12,.2f}", "-" * 50, f"Generated: {payslip.generated_at.isoformat() if payslip.generated_at else 'N/A'}", f"Status: {payslip.status.value if payslip.status else 'N/A'}"])
    return "\n".join(lines)


def _payslip_elements(source: Payslip, record: PayrollRecord, company: Company) -> list:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    emp_code, emp_name, department, designation = _employee_display(source)
    period_label = _period_label(source)
    attendance = source.payroll_record
    earnings = [c for c in record.components if c.component_type.value == "EARNING"]
    deductions = [c for c in record.components if c.component_type.value == "DEDUCTION"]

    # ── Banner: "PAYSLIP" label ──
    payslip_banner = Table([[Paragraph(
        "<b>PAYSLIP</b>",
        ParagraphStyle("Banner", parent=styles["Normal"],
                         fontName="Helvetica-Bold", fontSize=20,
                         leading=24, textColor="#ffffff"))]],
        colWidths=[160 * mm])
    payslip_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1e40af")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    # ── Employee info box ──
    info_rows = [
        ["Employee", f"{emp_code} — {emp_name}"],
        ["Department", f"{department} — {designation}"],
        ["Period", period_label],
    ]
    info = Table([[k, v] for k, v in info_rows], colWidths=[40 * mm, 120 * mm])
    info.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))

    # ── Attendance section ──
    att_rows = [
        ["Working Days", str(attendance.working_days)],
        ["Present", str(attendance.present_days)],
        ["Leave", str(attendance.leave_days)],
        ["LOP", str(attendance.lop_days)],
        ["Overtime", f"{attendance.overtime_minutes} min"],
    ]
    att = Table(att_rows, colWidths=[50 * mm, 30 * mm])
    att.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))

    # ── Earnings & Deductions table ──
    all_rows = [["Description", "Amount (₹)", "Type"]]
    for c in earnings:
        all_rows.append([c.name, f"{c.amount:,.2f}", "Earning"])
    for c in deductions:
        all_rows.append([c.name, f"{c.amount:,.2f}", "Deduction"])
    comp_table = Table(all_rows, colWidths=[90 * mm, 40 * mm, 30 * mm])
    comp_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0e7ff")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))

    # ── Summary box (Gross / Deductions / Net) ──
    summary = Table([
        ["Gross Salary", f"{source.gross:,.2f}"],
        ["Total Deductions", f"{source.total_deductions:,.2f}"],
        ["Net Pay", f"{source.net:,.2f}"],
    ], colWidths=[80 * mm, 40 * mm])
    summary.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#dcfce7")),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#166534")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    # ── Footer ──
    footer = Paragraph(
        f"Generated: {source.generated_at.strftime('%Y-%m-%d %H:%M') if source.generated_at else 'N/A'} | "
        f"Payslip ID: {str(source.id)} | "
        f"Status: {source.status.value if source.status else 'N/A'}",
        ParagraphStyle("Footer", parent=styles["Normal"],
                       fontName="Helvetica", fontSize=7.5,
                       textColor="#94a3b8", leading=10),
    )

    return [
        header, Spacer(1, 3 * mm),
        payslip_banner, Spacer(1, 3 * mm),
        info, Spacer(1, 3 * mm),
        att, Spacer(1, 4 * mm),
        comp_table, Spacer(1, 4 * mm),
        summary, Spacer(1, 3 * mm),
        footer,
    ]


def build_payslip_pdf(db: Session, payslip: Payslip) -> str:
    """Render a payslip PDF and return its absolute file path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib import colors

    output_dir = _ensure_dirs(payslip)
    emp_code, _name, _dept, _desig = _employee_display(payslip)
    filename = f"{payslip.period.year}-{payslip.period.month:02d}-{emp_code}.pdf"
    filepath = output_dir / filename
    doc = SimpleDocTemplate(
        str(filepath), pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"Payslip - {emp_code} - {payslip.period.year}-{payslip.period.month:02d}",
        author="ESSL HRMS",
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