from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "155_AUTO_CYCLE_RUNNER"
REPORT = OUT / "AUTO_CYCLE_RUNNER.md"
STATE = OUT / "AUTO_CYCLE_RUNNER.json"

STEPS = [
    ("repo-snapshot", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "repo-snapshot", "snapshot"]),
    ("execution-index", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "execution-index", "index"]),
    ("command-health", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "command-health", "run"]),
    ("maintenance-cycle", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "maintenance-cycle", "run"]),
    ("next-action", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "next-action", "plan"]),
    ("patch-catalog", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "patch-catalog", "next"]),
    ("autoship-status", ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "autoship", "status"]),
    ("git-status", ["git", "status", "-sb"]),
    ("git-log", ["git", "log", "--oneline", "-8"]),
]


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def cycle() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    blockers = []

    for name, cmd in STEPS:
        item = run(cmd)
        item["name"] = name
        results.append(item)

        if item["exit_code"] != 0 and name not in ["autoship-status"]:
            blockers.append(f"{name} failed")

    status = results[-2]["output"] if len(results) >= 2 else ""
    last_commit = results[-1]["output"].splitlines()[0] if results and results[-1]["output"] else ""

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "git_status": status,
        "last_commit": last_commit,
        "results": results,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Auto Cycle Runner — Block 155",
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
        results[-1]["output"] if results else "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("AUTO_CYCLE_RUNNER_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
        "last_commit": payload["last_commit"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 155 Auto Cycle Runner")
    parser.add_argument("action", choices=["run"], default="run")
    args = parser.parse_args()

    if args.action == "run":
        return cycle()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
