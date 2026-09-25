"""Audit log endpoints — Document 21 Table 11 & Master Spec §11."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.db.models import AuditLog, User
from val.db.session import get_session
from val.models.schemas import AuditLogOut

router = APIRouter(prefix="/audit", tags=["Audit Log"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    action: str | None = None,
    actor_type: str | None = None,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[AuditLogOut]:
    q = select(AuditLog).where(AuditLog.org_id == user.org_id)
    if action:
        q = q.where(AuditLog.action.like(f"%{action}%"))
    if actor_type:
        q = q.where(AuditLog.actor_type == actor_type)

    q = q.order_by(desc(AuditLog.created_at)).limit(limit)
    res = await session.execute(q)
    return [AuditLogOut.model_validate(log) for log in res.scalars().all()]
