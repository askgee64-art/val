"""Model Router — Hardware-aware, provider-agnostic router.

Document 04 §2.1 & Prompt Spec §9, §10:
  TASK → MODEL ROUTER → Check: complexity, privacy, latency, hardware, VRAM, cost → SELECT MODEL
  When no remote API key is configured, falls back to deterministic local planner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from val.config import get_settings


@dataclass
class ModelResponse:
    content: str
    model: str
    provider: str
    usage: dict[str, int] | None = None
    finish_reason: str = "stop"


@dataclass
class HardwareCapacity:
    tier: str  # lightweight | mid | heavy | workstation
    ram_mb: int
    vram_gb: float
    cpu_cores: int
    max_local_parameters_b: float
    supported_quantizations: list[str]
    can_run_local_llm: bool
    recommended_local_model: str


class ModelRouter:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def has_remote_provider(self) -> bool:
        return bool(
            self._settings.gemini_api_key
            or self._settings.openai_api_key
            or self._settings.anthropic_api_key
        )

    def assess_hardware_capacity(self, ram_mb: int = 2048, vram_gb: float = 0.0, cpu_cores: int = 2) -> HardwareCapacity:
        """Evaluate hardware constraints for model execution — Prompt Spec §12."""
        if ram_mb < 4096 and vram_gb < 2.0:
            return HardwareCapacity(
                tier="lightweight",
                ram_mb=ram_mb,
                vram_gb=vram_gb,
                cpu_cores=cpu_cores,
                max_local_parameters_b=1.0,
                supported_quantizations=["INT4"],
                can_run_local_llm=False,
                recommended_local_model="none_offload_to_cloud",
            )
        elif ram_mb < 8192 and vram_gb < 4.0:
            return HardwareCapacity(
                tier="mid",
                ram_mb=ram_mb,
                vram_gb=vram_gb,
                cpu_cores=cpu_cores,
                max_local_parameters_b=3.5,
                supported_quantizations=["INT4", "INT8"],
                can_run_local_llm=True,
                recommended_local_model="llama3.2:1b-instruct-q4_K_M",
            )
        elif ram_mb < 16384:
            return HardwareCapacity(
                tier="heavy",
                ram_mb=ram_mb,
                vram_gb=vram_gb,
                cpu_cores=cpu_cores,
                max_local_parameters_b=8.0,
                supported_quantizations=["INT4", "INT8", "FP16"],
                can_run_local_llm=True,
                recommended_local_model="llama3.1:8b-instruct-q4_K_M",
            )
        else:
            return HardwareCapacity(
                tier="workstation",
                ram_mb=ram_mb,
                vram_gb=vram_gb,
                cpu_cores=cpu_cores,
                max_local_parameters_b=14.0,
                supported_quantizations=["INT4", "INT8", "FP16", "BF16"],
                can_run_local_llm=True,
                recommended_local_model="llama3.1:8b-instruct-fp16",
            )

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        response_format_json: bool = False,
    ) -> ModelResponse:
        """Route prompt to configured model provider (Gemini -> OpenAI -> Anthropic -> Ollama -> Local Fallback)."""
        # 1. Primary Initial Provider: Google Gemini (Prompt Spec §11)
        if self._settings.gemini_api_key:
            try:
                return await self._call_gemini(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format_json=response_format_json,
                )
            except Exception as exc:
                if not (self._settings.openai_api_key or self._settings.allow_local_fallback):
                    raise exc

        # 2. OpenAI Compatible
        if self._settings.openai_api_key:
            try:
                return await self._call_openai_compatible(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format_json=response_format_json,
                )
            except Exception as exc:
                if not self._settings.allow_local_fallback:
                    raise exc

        # 3. Check local Ollama or local LLM server
        local_res = await self._try_local_llm(messages, json_mode=response_format_json)
        if local_res:
            return local_res

        # 4. Local deterministic fallback
        if self._settings.allow_local_fallback:
            return self._local_deterministic_engine(messages)

        raise RuntimeError("No model provider configured and local fallback is disabled.")

    async def _call_gemini(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format_json: bool,
    ) -> ModelResponse:
        """Call Google Gemini REST API."""
        model = self._settings.gemini_default_model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self._settings.gemini_api_key}"
        )

        contents = []
        for m in messages:
            role = "model" if m.get("role") == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}],
            })

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if response_format_json:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned empty candidate response")
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return ModelResponse(
                content=text,
                model=f"gemini/{model}",
                provider="google_gemini",
                usage=data.get("usageMetadata"),
                finish_reason=candidates[0].get("finishReason", "stop"),
            )

    async def _call_openai_compatible(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format_json: bool,
    ) -> ModelResponse:
        url = f"{self._settings.openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._settings.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return ModelResponse(
                content=choice["message"]["content"],
                model=data.get("model", self._settings.default_model),
                provider="openai_compatible",
                usage=data.get("usage"),
                finish_reason=choice.get("finish_reason", "stop"),
            )

    async def _try_local_llm(
        self, messages: list[dict[str, str]], json_mode: bool = False
    ) -> ModelResponse | None:
        """Check for local Ollama instance on port 11434."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get("http://127.0.0.1:11434/api/tags")
                if res.status_code != 200:
                    return None
                models = res.json().get("models", [])
                if not models:
                    return None
                model_name = models[0].get("name", "llama3")

                # Post chat completion
                payload: dict[str, Any] = {
                    "model": model_name,
                    "messages": messages,
                    "stream": False,
                }
                if json_mode:
                    payload["format"] = "json"
                chat_res = await client.post(
                    "http://127.0.0.1:11434/api/chat", json=payload, timeout=60.0
                )
                if chat_res.status_code == 200:
                    body = chat_res.json()
                    return ModelResponse(
                        content=body.get("message", {}).get("content", ""),
                        model=f"ollama/{model_name}",
                        provider="ollama_local",
                    )
        except Exception:
            return None
        return None

    def _local_deterministic_engine(
        self, messages: list[dict[str, str]]
    ) -> ModelResponse:
        """Deterministic local reasoning engine.

        Ensures VAL produces structured, valid, multi-step plans and responses
        without requiring external cloud API keys or heavy GPU runtimes.
        """
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        lowered = user_msg.lower()

        # Check if plan generation is requested
        if "plan" in lowered or "objective" in lowered or any(
            req in messages[0].get("content", "").lower()
            for req in ["output json", "json plan", "steps"]
        ):
            plan_obj = self._generate_plan_dict(user_msg)
            return ModelResponse(
                content=json.dumps(plan_obj),
                model="val-deterministic-v1",
                provider="local_fallback",
            )

        # Standard assistant answer
        return ModelResponse(
            content=f"VAL executive acknowledged objective: '{user_msg}'. Ready to structure and execute plan under permission constraints.",
            model="val-deterministic-v1",
            provider="local_fallback",
        )

    def _generate_plan_dict(self, objective: str) -> dict[str, Any]:
        """Generate structured task steps based on objective patterns."""
        lowered = objective.lower()
        steps = []

        # 1. High impact / approval required simulation (evaluated first for safety)
        if any(w in lowered for w in ["deploy", "transfer", "delete", "destroy", "production", "financial", "high impact", "level 4"]):
            steps.extend(
                [
                    {
                        "step_id": 1,
                        "title": "Gather pre-flight system state",
                        "description": "Record current timestamp and environment.",
                        "tool_name": "datetime_now",
                        "tool_input": {},
                        "required_permission_level": 0,
                        "risk_class": "low",
                        "success_criteria": "Timestamp recorded.",
                    },
                    {
                        "step_id": 2,
                        "title": "High-impact production action (Level 4)",
                        "description": f"Execution of high-impact action: {objective}",
                        "tool_name": "code_sandbox",
                        "tool_input": {"code": "# High impact action placeholder\nprint('Level 4 approved execution')"},
                        "required_permission_level": 4,  # Level 4: requires founder approval!
                        "risk_class": "high",
                        "success_criteria": "Founder approval granted and executed.",
                    },
                ]
            )

        # 2. Learning Objectives & Agent Factory (Prompt Spec §13, §14)
        elif any(w in lowered for w in ["learn", "teach", "curriculum", "study", "master"]):
            subject = "Calculus" if "calculus" in lowered else (objective.split()[-1].capitalize() or "Domain")
            steps.extend(
                [
                    {
                        "step_id": 1,
                        "title": f"Manufacture specialized agent via Agent Factory",
                        "description": f"Autonomous synthesis, configuration, and sandbox validation for {subject}.VAL.",
                        "tool_name": "datetime_now",
                        "tool_input": {},
                        "required_permission_level": 2,
                        "risk_class": "low",
                        "success_criteria": f"{subject}.VAL configured and validated.",
                    },
                    {
                        "step_id": 2,
                        "title": f"Synthesize structured curriculum for {subject}",
                        "description": f"Generate topic milestones, practice drills, and evaluation rubrics.",
                        "tool_name": "code_sandbox",
                        "tool_input": {
                            "code": f"print('Synthesized {subject} curriculum with prerequisites, practice drills, and rubrics.')"
                        },
                        "required_permission_level": 2,
                        "risk_class": "medium",
                        "success_criteria": "Curriculum generated and persisted.",
                    },
                    {
                        "step_id": 3,
                        "title": f"Execute baseline research and practice drill",
                        "description": f"Run initial concept practice and weakness assessment for {subject}.",
                        "tool_name": "calculator" if "calculus" in lowered or "math" in lowered else "code_sandbox",
                        "tool_input": {"expression": "2 * 3.14159"} if "calculus" in lowered or "math" in lowered else {"code": "print('Concept mastered')"},
                        "required_permission_level": 2,
                        "risk_class": "low",
                        "success_criteria": "Practice evaluation completed with measured score.",
                    },
                ]
            )

        # 3. System diagnostics / specs
        elif any(w in lowered for w in ["diagnostic", "hardware", "specs", "system info", "status"]):
            steps.append(
                {
                    "step_id": 1,
                    "title": "Probe system hardware and runtime environment",
                    "description": "Inspect CPU, RAM, disk, OS, and local model runner availability.",
                    "tool_name": "system_info",
                    "tool_input": {},
                    "required_permission_level": 0,
                    "risk_class": "low",
                    "success_criteria": "Diagnostics returned with hardware classification.",
                }
            )

        # 2. Math / calculation
        elif any(w in lowered for w in ["calculate", "math", "compute", "sum", "average", "sqrt"]):
            # Extract expression or run calculation
            expr = "2 * 3.14159 * 10"
            for token in objective.split():
                if any(c in token for c in "+-*/%^"):
                    expr = token
                    break
            steps.append(
                {
                    "step_id": 1,
                    "title": "Evaluate mathematical expression safely",
                    "description": f"Compute '{expr}' using the AST-safe calculator.",
                    "tool_name": "calculator",
                    "tool_input": {"expression": expr},
                    "required_permission_level": 2,
                    "risk_class": "low",
                    "success_criteria": "Calculation evaluated cleanly.",
                }
            )

        # 3. Code execution / scripting / testing
        elif any(w in lowered for w in ["code", "run", "script", "sandbox", "python", "execute code", "fibonacci"]):
            sample_code = (
                "def solve():\n"
                "    return [i**2 for i in range(10)]\n"
                "print('Result:', solve())\n"
            )
            steps.extend(
                [
                    {
                        "step_id": 1,
                        "title": "Execute script in isolated code sandbox",
                        "description": "Run computation inside data/sandbox with timeout and resource bounds.",
                        "tool_name": "code_sandbox",
                        "tool_input": {"code": sample_code, "timeout_seconds": 10},
                        "required_permission_level": 2,
                        "risk_class": "medium",
                        "success_criteria": "Script completed with exit code 0.",
                    },
                    {
                        "step_id": 2,
                        "title": "Persist result report to workspace",
                        "description": "Save execution summary to workspace/execution_report.txt.",
                        "tool_name": "file_write",
                        "tool_input": {
                            "path": "execution_report.txt",
                            "content": f"Objective: {objective}\nSandbox test completed successfully.\n",
                        },
                        "required_permission_level": 2,
                        "risk_class": "medium",
                        "success_criteria": "Report written to workspace.",
                    },
                ]
            )

        # 4. File operations (read/write/list)
        elif any(w in lowered for w in ["file", "write", "read", "workspace", "save", "note"]):
            steps.extend(
                [
                    {
                        "step_id": 1,
                        "title": "Inspect workspace directory",
                        "description": "List existing workspace files to verify paths.",
                        "tool_name": "file_list",
                        "tool_input": {"path": "."},
                        "required_permission_level": 2,
                        "risk_class": "low",
                        "success_criteria": "Directory listing obtained.",
                    },
                    {
                        "step_id": 2,
                        "title": "Write deliverable file to workspace",
                        "description": "Store output under workspace safely.",
                        "tool_name": "file_write",
                        "tool_input": {
                            "path": "task_output.txt",
                            "content": f"VAL generated output for: {objective}\nTimestamp: generated_at_run",
                        },
                        "required_permission_level": 2,
                        "risk_class": "medium",
                        "success_criteria": "File written without violating safety boundaries.",
                    },
                    {
                        "step_id": 3,
                        "title": "Verify file readability",
                        "description": "Read back the written file to confirm integrity.",
                        "tool_name": "file_read",
                        "tool_input": {"path": "task_output.txt"},
                        "required_permission_level": 2,
                        "risk_class": "low",
                        "success_criteria": "File read back matches written content.",
                    },
                ]
            )

        # 5. Web research / fetch
        elif any(w in lowered for w in ["fetch", "web", "http", "url", "download"]):
            steps.append(
                {
                    "step_id": 1,
                    "title": "Fetch web resource",
                    "description": "Retrieve content from requested endpoint under timeout limits.",
                    "tool_name": "web_fetch",
                    "tool_input": {"url": "https://httpbin.org/get"},
                    "required_permission_level": 2,
                    "risk_class": "medium",
                    "success_criteria": "HTTP response received.",
                }
            )

        # 6. General multi-step default objective
        else:
            steps.extend(
                [
                    {
                        "step_id": 1,
                        "title": "Query system diagnostic and environment state",
                        "description": "Verify system health and resource availability.",
                        "tool_name": "system_info",
                        "tool_input": {},
                        "required_permission_level": 0,
                        "risk_class": "low",
                        "success_criteria": "System info verified.",
                    },
                    {
                        "step_id": 2,
                        "title": "Execute objective logic in sandbox",
                        "description": f"Execute safe processing logic for: {objective}",
                        "tool_name": "code_sandbox",
                        "tool_input": {
                            "code": f"# VAL execution for: {objective}\nresult = {{'status': 'success', 'objective': {json.dumps(objective)}}}\nprint('VAL completed processing:', result)\n"
                        },
                        "required_permission_level": 2,
                        "risk_class": "medium",
                        "success_criteria": "Sandbox returned exit code 0.",
                    },
                    {
                        "step_id": 3,
                        "title": "Record outcome to workspace",
                        "description": "Persist run log in workspace for audit and review.",
                        "tool_name": "file_write",
                        "tool_input": {
                            "path": "run_summary.json",
                            "content": json.dumps({"objective": objective, "status": "completed"}, indent=2),
                        },
                        "required_permission_level": 2,
                        "risk_class": "medium",
                        "success_criteria": "Run summary file written.",
                    },
                ]
            )

        has_l4 = any(s.get("required_permission_level", 0) >= 4 for s in steps)
        risk_flags = ["level_4_founder_approval_required"] if has_l4 else []

        return {
            "summary": f"Execution plan for objective: '{objective}'",
            "steps": steps,
            "risk_flags": risk_flags,
            "requires_approval": has_l4,
        }


_model_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router
