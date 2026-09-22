from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from models.enums import AttendanceStatus, EventType, LogSource
from services import attendance_service

from tests.conftest import make_company, make_employee, make_shift

DAY = date(2024, 7, 15)


def _ts(hour: int, minute: int) -> datetime:
    return datetime(2024, 7, 15, hour, minute, tzinfo=ZoneInfo("Asia/Kolkata"))


@pytest.fixture()
def ctx(db):
    company = make_company(db)
    # 09:00-18:00, grace 10m, min work 420m, break 60m, OT +60m
    shift = make_shift(db, str(company.id))
    emp = make_employee(db, str(company.id), code="A001")
    return {"company_id": str(company.id), "employee_id": str(emp.id), "shift": shift}


def test_present_with_late_and_overtime(db, ctx):
    for ts, ev in [(_ts(9, 30), EventType.IN), (_ts(19, 45), EventType.OUT)]:
        attendance_service.insert_raw_log(
            db,
            company_id=ctx["company_id"],
            device_id=None,
            employee_id=ctx["employee_id"],
            device_user_id="A001",
            event_timestamp=ts,
            event_type=ev,
            source=LogSource.MANUAL,
        )

    rec = attendance_service.process_day(db, ctx["company_id"], ctx["employee_id"], DAY)
    assert rec.status == AttendanceStatus.PRESENT
    assert rec.late_minutes == 20      # 09:30 - (09:00 + 10 grace)
    assert rec.overtime_minutes == 45  # 19:45 - (18:00 + 60)
    assert rec.worked_minutes == 555   # 615 - 60 break
    assert rec.first_in.astimezone(ZoneInfo("Asia/Kolkata")).hour == 9


def test_absent_when_no_punches(db, ctx):
    rec = attendance_service.process_day(db, ctx["company_id"], ctx["employee_id"], DAY)
    assert rec.status == AttendanceStatus.ABSENT
    assert rec.first_in is None


def test_missing_punch_when_only_in(db, ctx):
    attendance_service.insert_raw_log(
        db,
        company_id=ctx["company_id"],
        device_id=None,
        employee_id=ctx["employee_id"],
        device_user_id="A001",
        event_timestamp=_ts(9, 5),
        event_type=EventType.IN,
        source=LogSource.MANUAL,
    )
    rec = attendance_service.process_day(db, ctx["company_id"], ctx["employee_id"], DAY)
    assert rec.status == AttendanceStatus.MISSING_PUNCH
    assert rec.worked_minutes == 0


def test_daily_summary_counts(db, ctx):
    attendance_service.insert_raw_log(
        db,
        company_id=ctx["company_id"],
        device_id=None,
        employee_id=ctx["employee_id"],
        device_user_id="A001",
        event_timestamp=_ts(9, 5),
        event_type=EventType.IN,
        source=LogSource.MANUAL,
    )
    attendance_service.insert_raw_log(
        db,
        company_id=ctx["company_id"],
        device_id=None,
        employee_id=ctx["employee_id"],
        device_user_id="A001",
        event_timestamp=_ts(18, 5),
        event_type=EventType.OUT,
        source=LogSource.MANUAL,
    )
    attendance_service.process_day(db, ctx["company_id"], ctx["employee_id"], DAY)
    summary = attendance_service.get_daily_summary(
        db, ctx["company_id"], ctx["employee_id"], DAY, DAY
    )
    assert summary["total_days"] == 1
    assert summary["status_counts"]["PRESENT"] == 1


def test_duplicate_punch_deduped(db, ctx):
    first = attendance_service.insert_raw_log(
        db,
        company_id=ctx["company_id"],
        device_id=None,
        employee_id=ctx["employee_id"],
        device_user_id="A001",
        event_timestamp=_ts(9, 5),
        event_type=EventType.IN,
        source=LogSource.MANUAL,
    )
    second = attendance_service.insert_raw_log(
        db,
        company_id=ctx["company_id"],
        device_id=None,
        employee_id=ctx["employee_id"],
        device_user_id="A001",
        event_timestamp=_ts(9, 5),
        event_type=EventType.IN,
        source=LogSource.MANUAL,
    )
    assert first.inserted is True
    assert second.inserted is False
    assert second.duplicate is True