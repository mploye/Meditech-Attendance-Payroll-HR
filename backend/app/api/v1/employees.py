"""Employee endpoints under /employees."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict, page_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.user import User
from schemas.employee import EmployeeCreateRequest, EmployeeUpdateRequest
from schemas.employee_associate import EmployeeAssociateUserRequest
from schemas.employee_device import EmployeeDeviceMappingRequest
from schemas.employee_salary_set import EmployeeSalarySetRequest
from services import employee_service

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("")
def list_employees(
    search: Optional[str] = None,
    department_id: Optional[str] = None,
    designation_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "employees.view")
    scope = company_scope(user=user)
    result = employee_service.list_employees(
        db,
        scope,
        search=search,
        department_id=department_id,
        designation_id=designation_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success_response(page_dict(result))


@router.post("")
def create_employee(
    payload: EmployeeCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "employees.create")
    scope = company_scope(user=user)
    emp = employee_service.create_employee(db, scope, payload.model_dump(exclude_unset=True), user_id=str(user.id))
    return success_response(orm_to_dict(emp))


@router.get("/{employee_id}")
def get_employee(
    employee_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "employees.view")
    scope = company_scope(user=user)
    emp = employee_service.get_employee(db, scope, employee_id)
    return success_response(orm_to_dict(emp))


@router.patch("/{employee_id}")
def update_employee(
    employee_id: str,
    payload: EmployeeUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "employees.edit")
    scope = company_scope(user=user)
    emp = employee_service.update_employee(
        db, scope, employee_id, payload.model_dump(exclude_unset=True), user_id=str(user.id)
    )
    return success_response(orm_to_dict(emp))


@router.post("/{employee_id}/salary")
def set_employee_salary(
    employee_id: str,
    payload: EmployeeSalarySetRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.create")
    scope = company_scope(user=user)
    salary = employee_service.set_employee_salary(db, scope, employee_id, payload.model_dump())
    return success_response(orm_to_dict(salary))


@router.get("/{employee_id}/salary")
def get_employee_salary(
    employee_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.view")
    scope = company_scope(user=user)
    history = employee_service.employee_salary_history(db, scope, employee_id)
    active = employee_service.active_salary(db, scope, employee_id)
    return success_response(
        {"active": orm_to_dict(active), "history": orm_to_dict(history)}
    )


@router.post("/{employee_id}/devices")
def add_employee_device(
    employee_id: str,
    payload: EmployeeDeviceMappingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.create")
    scope = company_scope(user=user)
    mapping = employee_service.add_device_mapping(
        db, scope, employee_id, device_id=payload.device_id, device_user_id=payload.device_user_id
    )
    return success_response(orm_to_dict(mapping))


@router.get("/{employee_id}/devices")
def get_employee_devices(
    employee_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.view")
    scope = company_scope(user=user)
    devices = employee_service.employee_devices(db, scope, employee_id)
    return success_response(orm_to_dict(devices))


@router.post("/{employee_id}/devices/sync")
def sync_employee_to_essl(
    employee_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "employees.sync")
    scope = company_scope(user=user)
    result = employee_service.sync_employee_to_essl(db, scope, employee_id)
    return success_response(result)


@router.post("/{employee_id}/associate-user")
def associate_user(
    employee_id: str,
    payload: EmployeeAssociateUserRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "employees.create")
    scope = company_scope(user=user)
    linked = employee_service.associate_user(
        db, scope, employee_id, email=payload.email, full_name=payload.full_name, password=payload.password
    )
    return success_response(orm_to_dict(linked, exclude={"password_hash"}))