"""Built-in safe tools for VAL MVP — Document 12 & Document 30.

All tools adhere to:
  - Input/output schemas
  - Risk classification (low / medium / high)
  - Required permission levels (L0-L4)
  - Strict timeouts
  - File safety guard enforcement outside LLM
"""

from __future__ import annotations

import ast
import asyncio
import math
import operator as op
import os
import platform
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from val.config import get_settings
from val.models.enums import PermissionLevel, RiskClass
from val.security.file_safety import get_file_safety_guard
from val.tools.base import BaseTool, ToolMeta, ToolResult


class EchoTool(BaseTool):
    meta = ToolMeta(
        name="echo",
        description="Echoes back the provided message. Useful for testing and heartbeat.",
        risk_class=RiskClass.LOW,
        required_permission_level=PermissionLevel.OBSERVE,
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema={"type": "object", "properties": {"echo": {"type": "string"}}},
        timeout_seconds=5,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        msg = params.get("message", "")
        return ToolResult(success=True, output={"echo": msg})


class DateTimeTool(BaseTool):
    meta = ToolMeta(
        name="datetime_now",
        description="Returns the current UTC and system timestamp in ISO format.",
        risk_class=RiskClass.LOW,
        required_permission_level=PermissionLevel.OBSERVE,
        input_schema={"type": "object", "properties": {}},
        output_schema={
            "type": "object",
            "properties": {
                "utc_iso": {"type": "string"},
                "unix_timestamp": {"type": "number"},
            },
        },
        timeout_seconds=2,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        now = datetime.now(timezone.utc)
        return ToolResult(
            success=True,
            output={
                "utc_iso": now.isoformat(),
                "unix_timestamp": now.timestamp(),
            },
        )


class SystemInfoTool(BaseTool):
    """Hardware diagnostic probe (Document 08/09/PRD Section 8).

    Classifies system compute, RAM, storage, OS, and local runtime status.
    """

    meta = ToolMeta(
        name="system_info",
        description="Gathers system diagnostics: CPU, RAM, storage, OS, and local model runtime availability.",
        risk_class=RiskClass.LOW,
        required_permission_level=PermissionLevel.OBSERVE,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
        timeout_seconds=10,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        t0 = time.perf_counter()
        # Storage
        settings = get_settings()
        disk = shutil.disk_usage(str(settings.project_root))

        # Check for local LLM runtimes
        ollama_ok = False
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                res = await client.get("http://127.0.0.1:11434/api/tags")
                ollama_ok = res.status_code == 200
        except Exception:
            ollama_ok = False

        # Memory info via /proc/meminfo or fallback
        total_ram_mb = 0
        free_ram_mb = 0
        if os.path.exists("/proc/meminfo"):
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            total_ram_mb = int(line.split()[1]) // 1024
                        elif line.startswith("MemAvailable:"):
                            free_ram_mb = int(line.split()[1]) // 1024
            except Exception:
                pass

        # CPU count
        cpu_count = os.cpu_count() or 1

        info = {
            "os": platform.platform(),
            "python_version": sys.version.split()[0],
            "cpu_cores": cpu_count,
            "ram_total_mb": total_ram_mb,
            "ram_available_mb": free_ram_mb,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "local_runtimes": {
                "ollama_available": ollama_ok,
                "local_fallback_active": settings.allow_local_fallback,
            },
            "classification": {
                "hardware_tier": "desktop_linux" if total_ram_mb >= 8192 else "lightweight",
                "local_quantized_capable": total_ram_mb >= 8192,
                "recommended_mode": "hybrid",
            },
        }
        return ToolResult(
            success=True,
            output=info,
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class SafeCalculatorTool(BaseTool):
    """AST-based safe math evaluator — no arbitrary eval()."""

    meta = ToolMeta(
        name="calculator",
        description="Performs safe mathematical calculations: +, -, *, /, %, **, sqrt, abs, round, sin, cos.",
        risk_class=RiskClass.LOW,
        required_permission_level=PermissionLevel.EXECUTE,
        input_schema={
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
        output_schema={"type": "object", "properties": {"result": {"type": "number"}}},
        timeout_seconds=2,
    )

    _OPS = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv,
        ast.Mod: op.mod,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.UAdd: op.pos,
    }

    _FUNCS = {
        "sqrt": math.sqrt,
        "abs": abs,
        "round": round,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "exp": math.exp,
        "ceil": math.ceil,
        "floor": math.floor,
        "pi": math.pi,
        "e": math.e,
    }

    def _eval(self, node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return self._eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"unsupported constant: {node.value}")
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            fn = self._OPS.get(type(node.op))
            if fn is None:
                raise ValueError(f"unsupported binary op: {type(node.op)}")
            return float(fn(left, right))
        if isinstance(node, ast.UnaryOp):
            operand = self._eval(node.operand)
            fn = self._OPS.get(type(node.op))
            if fn is None:
                raise ValueError(f"unsupported unary op: {type(node.op)}")
            return float(fn(operand))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("only simple function calls supported")
            func_name = node.func.id
            fn = self._FUNCS.get(func_name)
            if fn is None or not callable(fn):
                raise ValueError(f"unsupported function: {func_name}")
            args = [self._eval(arg) for arg in node.args]
            return float(fn(*args))
        if isinstance(node, ast.Name):
            val = self._FUNCS.get(node.id)
            if isinstance(val, (int, float)):
                return float(val)
            raise ValueError(f"unrecognized identifier: {node.id}")
        raise ValueError(f"unsupported expression node: {type(node).__name__}")

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        raw_expr = str(params.get("expression", "")).strip()
        if not raw_expr:
            return ToolResult(success=False, error="empty expression")

        # Clean and normalize mathematical operators (e.g., unicode ×, ^, x between numbers)
        expr = raw_expr.replace("×", "*").replace("X", "*")
        expr = re.sub(r"(\d+)\s*[xX]\s*(\d+)", r"\1 * \2", expr)
        expr = expr.replace("^", "**")
        expr = re.sub(r"[?!=]+$", "", expr).strip()

        try:
            tree = ast.parse(expr, mode="eval")
            res = self._eval(tree)
            # Format integer nicely if whole number
            if isinstance(res, float) and res.is_integer():
                formatted_res = int(res)
            else:
                formatted_res = res
            return ToolResult(success=True, output={"expression": expr, "result": formatted_res})
        except Exception as exc:
            return ToolResult(success=False, error=f"calculation error: {exc}")


class FileReadTool(BaseTool):
    """File read tool guarded by FileSafetyGuard."""

    meta = ToolMeta(
        name="file_read",
        description="Reads contents of a file within the allowed workspace directory.",
        risk_class=RiskClass.LOW,
        required_permission_level=PermissionLevel.EXECUTE,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "base": {"type": "string", "enum": ["workspace", "sandbox"]},
                "max_bytes": {"type": "integer"},
            },
            "required": ["path"],
        },
        output_schema={"type": "object", "properties": {"content": {"type": "string"}}},
        timeout_seconds=5,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        guard = get_file_safety_guard()
        path = params.get("path", "")
        base = params.get("base", "workspace")
        max_bytes = params.get("max_bytes", 200_000)

        decision = guard.check("read", path, base=base)
        if not decision.allowed:
            return ToolResult(success=False, error=f"file_read_denied: {decision.reason}")

        target = Path(decision.resolved_path)  # type: ignore[arg-type]
        if not target.exists():
            return ToolResult(success=False, error=f"file_not_found: {path}")
        if target.is_dir():
            return ToolResult(success=False, error=f"path_is_directory: {path}")

        try:
            size = target.stat().st_size
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            return ToolResult(
                success=True,
                output={
                    "path": path,
                    "resolved_path": str(target),
                    "size_bytes": size,
                    "truncated": size > max_bytes,
                    "content": content,
                },
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"read_error: {exc}")


class FileWriteTool(BaseTool):
    """File write tool strictly enforcing Document 35 (File Safety)."""

    meta = ToolMeta(
        name="file_write",
        description="Writes content to a file in the workspace or sandbox. Protected paths are strictly refused.",
        risk_class=RiskClass.MEDIUM,
        required_permission_level=PermissionLevel.EXECUTE,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "base": {"type": "string", "enum": ["workspace", "sandbox"]},
                "overwrite": {"type": "boolean"},
            },
            "required": ["path", "content"],
        },
        output_schema={"type": "object", "properties": {"bytes_written": {"type": "integer"}}},
        timeout_seconds=10,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        guard = get_file_safety_guard()
        path = params.get("path", "")
        content = params.get("content", "")
        base = params.get("base", "workspace")
        overwrite = params.get("overwrite", True)

        decision = guard.check("write", path, base=base)
        if not decision.allowed:
            return ToolResult(
                success=False,
                error=f"file_write_denied: {decision.reason} (protected={decision.is_protected})",
            )

        target = Path(decision.resolved_path)  # type: ignore[arg-type]
        if target.exists() and not overwrite:
            return ToolResult(success=False, error="file_already_exists_and_overwrite_false")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output={
                    "path": path,
                    "resolved_path": str(target),
                    "bytes_written": len(content.encode("utf-8")),
                },
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"write_error: {exc}")


class FileListTool(BaseTool):
    """List directory contents within allowed workspace/sandbox."""

    meta = ToolMeta(
        name="file_list",
        description="Lists files in a workspace or sandbox directory.",
        risk_class=RiskClass.LOW,
        required_permission_level=PermissionLevel.EXECUTE,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "base": {"type": "string", "enum": ["workspace", "sandbox"]},
            },
        },
        output_schema={"type": "object", "properties": {"files": {"type": "array"}}},
        timeout_seconds=5,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        guard = get_file_safety_guard()
        path = params.get("path", ".")
        base = params.get("base", "workspace")

        decision = guard.check("list", path, base=base)
        if not decision.allowed:
            return ToolResult(success=False, error=f"file_list_denied: {decision.reason}")

        target = Path(decision.resolved_path)  # type: ignore[arg-type]
        if not target.exists():
            return ToolResult(success=False, error=f"directory_not_found: {path}")
        if not target.is_dir():
            return ToolResult(success=False, error=f"not_a_directory: {path}")

        try:
            entries = []
            for item in sorted(target.iterdir()):
                entries.append(
                    {
                        "name": item.name,
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else None,
                    }
                )
            return ToolResult(
                success=True,
                output={"path": path, "resolved_path": str(target), "entries": entries},
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"list_error: {exc}")


class WebFetchTool(BaseTool):
    """Safely fetch web text / JSON under timeout and size limits."""

    meta = ToolMeta(
        name="web_fetch",
        description="Fetches content from a URL via HTTP GET. Enforces timeout and max response size.",
        risk_class=RiskClass.MEDIUM,
        required_permission_level=PermissionLevel.EXECUTE,
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_bytes": {"type": "integer"},
            },
            "required": ["url"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "status_code": {"type": "integer"},
                "content": {"type": "string"},
            },
        },
        timeout_seconds=15,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params.get("url", "").strip()
        max_bytes = params.get("max_bytes", 150_000)

        if not (url.startswith("http://") or url.startswith("https://")):
            return ToolResult(success=False, error="invalid_url: must start with http:// or https://")

        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": "VAL-Autonomous-Core/0.1.0"},
            ) as client:
                res = await client.get(url)
                body = res.text[:max_bytes]
                return ToolResult(
                    success=res.status_code < 400,
                    output={
                        "url": str(res.url),
                        "status_code": res.status_code,
                        "content_type": res.headers.get("content-type", ""),
                        "content": body,
                        "truncated": len(res.text) > max_bytes,
                    },
                    error=None if res.status_code < 400 else f"HTTP_{res.status_code}",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"fetch_error: {exc}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )


class CodeSandboxTool(BaseTool):
    """Runs Python code inside a sandboxed subprocess with cwd in data/sandbox.

    Enforces timeout, max output bytes, and isolated environment.
    Document 10 & 35.
    """

    meta = ToolMeta(
        name="code_sandbox",
        description="Executes Python code in an isolated subprocess under strict timeout and sandbox directory limits.",
        risk_class=RiskClass.MEDIUM,
        required_permission_level=PermissionLevel.EXECUTE,
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "timeout_seconds": {"type": "integer"},
            },
            "required": ["code"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "exit_code": {"type": "integer"},
            },
        },
        timeout_seconds=15,
    )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        settings = get_settings()
        code = params.get("code", "")
        timeout = min(
            params.get("timeout_seconds", settings.code_sandbox_timeout_seconds),
            settings.code_sandbox_timeout_seconds,
        )

        sandbox_dir = Path(settings.sandbox_dir).resolve()
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Temporary runner file inside sandbox
        run_file = sandbox_dir / f"_run_{int(time.time() * 1000)}.py"
        try:
            run_file.write_text(code, encoding="utf-8")
        except Exception as exc:
            return ToolResult(success=False, error=f"sandbox_write_failed: {exc}")

        # Build clean environment with PYTHONPATH pointing only to standard library + sandbox
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": str(sandbox_dir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }

        t0 = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(run_file),
                cwd=str(sandbox_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=float(timeout)
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                return ToolResult(
                    success=False,
                    error=f"execution_timed_out_after_{timeout}s",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            max_out = settings.code_sandbox_max_output_bytes
            stdout = stdout_bytes.decode("utf-8", errors="replace")[:max_out]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:max_out]

            return ToolResult(
                success=proc.returncode == 0,
                output={
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": proc.returncode,
                },
                error=None if proc.returncode == 0 else f"exit_code_{proc.returncode}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        finally:
            if run_file.exists():
                try:
                    run_file.unlink()
                except Exception:
                    pass
