"""SQLAlchemy ORM models — aligned with Document 21 (Database Design).

MVP uses SQLite for zero-dependency local boot. Schema maps 1:1 to the
PostgreSQL design so production migration is a connection-string change +
type swaps (UUID, JSONB, VECTOR).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator, CHAR


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class GUID(TypeDecorator):
    """Platform-independent UUID stored as string(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    org_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    plan_tier: Mapped[str] = mapped_column(String(64), default="internal")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.org_id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(32), default="founder")
    status: Mapped[str] = mapped_column(String(32), default="active")
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.org_id"), nullable=False)
    parent_agent_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    status: Mapped[str] = mapped_column(String(32), default="active")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    knowledge_sources: Mapped[dict] = mapped_column(JSON, default=list)
    created_by: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.org_id"), nullable=False)
    agent_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    parent_task_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolRecord(Base):
    __tablename__ = "tools"

    tool_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    risk_class: Mapped[str] = mapped_column(String(16), default="low")
    required_permission_level: Mapped[int] = mapped_column(Integer, default=2)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    effect: Mapped[str] = mapped_column(String(16), default="allow")  # allow | deny
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    memory_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.org_id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    knowledge_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.org_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="human")
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_score: Mapped[float] = mapped_column(Float, default=0.5)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.org_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    owner_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Approval(Base):
    __tablename__ = "approvals"

    approval_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.org_id"), nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    requested_by: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    action_type: Mapped[str] = mapped_column(String(128), nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk_level: Mapped[int] = mapped_column(Integer, default=4)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    decided_by: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    """Immutable append-only audit log. Never update or delete rows."""

    __tablename__ = "audit_logs"

    log_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.org_id"), nullable=False)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.user_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), default="Conversation")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("conversations.conversation_id"), nullable=False
    )
    org_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Prevent updates/deletes on audit_logs at the ORM level
@event.listens_for(AuditLog, "before_update")
def _audit_no_update(mapper, connection, target):  # type: ignore[no-untyped-def]
    raise RuntimeError("audit_logs is immutable — updates are forbidden")


@event.listens_for(AuditLog, "before_delete")
def _audit_no_delete(mapper, connection, target):  # type: ignore[no-untyped-def]
    raise RuntimeError("audit_logs is immutable — deletes are forbidden")
