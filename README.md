# VAL — Autonomous AI Core (MVP Release v0.1.0)

> **Authority Hierarchy (Non-Negotiable):**  
> **Founder** → **Arena AI** (Senior Guide) → **VAL Development** → **VAL Core** → **VAL Workforce** → **Specialized Agents** → **Tools / APIs / Data**

VAL is the core autonomous AI system designed to operate as an independent executive workforce layer. It accepts natural-language objectives, plans complex work, executes tools under strict permission control, requests Founder approval for any high-impact action, maintains scoped memory, and writes an immutable audit trail.

---

## 1. Quick Start

### Starting the VAL Server & Dashboard
```bash
cd /home/user/val/backend
python3 -m uvicorn val.api.app:app --host 0.0.0.0 --port 8000
```
- **Web Dashboard:** Open `http://localhost:8000` (or the live preview host)
- **API Documentation:** `http://localhost:8000/docs`

---

## 2. Using the Founder CLI

A dedicated command-line interface is available in `scripts/val_cli.py`:

```bash
# Check system status
./scripts/val_cli.py status

# Run hardware & runtime diagnostics
./scripts/val_cli.py diagnostics

# Submit an autonomous objective
./scripts/val_cli.py objective "Inspect hardware diagnostics and verify system status"

# List recent tasks
./scripts/val_cli.py tasks --limit 10

# Inspect pending Level 4 approvals
./scripts/val_cli.py approvals

# Approve a Level 4 action
./scripts/val_cli.py approve <approval_id> --reason "Founder authorized"

# Emergency control plane
./scripts/val_cli.py pause
./scripts/val_cli.py resume
./scripts/val_cli.py emergency
./scripts/val_cli.py clear-emergency

# Inspect immutable audit trail
./scripts/val_cli.py audit --limit 20
```

---

## 3. Core Architecture & Enforced Invariants

1. **Enforcement Outside the LLM:**  
   Permission levels (L0–L4) and file safety boundaries are checked by Python code before any tool executes. Instructions in prompts are never the sole line of defense.
2. **Level 4 High-Impact Approval Gate:**  
   Any action touching money, production servers, security policies, or protected system code automatically pauses execution, generates an approval request in the database, and waits for explicit Founder approval.
3. **File Safety Guard:**  
   System configuration, security code, audit trails, and the database file cannot be overwritten or deleted by VAL regardless of what the reasoning model asks for. Directory traversal attacks (`../../`) are blocked.
4. **Immutable Audit Trail:**  
   Every objective, plan, tool invocation, permission decision, and emergency trigger is written to the `audit_logs` table. Database triggers prevent any `UPDATE` or `DELETE` on audit records. Dual-write appends to `data/audit/audit.jsonl`.
5. **Hardware-Aware Model Router:**  
   Supports remote LLMs via OpenAI-compatible endpoints, local Ollama models, and an offline deterministic planning fallback so VAL is 100% functional even without API keys or internet access.
6. **Scoped Memory:**  
   Multi-tier memory architecture (Working, Short-Term, Long-Term, User, Project, Company) with TTL pruning and importance scoring.

---

## 4. Running the Automated Test Suite

```bash
cd /home/user/val
PYTHONPATH=backend pytest tests -v
```

All 26 tests cover permissions, file safety, tool execution, code sandbox timeouts, autonomy loop execution, approval gates, and audit immutability.
