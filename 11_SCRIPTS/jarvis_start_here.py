from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "161_START_HERE"
REPORT = OUT / "START_HERE.md"
STATE = OUT / "START_HERE.json"

COMMANDS = [
    ("Check status", "py -3 11_SCRIPTS/jarvis_ops.py status-board board"),
    ("Run control center", "py -3 11_SCRIPTS/jarvis_ops.py control-center run"),
    ("Run command health", "py -3 11_SCRIPTS/jarvis_ops.py command-health run"),
    ("Plan next action", "py -3 11_SCRIPTS/jarvis_ops.py next-action plan"),
    ("Run full cycle", "py -3 11_SCRIPTS/jarvis_ops.py auto-cycle-runner run"),
    ("Ship safe changes", "py -3 11_SCRIPTS/jarvis_ops.py autoship commit \"chore: ship guarded Jarvis changes\" --push"),
]


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def build() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run(["git", "status", "-sb"])
    git_log = run(["git", "log", "--oneline", "-8"])
    autoship = run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "autoship", "status"])
    next_action = run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "next-action", "plan"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "git_status": git_status["output"],
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
        "commands": [{"title": title, "command": command} for title, command in COMMANDS],
        "checks": {
            "git_status": git_status,
            "git_log": git_log,
            "autoship": autoship,
            "next_action": next_action,
        },
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Start Here — Block 161",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Last commit: `{payload['last_commit']}`",
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
        "## Commands",
        "",
    ]

    for item in payload["commands"]:
        lines += [
            f"### {item['title']}",
            "",
            "```powershell",
            item["command"],
            "```",
            "",
        ]

    lines += [
        "## Next action raw output",
        "",
        "```text",
        next_action["output"][-3500:] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("START_HERE_DONE")
    print(REPORT)
    print(json.dumps({
        "last_commit": payload["last_commit"],
        "git_status": payload["git_status"],
        "command_count": len(payload["commands"]),
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 161 Start Here")
    parser.add_argument("action", choices=["build"], default="build")
    args = parser.parse_args()

    if args.action == "build":
        return build()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
