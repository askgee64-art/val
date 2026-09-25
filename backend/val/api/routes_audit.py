"""Audit log endpoints — Document 21 Table 11 & Master Spec §11."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.db.models import AuditLog, User
from val.db.session import get_session
from val.models.schemas import AuditLogOut

router = APIRouter(tags=["Audit & Activity"])


def format_activity_title(action: str, actor_type: str, details: dict | None) -> str:
    details = details or {}
    if action == "objective.received":
        return f"VAL received new objective: '{details.get('objective', '')[:50]}...'"
    elif action == "plan.created":
        return f"VAL structured an autonomous execution plan ({details.get('steps_count', 0)} steps)"
    elif action == "task.completed":
        return "VAL completed an autonomous task"
    elif action.startswith("factory.agent_created."):
        name = action.replace("factory.agent_created.", "")
        return f"VAL manufactured specialized agent {name}"
    elif action.startswith("agent.registered."):
        name = action.replace("agent.registered.", "")
        return f"Specialized agent {name} was registered into the workforce"
    elif action == "learning.objective_initialized":
        return f"VAL initiated learning curriculum for {details.get('subject', 'specialized subject')}"
    elif action == "learning.cycle_advanced":
        return f"Knowledge evaluation completed on topic: {details.get('topic', 'concept')}"
    elif action == "founder.taught_knowledge":
        return f"Founder personally taught VAL: {details.get('topic', 'directive')}"
    elif action == "approval.requested":
        return "VAL requested Founder approval for a Level 4 action"
    elif action == "approval.decided":
        return f"Founder {details.get('decision', 'decided')} Level 4 action"
    elif action.startswith("tool.executed."):
        tool = action.replace("tool.executed.", "")
        return f"Executed safe capability [{tool}]"
    elif action.startswith("tool.denied."):
        tool = action.replace("tool.denied.", "")
        return f"Security policy blocked [{tool}]"
    elif action == "system.paused":
        return "Autonomy loop paused by Founder"
    elif action == "system.resumed":
        return "Autonomy loop resumed by Founder"
    elif action == "system.emergency":
        return "Emergency stop activated by Founder"
    return f"{actor_type.upper()}: {action}"


@router.get("/activity")
async def list_recent_activity(
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict]:
    q = (
        select(AuditLog)
        .where(AuditLog.org_id == user.org_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    res = await session.execute(q)
    logs = res.scalars().all()
    return [
        {
            "id": log.log_id,
            "title": format_activity_title(log.action, log.actor_type, log.details),
            "raw_action": log.action,
            "actor": log.actor_type,
            "resource_type": log.resource_type,
            "details": log.details,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/audit", response_model=list[AuditLogOut])
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
