## VAL Pull Request Summary

### 1. What does this PR change?
<!-- Brief description of the change, agent capability, or fix -->

### 2. Authority & Permission Impact
- [ ] Level 0 (Observe) — Read-only
- [ ] Level 1 (Recommend) — Proposals only
- [ ] Level 2 (Execute) — Low/Medium impact within pre-approved sandbox bounds
- [ ] Level 3 (Delegate) — Multi-agent delegation
- [ ] Level 4 (High-Impact) — **Requires explicit Founder Sign-off!**

### 3. Invariants & Security Checklist
- [ ] No secrets, keys, or credentials committed
- [ ] Enforcement occurs outside the LLM (tested at tool/service layer)
- [ ] Protected paths (`backend/val`, `data/audit`, `.git`) cannot be mutated
- [ ] Full automated test suite passes (`pytest tests -v`)
- [ ] Supabase RLS policies maintained if database changes were made
- [ ] Immutable audit logs remain untampered

### 4. Test Results
```text
<!-- Paste output of PYTHONPATH=backend pytest tests -v here -->
```

### 5. Founder Approval
- [ ] Reviewed and Approved by Founder
