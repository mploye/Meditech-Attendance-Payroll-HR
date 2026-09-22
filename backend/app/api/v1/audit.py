"""Audit log endpoints under /audit."""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.audit import AuditLog
from models.user import User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
def audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "audit.view")
    scope = company_scope(user=user)
    stmt = select(AuditLog).where(AuditLog.company_id == scope)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if from_date:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        stmt = stmt.where(AuditLog.created_at <= datetime.combine(to_date, datetime.max.time()))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return success_response(
        {"items": orm_to_dict(rows), "total": total, "page": page, "page_size": page_size}
    )


@router.get("/stats")
def audit_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "audit.view")
    scope = company_scope(user=user)
    rows = db.execute(
        select(AuditLog.action, func.count(AuditLog.id).label("count"))
        .where(AuditLog.company_id == scope)
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
    ).all()
    total = db.scalar(select(func.count(AuditLog.id)).where(AuditLog.company_id == scope)) or 0
    return success_response(
        {"total": total, "by_action": [{"action": action, "count": count} for action, count in rows]}
    )