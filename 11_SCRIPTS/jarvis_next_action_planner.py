from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "154_NEXT_ACTION_PLANNER"
REPORT = OUT / "NEXT_ACTION_PLANNER.md"
STATE = OUT / "NEXT_ACTION_PLANNER.json"


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def first_line(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[0] if lines else ""


def decide(data: dict) -> list[dict]:
    actions = []

    clean = data["clean"]

    if not clean:
        actions.append({
            "priority": 1,
            "title": "Clean current worktree",
            "command": "py -3 11_SCRIPTS/jarvis_ops.py autoship status",
            "reason": "Git has local changes.",
        })
        actions.append({
            "priority": 2,
            "title": "Ship guarded changes",
            "command": "py -3 11_SCRIPTS/jarvis_ops.py autoship commit \"chore: ship guarded Jarvis changes\" --push",
            "reason": "Use Autoship only after status looks safe.",
        })
        return actions

    actions.append({
        "priority": 1,
        "title": "Run command health",
        "command": "py -3 11_SCRIPTS/jarvis_ops.py command-health run",
        "reason": "Confirm all core commands still work.",
    })

    actions.append({
        "priority": 2,
        "title": "Run maintenance cycle",
        "command": "py -3 11_SCRIPTS/jarvis_ops.py maintenance-cycle run",
        "reason": "Refresh repo snapshot, operator brief, checkpoint, and catalog view.",
    })

    actions.append({
        "priority": 3,
        "title": "Create next small capability",
        "command": "py -3 11_SCRIPTS/jarvis_ops.py patch-catalog next",
        "reason": "Find the next safe feature candidate.",
    })

    return actions


def collect() -> dict:
    status = run(["git", "status", "-sb"])
    porcelain = run(["git", "status", "--porcelain"])
    log = run(["git", "log", "--oneline", "-8"])
    branch = run(["git", "branch", "--show-current"])
    catalog = run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "patch-catalog", "next"])
    autoship = run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "autoship", "status"])
    ship_guard = run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "ship-guard", "preflight"])

    data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "branch": branch["output"],
        "clean": len(porcelain["output"].strip()) == 0,
        "last_commit": first_line(log["output"]),
        "checks": {
            "branch": branch,
            "status": status,
            "porcelain": porcelain,
            "log": log,
            "catalog": catalog,
            "autoship": autoship,
            "ship_guard": ship_guard,
        },
    }

    data["actions"] = decide(data)
    data["verdict"] = "ready" if data["clean"] else "needs_cleanup"
    return data


def write(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Next Action Planner — Block 154",
        "",
        f"Created at: `{data['created_at']}`",
        f"Branch: `{data['branch']}`",
        f"Clean: `{data['clean']}`",
        f"Verdict: `{data['verdict']}`",
        f"Last commit: `{data['last_commit']}`",
        "",
        "## Actions",
        "",
    ]

    for action in data["actions"]:
        lines += [
            f"### {action['priority']}. {action['title']}",
            "",
            "```powershell",
            action["command"],
            "```",
            "",
            f"Reason: {action['reason']}",
            "",
        ]

    lines += [
        "## Git status",
        "",
        "```text",
        data["checks"]["status"]["output"] or "-",
        "```",
        "",
        "## Catalog next",
        "",
        "```text",
        data["checks"]["catalog"]["output"][-2500:] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def plan() -> int:
    data = collect()
    write(data)

    print("NEXT_ACTION_PLANNER_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": data["verdict"],
        "clean": data["clean"],
        "last_commit": data["last_commit"],
        "next_command": data["actions"][0]["command"] if data["actions"] else None,
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 154 Next Action Planner")
    parser.add_argument("action", choices=["plan"], default="plan")
    args = parser.parse_args()

    if args.action == "plan":
        return plan()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
