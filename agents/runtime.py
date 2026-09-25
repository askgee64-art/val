"""Agent Runtime — Isolated execution context for specialized VAL agents.

Document 05 §4 & Master Spec §7:
  Loads agent config, provides isolated execution context, enforces
  tool allow-lists, restricts memory scope, and audits all actions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.registry import get_agent_registry
from val.audit.logger import get_audit_logger
from val.core.model_router import get_model_router
from val.db.models import Agent
from val.memory.service import get_memory_service
from val.models.enums import ActorType, PermissionLevel
from val.permissions.engine import PermissionContext, get_permission_engine
from val.tools.registry import get_tool_registry


@dataclass
class AgentExecutionResult:
    success: bool
    output: str
    tool_calls: list[dict[str, Any]]
    error: str | None = None
    agent_name: str = ""
    version: str = "1.0.0"


class AgentRuntime:
    def __init__(self) -> None:
        self._router = get_model_router()
        self._registry = get_tool_registry()
        self._perm_engine = get_permission_engine()
        self._memory = get_memory_service()
        self._audit = get_audit_logger()

    async def run(
        self,
        session: AsyncSession,
        *,
        agent: Agent,
        input_text: str,
        task_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AgentExecutionResult:
        config = agent.config or {}
        permissions = agent.permissions or {}
        tool_allow_list = permissions.get("tool_allow_list", [])
        max_level = permissions.get("max_level", PermissionLevel.EXECUTE)

        # 1. Permission Context for this specific specialized agent
        ctx = PermissionContext(
            actor_type=ActorType.AGENT,
            actor_id=agent.agent_id,
            org_id=agent.org_id,
            agent_max_level=max_level,
            tool_allow_list=tool_allow_list,
            is_founder=False,
        )

        # 2. Working memory retrieval
        agent_memories = await self._memory.recall(
            session,
            org_id=agent.org_id,
            scope_type="agent",
            scope_id=agent.agent_id,
            limit=5,
        )
        mem_text = "\n".join([f"- {m.key}: {json.dumps(m.content)}" for m in agent_memories])

        # 3. Assemble prompt with strict domain system prompt
        system_prompt = config.get(
            "system_prompt", f"You are {agent.name}, a specialized AI agent for {agent.role}."
        )
        if mem_text:
            system_prompt += f"\n\nAgent Scoped Memory:\n{mem_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text},
        ]

        # 4. Generate response via model router
        response = await self._router.complete(messages, temperature=0.1)

        # 5. Record agent action in audit
        await self._audit.log(
            session,
            org_id=agent.org_id,
            actor_type=ActorType.AGENT,
            actor_id=agent.agent_id,
            action=f"agent.executed.{agent.name}",
            resource_type="task" if task_id else "direct_query",
            resource_id=task_id,
            details={"input_snippet": input_text[:100], "model": response.model},
        )

        return AgentExecutionResult(
            success=True,
            output=response.content,
            tool_calls=[],
            agent_name=agent.name,
            version=agent.version,
        )


_agent_runtime: AgentRuntime | None = None


def get_agent_runtime() -> AgentRuntime:
    global _agent_runtime
    if _agent_runtime is None:
        _agent_runtime = AgentRuntime()
    return _agent_runtime
