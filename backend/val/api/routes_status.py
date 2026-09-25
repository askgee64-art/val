"""System status and diagnostics endpoints — Document 24 & Prompt Spec §8, §9."""

from __future__ import annotations

import time
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.config import get_settings
from val.db.models import Approval, Task, User
from val.db.session import get_session, health_check
from val.models.enums import ApprovalStatus, TaskStatus
from val.models.schemas import SystemStatus
from val.permissions.engine import get_permission_engine
from val.tools.builtins import SystemInfoTool
from val.tools.registry import get_tool_registry

router = APIRouter(tags=["Status & Diagnostics"])
_START_TIME = time.time()


@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> SystemStatus:
    settings = get_settings()
    engine = get_permission_engine()
    registry = get_tool_registry()

    db_ok = await health_check()

    # Pending approvals
    appr_q = select(func.count()).select_from(Approval).where(Approval.status == ApprovalStatus.PENDING)
    pending_approvals = (await session.execute(appr_q)).scalar() or 0

    # Running tasks
    task_q = select(func.count()).select_from(Task).where(Task.status.in_([TaskStatus.RUNNING, TaskStatus.PLANNING]))
    running_tasks = (await session.execute(task_q)).scalar() or 0

    tools = registry.list_tools()
    tools_registered = len(tools)
    tools_enabled = len([t for t in tools if t.is_enabled])

    model_mode = "remote" if settings.openai_api_key else "local_fallback"

    return SystemStatus(
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        global_paused=engine.global_paused,
        emergency=engine.emergency,
        database_ok=db_ok,
        tools_registered=tools_registered,
        tools_enabled=tools_enabled,
        pending_approvals=pending_approvals,
        running_tasks=running_tasks,
        model_mode=model_mode,
        uptime_seconds=round(time.time() - _START_TIME, 1),
        founder_authenticated=user.role == "founder",
        founder_display_name=user.display_name or settings.founder_display_name,
    )


@router.get("/diagnostics")
async def get_diagnostics(user: User = Depends(get_current_user)) -> dict:
    tool = SystemInfoTool()
    res = await tool.execute({})
    return res.output or {}
