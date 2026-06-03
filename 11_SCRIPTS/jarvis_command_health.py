from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "152_COMMAND_HEALTH"
REPORT = OUT / "COMMAND_HEALTH.md"
STATE = OUT / "COMMAND_HEALTH.json"

COMMANDS = [
    ["autoship", "status"],
    ["ship-guard", "preflight"],
    ["diff-gate", "review"],
    ["patch-catalog", "next"],
    ["repo-snapshot", "snapshot"],
    ["operator-brief", "brief"],
    ["daily-checkpoint", "checkpoint"],
    ["maintenance-cycle", "run"],
]


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def health() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    blockers = []

    compile_check = run(["py", "-3", "-m", "py_compile", "11_SCRIPTS\\jarvis_ops.py"])
    results.append({"name": "py_compile_ops", **compile_check})

    if compile_check["exit_code"] != 0:
        blockers.append("jarvis_ops.py compile failed")

    for parts in COMMANDS:
        name = " ".join(parts)
        item = run(["py", "-3", "11_SCRIPTS\\jarvis_ops.py", *parts])
        results.append({"name": name, **item})

        if item["exit_code"] != 0 and parts[0] not in ["diff-gate"]:
            blockers.append(f"{name} failed")

    status = run(["git", "status", "-sb"])
    log = run(["git", "log", "--oneline", "-8"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "git_status": status["output"],
        "last_commits": log["output"],
        "results": results,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Command Health — Block 152",
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
        "## Commands",
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
        payload["last_commits"] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("COMMAND_HEALTH_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 152 Command Health")
    parser.add_argument("action", choices=["run"], default="run")
    args = parser.parse_args()

    if args.action == "run":
        return health()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
