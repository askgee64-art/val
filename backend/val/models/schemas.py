"""Pydantic request/response schemas for VAL API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from val.models.enums import (
    ApprovalStatus,
    MemoryScope,
    MessageRole,
    PermissionLevel,
    RiskClass,
    TaskStatus,
)


class ObjectiveRequest(BaseModel):
    """Founder submits a natural-language objective."""

    objective: str = Field(..., min_length=1, max_length=10_000)
    context: dict[str, Any] | None = None
    auto_execute: bool = Field(
        default=True,
        description="If true, VAL executes plan steps within permission bounds automatically.",
    )
    project_id: UUID | None = None


class PlanStep(BaseModel):
    """A single step in a structured plan."""

    step_id: int
    title: str
    description: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    required_permission_level: PermissionLevel = PermissionLevel.EXECUTE
    risk_class: RiskClass = RiskClass.LOW
    depends_on: list[int] = Field(default_factory=list)
    success_criteria: str | None = None
    status: str = "pending"
    result: Any | None = None
    error: str | None = None


class Plan(BaseModel):
    """Structured multi-step plan produced by VAL planner."""

    plan_id: str
    objective: str
    summary: str
    steps: list[PlanStep]
    risk_flags: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    estimated_tool_calls: int = 0
    model_used: str | None = None
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    input: dict[str, Any] | None = None
    priority: int = 0


class TaskOut(BaseModel):
    task_id: UUID
    org_id: UUID
    title: str
    description: str | None = None
    status: TaskStatus
    priority: int = 0
    input: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    requires_approval: bool = False
    approval_id: UUID | None = None
    parent_task_id: UUID | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    message_id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=20_000)
    conversation_id: UUID | None = None
    auto_execute: bool = True


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: MessageOut
    task: TaskOut | None = None
    plan: Plan | None = None
    status: str


class ApprovalOut(BaseModel):
    approval_id: UUID
    org_id: UUID
    task_id: UUID | None = None
    action_type: str
    action_payload: dict[str, Any]
    risk_level: int
    status: ApprovalStatus
    decided_by: UUID | None = None
    decision_reason: str | None = None
    created_at: datetime
    decided_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    reason: str | None = None


class ToolInfo(BaseModel):
    name: str
    description: str
    risk_class: RiskClass
    required_permission_level: PermissionLevel
    is_enabled: bool
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None


class AuditLogOut(BaseModel):
    log_id: UUID
    org_id: UUID
    actor_type: str
    actor_id: UUID | None = None
    action: str
    resource_type: str | None = None
    resource_id: UUID | None = None
    details: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryRecordOut(BaseModel):
    memory_id: UUID
    scope_type: MemoryScope
    scope_id: UUID | None = None
    key: str | None = None
    content: dict[str, Any]
    importance: float = 0.5
    expires_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SystemStatus(BaseModel):
    app_name: str
    version: str
    environment: str
    global_paused: bool
    emergency: bool
    database_ok: bool
    tools_registered: int
    tools_enabled: int
    pending_approvals: int
    running_tasks: int
    model_mode: str  # "REAL_MODEL" | "DEGRADED_FALLBACK" | "local_fallback"
    model_status: str = "CONNECTED"  # "CONNECTED" | "UNAVAILABLE"
    memory_status: str = "CONNECTED"
    autonomy_status: str = "RUNNING"
    active_model: str = "gemini-3.5-flash-lite"
    uptime_seconds: float
    founder_authenticated: bool = False
    founder_display_name: str = "Tomiwa"
