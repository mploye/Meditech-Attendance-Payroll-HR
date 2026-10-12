from fastapi import APIRouter, Depends, File, Form, UploadFile

from api.deps import ensure_perm, get_current_user, get_db, resolve_company_id
from core.errors import NotFoundError, ValidationError, success_response
from models.user import User
from services import device_user_import

router = APIRouter()


@router.post("/device-users")
def import_device_users(
    device_id: str = Form(...),
    file: UploadFile = File(...),
    default_department: str | None = Form(None),
    default_designation: str | None = Form(None),
    create_accounts: bool = Form(True),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "employees.create")
    cid = resolve_company_id(user)
    try:
        result = device_user_import.import_device_users(
            db,
            cid,
            device_id,
            file.file.read(),
            default_department=default_department,
            default_designation=default_designation,
            create_accounts=create_accounts,
            user_id=str(user.id),
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return success_response(result)


@router.get("/device-users/{device_id}")
def mapped_device_users(
    device_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "devices.view")
    cid = resolve_company_id(user)
    try:
        result = device_user_import.mapped_employees(db, cid, device_id)
    except ValueError as exc:
        raise NotFoundError("Device") from exc
    return success_response(result)