from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "120_POWER_LOOP"
REPORT = OUT / "POWER_LOOP_REPORT.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py(script: str, *args: str) -> tuple[int, str]:
    return run([sys.executable, script, *args])


def dirty() -> bool:
    _, out = run(["git", "status", "--porcelain"])
    return bool(out.strip())


def power(goal: str, steps: int = 2, autoship: bool = False, message: str = "") -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs: list[dict] = []

    plan = [
        ("snapshot-before", ["11_SCRIPTS/jarvis_ops.py", "snapshot", "power-before"]),
        ("mission", ["11_SCRIPTS/jarvis_ops.py", "mission", goal, "--steps", str(steps)]),
        ("review", ["11_SCRIPTS/jarvis_ops.py", "review"]),
        ("snapshot-after", ["11_SCRIPTS/jarvis_ops.py", "snapshot", "power-after"]),
    ]

    max_code = 0

    for name, cmd in plan:
        code, out = py(*cmd)
        max_code = max(max_code, code)
        outputs.append({"name": name, "cmd": cmd, "code": code, "output": out[-5000:]})

    shipped = False
    ship_output = ""

    if autoship and dirty():
        commit_message = message.strip() or "feat: run Jarvis power loop"
        code, ship_output = py("11_SCRIPTS/jarvis_ops.py", "ship", commit_message)
        max_code = max(max_code, code)
        shipped = code == 0

    _, status = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-12"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "steps": steps,
        "autoship": autoship,
        "shipped": shipped,
        "status": status,
        "diff": diff or "clean",
        "commits": commits,
        "outputs": outputs,
        "ship_output": ship_output[-5000:] if ship_output else "",
    }

    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("POWER_LOOP_DONE")
    print(REPORT)
    print(status)

    return max_code


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 120 Power Loop")
    parser.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--ship", action="store_true")
    parser.add_argument("--message", default="")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar Jarvis"
    return power(goal, steps=args.steps, autoship=args.ship, message=args.message)


if __name__ == "__main__":
    raise SystemExit(main())
