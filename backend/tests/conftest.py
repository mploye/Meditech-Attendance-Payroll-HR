import os
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")

# Must be set before any app import so engine/settings bind to the test DB.
# The temp dir avoids file-lock interference from scanners on rapid create/drop.
_TEST_DB = os.path.join(tempfile.gettempdir(), "opencode", "test_hrms.db")
os.makedirs(os.path.dirname(_TEST_DB), exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.replace(os.sep, '/')}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"
os.environ["ESSL_MOCK_MODE"] = "true"
os.environ["DEVICE_CONNECTOR_API_KEY"] = "test-connector-key"
os.environ["APP_ENV"] = "test"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _reset_db() -> None:
    from core.database import engine
    from models.base import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db():
    """Fresh database session for every test."""
    from core.database import SessionLocal

    _reset_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    """Fresh TestClient bound to the test database."""
    import main

    _reset_db()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def superadmin(client):
    """Register and return the bootstrap super admin with auth headers."""
    r = client.post(
        "/api/v1/auth/register-super-admin",
        json={"email": "root@example.com", "password": "Root12345", "full_name": "Root Admin"},
    )
    assert r.status_code == 200, r.text
    login = client.post(
        "/api/v1/auth/login", json={"email": "root@example.com", "password": "Root12345"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "token": token, "user": login.json()["data"]["user"]}


@pytest.fixture()
def company(client, superadmin):
    """Create a company via the super admin and return HR user + company ids."""
    r = client.post(
        "/api/v1/auth/companies",
        headers=superadmin["headers"],
        json={
            "company": {"name": "Acme Pvt Ltd", "short_name": "ACME", "timezone": "Asia/Kolkata", "country": "India"},
            "admin_user": {"email": "hr@example.com", "password": "Hr123456", "full_name": "HR Head"},
        },
    )
    assert r.status_code == 200, r.text
    company_id = r.json()["data"]["company"]["id"]
    data = r.json()["data"]["admin_user"]

    login = client.post("/api/v1/auth/login", json={"email": "hr@example.com", "password": "Hr123456"})
    assert login.status_code == 200, login.text
    hr_token = login.json()["data"]["access_token"]
    return {
        "company_id": company_id,
        "headers": {"Authorization": f"Bearer {hr_token}"},
        "token": hr_token,
        "admin_user": data,
    }


def make_company(db):
    """Create a company row directly through the service layer."""
    from services import company_service

    return company_service.create_company(
        db,
        name="Acme Pvt Ltd",
        short_name="ACME",
        timezone="Asia/Kolkata",
        country="India",
    )


def make_user(db, company_id, email, password="Pass12345", full_name="Test User", role="EMPLOYEE"):
    """Create a user row directly through the service layer."""
    from models.enums import Role
    from services import user_service

    return user_service.create_user(
        db,
        company_id,
        email=email,
        password=password,
        full_name=full_name,
        role=Role(role),
    )


def make_shift(db, company_id, **overrides):
    """Create a shift row directly with defaults matching the API input."""
    from datetime import time as dt_time

    from models.shift import Shift

    payload = {
        "name": "Day Shift",
        "code": "DAY",
        "start_time": dt_time(9, 0),
        "end_time": dt_time(18, 0),
        "grace_period_minutes": 10,
        "minimum_work_minutes": 420,
        "break_minutes": 60,
        "overtime_enabled": True,
        "overtime_after_minutes": 60,
        "night_shift": False,
        "is_default": True,
        "active": True,
    }
    payload.update(overrides)
    shift = Shift(company_id=company_id, **payload)
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


def make_salary_structure(db, company_id, basic=40000.0, **overrides):
    """Create a salary structure with fixed basic earnings component."""
    from models.enums import CalculationType, SalaryComponentType, SalaryFrequency
    from models.salary import SalaryStructure, SalaryStructureComponent

    payload = {
        "name": "Standard",
        "code": "STD",
        "payment_frequency": SalaryFrequency.MONTHLY,
        "monthly_gross": basic,
    }
    payload.update(overrides)
    structure = SalaryStructure(company_id=company_id, **payload)
    db.add(structure)
    db.flush()
    db.add(
        SalaryStructureComponent(
            company_id=company_id,
            salary_structure_id=str(structure.id),
            name="Basic",
            component_type=SalaryComponentType.EARNING,
            calculation_type=CalculationType.FIXED,
            value=basic,
        )
    )
    db.commit()
    db.refresh(structure)
    return structure


def make_employee(db, company_id, code="E001", salary_structure_id=None, **overrides):
    """Create an employee (and optional salary) directly through services."""
    from services import employee_service

    payload = {
        "employee_code": code,
        "first_name": "Alice",
        "last_name": "Doe",
        "status": "ACTIVE",
        "employment_type": "FULL_TIME",
    }
    payload.update(overrides)
    emp = employee_service.create_employee(db, company_id, payload, audit=False)
    if salary_structure_id:
        from datetime import date

        employee_service.set_employee_salary(
            db,
            company_id,
            str(emp.id),
            {
                "effective_from": date(2024, 1, 1),
                "salary_structure_id": str(salary_structure_id),
                "gross_salary": 50000.0,
                "basic_salary": 40000.0,
                "payment_frequency": "MONTHLY",
            },
        )
    return emp