from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id, user_dict
from core.errors import NotFoundError, success_response
from models.enums import Role
from models.user import User
from services import company_service

router = APIRouter()


@router.get("/")
def list_companies(
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "companies.view")
    if user.role != Role.SUPER_ADMIN:
        company = company_service.get_company(db, str(user.company_id))
        return success_response([orm_to_dict(company)])
    companies = company_service.list_companies(db, search)
    return success_response([orm_to_dict(c) for c in companies])


@router.get("/{company_id}")
def get_company(company_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "companies.view")
    cid = resolve_company_id(user, company_id)
    company = company_service.get_company(db, cid)
    return success_response(orm_to_dict(company))


@router.patch("/{company_id}")
def update_company(
    company_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)
):
    ensure_perm(user, "companies.edit")
    cid = resolve_company_id(user, company_id)
    company = company_service.update_company(db, cid, body)
    return success_response(orm_to_dict(company))


@router.patch("/{company_id}/settings")
def update_company_settings(
    company_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)
):
    ensure_perm(user, "settings.edit")
    cid = resolve_company_id(user, company_id)
    company = company_service.update_company_settings(db, cid, body)
    return success_response(orm_to_dict(company))