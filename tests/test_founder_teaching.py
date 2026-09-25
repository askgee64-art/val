"""Tests for Founder Teaching Mode — Prompt Spec §15."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from learning.founder_teaching import get_founder_teaching_service


@pytest.mark.asyncio
async def test_founder_teaching_provenance(test_session: AsyncSession):
    svc = get_founder_teaching_service()
    org_id = "00000000-0000-4000-8000-000000000010"
    founder_id = "00000000-0000-4000-8000-000000000001"

    statement = (
        "VAL, this is how I want our company to operate: always enforce sandboxing "
        "and never allow automatic deployment to production without my explicit sign-off."
    )

    res = await svc.teach(
        test_session,
        statement=statement,
        org_id=org_id,
        founder_user_id=founder_id,
        scope="company",
    )

    assert res.knowledge_id is not None
    assert res.scope == "company"
    assert res.provenance["source_type"] == "founder_teaching"
    assert res.provenance["authoritative"] is True
    assert res.provenance["teacher_user_id"] == founder_id
    assert len(res.clarifying_questions) >= 1
