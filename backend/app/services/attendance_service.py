from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.timezone import get_zone, to_utc
from models.attendance import AttendanceDaily, AttendanceLog, DeviceSyncLog
from models.company import Company
from models.employee import Employee
from models.employee_device import EmployeeDevice
from models.enums import AttendanceStatus, EventType, LogSource, SyncLogStatus
from models.shift import Shift
from services import shift_service


@dataclass
class InsertResult:
    log: AttendanceLog
    inserted: bool
    duplicate: bool


@dataclass
class SyncCounts:
    received: int = 0
    inserted: int = 0
    duplicates: int = 0
    failed: int = 0

    def add(self, other: "SyncCounts") -> "SyncCounts":
        self.received += other.received
        self.inserted += other.inserted
        self.duplicates += other.duplicates
        self.failed += other.failed
        return self


def build_idempotency_key(
    company_id: str,
    device_id: str | None,
    device_user_id: str,
    timestamp: datetime,
    event_type: EventType,
) -> str:
    """Build a stable unique key for a single raw attendance event."""
    ts = to_utc(timestamp).isoformat(timespec="microseconds")
    return f"{company_id}|{device_id or ''}|{device_user_id}|{ts}|{event_type.value}"


def _coerce_event_type(value: object) -> EventType:
    """Normalize a raw event type value into an EventType enum."""
    if isinstance(value, EventType):
        return value
    if isinstance(value, str):
        v = value.strip().upper()
        if v in ("IN", "CHECKIN", "CHECK_IN", "CHECK-IN", "PUNCHIN", "PUNCH_IN", "1"):
            return EventType.IN
        if v in ("OUT", "CHECKOUT", "CHECK_OUT", "CHECK-OUT", "PUNCHOUT", "PUNCH_OUT", "0"):
            return EventType.OUT
    return EventType.UNKNOWN


def insert_raw_log(
    db: Session,
    *,
    company_id: str,
    device_id: str | None,
    employee_id: str | None,
    device_user_id: str,
    event_timestamp: datetime,
    event_type: EventType,
    source: LogSource = LogSource.ESSL,
    external_event_id: str | None = None,
    raw_payload: dict | None = None,
) -> InsertResult:
    """Insert one immutable raw log, deduped by idempotency key."""
    key = build_idempotency_key(company_id, device_id, device_user_id, event_timestamp, event_type)
    existing = db.scalar(
        select(AttendanceLog).where(
            AttendanceLog.company_id == company_id,
            AttendanceLog.idempotency_key == key,
        )
    )
    if existing is not None:
        return InsertResult(log=existing, inserted=False, duplicate=True)
    log = AttendanceLog(
        company_id=company_id,
        device_id=device_id,
        employee_id=employee_id,
        device_user_id=str(device_user_id),
        event_timestamp=to_utc(event_timestamp),
        event_type=_coerce_event_type(event_type),
        source=source,
        external_event_id=external_event_id,
        idempotency_key=key,
        raw_payload=raw_payload,
    )
    db.add(log)
    db.flush()
    return InsertResult(log=log, inserted=True, duplicate=False)


def _resolve_employee_id(
    db: Session, company_id: str, device_id: str | None, device_user_id: str
) -> str | None:
    """Map a device user id to an employee via employee_devices, if possible."""
    if device_id is None:
        return None
    mapping = db.scalar(
        select(EmployeeDevice).where(
            EmployeeDevice.company_id == company_id,
            EmployeeDevice.device_id == device_id,
            EmployeeDevice.device_user_id == str(device_user_id),
        )
    )
    return mapping.employee_id if mapping is not None else None


def insert_transactions(
    db: Session,
    company_id: str,
    device_id: str | None,
    transactions: list,
) -> SyncCounts:
    """Insert a batch of device transactions, counting outcomes without failing the batch."""
    counts = SyncCounts(received=len(transactions), inserted=0, duplicates=0, failed=0)
    for tx in transactions:
        device_user_id = str(getattr(tx, "device_user_id", "") or "")
        timestamp = getattr(tx, "timestamp", None)
        if not device_user_id or timestamp is None:
            counts.failed += 1
            continue
        try:
            employee_id = _resolve_employee_id(db, company_id, device_id, device_user_id)
            if employee_id is None:
                counts.failed += 1
                continue
            with db.begin_nested():
                result = insert_raw_log(
                    db,
                    company_id=company_id,
                    device_id=device_id,
                    employee_id=employee_id,
                    device_user_id=device_user_id,
                    event_timestamp=timestamp,
                    event_type=getattr(tx, "event_type", EventType.UNKNOWN),
                    source=LogSource.ESSL,
                    external_event_id=getattr(tx, "external_event_id", None),
                    raw_payload=getattr(tx, "raw", None),
                )
        except Exception:
            counts.failed += 1
            continue
        if result.inserted:
            counts.inserted += 1
        else:
            counts.duplicates += 1
    db.commit()
    return counts


def _company_timezone(db: Session, company_id: str) -> str:
    """Return the company timezone name, falling back to the configured default."""
    tz = db.scalar(select(Company.timezone).where(Company.id == company_id))
    return tz or settings.DEFAULT_TIMEZONE


def _normalize_ts(dt: datetime) -> datetime:
    """Return a tz-aware datetime, treating naive values as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _logs_on_day(
    db: Session, company_id: str, employee_id: str, day: date, company_timezone: str
) -> list[AttendanceLog]:
    """Return attendance logs for one employee localized to a single calendar day."""
    zone = get_zone(company_timezone)
    start_local = datetime.combine(day, time(0, 0), tzinfo=zone)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    return list(
        db.scalars(
            select(AttendanceLog)
            .where(
                AttendanceLog.company_id == company_id,
                AttendanceLog.employee_id == employee_id,
                AttendanceLog.event_timestamp >= start_utc,
                AttendanceLog.event_timestamp <= end_utc,
            )
            .order_by(AttendanceLog.event_timestamp)
        )
    )


def _late_minutes(
    first_in: datetime | None, resolved_start: datetime | None, grace_minutes: int
) -> int:
    """Compute minutes late beyond shift start plus grace, clamped to zero."""
    if first_in is None or resolved_start is None:
        return 0
    allowed = resolved_start + timedelta(minutes=grace_minutes)
    return int(max((first_in - allowed).total_seconds() // 60, 0))


def _early_leave_minutes(
    last_out: datetime | None, resolved_end: datetime | None
) -> int:
    """Compute minutes leaving before shift end, clamped to zero."""
    if last_out is None or resolved_end is None:
        return 0
    return int(max((resolved_end - last_out).total_seconds() // 60, 0))


def _overtime_minutes(
    last_out: datetime | None, shift: Shift, resolved_end: datetime | None
) -> int:
    """Compute overtime minutes worked past shift end plus the allowed threshold."""
    if not shift.overtime_enabled or last_out is None or resolved_end is None:
        return 0
    threshold = resolved_end + timedelta(minutes=int(shift.overtime_after_minutes or 0))
    return int(max((last_out - threshold).total_seconds() // 60, 0))


def _upsert_daily(
    db: Session,
    company_id: str,
    employee_id: str,
    day: date,
    shift_id: str | None,
    first_in: datetime | None,
    last_out: datetime | None,
    worked_minutes: int,
    break_minutes: int,
    late_minutes: int,
    early_leave_minutes: int,
    overtime_minutes: int,
    status: AttendanceStatus,
    remarks: str | None,
) -> AttendanceDaily:
    """Insert or update the daily attendance record for an employee/date unique key."""
    record = db.scalar(
        select(AttendanceDaily).where(
            AttendanceDaily.company_id == company_id,
            AttendanceDaily.employee_id == employee_id,
            AttendanceDaily.attendance_date == day,
        )
    )
    if record is None:
        record = AttendanceDaily(
            company_id=company_id,
            employee_id=employee_id,
            attendance_date=day,
            shift_id=shift_id,
            first_in=first_in,
            last_out=last_out,
            worked_minutes=worked_minutes,
            break_minutes=break_minutes,
            late_minutes=late_minutes,
            early_leave_minutes=early_leave_minutes,
            overtime_minutes=overtime_minutes,
            status=status,
            remarks=remarks,
        )
        db.add(record)
    else:
        record.shift_id = shift_id
        record.first_in = first_in
        record.last_out = last_out
        record.worked_minutes = worked_minutes
        record.break_minutes = break_minutes
        record.late_minutes = late_minutes
        record.early_leave_minutes = early_leave_minutes
        record.overtime_minutes = overtime_minutes
        record.status = status
        record.remarks = remarks
    db.flush()
    return record


def process_day(
    db: Session, company_id: str, employee_id: str, day: date
) -> AttendanceDaily | None:
    """Compute and upsert the daily attendance record for one employee on one day."""
    tz = _company_timezone(db, company_id)
    logs = _logs_on_day(db, company_id, employee_id, day, tz)
    shift = shift_service.get_employee_shift(db, company_id, employee_id, day)

    in_candidates = [log for log in logs if log.event_type in (EventType.IN, EventType.UNKNOWN)]
    first_in = min((_normalize_ts(log.event_timestamp) for log in in_candidates), default=None)
    last_out = max((_normalize_ts(log.event_timestamp) for log in logs), default=None)

    if shift is None:
        status = AttendanceStatus.PRESENT if logs else AttendanceStatus.ABSENT
        worked = int((last_out - first_in).total_seconds() // 60) if first_in and last_out else 0
        return _upsert_daily(
            db,
            company_id,
            employee_id,
            day,
            shift_id=None,
            first_in=first_in,
            last_out=last_out,
            worked_minutes=max(0, worked),
            break_minutes=0,
            late_minutes=0,
            early_leave_minutes=0,
            overtime_minutes=0,
            status=status,
            remarks=None,
        )

    resolved_start, resolved_end = shift_service.resolve_shift_times(shift, day, tz)
    break_minutes = int(shift.break_minutes or 0)
    worked_minutes = (
        int((last_out - first_in).total_seconds() // 60) - break_minutes
        if first_in and last_out
        else 0
    )
    worked_minutes = max(0, worked_minutes)
    late_minutes = _late_minutes(first_in, resolved_start, int(shift.grace_period_minutes or 0))
    early_leave_minutes = _early_leave_minutes(last_out, resolved_end)
    overtime_minutes = _overtime_minutes(last_out, shift, resolved_end)

    if first_in is None and last_out is None:
        status = AttendanceStatus.ABSENT
    elif worked_minutes >= int(shift.minimum_work_minutes or 0):
        status = AttendanceStatus.PRESENT
    else:
        status = AttendanceStatus.MISSING_PUNCH

    return _upsert_daily(
        db,
        company_id,
        employee_id,
        day,
        shift_id=shift.id,
        first_in=first_in,
        last_out=last_out,
        worked_minutes=worked_minutes,
        break_minutes=break_minutes,
        late_minutes=late_minutes,
        early_leave_minutes=early_leave_minutes,
        overtime_minutes=overtime_minutes,
        status=status,
        remarks=None,
    )


def process_range(
    db: Session,
    company_id: str,
    from_date: date,
    to_date: date,
    employee_id: str | None = None,
) -> dict:
    """Compute daily attendance across a date range for all (or one) employees of a company."""
    if employee_id:
        employee_ids = [employee_id]
    else:
        employee_ids = list(db.scalars(select(Employee.id).where(Employee.company_id == company_id)))
    status_counts: dict[str, int] = {}
    days_processed = 0
    records = 0
    current = from_date
    while current <= to_date:
        days_processed += 1
        for emp_id in employee_ids:
            rec = process_day(db, company_id, emp_id, current)
            records += 1
            if rec is not None:
                key = rec.status.value
                status_counts[key] = status_counts.get(key, 0) + 1
        current += timedelta(days=1)
    db.commit()
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "days": days_processed,
        "records": records,
        "status_counts": status_counts,
    }


def get_daily_summary(
    db: Session, company_id: str, employee_id: str, from_date: date, to_date: date
) -> dict:
    """Aggregate attendance metrics for one employee across a date range."""
    rows = list(
        db.scalars(
            select(AttendanceDaily).where(
                AttendanceDaily.company_id == company_id,
                AttendanceDaily.employee_id == employee_id,
                AttendanceDaily.attendance_date >= from_date,
                AttendanceDaily.attendance_date <= to_date,
            )
        )
    )
    status_counts: dict[str, int] = {}
    present_minutes = 0
    late_minutes = 0
    overtime_minutes = 0
    early_leave_minutes = 0
    for row in rows:
        status_counts[row.status.value] = status_counts.get(row.status.value, 0) + 1
        if row.status == AttendanceStatus.PRESENT:
            present_minutes += row.worked_minutes
        late_minutes += row.late_minutes
        overtime_minutes += row.overtime_minutes
        early_leave_minutes += row.early_leave_minutes
    return {
        "company_id": company_id,
        "employee_id": employee_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "total_days": len(rows),
        "present_minutes": present_minutes,
        "late_minutes": late_minutes,
        "overtime_minutes": overtime_minutes,
        "early_leave_minutes": early_leave_minutes,
        "status_counts": status_counts,
    }


def log_sync_start(db: Session, company_id: str, device_id: str | None = None) -> DeviceSyncLog:
    """Create and return a new device sync log with the start timestamp."""
    sync_log = DeviceSyncLog(
        company_id=company_id,
        device_id=device_id,
        started_at=datetime.now(timezone.utc),
        records_received=0,
        records_inserted=0,
        records_duplicate=0,
        records_failed=0,
        status=SyncLogStatus.SUCCESS,
    )
    db.add(sync_log)
    db.flush()
    return sync_log


def log_sync_end(
    db: Session,
    sync_log: DeviceSyncLog,
    *,
    received: int,
    inserted: int,
    duplicates: int,
    failed: int,
    status: SyncLogStatus,
    error_message: str | None = None,
) -> DeviceSyncLog:
    """Finalize a device sync log with outcome counters and status."""
    sync_log.completed_at = datetime.now(timezone.utc)
    sync_log.records_received = received
    sync_log.records_inserted = inserted
    sync_log.records_duplicate = duplicates
    sync_log.records_failed = failed
    sync_log.status = status
    sync_log.error_message = error_message
    db.flush()
    return sync_log