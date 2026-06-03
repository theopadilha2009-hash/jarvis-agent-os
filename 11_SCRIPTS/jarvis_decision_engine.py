from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "122_DECISION_ENGINE"
REPORT = OUT / "DECISION_REPORT.md"
STATE = OUT / "DECISION_STATE.json"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py_ops(*args: str) -> tuple[int, str]:
    return run([sys.executable, "11_SCRIPTS/jarvis_ops.py", *args])


def git_clean() -> bool:
    _, out = run(["git", "status", "--porcelain"])
    return not bool(out.strip())


def get_status() -> dict:
    _, status = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-10"])
    return {"clean": git_clean(), "status": status, "diff": diff or "clean", "commits": commits}


def inspect_task_next() -> dict:
    code, out = py_ops("task", "list")
    try:
        data = json.loads(out)
    except Exception:
        data = {"raw": out}
    return {"code": code, "data": data}


def decide(goal: str) -> dict:
    status = get_status()
    task_info = inspect_task_next()
    next_task = task_info.get("data", {}).get("next")
    inside_task_engine = os.environ.get("JARVIS_TASK_ENGINE_RUNNING") == "1"

    if not status["clean"]:
        return {"action": "review", "reason": "git is dirty; review before continuing", "command": ["review"], "status": status, "next_task": next_task}

    if inside_task_engine:
        return {"action": "mission", "reason": "already inside task engine; avoid recursive task-next", "command": ["mission", goal, "--steps", "1"], "status": status, "next_task": next_task}

    if next_task:
        return {"action": "task-next", "reason": "safe queued task exists", "command": ["task", "next"], "status": status, "next_task": next_task}

    return {"action": "mission", "reason": "no queued tasks; run controlled mission", "command": ["mission", goal, "--steps", "1"], "status": status, "next_task": None}


def execute(goal: str, plan_only: bool = False) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    decision = decide(goal)
    command = decision["command"]
    code = 0
    output = ""

    if not plan_only:
        code, output = py_ops(*command)

    final_status = get_status()
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "plan_only": plan_only,
        "decision": decision,
        "executed_command": command if not plan_only else None,
        "exit_code": code,
        "output": output[-6000:] if output else "",
        "final_status": final_status,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    REPORT.write_text(
        "\n".join([
            "# JARVIS Decision Engine ? Block 124 Hardened",
            "",
            f"Generated at: `{payload['created_at']}`",
            f"Goal: **{goal}**",
            f"Plan only: `{plan_only}`",
            f"Decision: **{decision['action']}**",
            f"Reason: {decision['reason']}",
            "",
            "## Command",
            "",
            "```bash",
            "python3 11_SCRIPTS/jarvis_ops.py " + " ".join(command),
            "```",
            "",
            "## Output",
            "",
            "```text",
            output[-6000:] if output else "-",
            "```",
            "",
            "## Final Status",
            "",
            "```text",
            final_status["status"] or "-",
            "```",
            "",
            "## Diff",
            "",
            "```text",
            final_status["diff"],
            "```",
            "",
        ]),
        encoding="utf-8",
    )

    print("DECISION_ENGINE_DONE")
    print(REPORT)
    print(final_status["status"])
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 124 Hardened Decision Engine")
    parser.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    goal = " ".join(args.goal).strip() or "melhorar Jarvis"
    return execute(goal, plan_only=args.plan_only)


if __name__ == "__main__":
    raise SystemExit(main())
