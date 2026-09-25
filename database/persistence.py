"""Persistence Abstraction Layer — Prompt Spec §5, §6, §7.

Provides unified interface across:
  - Local SQLite (offline zero-dependency execution on laptop)
  - Supabase PostgreSQL (connected cloud mode with RLS & pgvector)
  - Hybrid Persistence (local-first with cloud synchronization queue)

Data Tier Classification:
  - Authoritative Cloud: Users, Tenant Orgs, Deployed Agent Registry, Customer records
  - Local-Authoritative: Ephemeral sandbox artifacts, scratch workspaces, local model weights
  - Synchronized: Tasks, Objectives, Approvals, Memory, Knowledge, Audit Logs
  - Cached: System diagnostic probes, model metadata
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from val.config import get_settings
from val.db.models import Agent, Approval, AuditLog, KnowledgeItem, MemoryRecord, Task

logger = logging.getLogger("val.persistence")


class PersistenceService(ABC):
    """Abstract persistence interface."""

    @abstractmethod
    async def save_task(self, session: AsyncSession, task_data: dict[str, Any]) -> str:
        """Create or update a task."""

    @abstractmethod
    async def get_task(self, session: AsyncSession, task_id: str) -> dict[str, Any] | None:
        """Fetch task by ID."""

    @abstractmethod
    async def list_tasks(
        self, session: AsyncSession, org_id: str, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List tasks."""

    @abstractmethod
    async def save_agent(self, session: AsyncSession, agent_data: dict[str, Any]) -> str:
        """Create or update an agent."""

    @abstractmethod
    async def get_agent(self, session: AsyncSession, agent_id: str) -> dict[str, Any] | None:
        """Fetch agent."""

    @abstractmethod
    async def save_approval(self, session: AsyncSession, approval_data: dict[str, Any]) -> str:
        """Save approval."""

    @abstractmethod
    async def log_audit(self, session: AsyncSession, audit_entry: dict[str, Any]) -> str:
        """Append audit record."""


class LocalSQLitePersistence(PersistenceService):
    """Local SQLite persistence for offline laptop operation."""

    async def save_task(self, session: AsyncSession, task_data: dict[str, Any]) -> str:
        task_id = str(task_data.get("task_id") or uuid4())
        existing = await session.get(Task, task_id)
        if existing:
            for k, v in task_data.items():
                if hasattr(existing, k) and k != "task_id":
                    setattr(existing, k, v)
        else:
            task = Task(**task_data)
            session.add(task)
        await session.flush()
        return task_id

    async def get_task(self, session: AsyncSession, task_id: str) -> dict[str, Any] | None:
        task = await session.get(Task, task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "org_id": task.org_id,
            "title": task.title,
            "status": task.status,
            "plan": task.plan,
            "result": task.result,
            "error": task.error,
            "requires_approval": task.requires_approval,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        }

    async def list_tasks(
        self, session: AsyncSession, org_id: str, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        q = select(Task).where(Task.org_id == org_id)
        if status:
            q = q.where(Task.status == status)
        res = await session.execute(q.limit(limit))
        return [
            {
                "task_id": t.task_id,
                "title": t.title,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in res.scalars().all()
        ]

    async def save_agent(self, session: AsyncSession, agent_data: dict[str, Any]) -> str:
        agent_id = str(agent_data.get("agent_id") or uuid4())
        existing = await session.get(Agent, agent_id)
        if existing:
            for k, v in agent_data.items():
                if hasattr(existing, k) and k != "agent_id":
                    setattr(existing, k, v)
        else:
            agent = Agent(**agent_data)
            session.add(agent)
        await session.flush()
        return agent_id

    async def get_agent(self, session: AsyncSession, agent_id: str) -> dict[str, Any] | None:
        agent = await session.get(Agent, agent_id)
        if not agent:
            return None
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "role": agent.role,
            "version": agent.version,
            "status": agent.status,
            "config": agent.config,
            "permissions": agent.permissions,
        }

    async def save_approval(self, session: AsyncSession, approval_data: dict[str, Any]) -> str:
        appr_id = str(approval_data.get("approval_id") or uuid4())
        existing = await session.get(Approval, appr_id)
        if existing:
            for k, v in approval_data.items():
                if hasattr(existing, k) and k != "approval_id":
                    setattr(existing, k, v)
        else:
            appr = Approval(**approval_data)
            session.add(appr)
        await session.flush()
        return appr_id

    async def log_audit(self, session: AsyncSession, audit_entry: dict[str, Any]) -> str:
        log_id = str(audit_entry.get("log_id") or uuid4())
        entry = AuditLog(**audit_entry)
        session.add(entry)
        await session.flush()
        return log_id


class SupabasePersistence(PersistenceService):
    """Direct Supabase REST / PostgreSQL client with RLS & pgvector support."""

    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        self.settings = get_settings()
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)

    async def save_task(self, session: AsyncSession, task_data: dict[str, Any]) -> str:
        task_id = str(task_data.get("task_id") or uuid4())
        task_data["task_id"] = task_id
        if self.is_configured:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{self.url}/rest/v1/tasks",
                        headers=self.headers,
                        json=task_data,
                    )
            except Exception as exc:
                logger.warning("Supabase save_task sync failed: %s", exc)
        return task_id

    async def get_task(self, session: AsyncSession, task_id: str) -> dict[str, Any] | None:
        if self.is_configured:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{self.url}/rest/v1/tasks?task_id=eq.{task_id}",
                        headers=self.headers,
                    )
                    if resp.status_code == 200 and resp.json():
                        return resp.json()[0]
            except Exception as exc:
                logger.warning("Supabase get_task failed: %s", exc)
        return None

    async def list_tasks(
        self, session: AsyncSession, org_id: str, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        if self.is_configured:
            try:
                url = f"{self.url}/rest/v1/tasks?org_id=eq.{org_id}&order=created_at.desc&limit={limit}"
                if status:
                    url += f"&status=eq.{status}"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url, headers=self.headers)
                    if resp.status_code == 200:
                        return resp.json()
            except Exception as exc:
                logger.warning("Supabase list_tasks failed: %s", exc)
        return []

    async def save_agent(self, session: AsyncSession, agent_data: dict[str, Any]) -> str:
        agent_id = str(agent_data.get("agent_id") or uuid4())
        agent_data["agent_id"] = agent_id
        if self.is_configured:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{self.url}/rest/v1/agents",
                        headers=self.headers,
                        json=agent_data,
                    )
            except Exception as exc:
                logger.warning("Supabase save_agent failed: %s", exc)
        return agent_id

    async def get_agent(self, session: AsyncSession, agent_id: str) -> dict[str, Any] | None:
        if self.is_configured:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{self.url}/rest/v1/agents?agent_id=eq.{agent_id}",
                        headers=self.headers,
                    )
                    if resp.status_code == 200 and resp.json():
                        return resp.json()[0]
            except Exception as exc:
                logger.warning("Supabase get_agent failed: %s", exc)
        return None

    async def save_approval(self, session: AsyncSession, approval_data: dict[str, Any]) -> str:
        appr_id = str(approval_data.get("approval_id") or uuid4())
        approval_data["approval_id"] = appr_id
        if self.is_configured:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{self.url}/rest/v1/approvals",
                        headers=self.headers,
                        json=approval_data,
                    )
            except Exception as exc:
                logger.warning("Supabase save_approval failed: %s", exc)
        return appr_id

    async def log_audit(self, session: AsyncSession, audit_entry: dict[str, Any]) -> str:
        log_id = str(audit_entry.get("log_id") or uuid4())
        audit_entry["log_id"] = log_id
        if self.is_configured:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{self.url}/rest/v1/audit_logs",
                        headers=self.headers,
                        json=audit_entry,
                    )
            except Exception as exc:
                logger.warning("Supabase log_audit failed: %s", exc)
        return log_id


class HybridPersistenceService(PersistenceService):
    """Hybrid Persistence: Local-First with non-blocking Cloud Sync.

    Invariants:
    1. Local SQLite write is always guaranteed first (zero-dependency laptop speed).
    2. Cloud sync to Supabase is queued or dual-written asynchronously.
    3. If cloud is unreachable, local operation continues unabated.
    """

    def __init__(self) -> None:
        self.local = LocalSQLitePersistence()
        self.cloud = SupabasePersistence()
        self._sync_queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

    async def save_task(self, session: AsyncSession, task_data: dict[str, Any]) -> str:
        # Write local
        tid = await self.local.save_task(session, task_data)
        # Non-blocking sync to cloud
        if self.cloud.is_configured:
            asyncio.create_task(self.cloud.save_task(session, task_data))
        return tid

    async def get_task(self, session: AsyncSession, task_id: str) -> dict[str, Any] | None:
        res = await self.local.get_task(session, task_id)
        if res is None and self.cloud.is_configured:
            res = await self.cloud.get_task(session, task_id)
        return res

    async def list_tasks(
        self, session: AsyncSession, org_id: str, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        return await self.local.list_tasks(session, org_id, status, limit)

    async def save_agent(self, session: AsyncSession, agent_data: dict[str, Any]) -> str:
        aid = await self.local.save_agent(session, agent_data)
        if self.cloud.is_configured:
            asyncio.create_task(self.cloud.save_agent(session, agent_data))
        return aid

    async def get_agent(self, session: AsyncSession, agent_id: str) -> dict[str, Any] | None:
        res = await self.local.get_agent(session, agent_id)
        if res is None and self.cloud.is_configured:
            res = await self.cloud.get_agent(session, agent_id)
        return res

    async def save_approval(self, session: AsyncSession, approval_data: dict[str, Any]) -> str:
        aid = await self.local.save_approval(session, approval_data)
        if self.cloud.is_configured:
            asyncio.create_task(self.cloud.save_approval(session, approval_data))
        return aid

    async def log_audit(self, session: AsyncSession, audit_entry: dict[str, Any]) -> str:
        lid = await self.local.log_audit(session, audit_entry)
        if self.cloud.is_configured:
            asyncio.create_task(self.cloud.log_audit(session, audit_entry))
        return lid


_persistence_instance: PersistenceService | None = None


def get_persistence_service() -> PersistenceService:
    global _persistence_instance
    if _persistence_instance is None:
        _persistence_instance = HybridPersistenceService()
    return _persistence_instance
