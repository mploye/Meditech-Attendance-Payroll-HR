import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from core.database import SessionLocal, engine
from models import Base
from models.attendance import AttendanceLog, AttendanceDaily

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    logs = db.query(AttendanceLog).all()
    print("LOGS:")
    for l in logs:
        print(" ", l.device_user_id, l.event_timestamp, type(l.event_timestamp), l.event_type, l.idempotency_key)
    days = db.query(AttendanceDaily).all()
    print("DAILY:")
    for d in days:
        print(" ", d.attendance_date, d.first_in, d.last_out, d.worked_minutes, d.status)
finally:
    db.close()