from fastapi import APIRouter, Depends

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import success_response
from models.user import User
from services import department_service, designation_service

departments_router = APIRouter()
designations_router = APIRouter()


@departments_router.get("/")
def list_departments(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "departments.view")
    cid = resolve_company_id(user)
    return success_response([orm_to_dict(d) for d in department_service.list_all(db, cid)])


@departments_router.post("/")
def create_department(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "departments.create")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(department_service.create(db, cid, body)))


@departments_router.get("/{department_id}")
def get_department(department_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "departments.view")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(department_service.get(db, cid, department_id)))


@departments_router.patch("/{department_id}")
def update_department(department_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "departments.edit")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(department_service.update(db, cid, department_id, body)))


@departments_router.delete("/{department_id}")
def delete_department(department_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "departments.delete")
    cid = resolve_company_id(user)
    department_service.delete(db, cid, department_id)
    return success_response({"deleted": True})


@designations_router.get("/")
def list_designations(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "designations.view")
    cid = resolve_company_id(user)
    return success_response([orm_to_dict(d) for d in designation_service.list_all(db, cid)])


@designations_router.post("/")
def create_designation(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "designations.create")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(designation_service.create(db, cid, body)))


@designations_router.get("/{designation_id}")
def get_designation(designation_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "designations.view")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(designation_service.get(db, cid, designation_id)))


@designations_router.patch("/{designation_id}")
def update_designation(designation_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "designations.edit")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(designation_service.update(db, cid, designation_id, body)))


@designations_router.delete("/{designation_id}")
def delete_designation(designation_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "designations.delete")
    cid = resolve_company_id(user)
    designation_service.delete(db, cid, designation_id)
    return success_response({"deleted": True})