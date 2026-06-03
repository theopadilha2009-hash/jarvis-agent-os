from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "126_SESSION_RUNNER"
REPORT = OUT / "SESSION_REPORT.md"
STATE = OUT / "SESSION_STATE.json"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py_ops(*args: str) -> tuple[int, str]:
    return run([sys.executable, "11_SCRIPTS/jarvis_ops.py", *args])


def step(name: str, cmd: list[str]) -> dict:
    code, out = run(cmd)
    return {
        "name": name,
        "cmd": cmd,
        "code": code,
        "output": out[-6000:] if out else "",
    }


def session(action: str, goal: str, limit: int = 1, auto: bool = False) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    steps: list[dict] = []

    if action == "start":
        plan = [
            ("machine", [sys.executable, "11_SCRIPTS/jarvis_ops.py", "machine"]),
            ("status", [sys.executable, "11_SCRIPTS/jarvis_ops.py", "status"]),
            ("task-list", [sys.executable, "11_SCRIPTS/jarvis_ops.py", "task", "list"]),
            ("decide-plan", [sys.executable, "11_SCRIPTS/jarvis_ops.py", "decide", goal, "--plan-only"]),
        ]
        if auto:
            plan.append(("task-run", [sys.executable, "11_SCRIPTS/jarvis_ops.py", "task", "run", "--limit", str(limit)]))

    elif action == "finish":
        plan = [
            ("review", [sys.executable, "11_SCRIPTS/jarvis_ops.py", "review"]),
            ("nightly", [sys.executable, "11_SCRIPTS/jarvis_ops.py", "nightly"]),
            ("status", [sys.executable, "11_SCRIPTS/jarvis_ops.py", "status"]),
        ]

    else:
        raise ValueError(f"unknown action: {action}")

    max_code = 0
    for name, cmd in plan:
        item = step(name, cmd)
        steps.append(item)
        max_code = max(max_code, item["code"])

    _, status = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-10"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "goal": goal,
        "limit": limit,
        "auto": auto,
        "exit_code": max_code,
        "status": status,
        "diff": diff or "clean",
        "commits": commits,
        "steps": steps,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Session Runner — Block 126",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Action: **{action}**",
        f"Goal: **{goal}**",
        f"Auto: `{auto}`",
        f"Exit code: `{max_code}`",
        "",
    ]

    for item in steps:
        lines += [
            f"## {item['name']}",
            "",
            "```text",
            item["output"] or "-",
            "```",
            "",
        ]

    lines += [
        "## Git Status",
        "",
        "```text",
        status or "-",
        "```",
        "",
        "## Diff",
        "",
        "```text",
        diff or "clean",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("SESSION_RUNNER_DONE")
    print(REPORT)
    print(status)
    return max_code


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 126 Session Runner")
    parser.add_argument("action", choices=["start", "finish"])
    parser.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--auto", action="store_true")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar Jarvis"
    return session(args.action, goal, limit=args.limit, auto=args.auto)


if __name__ == "__main__":
    raise SystemExit(main())
