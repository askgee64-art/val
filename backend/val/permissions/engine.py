"""Permission Engine — Document 09.

Enforcement occurs HERE, not in the LLM.
Fail-closed: if evaluation cannot complete, the action is DENIED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from val.config import get_settings
from val.models.enums import PermissionLevel, RiskClass


@dataclass
class PermissionContext:
    """Who is requesting what."""

    actor_type: str  # user | val | agent | system
    actor_id: str | None
    org_id: str
    agent_max_level: int = PermissionLevel.EXECUTE
    tool_allow_list: list[str] | None = None
    is_founder: bool = False


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str
    required_level: PermissionLevel
    actor_level: PermissionLevel
    requires_approval: bool = False
    policy_matched: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "required_level": int(self.required_level),
            "actor_level": int(self.actor_level),
            "requires_approval": self.requires_approval,
            "policy_matched": self.policy_matched,
            "details": self.details,
        }


# Default risk → minimum permission level
RISK_TO_LEVEL: dict[RiskClass, PermissionLevel] = {
    RiskClass.LOW: PermissionLevel.EXECUTE,
    RiskClass.MEDIUM: PermissionLevel.EXECUTE,
    RiskClass.HIGH: PermissionLevel.HIGH_IMPACT,
}


class PermissionEngine:
    """Policy decision point for every tool and high-impact action.

    Rules (MVP):
    1. Global pause / emergency → deny all mutating actions
    2. Tool must be enabled and on actor allow-list (if list set)
    3. Required permission level must be ≤ actor max level for autonomous exec
    4. Level 4 (HIGH_IMPACT) always requires founder approval
    5. Level 3 (DELEGATE) denied in MVP (no multi-agent yet) unless founder override
    6. File safety is enforced separately in the file tool; this engine still
       checks the declared permission level of the file tool action
    7. Fail closed on any internal error
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._global_paused = False
        self._emergency = False
        self._disabled_tools: set[str] = set()

    # --- Emergency / control plane -----------------------------------------

    @property
    def global_paused(self) -> bool:
        return self._global_paused or self._settings.global_paused

    @property
    def emergency(self) -> bool:
        return self._emergency

    def pause(self) -> None:
        self._global_paused = True

    def resume(self) -> None:
        if not self._emergency:
            self._global_paused = False

    def trigger_emergency(self) -> None:
        self._emergency = True
        self._global_paused = True

    def clear_emergency(self) -> None:
        """Founder-only recovery path."""
        self._emergency = False
        self._global_paused = False

    def disable_tool(self, tool_name: str) -> None:
        self._disabled_tools.add(tool_name)

    def enable_tool(self, tool_name: str) -> None:
        self._disabled_tools.discard(tool_name)

    # --- Core evaluation ---------------------------------------------------

    def evaluate(
        self,
        *,
        action: str,
        resource_type: str,
        required_level: PermissionLevel | int,
        ctx: PermissionContext,
        tool_name: str | None = None,
        risk_class: RiskClass | str = RiskClass.LOW,
        extra: dict[str, Any] | None = None,
    ) -> PermissionDecision:
        try:
            return self._evaluate_inner(
                action=action,
                resource_type=resource_type,
                required_level=PermissionLevel(int(required_level)),
                ctx=ctx,
                tool_name=tool_name,
                risk_class=RiskClass(risk_class) if isinstance(risk_class, str) else risk_class,
                extra=extra or {},
            )
        except Exception as exc:  # fail closed
            return PermissionDecision(
                allowed=False,
                reason=f"permission_evaluation_error: {exc}",
                required_level=PermissionLevel.HIGH_IMPACT,
                actor_level=PermissionLevel(ctx.agent_max_level),
                requires_approval=False,
                details={"error": str(exc)},
            )

    def _evaluate_inner(
        self,
        *,
        action: str,
        resource_type: str,
        required_level: PermissionLevel,
        ctx: PermissionContext,
        tool_name: str | None,
        risk_class: RiskClass,
        extra: dict[str, Any],
    ) -> PermissionDecision:
        actor_level = PermissionLevel(ctx.agent_max_level)

        # Founder acting as user gets full authority for control plane,
        # but still goes through approval recording for L4 tool actions.
        if ctx.is_founder and resource_type == "control":
            return PermissionDecision(
                allowed=True,
                reason="founder_control_plane",
                required_level=required_level,
                actor_level=PermissionLevel.HIGH_IMPACT,
                policy_matched="founder_override",
            )

        # Emergency: only founder control actions allowed
        if self._emergency:
            return PermissionDecision(
                allowed=False,
                reason="system_emergency_active",
                required_level=required_level,
                actor_level=actor_level,
                details={"emergency": True},
            )

        # Global pause: block execute+ for non-observe
        if self.global_paused and required_level >= PermissionLevel.EXECUTE:
            return PermissionDecision(
                allowed=False,
                reason="system_globally_paused",
                required_level=required_level,
                actor_level=actor_level,
            )

        # Tool disabled by control plane
        if tool_name and tool_name in self._disabled_tools:
            return PermissionDecision(
                allowed=False,
                reason=f"tool_disabled:{tool_name}",
                required_level=required_level,
                actor_level=actor_level,
            )

        # Allow-list check
        if tool_name and ctx.tool_allow_list is not None:
            if tool_name not in ctx.tool_allow_list:
                return PermissionDecision(
                    allowed=False,
                    reason=f"tool_not_on_allow_list:{tool_name}",
                    required_level=required_level,
                    actor_level=actor_level,
                    details={"allow_list": ctx.tool_allow_list},
                )

        # Escalate by risk class
        min_for_risk = RISK_TO_LEVEL.get(risk_class, PermissionLevel.EXECUTE)
        effective_required = PermissionLevel(max(int(required_level), int(min_for_risk)))

        # Level 4 always needs approval
        if effective_required >= PermissionLevel.HIGH_IMPACT:
            return PermissionDecision(
                allowed=False,
                reason="level_4_requires_founder_approval",
                required_level=effective_required,
                actor_level=actor_level,
                requires_approval=True,
                policy_matched="l4_gate",
                details=extra,
            )

        # Level 3 (delegate) blocked in MVP for agents
        if effective_required >= PermissionLevel.DELEGATE and not ctx.is_founder:
            return PermissionDecision(
                allowed=False,
                reason="level_3_delegate_not_enabled_in_mvp",
                required_level=effective_required,
                actor_level=actor_level,
                requires_approval=True,
                policy_matched="mvp_no_delegate",
            )

        # Autonomous if actor level covers required
        if int(actor_level) >= int(effective_required):
            return PermissionDecision(
                allowed=True,
                reason="autonomous_within_level",
                required_level=effective_required,
                actor_level=actor_level,
                policy_matched="level_check",
            )

        # Actor lacks level → request approval
        return PermissionDecision(
            allowed=False,
            reason="insufficient_permission_level",
            required_level=effective_required,
            actor_level=actor_level,
            requires_approval=True,
            policy_matched="level_escalation",
            details={
                "needed": int(effective_required),
                "have": int(actor_level),
            },
        )

    def check_tool(
        self,
        tool_name: str,
        required_level: PermissionLevel | int,
        risk_class: RiskClass | str,
        ctx: PermissionContext,
        action: str = "execute",
    ) -> PermissionDecision:
        return self.evaluate(
            action=action,
            resource_type="tool",
            required_level=required_level,
            ctx=ctx,
            tool_name=tool_name,
            risk_class=risk_class,
        )


_engine: PermissionEngine | None = None


def get_permission_engine() -> PermissionEngine:
    global _engine
    if _engine is None:
        _engine = PermissionEngine()
    return _engine
