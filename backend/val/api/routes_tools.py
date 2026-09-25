"""Tool inspection and direct invocation — Document 12."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.db.models import User
from val.db.session import get_session
from val.models.enums import ActorType, PermissionLevel
from val.models.schemas import ToolInfo
from val.permissions.engine import PermissionContext
from val.tools.registry import get_tool_registry

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.get("", response_model=list[ToolInfo])
async def list_tools(user: User = Depends(get_current_user)) -> list[ToolInfo]:
    registry = get_tool_registry()
    return registry.list_tools()


@router.post("/{tool_name}/execute")
async def execute_tool(
    tool_name: str,
    params: dict[str, Any],
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    registry = get_tool_registry()
    ctx = PermissionContext(
        actor_type=ActorType.USER,
        actor_id=user.user_id,
        org_id=user.org_id,
        agent_max_level=PermissionLevel.HIGH_IMPACT if user.role == "founder" else PermissionLevel.EXECUTE,
        is_founder=user.role == "founder",
    )

    result = await registry.execute(
        tool_name,
        params,
        ctx=ctx,
        session=session,
    )
    await session.commit()
    return result.to_dict()
