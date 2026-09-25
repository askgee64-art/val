"""Agent definitions and schemas — Document 05, Document 06 & Prompt Spec §13."""

from __future__ import annotations

from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field

from val.models.enums import AgentStatus, PermissionLevel


class AgentConfig(BaseModel):
    system_prompt: str
    domain: str
    model_preferences: dict[str, str] = Field(default_factory=lambda: {"default": "gemini-1.5-flash"})
    tool_allow_list: list[str] = Field(default_factory=list)
    memory_scope: list[str] = Field(default_factory=lambda: ["working", "short_term", "agent"])
    max_permission_level: PermissionLevel = PermissionLevel.EXECUTE
    evaluation_criteria: list[str] = Field(default_factory=list)
    learning_objective_id: str | None = None


class AgentCreate(BaseModel):
    name: str = Field(..., pattern=r"^[A-Z0-9_\-\.]+$", description="e.g. CALCULUS.VAL")
    role: str
    domain: str
    config: AgentConfig
    knowledge_sources: list[str] = Field(default_factory=list)


class AgentOut(BaseModel):
    agent_id: UUID
    org_id: UUID
    parent_agent_id: UUID | None = None
    name: str
    role: str
    version: str
    status: AgentStatus
    config: dict[str, Any]
    permissions: dict[str, Any]
    knowledge_sources: list[Any] = Field(default_factory=list)
    created_at: str
    retired_at: str | None = None
