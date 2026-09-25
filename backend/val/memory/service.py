"""Memory and Knowledge Service — Document 11 & Document 21 Table 7.

Scoped memory layers:
  - Working (ephemeral per task / conversation)
  - Short-term (days to weeks)
  - Long-term (durable facts, preferences, decisions)
  - Project & Company
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from val.config import get_settings
from val.db.models import MemoryRecord, utcnow
from val.models.enums import MemoryScope


class MemoryService:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def store(
        self,
        session: AsyncSession,
        *,
        org_id: str,
        scope_type: MemoryScope | str,
        content: dict[str, Any],
        key: str | None = None,
        scope_id: str | None = None,
        importance: float = 0.5,
        ttl_hours: int | None = None,
    ) -> MemoryRecord:
        scope_str = scope_type.value if isinstance(scope_type, MemoryScope) else str(scope_type)
        expires_at: datetime | None = None
        if ttl_hours is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        elif scope_str == MemoryScope.WORKING:
            expires_at = datetime.now(timezone.utc) + timedelta(
                hours=self._settings.working_memory_ttl_hours
            )
        elif scope_str == MemoryScope.SHORT_TERM:
            expires_at = datetime.now(timezone.utc) + timedelta(
                days=self._settings.short_term_memory_ttl_days
            )

        # Upsert if key exists in same scope
        if key:
            query = select(MemoryRecord).where(
                MemoryRecord.org_id == org_id,
                MemoryRecord.scope_type == scope_str,
                MemoryRecord.key == key,
            )
            if scope_id:
                query = query.where(MemoryRecord.scope_id == scope_id)
            existing = (await session.execute(query)).scalar_one_or_none()
            if existing is not None:
                existing.content = content
                existing.importance = max(existing.importance, importance)
                existing.expires_at = expires_at
                existing.updated_at = utcnow()
                return existing

        record = MemoryRecord(
            memory_id=str(uuid4()),
            org_id=org_id,
            scope_type=scope_str,
            scope_id=scope_id,
            key=key,
            content=content,
            importance=importance,
            expires_at=expires_at,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(record)
        return record

    async def recall(
        self,
        session: AsyncSession,
        *,
        org_id: str,
        scope_type: MemoryScope | str | None = None,
        key: str | None = None,
        scope_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        query = select(MemoryRecord).where(MemoryRecord.org_id == org_id)

        if scope_type is not None:
            scope_str = scope_type.value if isinstance(scope_type, MemoryScope) else str(scope_type)
            query = query.where(MemoryRecord.scope_type == scope_str)
        if key is not None:
            query = query.where(MemoryRecord.key == key)
        if scope_id is not None:
            query = query.where(MemoryRecord.scope_id == scope_id)

        # Exclude expired
        now = datetime.now(timezone.utc)
        query = query.where(
            (MemoryRecord.expires_at.is_(None)) | (MemoryRecord.expires_at > now)
        )
        query = query.order_by(desc(MemoryRecord.importance), desc(MemoryRecord.created_at)).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_working_context(
        self, session: AsyncSession, org_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch active working memory to seed prompt context."""
        records = await self.recall(
            session,
            org_id=org_id,
            scope_type=MemoryScope.WORKING,
            limit=limit,
        )
        return [
            {"key": r.key, "content": r.content, "created_at": r.created_at.isoformat()}
            for r in records
        ]

    async def prune_expired(self, session: AsyncSession) -> int:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            delete(MemoryRecord).where(
                MemoryRecord.expires_at.is_not(None),
                MemoryRecord.expires_at < now,
            )
        )
        return int(result.rowcount or 0)


_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
