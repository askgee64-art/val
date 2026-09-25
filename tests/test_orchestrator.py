"""Tests for Autonomy Orchestrator & Audit Immutability — Document 07 & 21."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from val.audit.logger import get_audit_logger
from val.core.orchestrator import get_orchestrator
from val.db.models import Approval, AuditLog, Task
from val.models.enums import ApprovalStatus, TaskStatus


@pytest.mark.asyncio
async def test_orchestrator_autonomous_loop(test_session: AsyncSession):
    orchestrator = get_orchestrator()
    org_id = "00000000-0000-4000-8000-000000000010"
    user_id = "00000000-0000-4000-8000-000000000001"

    # Objective requiring diagnostics and safe execution
    task, plan = await orchestrator.submit_objective(
        test_session,
        objective="Inspect hardware diagnostic specs and record system status",
        user_id=user_id,
        org_id=org_id,
        auto_execute=True,
    )

    assert task.status == TaskStatus.SUCCEEDED
    assert len(plan.steps) >= 1
    assert task.completed_at is not None

    # Check that audit entries were recorded
    audit_q = select(AuditLog).where(AuditLog.org_id == org_id)
    logs = (await test_session.execute(audit_q)).scalars().all()
    actions = [l.action for l in logs]
    assert "objective.received" in actions
    assert "plan.created" in actions
    assert "task.completed" in actions


@pytest.mark.asyncio
async def test_orchestrator_level_4_approval_gate(test_session: AsyncSession):
    orchestrator = get_orchestrator()
    org_id = "00000000-0000-4000-8000-000000000010"
    user_id = "00000000-0000-4000-8000-000000000001"

    # Objective containing high-impact production / deployment keywords
    task, plan = await orchestrator.submit_objective(
        test_session,
        objective="Deploy high impact code update to production servers",
        user_id=user_id,
        org_id=org_id,
        auto_execute=True,
    )

    # Task must pause at Level 4 approval gate!
    assert task.status == TaskStatus.WAITING_APPROVAL
    assert task.requires_approval is True
    assert task.approval_id is not None

    # Check approval record
    approval = await test_session.get(Approval, task.approval_id)
    assert approval is not None
    assert approval.status == ApprovalStatus.PENDING
    assert approval.risk_level == 4

    # Founder decides: approve
    resumed_task = await orchestrator.decide_approval(
        test_session,
        approval_id=approval.approval_id,
        user_id=user_id,
        org_id=org_id,
        decision="approved",
        reason="Founder manually authorized deployment simulation",
    )

    assert resumed_task.status == TaskStatus.SUCCEEDED
    assert approval.status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_audit_log_immutability(test_session: AsyncSession):
    audit = get_audit_logger()
    org_id = "00000000-0000-4000-8000-000000000010"

    entry = await audit.log(
        test_session,
        org_id=org_id,
        actor_type="test",
        action="test.immutable_action",
    )
    await test_session.commit()

    # Attempting to update audit log entry must raise RuntimeError
    saved_log_id = str(entry.log_id)
    entry.action = "tampered_action"
    with pytest.raises(RuntimeError, match="audit_logs is immutable"):
        await test_session.commit()

    await test_session.rollback()

    # Attempting to delete must raise RuntimeError
    entry_to_del = await test_session.get(AuditLog, saved_log_id)
    assert entry_to_del is not None
    await test_session.delete(entry_to_del)
    with pytest.raises(RuntimeError, match="audit_logs is immutable"):
        await test_session.commit()
