from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "162_HOME_DASHBOARD"
REPORT = OUT / "HOME_DASHBOARD.md"
STATE = OUT / "HOME_DASHBOARD.json"


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def home() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    checks = {
        "git_status": run(["git", "status", "-sb"]),
        "git_log": run(["git", "log", "--oneline", "-10"]),
        "status_board": run(["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "status-board", "board"]),
        "start_here": run(["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "start-here", "build"]),
        "command_menu": run(["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "command-menu", "menu"]),
        "next_action": run(["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "next-action", "plan"]),
        "autoship_status": run(["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "autoship", "status"]),
    }

    blockers = []
    for name, item in checks.items():
        if item["exit_code"] != 0 and name != "autoship_status":
            blockers.append(f"{name} failed")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "git_status": checks["git_status"]["output"],
        "last_commit": checks["git_log"]["output"].splitlines()[0] if checks["git_log"]["output"] else "",
        "recommended_commands": [
            "py -3 11_SCRIPTS\\jarvis_ops.py home-dashboard home",
            "py -3 11_SCRIPTS\\jarvis_ops.py status-board board",
            "py -3 11_SCRIPTS\\jarvis_ops.py next-action plan",
            "py -3 11_SCRIPTS\\jarvis_ops.py auto-cycle-runner run",
            "py -3 11_SCRIPTS\\jarvis_ops.py autoship status",
        ],
        "checks": checks,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Home Dashboard — Block 162",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Last commit: `{payload['last_commit']}`",
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
        "## Recommended commands",
        "",
    ]

    for cmd in payload["recommended_commands"]:
        lines += [
            "```powershell",
            cmd,
            "```",
            "",
        ]

    lines += [
        "## Checks",
        "",
    ]

    for name, item in checks.items():
        lines.append(f"- `{name}` exit=`{item['exit_code']}`")

    lines += [
        "",
        "## Blockers",
        "",
    ]

    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- No blockers.")

    lines += [
        "",
        "## Last commits",
        "",
        "```text",
        checks["git_log"]["output"] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("HOME_DASHBOARD_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
        "last_commit": payload["last_commit"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 162 Home Dashboard")
    parser.add_argument("action", choices=["home"], default="home")
    args = parser.parse_args()

    if args.action == "home":
        return home()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
