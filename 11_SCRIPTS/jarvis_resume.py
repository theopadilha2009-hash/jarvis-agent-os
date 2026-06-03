from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "127_RESUME_COMMAND"
REPORT = OUT / "RESUME_REPORT.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py_ops(*args: str) -> tuple[int, str]:
    return run([sys.executable, "11_SCRIPTS/jarvis_ops.py", *args])


def resume(goal: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    steps = []
    for name, args in [
        ("machine", ["machine"]),
        ("status", ["status"]),
        ("task-list", ["task", "list"]),
        ("decision-plan", ["decide", goal, "--plan-only"]),
        ("session-start", ["session", "start", goal]),
    ]:
        code, out = py_ops(*args)
        steps.append({
            "name": name,
            "args": args,
            "code": code,
            "output": out[-5000:] if out else "",
        })

    _, git_status = run(["git", "status", "-sb"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-8"])

    next_command = f'py -3 11_SCRIPTS/jarvis_ops.py decide "{goal}"'

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "git_status": git_status,
        "commits": commits,
        "next_safe_command": next_command,
        "steps": steps,
    }

    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("RESUME_DONE")
    print(REPORT)
    print("NEXT_SAFE_COMMAND:")
    print(next_command)
    print(git_status)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 127 Resume Command")
    parser.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar Jarvis"
    return resume(goal)


if __name__ == "__main__":
    raise SystemExit(main())
