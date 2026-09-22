from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.user import User
from services.audit_service import list_audit_logs

router = APIRouter()


@router.get("/")
def audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    company_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "audit.view")
    cid = resolve_company_id(user, company_id if company_id else None)
    result = list_audit_logs(
        db,
        company_id=cid,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    if not isinstance(result, dict):
        result = {"items": [orm_to_dict(r) for r in result], "total": len(result), "page": 1, "page_size": len(result), "pages": 1}
    else:
        result["items"] = [orm_to_dict(i) for i in result.get("items", [])]
    return success_response(result)