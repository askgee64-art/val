"""VAL Planner — Document 07 §3 & Master Spec §3.

Decomposes natural language objectives into structured plans with explicit
steps, required tools, permission levels, risk classifications, and dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from val.core.model_router import get_model_router
from val.models.enums import PermissionLevel, RiskClass
from val.models.schemas import Plan, PlanStep
from val.tools.registry import get_tool_registry


PLANNER_SYSTEM_PROMPT = """You are the Senior Planning Core of VAL, the autonomous AI system.
Given a founder objective, your role is to decompose the goal into a safe, ordered, structured plan.

Available Tools:
{tools_doc}

Safety Rules:
1. Every step must specify:
   - "step_id": integer starting from 1
   - "title": short action title
   - "description": clear explanation
   - "tool_name": name of registered tool, or null if purely cognitive
   - "tool_input": dictionary matching the tool's input schema
   - "required_permission_level": 0 (Observe), 1 (Recommend), 2 (Execute), 3 (Delegate), 4 (High Impact)
   - "risk_class": "low", "medium", or "high"
   - "depends_on": list of step_ids that must complete first
   - "success_criteria": condition for considering step complete
2. HIGH-IMPACT actions (financial transactions, production deployment, deletion of protected files, modifying security policies) MUST have required_permission_level = 4 and risk_class = "high".
3. File operations MUST NOT target protected system directories (/backend/val, /data/audit, .git, etc.).
4. Return ONLY valid JSON matching this schema:
{{
  "summary": "Overall execution strategy summary",
  "steps": [ ... ],
  "risk_flags": [ ... ],
  "requires_approval": boolean
}}
"""


class Planner:
    def __init__(self) -> None:
        self._router = get_model_router()
        self._registry = get_tool_registry()

    def _build_tools_documentation(self) -> str:
        lines = []
        for t in self._registry.list_tools():
            lines.append(
                f"- Tool '{t.name}': {t.description}\n"
                f"  Risk: {t.risk_class}, Required Level: {int(t.required_permission_level)}\n"
                f"  Input Schema: {json.dumps(t.input_schema)}"
            )
        return "\n".join(lines)

    async def create_plan(
        self,
        objective: str,
        *,
        context: dict[str, Any] | None = None,
        working_memory: list[dict[str, Any]] | None = None,
    ) -> Plan:
        tools_doc = self._build_tools_documentation()
        system_content = PLANNER_SYSTEM_PROMPT.format(tools_doc=tools_doc)

        user_content = f"Objective:\n{objective}\n"
        if context:
            user_content += f"\nContext:\n{json.dumps(context, indent=2)}\n"
        if working_memory:
            user_content += f"\nActive Working Memory:\n{json.dumps(working_memory, indent=2)}\n"
        user_content += "\nProduce the structured JSON plan."

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        resp = await self._router.complete(
            messages,
            temperature=0.1,
            max_tokens=3000,
            response_format_json=True,
        )

        try:
            # Extract JSON substring if needed
            content = resp.content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join(
                    [l for l in lines if not l.startswith("```")]
                ).strip()
            data = json.loads(content)
        except Exception:
            # Fall back to local plan dictionary
            data = self._router._generate_plan_dict(objective)

        steps: list[PlanStep] = []
        for raw_s in data.get("steps", []):
            req_lvl = int(raw_s.get("required_permission_level", 2))
            risk_cls = raw_s.get("risk_class", "low")
            steps.append(
                PlanStep(
                    step_id=int(raw_s.get("step_id", len(steps) + 1)),
                    title=str(raw_s.get("title", f"Step {len(steps) + 1}")),
                    description=str(raw_s.get("description", "")),
                    tool_name=raw_s.get("tool_name"),
                    tool_input=raw_s.get("tool_input"),
                    required_permission_level=PermissionLevel(req_lvl),
                    risk_class=RiskClass(risk_cls),
                    depends_on=list(raw_s.get("depends_on", [])),
                    success_criteria=raw_s.get("success_criteria"),
                    status="pending",
                )
            )

        has_l4 = any(s.required_permission_level >= PermissionLevel.HIGH_IMPACT for s in steps)
        risk_flags = list(data.get("risk_flags", []))
        if has_l4 and "level_4_founder_approval_required" not in risk_flags:
            risk_flags.append("level_4_founder_approval_required")

        plan = Plan(
            plan_id=str(uuid4()),
            objective=objective,
            summary=str(data.get("summary", f"Plan for: {objective}")),
            steps=steps,
            risk_flags=risk_flags,
            requires_approval=has_l4 or bool(data.get("requires_approval", False)),
            estimated_tool_calls=len([s for s in steps if s.tool_name]),
            model_used=resp.model,
            created_at=datetime.now(timezone.utc),
        )
        return plan


_planner: Planner | None = None


def get_planner() -> Planner:
    global _planner
    if _planner is None:
        _planner = Planner()
    return _planner
