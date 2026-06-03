from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "128_OPERATOR_ONE"
REPORT = OUT / "OPERATOR_ONE_REPORT.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def ops(*args: str) -> tuple[int, str]:
    return run([sys.executable, "11_SCRIPTS/jarvis_ops.py", *args])


def operator_one(goal: str, auto: bool = False, limit: int = 1) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    plan = [
        ("machine", ["machine"]),
        ("resume", ["resume", goal]),
        ("session-start", ["session", "start", goal]),
        ("decide", ["decide", goal, "--plan-only"]),
    ]

    if auto:
        plan.append(("task-run", ["task", "run", "--limit", str(limit)]))

    plan.append(("session-finish", ["session", "finish", goal]))

    steps = []
    max_code = 0

    for name, args in plan:
        code, out = ops(*args)
        steps.append({
            "name": name,
            "args": args,
            "code": code,
            "output": out[-5000:] if out else "",
        })
        max_code = max(max_code, code)

    _, status = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-8"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "auto": auto,
        "limit": limit,
        "exit_code": max_code,
        "status": status,
        "diff": diff or "clean",
        "commits": commits,
        "steps": steps,
    }

    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OPERATOR_ONE_DONE")
    print(REPORT)
    print(status)
    return max_code


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 128 Operator One")
    parser.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar Jarvis"
    return operator_one(goal, auto=args.auto, limit=args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
