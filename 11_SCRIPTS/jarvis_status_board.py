from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "160_STATUS_BOARD"
REPORT = OUT / "STATUS_BOARD.md"
STATE = OUT / "STATUS_BOARD.json"


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def board() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    checks = {
        "git_status": run(["git", "status", "-sb"]),
        "git_log": run(["git", "log", "--oneline", "-8"]),
        "autoship": run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "autoship", "status"]),
        "ship_guard": run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "ship-guard", "preflight"]),
        "next_action": run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "next-action", "plan"]),
        "capability_map": run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "capability-map", "map"]),
    }

    blockers = []
    for name, item in checks.items():
        if item["exit_code"] != 0 and name != "autoship":
            blockers.append(f"{name} failed")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "git_status": checks["git_status"]["output"],
        "last_commit": checks["git_log"]["output"].splitlines()[0] if checks["git_log"]["output"] else "",
        "checks": checks,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Status Board — Block 160",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Last commit: `{payload['last_commit']}`",
        "",
        "## Git",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
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
        for item in blockers:
            lines.append(f"- {item}")
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

    print("STATUS_BOARD_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
        "last_commit": payload["last_commit"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 160 Status Board")
    parser.add_argument("action", choices=["board"], default="board")
    args = parser.parse_args()

    if args.action == "board":
        return board()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
