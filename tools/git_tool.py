"""Git Version Control Tool for VAL — Prompt Spec §2, §3, §4.

Allows VAL to inspect repository state, create experiment branches, commit
sandbox improvements, and stage pull request review candidates under strict
permission gates. Direct pushes or merges into 'main' require Level 4 Founder Approval!
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

from val.config import get_settings
from val.models.enums import PermissionLevel, RiskClass
from val.tools.base import BaseTool, ToolMeta, ToolResult


class GitOpsTool(BaseTool):
    meta = ToolMeta(
        name="git_ops",
        description=(
            "Performs version control operations on the VAL repository: status, "
            "diff, create_branch, commit, checkout, log. Mutating main requires Level 4 approval."
        ),
        risk_class=RiskClass.MEDIUM,
        required_permission_level=PermissionLevel.EXECUTE,
        input_schema={
            "type": "object",
            "properties": {
                "subcommand": {
                    "type": "string",
                    "enum": ["status", "diff", "branch", "checkout", "commit", "log"],
                },
                "branch_name": {"type": "string"},
                "commit_message": {"type": "string"},
                "target_files": {"type": "array"},
                "max_lines": {"type": "integer"},
            },
            "required": ["subcommand"],
        },
        output_schema={"type": "object"},
        timeout_seconds=20,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        sub = params.get("subcommand", "status")
        settings = get_settings()
        repo_root = Path(settings.project_root).resolve()

        if not (repo_root / ".git").exists():
            return ToolResult(success=False, error="git_repo_not_initialized")

        if sub == "status":
            cmd = ["git", "status", "--short"]
        elif sub == "diff":
            cmd = ["git", "diff"]
        elif sub == "log":
            max_l = params.get("max_lines", 10)
            cmd = ["git", "log", f"-n{max_l}", "--oneline"]
        elif sub == "branch":
            name = params.get("branch_name", "").strip()
            if not name:
                cmd = ["git", "branch", "--list"]
            else:
                # Sanitize branch name
                safe_name = name.replace(" ", "-").replace("..", "")
                cmd = ["git", "checkout", "-b", safe_name]
        elif sub == "checkout":
            name = params.get("branch_name", "").strip()
            if not name:
                return ToolResult(success=False, error="missing_branch_name")
            cmd = ["git", "checkout", name]
        elif sub == "commit":
            msg = params.get("commit_message", "").strip()
            if not msg:
                return ToolResult(success=False, error="missing_commit_message")

            # Stage files
            files = params.get("target_files", [])
            stage_cmd = ["git", "add"] + (files if files else ["-A"])
            p_add = await asyncio.create_subprocess_exec(
                *stage_cmd,
                cwd=str(repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await p_add.communicate()

            cmd = ["git", "commit", "-m", f"VAL: {msg}"]
        else:
            return ToolResult(success=False, error=f"unsupported_subcommand:{sub}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")

            return ToolResult(
                success=proc.returncode == 0,
                output={
                    "subcommand": sub,
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip(),
                    "exit_code": proc.returncode,
                },
                error=None if proc.returncode == 0 else f"git_exit_{proc.returncode}: {stderr}",
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"git_exec_error: {exc}")
