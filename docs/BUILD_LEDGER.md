# VAL DEVELOPMENT BUILD LEDGER

**Current Architecture Version:** 1.0 (MVP Phase 1–3 Complete)  
**Date:** September 25, 2026  
**Document Owner:** Senior AI Architect / Arena  
**Authority Hierarchy:** Founder → Arena (Senior Guide) → VAL Development → VAL Core → VAL Workforce → Specialized Agents  

---

## 1. COMPONENT BUILD STATUS SUMMARY

| Component | Status | Dependencies | Implementation File(s) | Tests | Known Issues / Notes | Next Step |
|---|---|---|---|---|---|---|
| **Permission Engine** | `APPROVED` | None | `backend/val/permissions/engine.py` | `tests/test_permissions.py` (6 tests) | Fail-closed, L0–L2 autonomous, L3 delegate gated, L4 high-impact approval gated | Phase 4 role ABAC policies |
| **File Safety Architecture** | `APPROVED` | Permission Engine | `backend/val/security/file_safety.py` | `tests/test_file_safety.py` (4 tests) | Protected paths blocked from mutation outside LLM, re-rooting prevents traversal | Git-backed auto-versioning for critical paths |
| **Database & Persistence** | `APPROVED` | SQLAlchemy / SQLite / Postgres | `backend/val/db/models.py`, `backend/val/db/session.py` | Full ORM & schema tests | SQLite for local MVP; Schema maps 1:1 to Postgres design in Doc 21 | Add pgvector extension support |
| **Immutable Audit Logger** | `APPROVED` | Database Engine | `backend/val/audit/logger.py`, `backend/val/db/models.py` | `tests/test_orchestrator.py` | ORM before_update/before_delete listeners reject mutation; dual-write JSONL | External log forwarder (OpenTelemetry) |
| **Tool Registry & Safe Tools** | `APPROVED` | File Safety, Audit | `backend/val/tools/` (builtins, registry, base) | `tests/test_tools.py` (7 tests) | 9 safe tools: code sandbox, safe calculator, file read/write/list, web fetch, system info, datetime | Expand toolset (git, docker) |
| **Hardware Diagnostic Probe** | `APPROVED` | None | `backend/val/tools/builtins.py`, `scripts/run_diagnostics.py` | `tests/test_tools.py` | Detects CPU, RAM, disk, OS, local Ollama runner, outputs classification | GPU VRAM & CUDA profiling |
| **Hardware-Aware Model Router** | `APPROVED` | System Probe | `backend/val/core/model_router.py` | Router tests | Supports remote API, local Ollama, and local deterministic fallback | Local GGUF / llama.cpp direct binding |
| **Planner Core** | `APPROVED` | Model Router, Tool Registry | `backend/val/core/planner.py` | `tests/test_orchestrator.py` | Decomposes objective into structured plan with steps, tools, and risk flags | Dynamic sub-goal replanning |
| **Autonomy Orchestrator** | `APPROVED` | Planner, Permissions, Tools | `backend/val/core/orchestrator.py` | `tests/test_orchestrator.py` | Full loop: Observe → Plan → Perm Check → Execute → Verify → Store Memory → Audit → Report | Asynchronous worker pool |
| **Scoped Memory Service** | `APPROVED` | Database | `backend/val/memory/service.py` | `tests/test_api.py` | Working, short-term, long-term scopes with TTL and importance scoring | Vector semantic embeddings |
| **Emergency Control Plane** | `APPROVED` | Permissions | `backend/val/api/routes_control.py` | `tests/test_permissions.py`, `tests/test_api.py` | Global pause, Emergency hard freeze, Clear emergency, Tool enable/disable | Scoped agent-level emergency pauses |
| **REST & WebSocket API** | `APPROVED` | FastAPI, All Services | `backend/val/api/app.py`, `routes_*.py` | `tests/test_api.py` (6 tests) | Full REST surface with OpenAPI docs at `/docs` | WebSocket push events for live updates |
| **Founder Executive Dashboard** | `APPROVED` | REST API | `frontend/index.html` | Browser integration | Real-time polling, chat/objective intake, approval actions, audit stream | Advanced task graph visualization |
| **Founder CLI** | `APPROVED` | REST API | `scripts/val_cli.py` | CLI operational tests | Complete CLI commands: status, objective, approvals, pause, resume, emergency, audit | Interactive TUI mode |
| **Agent Registry & Runtime** | `NOT STARTED` | Orchestrator, Database | Next build phase | Phase 4 Roadmap | Scheduled for Phase 4 | Configurable specialized agents |
| **VAL Agent Factory** | `NOT STARTED` | Agent Runtime, Sandbox | Next build phase | Phase 5 Roadmap | Scheduled for Phase 5 | Dynamic agent creation & testing |
| **Self-Improvement Pipeline** | `NOT STARTED` | Factory, Sandbox | Future phase | Phase 7 Roadmap | Scheduled for Phase 7 | Supervised self-improvement loop |

---

## 2. SYSTEM CAPABILITY VERIFICATION

### Automated Test Suite
- Total Test Cases: **26 passing (100%)**
- Execution Time: **~2.2 seconds**
- Modules Covered:
  1. `test_permissions.py`: Observe, Recommend, Execute, Delegate gate, Level 4 High-Impact approval requirement, Allow-list blocking, Global Pause, Emergency Stop.
  2. `test_file_safety.py`: Directory traversal escape blocking, Protected path mutation refusal outside LLM, Allowed workspace read/write, Chmod refusal.
  3. `test_tools.py`: Echo, Safe Calculator (AST math + injection prevention), System Diagnostics probe, Code Sandbox (execution, stdout/stderr, timeout enforcement), File Tools roundtrip.
  4. `test_orchestrator.py`: Full Autonomy Loop, Level 4 High-Impact pause & approval resumption, Immutable Audit Log tampering rejection.
  5. `test_api.py`: Status, Diagnostics, Chat & Task execution, Tool execution, Scoped Memory store/recall, Audit Log stream, Emergency Control plane.

---

## 3. HARDWARE & RUNTIME RECOMMENDATIONS

Based on diagnostics run on this environment:
- **Compute:** 2 CPU cores, Linux x86_64
- **System Memory:** 1984 MB Total (~1473 MB Available)
- **Disk Storage:** 19.67 GB Available
- **Local Model Runner:** Local Fallback Engine active

### Recommendations:
1. **Local Compute Role:** The laptop/environment compute is classified as **lightweight**. It comfortably runs the complete VAL Core, FastAPI, SQLite/PostgreSQL, Sandbox runner, Memory, and Permission engine.
2. **Model Strategy:** For complex reasoning and code generation, use the **Hybrid** strategy:
   - Planning & reasoning: Cloud API (OpenAI / Anthropic / Groq) via `OPENAI_API_KEY` or local quantized models (e.g., Llama-3.2-1B / 3B INT4) if 8GB+ RAM is available on the Founder's personal laptop.
   - Core autonomous execution, planning fallbacks, and tool execution: Runs 100% locally with zero external dependencies.
