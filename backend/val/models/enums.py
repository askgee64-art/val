"""Shared enumerations for VAL domain models."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class PermissionLevel(IntEnum):
    """Permission levels — Document 09.

    L0 Observe | L1 Recommend | L2 Execute | L3 Delegate | L4 High-Impact (approval)
    """

    OBSERVE = 0
    RECOMMEND = 1
    EXECUTE = 2
    DELEGATE = 3
    HIGH_IMPACT = 4


class RiskClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class AgentStatus(StrEnum):
    DRAFT = "draft"
    TESTING = "testing"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ActorType(StrEnum):
    USER = "user"
    AGENT = "system_agent"
    SYSTEM = "system"
    VAL = "val"


class MemoryScope(StrEnum):
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    USER = "user"
    AGENT = "agent"
    PROJECT = "project"
    COMPANY = "company"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class OrgStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class UserRole(StrEnum):
    FOUNDER = "founder"
    OPERATOR = "operator"
    VIEWER = "viewer"
    CUSTOMER_ADMIN = "customer_admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    DISABLED = "disabled"


class EventType(StrEnum):
    OBJECTIVE_RECEIVED = "objective.received"
    PLAN_CREATED = "plan.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TOOL_INVOKED = "tool.invoked"
    TOOL_DENIED = "tool.denied"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    MEMORY_WRITTEN = "memory.written"
    SYSTEM_PAUSED = "system.paused"
    SYSTEM_RESUMED = "system.resumed"
    EMERGENCY = "system.emergency"
    MESSAGE = "message.created"
