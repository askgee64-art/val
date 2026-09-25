"""Tests for Agent Factory & Specialized Agent Workforce — Prompt Spec §13."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agents.factory import get_agent_factory
from agents.registry import get_agent_registry
from agents.runtime import get_agent_runtime
from val.models.enums import AgentStatus


@pytest.mark.asyncio
async def test_agent_factory_creates_calculus_val(test_session: AsyncSession):
    factory = get_agent_factory()
    registry = get_agent_registry()
    org_id = "00000000-0000-4000-8000-000000000010"

    # Autonomous creation of CALCULUS.VAL
    result = await factory.create_specialized_agent(
        test_session,
        objective="Learn calculus well enough to teach me",
        org_id=org_id,
    )

    assert result.success is True
    assert result.agent_name == "CALCULUS.VAL"
    assert result.validation_passed is True
    assert len(result.test_results) >= 2

    # Verify agent exists in registry
    agent = await registry.get(test_session, "CALCULUS.VAL", org_id)
    assert agent is not None
    assert agent.name == "CALCULUS.VAL"
    assert "calculator" in agent.config["tool_allow_list"]
    assert agent.status == AgentStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_agent_runtime_isolated_execution(test_session: AsyncSession):
    factory = get_agent_factory()
    runtime = get_agent_runtime()
    org_id = "00000000-0000-4000-8000-000000000010"

    build_res = await factory.create_specialized_agent(
        test_session,
        objective="Build python algorithms and scripts",
        org_id=org_id,
        force_name="CODE.VAL",
    )
    assert build_res.success is True
    agent = build_res.agent
    assert agent is not None

    # Execute isolated query on CODE.VAL
    run_res = await runtime.run(
        test_session,
        agent=agent,
        input_text="Write a function to compute factorial",
    )

    assert run_res.success is True
    assert run_res.agent_name == "CODE.VAL"
    assert len(run_res.output) > 0
