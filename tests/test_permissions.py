"""Tests for Permission Engine — Document 09 & Master Spec §6."""

import pytest
from val.models.enums import PermissionLevel, RiskClass
from val.permissions.engine import PermissionContext, PermissionEngine


def test_permission_observe_level():
    engine = PermissionEngine()
    ctx = PermissionContext(
        actor_type="val",
        actor_id=None,
        org_id="test-org",
        agent_max_level=PermissionLevel.EXECUTE,
    )
    decision = engine.evaluate(
        action="view_status",
        resource_type="system",
        required_level=PermissionLevel.OBSERVE,
        ctx=ctx,
    )
    assert decision.allowed is True
    assert decision.requires_approval is False


def test_permission_level_4_requires_approval():
    engine = PermissionEngine()
    ctx = PermissionContext(
        actor_type="val",
        actor_id=None,
        org_id="test-org",
        agent_max_level=PermissionLevel.EXECUTE,
    )
    decision = engine.evaluate(
        action="transfer_funds",
        resource_type="financial",
        required_level=PermissionLevel.HIGH_IMPACT,
        ctx=ctx,
    )
    assert decision.allowed is False
    assert decision.requires_approval is True
    assert "level_4_requires_founder_approval" in decision.reason


def test_permission_risk_class_escalation():
    engine = PermissionEngine()
    ctx = PermissionContext(
        actor_type="val",
        actor_id=None,
        org_id="test-org",
        agent_max_level=PermissionLevel.EXECUTE,
    )
    # Even if required_level is declared as 2, risk_class HIGH forces Level 4
    decision = engine.evaluate(
        action="high_risk_step",
        resource_type="tool",
        required_level=PermissionLevel.EXECUTE,
        risk_class=RiskClass.HIGH,
        ctx=ctx,
    )
    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.required_level == PermissionLevel.HIGH_IMPACT


def test_permission_allow_list_blocking():
    engine = PermissionEngine()
    ctx = PermissionContext(
        actor_type="agent",
        actor_id="agent-123",
        org_id="test-org",
        agent_max_level=PermissionLevel.EXECUTE,
        tool_allow_list=["echo", "calculator"],
    )
    # Echo allowed
    decision_echo = engine.check_tool("echo", 0, "low", ctx)
    assert decision_echo.allowed is True

    # web_fetch not in allow-list
    decision_fetch = engine.check_tool("web_fetch", 2, "medium", ctx)
    assert decision_fetch.allowed is False
    assert "tool_not_on_allow_list" in decision_fetch.reason


def test_permission_global_pause():
    engine = PermissionEngine()
    ctx = PermissionContext(
        actor_type="val",
        actor_id=None,
        org_id="test-org",
        agent_max_level=PermissionLevel.EXECUTE,
    )
    engine.pause()
    decision = engine.evaluate(
        action="write_file",
        resource_type="tool",
        required_level=PermissionLevel.EXECUTE,
        ctx=ctx,
    )
    assert decision.allowed is False
    assert "system_globally_paused" in decision.reason

    engine.resume()
    decision_after = engine.evaluate(
        action="write_file",
        resource_type="tool",
        required_level=PermissionLevel.EXECUTE,
        ctx=ctx,
    )
    assert decision_after.allowed is True


def test_permission_emergency_lock():
    engine = PermissionEngine()
    ctx = PermissionContext(
        actor_type="val",
        actor_id=None,
        org_id="test-org",
        agent_max_level=PermissionLevel.EXECUTE,
    )
    engine.trigger_emergency()
    decision = engine.evaluate(
        action="any_action",
        resource_type="tool",
        required_level=PermissionLevel.OBSERVE,
        ctx=ctx,
    )
    assert decision.allowed is False
    assert "system_emergency_active" in decision.reason

    # Resume cannot override emergency
    engine.resume()
    assert engine.emergency is True

    # Only clear_emergency restores
    engine.clear_emergency()
    assert engine.emergency is False
