"""File Safety Architecture — Document 35.

Enforcement is OUTSIDE the model. Protected paths cannot be written,
deleted, moved, or permission-changed regardless of what the LLM requests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from val.config import get_settings


Operation = Literal[
    "list", "stat", "read", "write", "create", "delete", "move", "chmod"
]


@dataclass
class FileSafetyDecision:
    allowed: bool
    reason: str
    resolved_path: str | None = None
    is_protected: bool = False
    operation: str = ""


class FileSafetyGuard:
    """Path-canonicalizing allow/deny gate for all file tools."""

    MUTATING = frozenset({"write", "create", "delete", "move", "chmod"})

    def __init__(self) -> None:
        self._settings = get_settings()
        self._workspace = Path(self._settings.workspace_dir).resolve()
        self._sandbox = Path(self._settings.sandbox_dir).resolve()
        self._project_root = Path(self._settings.project_root).resolve()
        self._protected: list[Path] = [
            Path(p).resolve() for p in self._settings.protected_dirs
        ]
        # Always protect audit, security, permissions, and the DB file
        extras = [
            Path(self._settings.audit_dir),
            self._project_root / "backend" / "val",
            self._project_root / "data" / "val.db",
            self._project_root / ".env",
        ]
        for e in extras:
            rp = e.resolve()
            if rp not in self._protected:
                self._protected.append(rp)

        self._workspace.mkdir(parents=True, exist_ok=True)
        self._sandbox.mkdir(parents=True, exist_ok=True)

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def sandbox(self) -> Path:
        return self._sandbox

    def resolve(self, path: str, base: str = "workspace") -> Path:
        """Resolve user path under workspace or sandbox. Blocks escape."""
        root = self._sandbox if base == "sandbox" else self._workspace
        # Absolute paths are re-rooted under the base to prevent escape
        raw = Path(path)
        if raw.is_absolute():
            # Treat as relative to base by stripping anchor
            candidate = root / raw.name
        else:
            candidate = (root / raw).resolve()

        # Must stay inside root
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError(f"path_escape_blocked: {path}") from exc
        return candidate

    def is_protected(self, path: Path) -> bool:
        resolved = path.resolve()
        for prot in self._protected:
            try:
                if resolved == prot or resolved.is_relative_to(prot):
                    return True
            except (ValueError, OSError):
                # is_relative_to can fail on some edge cases
                prot_str = str(prot)
                res_str = str(resolved)
                if res_str == prot_str or res_str.startswith(prot_str + os.sep):
                    return True
        return False

    def check(
        self,
        operation: Operation,
        path: str,
        *,
        base: str = "workspace",
        dest_path: str | None = None,
    ) -> FileSafetyDecision:
        raw = Path(path)
        # If absolute path was supplied, check directly against protected list first
        if raw.is_absolute() and self.is_protected(raw):
            return FileSafetyDecision(
                allowed=False,
                reason="protected_path_mutation_denied",
                resolved_path=str(raw),
                is_protected=True,
                operation=operation,
            )

        try:
            resolved = self.resolve(path, base=base)
        except PermissionError as exc:
            return FileSafetyDecision(
                allowed=False,
                reason=str(exc),
                operation=operation,
            )

        protected = self.is_protected(resolved)

        if operation in ("list", "stat", "read"):
            return FileSafetyDecision(
                allowed=True,
                reason="read_allowed",
                resolved_path=str(resolved),
                is_protected=protected,
                operation=operation,
            )
            # Read ops allowed on workspace; protected still readable if inside
            # an allowed base (workspace reads of protected host paths won't
            # resolve here because resolve() re-roots under workspace).
            return FileSafetyDecision(
                allowed=True,
                reason="read_allowed",
                resolved_path=str(resolved),
                is_protected=protected,
                operation=operation,
            )

        if operation in self.MUTATING:
            if protected:
                return FileSafetyDecision(
                    allowed=False,
                    reason="protected_path_mutation_denied",
                    resolved_path=str(resolved),
                    is_protected=True,
                    operation=operation,
                )

            # Ensure still inside workspace/sandbox
            root = self._sandbox if base == "sandbox" else self._workspace
            try:
                resolved.relative_to(root)
            except ValueError:
                return FileSafetyDecision(
                    allowed=False,
                    reason="outside_allowed_root",
                    resolved_path=str(resolved),
                    operation=operation,
                )

            if operation == "move" and dest_path:
                dest_decision = self.check("write", dest_path, base=base)
                if not dest_decision.allowed:
                    return FileSafetyDecision(
                        allowed=False,
                        reason=f"move_dest_denied:{dest_decision.reason}",
                        resolved_path=str(resolved),
                        operation=operation,
                    )

            if operation == "chmod":
                return FileSafetyDecision(
                    allowed=False,
                    reason="chmod_denied_by_policy",
                    resolved_path=str(resolved),
                    operation=operation,
                )

            return FileSafetyDecision(
                allowed=True,
                reason="mutation_allowed_unprotected",
                resolved_path=str(resolved),
                is_protected=False,
                operation=operation,
            )

        return FileSafetyDecision(
            allowed=False,
            reason=f"unknown_operation:{operation}",
            operation=operation,
        )


_guard: FileSafetyGuard | None = None


def get_file_safety_guard() -> FileSafetyGuard:
    global _guard
    if _guard is None:
        _guard = FileSafetyGuard()
    return _guard
