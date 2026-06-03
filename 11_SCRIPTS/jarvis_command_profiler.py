from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "166_COMMAND_PROFILER"
REPORT = OUT / "COMMAND_PROFILER.md"
STATE = OUT / "COMMAND_PROFILER.json"

COMMANDS = [
    ("git_status", ["git", "status", "-sb"]),
    ("home_dashboard", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "home-dashboard", "home"]),
    ("integrity_audit", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "integrity-audit", "audit"]),
    ("deep_sweep", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "deep-sweep", "sweep"]),
    ("capability_map", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "capability-map", "map"]),
    ("command_menu", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "command-menu", "menu"]),
    ("next_action", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "next-action", "plan"]),
    ("autoship_status", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "autoship", "status"]),
]


def run_timed(cmd: list[str]) -> dict:
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    elapsed = time.perf_counter() - started

    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(elapsed, 4),
        "output_chars": len((result.stdout or "") + (result.stderr or "")),
        "output": (result.stdout + result.stderr).strip()[-2500:],
    }


def profile() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    blockers = []

    for name, cmd in COMMANDS:
        item = run_timed(cmd)
        item["name"] = name
        results.append(item)

        if item["exit_code"] != 0 and name != "autoship_status":
            blockers.append(f"{name} failed")

    total_seconds = round(sum(item["seconds"] for item in results), 4)
    slowest = sorted(results, key=lambda item: item["seconds"], reverse=True)[:5]

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "total_seconds": total_seconds,
        "slowest": slowest,
        "results": results,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Command Profiler — Block 166",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Results",
        "",
    ]

    for item in results:
        lines.append(f"- `{item['name']}` exit=`{item['exit_code']}` seconds=`{item['seconds']}` output_chars=`{item['output_chars']}`")

    lines += [
        "",
        "## Slowest",
        "",
    ]

    for item in slowest:
        lines.append(f"- `{item['name']}` seconds=`{item['seconds']}`")

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

    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("COMMAND_PROFILER_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "blockers": payload["blockers"],
        "total_seconds": payload["total_seconds"],
        "slowest": [{"name": x["name"], "seconds": x["seconds"]} for x in slowest],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 166 Command Profiler")
    parser.add_argument("action", choices=["profile"], default="profile")
    args = parser.parse_args()

    if args.action == "profile":
        return profile()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
