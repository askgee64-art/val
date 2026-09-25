"""Memory query and store endpoints — Document 11 & Document 21 Table 7."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.db.models import User
from val.db.session import get_session
from val.memory.service import get_memory_service
from val.models.enums import MemoryScope
from val.models.schemas import MemoryRecordOut

router = APIRouter(prefix="/memory", tags=["Memory"])


class MemoryStoreRequest(BaseModel):
    scope_type: MemoryScope = MemoryScope.WORKING
    key: str | None = None
    content: dict[str, Any]
    importance: float = 0.5
    ttl_hours: int | None = None


@router.get("", response_model=list[MemoryRecordOut])
async def recall_memory(
    scope: MemoryScope | None = None,
    key: str | None = None,
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[MemoryRecordOut]:
    service = get_memory_service()
    records = await service.recall(
        session,
        org_id=user.org_id,
        scope_type=scope,
        key=key,
        limit=limit,
    )
    return [MemoryRecordOut.model_validate(r) for r in records]


@router.post("", response_model=MemoryRecordOut)
async def store_memory(
    body: MemoryStoreRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MemoryRecordOut:
    service = get_memory_service()
    rec = await service.store(
        session,
        org_id=user.org_id,
        scope_type=body.scope_type,
        key=body.key,
        content=body.content,
        importance=body.importance,
        ttl_hours=body.ttl_hours,
    )
    await session.commit()
    return MemoryRecordOut.model_validate(rec)
