"""Tool Registry — Document 12 §3 & Master Spec §8.

Maintains registered tools, enforces permission check BEFORE execution,
and logs every invocation to the immutable audit log.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from val.audit.logger import get_audit_logger
from val.models.enums import PermissionLevel, RiskClass
from val.models.schemas import ToolInfo
from val.permissions.engine import PermissionContext, get_permission_engine
from val.tools.base import BaseTool, ToolResult
from val.tools.builtins import (
    CodeSandboxTool,
    DateTimeTool,
    EchoTool,
    FileListTool,
    FileReadTool,
    FileWriteTool,
    SafeCalculatorTool,
    SystemInfoTool,
    WebFetchTool,
)
from tools.git_tool import GitOpsTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(EchoTool())
        self.register(DateTimeTool())
        self.register(SystemInfoTool())
        self.register(SafeCalculatorTool())
        self.register(FileReadTool())
        self.register(FileWriteTool())
        self.register(FileListTool())
        self.register(WebFetchTool())
        self.register(CodeSandboxTool())
        self.register(GitOpsTool())

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.meta.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolInfo]:
        return [
            ToolInfo(
                name=t.meta.name,
                description=t.meta.description,
                risk_class=t.meta.risk_class,
                required_permission_level=t.meta.required_permission_level,
                is_enabled=t.meta.is_enabled,
                input_schema=t.meta.input_schema,
                output_schema=t.meta.output_schema,
            )
            for t in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        params: dict[str, Any],
        ctx: PermissionContext,
        session: AsyncSession | None = None,
    ) -> ToolResult:
        t0 = time.perf_counter()
        tool = self.get(name)
        audit = get_audit_logger()
        engine = get_permission_engine()

        if tool is None:
            err = f"tool_not_found:{name}"
            if session:
                await audit.log(
                    session,
                    org_id=ctx.org_id,
                    actor_type=ctx.actor_type,
                    actor_id=ctx.actor_id,
                    action=f"tool.failed.{name}",
                    resource_type="tool",
                    details={"error": err, "params": params},
                )
            return ToolResult(success=False, error=err)

        if not tool.meta.is_enabled:
            err = f"tool_disabled:{name}"
            return ToolResult(success=False, error=err)

        # 1. Permission check
        decision = engine.check_tool(
            tool_name=name,
            required_level=tool.meta.required_permission_level,
            risk_class=tool.meta.risk_class,
            ctx=ctx,
        )

        if not decision.allowed:
            err = f"permission_denied:{decision.reason}"
            if session:
                await audit.log(
                    session,
                    org_id=ctx.org_id,
                    actor_type=ctx.actor_type,
                    actor_id=ctx.actor_id,
                    action=f"tool.denied.{name}",
                    resource_type="tool",
                    details={
                        "reason": decision.reason,
                        "required_level": int(decision.required_level),
                        "actor_level": int(decision.actor_level),
                        "requires_approval": decision.requires_approval,
                    },
                )
            return ToolResult(
                success=False,
                error=err,
                metadata={
                    "permission_decision": decision.to_dict(),
                    "requires_approval": decision.requires_approval,
                },
            )

        # 2. Schema validation
        schema_err = tool.validate_input(params)
        if schema_err:
            return ToolResult(success=False, error=f"input_validation_failed:{schema_err}")

        # 3. Execution
        try:
            result = await tool.execute(params)
        except Exception as exc:
            result = ToolResult(
                success=False,
                error=f"unhandled_tool_exception:{exc}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        result.duration_ms = (time.perf_counter() - t0) * 1000

        # 4. Audit logging
        if session:
            # Mask potential sensitive large data in audit payload
            masked_params = {k: v for k, v in params.items() if k != "password"}
            await audit.log(
                session,
                org_id=ctx.org_id,
                actor_type=ctx.actor_type,
                actor_id=ctx.actor_id,
                action=f"tool.executed.{name}" if result.success else f"tool.failed.{name}",
                resource_type="tool",
                details={
                    "params": masked_params,
                    "success": result.success,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                },
            )

        return result


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
