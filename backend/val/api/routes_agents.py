"""Agent Registry & Agent Factory API endpoints — Prompt Spec §13."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agents.factory import get_agent_factory
from agents.registry import get_agent_registry
from agents.runtime import get_agent_runtime
from val.api.auth import get_current_user
from val.db.models import User
from val.db.session import get_session

router = APIRouter(prefix="/agents", tags=["Workforce & Agent Factory"])


class FactoryBuildRequest(BaseModel):
    objective: str
    force_name: str | None = None


class AgentQueryRequest(BaseModel):
    query: str
    context: dict[str, Any] | None = None


@router.post("/factory/build")
async def build_specialized_agent(
    body: FactoryBuildRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    factory = get_agent_factory()
    result = await factory.create_specialized_agent(
        session,
        objective=body.objective,
        org_id=user.org_id,
        user_id=user.user_id,
        force_name=body.force_name,
    )
    await session.commit()
    return {
        "success": result.success,
        "agent_name": result.agent_name,
        "agent_id": result.agent.agent_id if result.agent else None,
        "validation_passed": result.validation_passed,
        "test_results": result.test_results,
        "requires_founder_approval": result.requires_founder_approval,
        "error": result.error,
    }


@router.get("")
async def list_agents(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    registry = get_agent_registry()
    agents = await registry.list_agents(session, org_id=user.org_id, status=status)
    return [
        {
            "agent_id": a.agent_id,
            "name": a.name,
            "role": a.role,
            "version": a.version,
            "status": a.status,
            "config": a.config,
            "permissions": a.permissions,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in agents
    ]


@router.get("/{id_or_name}")
async def get_agent_details(
    id_or_name: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    registry = get_agent_registry()
    agent = await registry.get(session, id_or_name, org_id=user.org_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{id_or_name}' not found")
    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "role": agent.role,
        "version": agent.version,
        "status": agent.status,
        "config": agent.config,
        "permissions": agent.permissions,
        "knowledge_sources": agent.knowledge_sources,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


@router.post("/{id_or_name}/run")
async def run_agent(
    id_or_name: str,
    body: AgentQueryRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    registry = get_agent_registry()
    agent = await registry.get(session, id_or_name, org_id=user.org_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{id_or_name}' not found")

    runtime = get_agent_runtime()
    result = await runtime.run(
        session,
        agent=agent,
        input_text=body.query,
        context=body.context,
    )
    await session.commit()
    return {
        "success": result.success,
        "agent_name": result.agent_name,
        "output": result.output,
        "version": result.version,
        "error": result.error,
    }
