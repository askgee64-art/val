"""Tests for Hybrid & Supabase Persistence — Prompt Spec §5, §6, §7."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from database.persistence import (
    HybridPersistenceService,
    LocalSQLitePersistence,
    SupabasePersistence,
)


@pytest.mark.asyncio
async def test_persistence_abstraction(test_session: AsyncSession):
    service = HybridPersistenceService()
    org_id = "00000000-0000-4000-8000-000000000010"

    task_id = await service.save_task(
        test_session,
        {
            "org_id": org_id,
            "title": "Hybrid Persistence Test Task",
            "status": "pending",
        },
    )
    assert task_id is not None

    task = await service.get_task(test_session, task_id)
    assert task is not None
    assert task["title"] == "Hybrid Persistence Test Task"

    # Test SupabasePersistence is_configured flag
    sp = SupabasePersistence()
    assert isinstance(sp.is_configured, bool)
