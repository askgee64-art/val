"""Tool base types — Document 12.

Every tool declares ID, description, schemas, risk class, required
permission level, timeouts, and logging requirements.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from val.models.enums import PermissionLevel, RiskClass


@dataclass
class ToolMeta:
    name: str
    description: str
    risk_class: RiskClass = RiskClass.LOW
    required_permission_level: PermissionLevel = PermissionLevel.EXECUTE
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30
    is_enabled: bool = True
    tags: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    meta: ToolMeta

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Run the tool. Permission checks happen BEFORE this is called."""

    def validate_input(self, params: dict[str, Any]) -> str | None:
        """Basic required-field validation against input_schema.properties."""
        schema = self.meta.input_schema or {}
        required = schema.get("required") or []
        props = schema.get("properties") or {}
        for key in required:
            if key not in params:
                return f"missing_required_field:{key}"
        for key, value in params.items():
            if key in props:
                expected = props[key].get("type")
                if expected and not _type_matches(value, expected):
                    return f"type_mismatch:{key}:expected_{expected}"
        return None


def _type_matches(value: Any, expected: str) -> bool:
    mapping = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    py = mapping.get(expected)
    if py is None:
        return True
    return isinstance(value, py)
