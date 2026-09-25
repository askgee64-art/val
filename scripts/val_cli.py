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
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
