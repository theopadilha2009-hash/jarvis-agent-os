from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "159_CONTROL_CENTER"
REPORT = OUT / "CONTROL_CENTER.md"
STATE = OUT / "CONTROL_CENTER.json"

STEPS = [
    ("git_status", ["git", "status", "-sb"]),
    ("last_commits", ["git", "log", "--oneline", "-8"]),
    ("autoship_status", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "autoship", "status"]),
    ("ship_guard", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "ship-guard", "preflight"]),
    ("command_menu", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "command-menu", "menu"]),
    ("capability_map", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "capability-map", "map"]),
    ("next_action", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "next-action", "plan"]),
]


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def control() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    blockers = []

    for name, cmd in STEPS:
        item = run(cmd)
        item["name"] = name
        results.append(item)

        if item["exit_code"] != 0 and name not in ["autoship_status"]:
            blockers.append(f"{name} failed")

    git_status = results[0]["output"] if results else ""
    last_commits = results[1]["output"] if len(results) > 1 else ""

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "git_status": git_status,
        "last_commit": last_commits.splitlines()[0] if last_commits else "",
        "results": results,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Control Center — Block 159",
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
        "## Steps",
        "",
    ]

    for item in results:
        lines.append(f"- `{item['name']}` exit=`{item['exit_code']}`")

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
        last_commits or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("CONTROL_CENTER_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
        "last_commit": payload["last_commit"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 159 Control Center")
    parser.add_argument("action", choices=["run"], default="run")
    args = parser.parse_args()

    if args.action == "run":
        return control()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
