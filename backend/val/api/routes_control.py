"""Emergency Control Plane — Document 28 & Master Spec §11.

Founder-controlled kill-switches and global pause mechanisms that operate
independently of the LLM reasoning loop.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.audit.logger import get_audit_logger
from val.db.models import User
from val.db.session import get_session
from val.models.enums import ActorType, EventType
from val.permissions.engine import get_permission_engine
from val.tools.registry import get_tool_registry

router = APIRouter(prefix="/control", tags=["Emergency Control Plane"])


class ControlResponse(BaseModel):
    status: str
    global_paused: bool
    emergency: bool
    message: str


@router.post("/pause", response_model=ControlResponse)
async def pause_system(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ControlResponse:
    if user.role != "founder":
        raise HTTPException(status_code=403, detail="founder_only")

    engine = get_permission_engine()
    engine.pause()

    audit = get_audit_logger()
    await audit.log(
        session,
        org_id=user.org_id,
        actor_type=ActorType.USER,
        actor_id=user.user_id,
        action=EventType.SYSTEM_PAUSED,
        resource_type="control",
        details={"reason": "founder_manual_pause"},
    )
    await session.commit()

    return ControlResponse(
        status="paused",
        global_paused=True,
        emergency=engine.emergency,
        message="System paused. All mutating actions are blocked.",
    )


@router.post("/resume", response_model=ControlResponse)
async def resume_system(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ControlResponse:
    if user.role != "founder":
        raise HTTPException(status_code=403, detail="founder_only")

    engine = get_permission_engine()
    if engine.emergency:
        raise HTTPException(
            status_code=400,
            detail="cannot_resume_while_emergency_is_active_clear_emergency_first",
        )

    engine.resume()

    audit = get_audit_logger()
    await audit.log(
        session,
        org_id=user.org_id,
        actor_type=ActorType.USER,
        actor_id=user.user_id,
        action=EventType.SYSTEM_RESUMED,
        resource_type="control",
        details={"reason": "founder_manual_resume"},
    )
    await session.commit()

    return ControlResponse(
        status="active",
        global_paused=False,
        emergency=False,
        message="System resumed normal autonomous operations.",
    )


@router.post("/emergency", response_model=ControlResponse)
async def trigger_emergency(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ControlResponse:
    if user.role != "founder":
        raise HTTPException(status_code=403, detail="founder_only")

    engine = get_permission_engine()
    engine.trigger_emergency()

    audit = get_audit_logger()
    await audit.log(
        session,
        org_id=user.org_id,
        actor_type=ActorType.USER,
        actor_id=user.user_id,
        action=EventType.EMERGENCY,
        resource_type="control",
        details={"reason": "founder_emergency_shutdown_triggered"},
    )
    await session.commit()

    return ControlResponse(
        status="emergency_shutdown",
        global_paused=True,
        emergency=True,
        message="EMERGENCY SHUTDOWN ACTIVATED. All tools and autonomy tasks are hard frozen.",
    )


@router.post("/emergency/clear", response_model=ControlResponse)
async def clear_emergency(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ControlResponse:
    if user.role != "founder":
        raise HTTPException(status_code=403, detail="founder_only")

    engine = get_permission_engine()
    engine.clear_emergency()

    audit = get_audit_logger()
    await audit.log(
        session,
        org_id=user.org_id,
        actor_type=ActorType.USER,
        actor_id=user.user_id,
        action="system.emergency_cleared",
        resource_type="control",
        details={"reason": "founder_cleared_emergency"},
    )
    await session.commit()

    return ControlResponse(
        status="active",
        global_paused=False,
        emergency=False,
        message="Emergency cleared. System restored to normal state.",
    )


@router.post("/tools/{tool_name}/toggle")
async def toggle_tool(
    tool_name: str,
    enabled: bool,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if user.role != "founder":
        raise HTTPException(status_code=403, detail="founder_only")

    engine = get_permission_engine()
    registry = get_tool_registry()
    tool = registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="tool_not_found")

    if enabled:
        engine.enable_tool(tool_name)
        tool.meta.is_enabled = True
    else:
        engine.disable_tool(tool_name)
        tool.meta.is_enabled = False

    return {"tool": tool_name, "is_enabled": tool.meta.is_enabled}
