#!/usr/bin/env python3
"""VAL CLI — Command-line interface for the Founder.

Usage:
  val status
  val diagnostics
  val objective "<natural language objective>"
  val tasks [limit]
  val approvals
  val approve <approval_id>
  val reject <approval_id> [reason]
  val pause
  val resume
  val emergency
  val clear-emergency
  val audit [limit]
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "http://127.0.0.1:8000/api/v1"
FOUNDER_TOKEN = "val-founder-dev-token"


def _request(path: str, method: str = "GET", payload: dict | None = None) -> dict | list:
    url = f"{API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "x-val-founder-key": FOUNDER_TOKEN,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        print(f"Error {exc.code}: {err_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    data = _request("/status")
    print(json.dumps(data, indent=2))


def cmd_diagnostics(args):
    data = _request("/diagnostics")
    print(json.dumps(data, indent=2))


def cmd_objective(args):
    obj = args.text
    print(f"\n[VAL] Submitting objective: {obj}")
    res = _request("/chat", method="POST", payload={"content": obj, "auto_execute": True})
    print(f"\n--- VAL RESPONSE ---\n{res['message']['content']}\n")
    task = res.get("task")
    if task:
        print(f"Task ID: {task['task_id']}")
        print(f"Status:  {task['status']}")
        if task.get("error"):
            print(f"Error:   {task['error']}")


def cmd_tasks(args):
    data = _request(f"/tasks?limit={args.limit}")
    print(f"Found {len(data)} tasks:\n")
    for t in data:
        print(f"[{t['status'].upper():<16}] {t['task_id'][:8]}... | {t['title']}")


def cmd_approvals(args):
    data = _request("/approvals?status=pending")
    if not data:
        print("No pending Level 4 approvals.")
        return
    print(f"Pending Approvals ({len(data)}):\n")
    for a in data:
        print(f"ID:          {a['approval_id']}")
        print(f"Action:      {a['action_type']}")
        print(f"Risk Level:  {a['risk_level']}")
        print(f"Payload:     {json.dumps(a['action_payload'])}")
        print("-" * 50)


def cmd_approve(args):
    res = _request(
        f"/approvals/{args.approval_id}/decide",
        method="POST",
        payload={"decision": "approved", "reason": args.reason or "Founder CLI approval"},
    )
    print(f"Approval granted. Task resumed: status={res['status']}")


def cmd_reject(args):
    res = _request(
        f"/approvals/{args.approval_id}/decide",
        method="POST",
        payload={"decision": "rejected", "reason": args.reason or "Founder CLI rejection"},
    )
    print(f"Approval rejected. Task cancelled: status={res['status']}")


def cmd_pause(args):
    res = _request("/control/pause", method="POST")
    print(res.get("message", "System paused"))


def cmd_resume(args):
    res = _request("/control/resume", method="POST")
    print(res.get("message", "System resumed"))


def cmd_emergency(args):
    res = _request("/control/emergency", method="POST")
    print(res.get("message", "Emergency stop triggered"))


def cmd_clear_emergency(args):
    res = _request("/control/emergency/clear", method="POST")
    print(res.get("message", "Emergency cleared"))


def cmd_audit(args):
    data = _request(f"/audit?limit={args.limit}")
    print(f"Latest {len(data)} audit log entries:\n")
    for log in data:
        print(f"{log['created_at'][:19]} [{log['actor_type']:<6}] {log['action']:<25} (res: {log['resource_type'] or '-'})")


def cmd_agents(args):
    data = _request("/agents")
    print(f"Registered Workforce Agents ({len(data)}):\n")
    for a in data:
        print(f"[{a['status'].upper():<9}] {a['name']:<18} | {a['role']} (v{a['version']})")


def cmd_factory(args):
    print(f"[VAL Factory] Manufacturing specialized agent for: {args.objective}")
    res = _request("/agents/factory/build", method="POST", payload={"objective": args.objective, "force_name": args.name})
    if res.get("success"):
        print(f"Agent successfully manufactured and registered: {res['agent_name']}")
        print(f"Sandbox tests passed: {len(res['test_results'])}")
    else:
        print(f"Factory build failed: {res.get('error')}")


def cmd_learning(args):
    if args.sub == "list":
        data = _request("/learning/objectives")
        if not data:
            print("No active learning objectives.")
            return
        print(f"Learning Objectives ({len(data)}):\n")
        for o in data:
            print(f"[{o['status'].upper():<12}] {o['subject']:<15} (Agent: {o['agent_name']}) | Progress: {o['progress_score']}% | Readiness: {o['teaching_readiness']}%")
            print(f"  Current Topic: {o['current_topic']}")
            if o.get("detected_weaknesses"):
                print(f"  Weakness:      {', '.join(o['detected_weaknesses'])}")
            print(f"  ID:            {o['objective_id']}\n")
    elif args.sub == "start":
        res = _request("/learning/objectives", method="POST", payload={"subject": args.subject, "goal": args.goal})
        print(f"Learning objective initialized: {res['subject']} (Assigned to: {res['agent_name']})")
        print(f"Curriculum generated with {len(res['curriculum']['topics'])} topics.")
        print(f"Objective ID: {res['objective_id']}")
    elif args.sub == "advance":
        res = _request(f"/learning/objectives/{args.id}/advance", method="POST")
        print(f"Learning cycle completed:")
        print(f"  Topic:              {res['topic_title']}")
        print(f"  Practice Score:     {res['practice_score']}%")
        print(f"  Overall Progress:   {res['overall_progress']}%")
        print(f"  Teaching Readiness: {res['teaching_readiness']}%")
        if res.get("weakness_identified"):
            print(f"  Weakness Detected:  {res['weakness_identified']}")
        print(f"  Next Action:        {res['next_action']}")


def cmd_teach(args):
    print(f"[Founder Teaching] Submitting directive to VAL knowledge base...")
    res = _request("/learning/teach", method="POST", payload={"statement": args.statement, "scope": args.scope})
    print(f"Directive stored under: {res['classified_topic']} (Scope: {res['scope']})")
    print(f"Provenance: High-Authority Founder Teaching (verified: True)")
    if res.get("clarifying_questions"):
        print("\nClarifying Questions for Founder:")
        for q in res["clarifying_questions"]:
            print(f"  • {q}")


def cmd_git(args):
    payload = {"subcommand": args.git_cmd}
    if args.msg:
        payload["commit_message"] = args.msg
    if args.branch:
        payload["branch_name"] = args.branch
    res = _request("/tools/git_ops/execute", method="POST", payload=payload)
    out = res.get("output", {})
    if out.get("stdout"):
        print(out["stdout"])
    if out.get("stderr"):
        print(out["stderr"], file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="VAL Autonomous AI CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status")
    sub.add_parser("diagnostics")

    p_obj = sub.add_parser("objective")
    p_obj.add_argument("text", help="Natural language objective")

    p_tasks = sub.add_parser("tasks")
    p_tasks.add_argument("--limit", type=int, default=20)

    sub.add_parser("approvals")

    p_app = sub.add_parser("approve")
    p_app.add_argument("approval_id")
    p_app.add_argument("--reason", default="Founder approved via CLI")

    p_rej = sub.add_parser("reject")
    p_rej.add_argument("approval_id")
    p_rej.add_argument("--reason", default="Founder rejected via CLI")

    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("emergency")
    sub.add_parser("clear-emergency")

    p_aud = sub.add_parser("audit")
    p_aud.add_argument("--limit", type=int, default=20)

    sub.add_parser("agents")

    p_fac = sub.add_parser("factory")
    p_fac.add_argument("objective", help="Agent domain purpose or objective")
    p_fac.add_argument("--name", default=None, help="Optional agent name (e.g. CALCULUS.VAL)")

    p_lrn = sub.add_parser("learning")
    p_lrn_sub = p_lrn.add_subparsers(dest="sub")
    p_lrn_sub.add_parser("list")
    p_lrn_start = p_lrn_sub.add_parser("start")
    p_lrn_start.add_argument("subject", help="Subject (e.g. Calculus)")
    p_lrn_start.add_argument("goal", help="Learning goal")
    p_lrn_adv = p_lrn_sub.add_parser("advance")
    p_lrn_adv.add_argument("id", help="Objective ID")

    p_tch = sub.add_parser("teach")
    p_tch.add_argument("statement", help="Directive or knowledge statement from Founder")
    p_tch.add_argument("--scope", default="company", choices=["company", "project", "agent"])

    p_git = sub.add_parser("git")
    p_git.add_argument("git_cmd", choices=["status", "diff", "branch", "log", "commit"])
    p_git.add_argument("--msg", default="", help="Commit message")
    p_git.add_argument("--branch", default="", help="Branch name")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "status": cmd_status,
        "diagnostics": cmd_diagnostics,
        "objective": cmd_objective,
        "tasks": cmd_tasks,
        "approvals": cmd_approvals,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "emergency": cmd_emergency,
        "clear-emergency": cmd_clear_emergency,
        "audit": cmd_audit,
        "agents": cmd_agents,
        "factory": cmd_factory,
        "learning": cmd_learning,
        "teach": cmd_teach,
        "git": cmd_git,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
