"""Tests for Autonomous Learning System — Prompt Spec §14."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from learning.engine import get_learning_engine
from learning.models import LearningObjectiveCreate


@pytest.mark.asyncio
async def test_calculus_learning_loop(test_session: AsyncSession):
    engine = get_learning_engine()
    org_id = "00000000-0000-4000-8000-000000000010"
    user_id = "00000000-0000-4000-8000-000000000001"

    # Initialize "Learn calculus" objective
    state = await engine.initialize_objective(
        test_session,
        org_id=org_id,
        user_id=user_id,
        data=LearningObjectiveCreate(
            subject="Calculus",
            goal="Learn calculus well enough to teach me",
        ),
    )

    obj_id = state["objective_id"]
    assert state["subject"] == "Calculus"
    assert state["agent_name"] == "CALCULUS.VAL"
    assert len(state["curriculum"]["topics"]) >= 4

    # Advance first learning step (Limits & Continuity)
    step_1 = await engine.advance_learning(test_session, obj_id)
    assert step_1.practice_score > 0.0
    assert step_1.overall_progress > 0.0
    assert "Limits" in step_1.topic_title

    # Advance until weakness detection or progress advances
    step_2 = await engine.advance_learning(test_session, obj_id)
    assert step_2.overall_progress >= step_1.overall_progress
