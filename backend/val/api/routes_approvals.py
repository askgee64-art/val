"""Approvals management — Document 09 §2 & Master Spec §6 (Level 4 gate)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.core.orchestrator import get_orchestrator
from val.db.models import Approval, User
from val.db.session import get_session
from val.models.enums import ApprovalStatus
from val.models.schemas import ApprovalDecision, ApprovalOut, TaskOut

router = APIRouter(prefix="/approvals", tags=["Approvals (Level 4)"])


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ApprovalOut]:
    q = select(Approval).where(Approval.org_id == user.org_id)
    if status:
        q = q.where(Approval.status == status)
    else:
        # Default: show pending first
        pass
    q = q.order_by(desc(Approval.created_at)).limit(50)
    res = await session.execute(q)
    return [ApprovalOut.model_validate(a) for a in res.scalars().all()]


@router.get("/{approval_id}", response_model=ApprovalOut)
async def get_approval(
    approval_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ApprovalOut:
    appr = await session.get(Approval, approval_id)
    if appr is None or appr.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="approval_not_found")
    return ApprovalOut.model_validate(appr)


@router.post("/{approval_id}/decide", response_model=TaskOut)
async def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TaskOut:
    if user.role != "founder":
        raise HTTPException(
            status_code=403, detail="only_founder_can_decide_level_4_approvals"
        )

    orchestrator = get_orchestrator()
    try:
        task = await orchestrator.decide_approval(
            session,
            approval_id=approval_id,
            user_id=user.user_id,
            org_id=user.org_id,
            decision=body.decision,
            reason=body.reason,
        )
        return TaskOut.model_validate(task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
