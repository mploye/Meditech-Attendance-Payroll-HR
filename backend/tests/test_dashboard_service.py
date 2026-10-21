from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from models.enums import AttendanceStatus, EventType, LogSource
from services import attendance_service, dashboard_service

from tests.conftest import make_company, make_employee, make_shift

DAY = date(2024, 7, 15)


def _ts(hour: int, minute: int) -> datetime:
    return datetime(2024, 7, 15, hour, minute, tzinfo=ZoneInfo("Asia/Kolkata"))


@pytest.fixture()
def ctx(db):
    company = make_company(db)
    make_shift(db, str(company.id))
    present = make_employee(db, str(company.id), code="E1", first_name="Present")
    absent = make_employee(db, str(company.id), code="E2", first_name="Absent")
    late = make_employee(db, str(company.id), code="E3", first_name="Late")
    return {
        "company_id": str(company.id),
        "present": present,
        "absent": absent,
        "late": late,
    }


def _punch(db, ctx, employee_id, hour, minute, event_type):
    attendance_service.insert_raw_log(
        db,
        company_id=ctx["company_id"],
        device_id=None,
        employee_id=employee_id,
        device_user_id=employee_id,
        event_timestamp=_ts(hour, minute),
        event_type=event_type,
        source=LogSource.DEVICE,
    )


def test_metric_detail_present_absent_late(db, ctx):
    cid = ctx["company_id"]

    # E1 present, on time
    _punch(db, ctx, str(ctx["present"].id), 9, 0, EventType.IN)
    _punch(db, ctx, str(ctx["present"].id), 18, 0, EventType.OUT)
    attendance_service.process_day(db, cid, str(ctx["present"].id), DAY)

    # E3 present but late (shift starts 09:00, grace 10m -> 40m late)
    _punch(db, ctx, str(ctx["late"].id), 9, 40, EventType.IN)
    _punch(db, ctx, str(ctx["late"].id), 18, 0, EventType.OUT)
    attendance_service.process_day(db, cid, str(ctx["late"].id), DAY)

    # E2 absent (no punches) - force a daily row via process_day
    attendance_service.process_day(db, cid, str(ctx["absent"].id), DAY)

    present = dashboard_service.metric_detail(db, cid, "present_today", DAY)
    assert present["count"] == 2
    codes = {r["employee_code"] for r in present["items"]}
    assert codes == {"E1", "E3"}

    late = dashboard_service.metric_detail(db, cid, "late_today", DAY)
    assert late["count"] == 1
    assert late["items"][0]["employee_code"] == "E3"
    assert late["items"][0]["late_minutes"] > 0

    absent = dashboard_service.metric_detail(db, cid, "absent_today", DAY)
    assert absent["count"] == 1
    assert absent["items"][0]["employee_code"] == "E2"
    assert absent["items"][0]["status"] == AttendanceStatus.ABSENT.value


def test_metric_detail_total_employees(db, ctx):
    detail = dashboard_service.metric_detail(db, ctx["company_id"], "total_employees", DAY)
    assert detail["count"] == 3
    assert {r["employee_code"] for r in detail["items"]} == {"E1", "E2", "E3"}


def test_metric_detail_unknown_metric_is_empty(db, ctx):
    detail = dashboard_service.metric_detail(db, ctx["company_id"], "payroll_amount", DAY)
    assert detail["count"] == 0
    assert detail["items"] == []
