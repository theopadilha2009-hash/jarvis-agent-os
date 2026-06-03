from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "151_MAINTENANCE_CYCLE"
REPORT = OUT / "MAINTENANCE_CYCLE.md"
STATE = OUT / "MAINTENANCE_CYCLE.json"


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def cycle() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    steps = [
        ("repo_snapshot", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "repo-snapshot", "snapshot"]),
        ("operator_brief", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "operator-brief", "brief"]),
        ("daily_checkpoint", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "daily-checkpoint", "checkpoint"]),
        ("patch_catalog_next", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "patch-catalog", "next"]),
        ("autoship_status", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "autoship", "status"]),
        ("ship_guard", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "ship-guard", "preflight"]),
        ("git_status", ["git", "status", "-sb"]),
        ("git_log", ["git", "log", "--oneline", "-8"]),
    ]

    results = []
    blockers = []

    for name, cmd in steps:
        item = run(cmd)
        item["name"] = name
        results.append(item)

        if item["exit_code"] != 0 and name not in ["autoship_status"]:
            blockers.append(f"{name} failed")

    status = results[-2]["output"] if len(results) >= 2 else ""

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "git_status": status,
        "results": results,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Maintenance Cycle — Block 151",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
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
        results[-1]["output"] if results else "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("MAINTENANCE_CYCLE_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 151 Maintenance Cycle")
    parser.add_argument("action", choices=["run"], default="run")
    args = parser.parse_args()

    if args.action == "run":
        return cycle()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
