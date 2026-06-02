from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "119_MISSION_ENGINE"
REPORT = OUT / "MISSION_REPORT.md"
STATE = OUT / "MISSION_STATE.json"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def shell(cmd: list[str]) -> str:
    return " ".join(shlex.quote(x) for x in cmd)


def build_plan(goal: str, steps: int) -> list[dict]:
    return [
        {
            "name": "snapshot-start",
            "reason": "capture state before work",
            "cmd": [sys.executable, "11_SCRIPTS/jarvis_ops.py", "snapshot", "mission-start"],
        },
        {
            "name": "grow",
            "reason": "apply pending safe growth if available",
            "cmd": [sys.executable, "11_SCRIPTS/jarvis_ops.py", "grow", "--limit", str(max(1, steps))],
        },
        {
            "name": "review",
            "reason": "audit progress and closeout after growth",
            "cmd": [sys.executable, "11_SCRIPTS/jarvis_ops.py", "review"],
        },
        {
            "name": "snapshot-end",
            "reason": "capture final state",
            "cmd": [sys.executable, "11_SCRIPTS/jarvis_ops.py", "snapshot", "mission-end"],
        },
    ]


def mission(goal: str, steps: int = 2, execute: bool = True) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    plan = build_plan(goal, steps)
    outputs: list[dict] = []

    for item in plan:
        entry = {
            "name": item["name"],
            "reason": item["reason"],
            "cmd": shell(item["cmd"]),
            "executed": execute,
            "code": 0,
            "output": "",
        }

        if execute:
            code, out = run(item["cmd"])
            entry["code"] = code
            entry["output"] = out

        outputs.append(entry)

    _, status = run(["git", "status", "-sb"])
    _, porcelain = run(["git", "status", "--porcelain"])
    _, diff = run(["git", "diff", "--stat"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-12"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "steps": steps,
        "execute": execute,
        "git_clean": not bool(porcelain.strip()),
        "status": status,
        "diff": diff or "clean",
        "commits": commits,
        "plan": outputs,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Mission Engine — Block 119",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Goal: **{goal}**",
        f"Execute: `{execute}`",
        f"Git clean: `{'yes' if payload['git_clean'] else 'no'}`",
        "",
        "## Plan",
        "",
    ]

    for item in outputs:
        lines += [
            f"### {item['name']}",
            "",
            f"Reason: {item['reason']}",
            "",
            "```bash",
            item["cmd"],
            "```",
            "",
            f"Exit code: `{item['code']}`",
            "",
            "```text",
            item["output"][-4000:] if item["output"] else "-",
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

    print("MISSION_ENGINE_DONE")
    print(REPORT)
    print(status)

    return max([item["code"] for item in outputs] or [0])


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 119 Mission Engine")
    parser.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar Jarvis"
    return mission(goal, steps=args.steps, execute=not args.plan_only)


if __name__ == "__main__":
    raise SystemExit(main())
