"""Smoke test: company -> employee -> device -> mock ESSL sync -> daily attendance."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from core.config import settings  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
from core.security import hash_password  # noqa: E402
from models import Base  # noqa: E402
from models.company import Company  # noqa: E402
from models.device import Device, ESSLConfig  # noqa: E402
from models.employee import Employee  # noqa: E402
from models.employee_device import EmployeeDevice  # noqa: E402
from models.enums import DeviceProvider, DeviceStatus, DeviceType, EmployeeStatus  # noqa: E402
from models.shift import Shift  # noqa: E402
from services import attendance_service as att  # noqa: E402
from services.sync_service import SyncService  # noqa: E402
from integrations.essl.mock import MockESSLClient  # noqa: E402

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    company = Company(name="Acme", short_name="ACME")
    db.add(company)
    db.flush()

    device = Device(
        company_id=company.id,
        name="Orcus-01",
        model="AI-FACE-ORCUS",
        serial_number="ORCUS001",
        device_type=DeviceType.FACE_PUNCH,
        provider=DeviceProvider.ESSL,
        status=DeviceStatus.ONLINE,
    )
    db.add(device)
    db.flush()

    essl_cfg = ESSLConfig(company_id=company.id, enabled=True, base_url="https://mock")
    db.add(essl_cfg)

    shift = Shift(
        company_id=company.id,
        name="General",
        start_time=__import__("datetime").time(9, 0),
        end_time=__import__("datetime").time(18, 0),
        grace_period_minutes=0,
        minimum_work_minutes=420,
        break_minutes=60,
        overtime_enabled=True,
        overtime_after_minutes=0,
        is_default=True,
    )
    db.add(shift)

    emp = Employee(
        company_id=company.id,
        employee_code="EMP001",
        first_name="Ravi",
        last_name="Kumar",
        status=EmployeeStatus.ACTIVE,
    )
    db.add(emp)
    db.flush()

    ed = EmployeeDevice(
        company_id=company.id,
        employee_id=emp.id,
        device_id=device.id,
        device_user_id="1001",
    )
    db.add(ed)
    db.flush()
    db.commit()

    from integrations.essl.config import ESSLConfiguration

    mock = MockESSLClient(ESSLConfiguration(enabled=True))
    mock.add_employee("EMP001", "Ravi Kumar", "1001")
    today = datetime.now(timezone.utc).date()
    mock.generate_transaction("1001", datetime(2026, 9, 22, 9, 12, tzinfo=timezone.utc), "IN")
    mock.generate_transaction("1001", datetime(2026, 9, 22, 18, 30, tzinfo=timezone.utc), "OUT")

    # run sync against mock by injecting the client via ESSLService override
    import asyncio

    from integrations.essl.service import ESSLService

    svc = SyncService(db)
    txns = asyncio.run(
        mock.get_transactions(
            datetime.now(timezone.utc) - timedelta(days=2),
            datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    counts = att.insert_transactions(db, company.id, device.id, txns)
    print("sync counts:", counts)

    # run manual sync path (uses real service wiring)
    # stub the module-level get_essl_service to return our mock-backed service
    import services.sync_service as ss

    ss.get_essl_service = lambda _db, _cid: ESSLService(_db, mock.config, client=mock, mock_override=True)
    # pre-seed the device's last sync so a fresh window includes our seeded txns
    device.last_sync_at = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)
    db.commit()

    result = svc.run_manual_sync(company.id, device.id)
    print("manual sync result:", result)

    # daily processing for the shift day
    from services.shift_service import get_employee_shift

    from core.timezone import local_date

    day = local_date(datetime(2026, 9, 22, tzinfo=timezone.utc), company.timezone)
    rec = att.process_day(db, company.id, emp.id, day)
    print("daily:", rec.status, "in", rec.first_in, "out", rec.last_out, "worked", rec.worked_minutes, "late", rec.late_minutes, "ot", rec.overtime_minutes)

    assert counts.inserted >= 1
    assert rec.first_in is not None
    assert rec.status.value == "PRESENT"
    assert rec.late_minutes == 12 or rec.late_minutes > 0
    print("SMOKE TEST PASSED")
finally:
    db.close()