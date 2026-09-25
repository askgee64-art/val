"""Autonomy Orchestrator — Document 07 §3 & Master Spec §3.

Implements the continuous Autonomy Operating Loop:
  Observe → Plan → Permission Check → Execute Tools → Verify → Store Memory → Audit → Report.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from val.audit.logger import get_audit_logger
from val.config import get_settings
from val.core.planner import get_planner
from val.db.models import Approval, Event, Task, utcnow
from val.memory.service import get_memory_service
from val.models.enums import (
    ActorType,
    ApprovalStatus,
    EventType,
    MemoryScope,
    PermissionLevel,
    RiskClass,
    TaskStatus,
)
from val.models.schemas import Plan, PlanStep
from val.permissions.engine import PermissionContext, get_permission_engine
from val.tools.registry import get_tool_registry


class Orchestrator:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._planner = get_planner()
        self._registry = get_tool_registry()
        self._perm_engine = get_permission_engine()
        self._audit = get_audit_logger()
        self._memory = get_memory_service()

    async def submit_objective(
        self,
        session: AsyncSession,
        *,
        objective: str,
        user_id: str,
        org_id: str,
        context: dict[str, Any] | None = None,
        auto_execute: bool = True,
    ) -> tuple[Task, Plan]:
        """Entry point for natural-language founder objectives."""
        # 1. Create task record
        task = Task(
            task_id=str(uuid4()),
            org_id=org_id,
            title=f"Objective: {objective[:100]}",
            description=objective,
            status=TaskStatus.PLANNING,
            priority=0,
            input={"objective": objective, "context": context or {}},
            created_at=utcnow(),
        )
        session.add(task)
        await session.flush()

        # 2. Audit log intake
        await self._audit.log(
            session,
            org_id=org_id,
            actor_type=ActorType.USER,
            actor_id=user_id,
            action=EventType.OBJECTIVE_RECEIVED,
            resource_type="task",
            resource_id=task.task_id,
            details={"objective": objective},
        )

        # 3. Pull working memory context
        working_ctx = await self._memory.get_working_context(session, org_id)

        # 4. Plan
        plan = await self._planner.create_plan(
            objective,
            context=context,
            working_memory=working_ctx,
        )

        task.plan = plan.model_dump(mode="json")
        task.status = TaskStatus.RUNNING
        task.started_at = utcnow()
        await session.flush()

        # Audit plan created
        await self._audit.log(
            session,
            org_id=org_id,
            actor_type=ActorType.VAL,
            action=EventType.PLAN_CREATED,
            resource_type="task",
            resource_id=task.task_id,
            details={
                "steps_count": len(plan.steps),
                "risk_flags": plan.risk_flags,
                "requires_approval": plan.requires_approval,
            },
        )

        # 5. Execute if requested
        if auto_execute:
            await self._run_plan_loop(session, task=task, plan=plan, user_id=user_id)

        await session.commit()
        return task, plan

    async def _run_plan_loop(
        self,
        session: AsyncSession,
        *,
        task: Task,
        plan: Plan,
        user_id: str,
    ) -> None:
        """Execute plan steps sequentially respecting permissions and approval gates."""
        ctx = PermissionContext(
            actor_type=ActorType.VAL,
            actor_id=None,
            org_id=task.org_id,
            agent_max_level=PermissionLevel.EXECUTE,
            is_founder=False,
        )

        results_accum: dict[int, Any] = {}

        for step in plan.steps:
            if step.status in ("succeeded", "skipped"):
                continue

            # Check dependencies
            if step.depends_on:
                missing_deps = [
                    d for d in step.depends_on if d not in results_accum
                ]
                if missing_deps:
                    step.status = "failed"
                    step.error = f"unmet_dependencies:{missing_deps}"
                    task.status = TaskStatus.FAILED
                    task.error = {"failed_step": step.step_id, "error": step.error}
                    task.completed_at = utcnow()
                    task.plan = plan.model_dump(mode="json")
                    return

            # Check permission: effective level is the highest of step requirement and tool baseline
            if step.tool_name:
                tool = self._registry.get(step.tool_name)
                tool_lvl = int(tool.meta.required_permission_level) if tool else 0
                step_lvl = int(step.required_permission_level)
                req_level = PermissionLevel(max(tool_lvl, step_lvl))

                # Escalate risk class if either step or tool is high/medium
                if (tool and tool.meta.risk_class == RiskClass.HIGH) or step.risk_class == RiskClass.HIGH:
                    risk_cls = RiskClass.HIGH
                elif (tool and tool.meta.risk_class == RiskClass.MEDIUM) or step.risk_class == RiskClass.MEDIUM:
                    risk_cls = RiskClass.MEDIUM
                else:
                    risk_cls = RiskClass.LOW
            else:
                req_level = step.required_permission_level
                risk_cls = step.risk_class

            perm_decision = self._perm_engine.evaluate(
                action="execute_step",
                resource_type="tool" if step.tool_name else "step",
                required_level=req_level,
                risk_class=risk_cls,
                ctx=ctx,
                tool_name=step.tool_name,
                extra={"step_id": step.step_id, "title": step.title},
            )

            # Level 4 or requires approval -> gate and pause
            if perm_decision.requires_approval or not perm_decision.allowed:
                approval = Approval(
                    approval_id=str(uuid4()),
                    org_id=task.org_id,
                    task_id=task.task_id,
                    requested_by=None,
                    action_type=f"execute_step:{step.tool_name or 'cognitive'}",
                    action_payload={
                        "step_id": step.step_id,
                        "title": step.title,
                        "tool_name": step.tool_name,
                        "tool_input": step.tool_input,
                        "required_level": int(req_level),
                        "reason": perm_decision.reason,
                    },
                    risk_level=int(req_level),
                    status=ApprovalStatus.PENDING,
                    created_at=utcnow(),
                )
                session.add(approval)
                await session.flush()

                task.status = TaskStatus.WAITING_APPROVAL
                task.requires_approval = True
                task.approval_id = approval.approval_id
                step.status = "waiting_approval"
                task.plan = plan.model_dump(mode="json")

                await self._audit.log(
                    session,
                    org_id=task.org_id,
                    actor_type=ActorType.VAL,
                    action=EventType.APPROVAL_REQUESTED,
                    resource_type="approval",
                    resource_id=approval.approval_id,
                    details={
                        "task_id": task.task_id,
                        "step_id": step.step_id,
                        "reason": perm_decision.reason,
                    },
                )
                return  # Paused awaiting founder decision

            # Allowed to execute tool
            if step.tool_name:
                step.status = "running"
                tool_input = step.tool_input or {}
                # Substitute outputs from prior steps if referenced
                tool_input = self._interpolate_deps(tool_input, results_accum)

                t_res = await self._registry.execute(
                    step.tool_name,
                    tool_input,
                    ctx=ctx,
                    session=session,
                )

                if t_res.success:
                    step.status = "succeeded"
                    step.result = t_res.output
                    results_accum[step.step_id] = t_res.output
                else:
                    step.status = "failed"
                    step.error = t_res.error
                    task.status = TaskStatus.FAILED
                    task.error = {
                        "failed_step": step.step_id,
                        "tool": step.tool_name,
                        "error": t_res.error,
                    }
                    task.completed_at = utcnow()
                    task.plan = plan.model_dump(mode="json")
                    return
            else:
                # Cognitive step
                step.status = "succeeded"
                step.result = {"status": "completed_by_reasoner"}
                results_accum[step.step_id] = step.result

        # All steps completed successfully
        task.status = TaskStatus.SUCCEEDED
        task.completed_at = utcnow()
        task.result = {
            "summary": "Plan executed successfully.",
            "step_results": results_accum,
            "steps_completed": len(plan.steps),
        }
        task.plan = plan.model_dump(mode="json")

        # 6. Store in working & long term memory
        await self._memory.store(
            session,
            org_id=task.org_id,
            scope_type=MemoryScope.WORKING,
            key=f"task:{task.task_id}:result",
            content={
                "task_id": task.task_id,
                "title": task.title,
                "summary": task.result["summary"],
                "completed_at": task.completed_at.isoformat(),
            },
            importance=0.6,
        )

        # 7. Audit task completed
        start_time = task.started_at or task.created_at
        if start_time and start_time.tzinfo is None and task.completed_at and task.completed_at.tzinfo:
            start_time = start_time.replace(tzinfo=timezone.utc)
        duration_s = (
            (task.completed_at - start_time).total_seconds()
            if start_time and task.completed_at
            else 0.0
        )
        await self._audit.log(
            session,
            org_id=task.org_id,
            actor_type=ActorType.VAL,
            action=EventType.TASK_COMPLETED,
            resource_type="task",
            resource_id=task.task_id,
            details={
                "steps_completed": len(plan.steps),
                "duration_s": duration_s,
            },
        )

    def _interpolate_deps(
        self, tool_input: dict[str, Any], results: dict[int, Any]
    ) -> dict[str, Any]:
        """Basic substitution if tool input references previous step output."""
        res_str = json.dumps(tool_input)
        for step_id, out in results.items():
            placeholder = f"$step_{step_id}"
            if placeholder in res_str:
                res_str = res_str.replace(placeholder, json.dumps(out))
        try:
            return json.loads(res_str)
        except Exception:
            return tool_input

    async def decide_approval(
        self,
        session: AsyncSession,
        *,
        approval_id: str,
        user_id: str,
        org_id: str,
        decision: str,  # approved | rejected
        reason: str | None = None,
    ) -> Task:
        """Founder makes decision on Level 4 pending approval."""
        approval = await session.get(Approval, approval_id)
        if approval is None:
            raise ValueError(f"Approval {approval_id} not found")

        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval already in state: {approval.status}")

        approval.status = (
            ApprovalStatus.APPROVED if decision == "approved" else ApprovalStatus.REJECTED
        )
        approval.decided_by = user_id
        approval.decided_at = utcnow()
        approval.decision_reason = reason

        await self._audit.log(
            session,
            org_id=org_id,
            actor_type=ActorType.USER,
            actor_id=user_id,
            action=EventType.APPROVAL_DECIDED,
            resource_type="approval",
            resource_id=approval_id,
            details={"decision": decision, "reason": reason, "task_id": approval.task_id},
        )

        task = await session.get(Task, approval.task_id)
        if task is None:
            raise ValueError("Task associated with approval not found")

        plan_data = task.plan or {}
        steps_raw = plan_data.get("steps", [])
        step_id = approval.action_payload.get("step_id")

        if decision == "rejected":
            task.status = TaskStatus.CANCELLED
            task.completed_at = utcnow()
            task.error = {"approval_rejected": True, "reason": reason}
            for s in steps_raw:
                if s.get("step_id") == step_id:
                    s["status"] = "rejected_by_founder"
            task.plan = plan_data
            await session.commit()
            return task

        # Approved: execute the step directly under founder-approved override
        task.status = TaskStatus.RUNNING
        for s in steps_raw:
            if s.get("step_id") == step_id:
                s["status"] = "running"
        await session.flush()

        # Reconstruct Plan and execute step
        tool_name = approval.action_payload.get("tool_name")
        tool_input = approval.action_payload.get("tool_input") or {}

        founder_ctx = PermissionContext(
            actor_type=ActorType.USER,
            actor_id=user_id,
            org_id=org_id,
            agent_max_level=PermissionLevel.HIGH_IMPACT,
            is_founder=True,
        )

        step_res: Any = None
        if tool_name:
            t_res = await self._registry.execute(
                tool_name, tool_input, ctx=founder_ctx, session=session
            )
            for s in steps_raw:
                if s.get("step_id") == step_id:
                    if t_res.success:
                        s["status"] = "succeeded"
                        s["result"] = t_res.output
                        step_res = t_res.output
                    else:
                        s["status"] = "failed"
                        s["error"] = t_res.error
                        task.status = TaskStatus.FAILED
                        task.error = {"step_id": step_id, "error": t_res.error}
                        task.completed_at = utcnow()
                        task.plan = plan_data
                        await session.commit()
                        return task

        # Continue remaining steps if any
        plan = Plan(**plan_data)
        # Mark current step succeeded in plan object
        for ps in plan.steps:
            if ps.step_id == step_id:
                ps.status = "succeeded"
                ps.result = step_res

        await self._run_plan_loop(session, task=task, plan=plan, user_id=user_id)
        await session.commit()
        return task


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
