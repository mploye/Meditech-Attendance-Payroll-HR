from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import success_response
from models.enums import EmployeeStatus
from models.user import User
from services import employee_service

router = APIRouter()


@router.get("/")
def list_employees(
    search: Optional[str] = None,
    department_id: Optional[str] = None,
    designation_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "employees.view")
    cid = resolve_company_id(user)
    emp_status = None
    if status:
        emp_status = EmployeeStatus(status)
    result = employee_service.list_employees(
        db,
        cid,
        search=search,
        department_id=department_id,
        designation_id=designation_id,
        status=emp_status,
        page=page,
        page_size=page_size,
    )
    result["items"] = [orm_to_dict(item) for item in result["items"]]
    return success_response(result)


@router.post("/")
def create_employee(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "employees.create")
    cid = resolve_company_id(user)
    salary_data = body.pop("salary", None)
    device_user_id = body.pop("device_user_id", None)
    essl_sync = body.pop("essl_sync", False)
    emp = employee_service.create_employee(db, cid, body, user_id=str(user.id))
    if salary_data:
        employee_service.set_employee_salary(db, cid, str(emp.id), salary_data)
    if device_user_id:
        device_id = body.get("device_id")
        if device_id:
            employee_service.add_device_mapping(
                db, cid, str(emp.id), device_id=device_id, device_user_id=str(device_user_id)
            )
    payload = orm_to_dict(emp)
    if essl_sync:
        payload["essl"] = employee_service.sync_employee_to_essl(db, cid, str(emp.id))
    return success_response(payload)


@router.get("/{employee_id}")
def get_employee(employee_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "employees.view")
    cid = resolve_company_id(user)
    emp = employee_service.get_employee(db, cid, employee_id)
    data = orm_to_dict(emp)
    salary = employee_service.active_salary(db, cid, employee_id)
    data["active_salary"] = orm_to_dict(salary)
    data["devices"] = [orm_to_dict(d) for d in employee_service.employee_devices(db, cid, employee_id)]
    return success_response(data)


@router.patch("/{employee_id}")
def update_employee(employee_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "employees.edit")
    cid = resolve_company_id(user)
    emp = employee_service.update_employee(db, cid, employee_id, body, user_id=str(user.id))
    return success_response(orm_to_dict(emp))


@router.post("/{employee_id}/salary")
def set_salary(employee_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.create")
    cid = resolve_company_id(user)
    salary = employee_service.set_employee_salary(db, cid, employee_id, body)
    return success_response(orm_to_dict(salary))


@router.get("/{employee_id}/salary")
def salary_history(employee_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.view")
    cid = resolve_company_id(user)
    rows = employee_service.employee_salary_history(db, cid, employee_id)
    return success_response([orm_to_dict(r) for r in rows])


@router.post("/{employee_id}/devices")
def add_device(employee_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "employees.sync")
    cid = resolve_company_id(user)
    mapping = employee_service.add_device_mapping(
        db,
        cid,
        employee_id,
        device_id=body["device_id"],
        device_user_id=str(body["device_user_id"]),
    )
    return success_response(orm_to_dict(mapping))


@router.get("/{employee_id}/devices")
def list_devices(employee_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "employees.view")
    cid = resolve_company_id(user)
    rows = employee_service.employee_devices(db, cid, employee_id)
    return success_response([orm_to_dict(r) for r in rows])


@router.post("/{employee_id}/devices/sync")
def sync_to_device(employee_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "employees.sync")
    cid = resolve_company_id(user)
    return success_response(employee_service.sync_employee_to_essl(db, cid, employee_id))


@router.post("/{employee_id}/associate-user")
def associate_user(employee_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "employees.edit")
    cid = resolve_company_id(user)
    created = employee_service.associate_user(
        db,
        cid,
        employee_id,
        email=body["email"],
        full_name=body.get("full_name"),
        password=body.get("password"),
    )
    from api.deps import user_dict

    return success_response(user_dict(created))