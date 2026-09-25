"""Agent Registry — Document 05, Document 06 & Document 21 Table 2.

Manages the registration, version snapshots, lifecycle states, and discovery
of all specialized VAL agents.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.models import AgentCreate
from val.audit.logger import get_audit_logger
from val.db.models import Agent, utcnow
from val.models.enums import ActorType, AgentStatus


class AgentRegistry:
    def __init__(self) -> None:
        self._audit = get_audit_logger()

    async def register(
        self,
        session: AsyncSession,
        *,
        org_id: str,
        user_id: str | None,
        data: AgentCreate,
        parent_agent_id: str | None = None,
        status: AgentStatus = AgentStatus.ACTIVE,
    ) -> Agent:
        """Register a new specialized agent in the workforce."""
        # Check uniqueness per org
        q = select(Agent).where(Agent.org_id == org_id, Agent.name == data.name)
        existing = (await session.execute(q)).scalar_one_or_none()
        if existing:
            raise ValueError(f"Agent '{data.name}' is already registered in this organization.")

        agent = Agent(
            agent_id=str(uuid4()),
            org_id=org_id,
            parent_agent_id=parent_agent_id,
            name=data.name,
            role=data.role,
            version="1.0.0",
            status=status.value,
            config=data.config.model_dump(mode="json"),
            permissions={
                "max_level": int(data.config.max_permission_level),
                "tool_allow_list": data.config.tool_allow_list,
                "can_delegate": False,
            },
            knowledge_sources=data.knowledge_sources,
            created_by=user_id,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(agent)
        await session.flush()

        await self._audit.log(
            session,
            org_id=org_id,
            actor_type=ActorType.USER if user_id else ActorType.VAL,
            actor_id=user_id,
            action=f"agent.registered.{data.name}",
            resource_type="agent",
            resource_id=agent.agent_id,
            details={"role": data.role, "version": "1.0.0", "tools": data.config.tool_allow_list},
        )
        return agent

    async def get(self, session: AsyncSession, agent_id_or_name: str, org_id: str) -> Agent | None:
        # Check by UUID or by Name
        q = select(Agent).where(Agent.org_id == org_id)
        if len(agent_id_or_name) == 36 and "-" in agent_id_or_name:
            q = q.where(Agent.agent_id == agent_id_or_name)
        else:
            q = q.where(Agent.name == agent_id_or_name)
        return (await session.execute(q)).scalar_one_or_none()

    async def list_agents(
        self, session: AsyncSession, org_id: str, status: str | None = None
    ) -> list[Agent]:
        q = select(Agent).where(Agent.org_id == org_id)
        if status:
            q = q.where(Agent.status == status)
        res = await session.execute(q.order_by(Agent.name.asc()))
        return list(res.scalars().all())

    async def update_status(
        self, session: AsyncSession, agent_id: str, new_status: AgentStatus, user_id: str | None = None
    ) -> Agent:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        old_status = agent.status
        agent.status = new_status.value
        agent.updated_at = utcnow()
        if new_status == AgentStatus.RETIRED:
            agent.retired_at = utcnow()

        await self._audit.log(
            session,
            org_id=agent.org_id,
            actor_type=ActorType.USER if user_id else ActorType.VAL,
            actor_id=user_id,
            action="agent.status_updated",
            resource_type="agent",
            resource_id=agent_id,
            details={"from": old_status, "to": new_status.value},
        )
        return agent


_agent_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry
