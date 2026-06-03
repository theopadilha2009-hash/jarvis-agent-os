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
    ("git_status", ["git", "status", "-sb"], False),
    ("quick_home", ["py", "-3", "11_SCRIPTS/jarvis_quick_home.py", "home"], False),
    ("fast_status", ["py", "-3", "11_SCRIPTS/jarvis_fast_status.py", "status"], False),
    ("home_dashboard", ["py", "-3", "11_SCRIPTS/jarvis_home_dashboard.py", "home"], False),
    ("next_action", ["py", "-3", "11_SCRIPTS/jarvis_next_action_planner.py", "plan"], False),
    ("integrity_audit", ["py", "-3", "11_SCRIPTS/jarvis_integrity_audit.py", "audit"], False),
    ("deep_sweep", ["py", "-3", "11_SCRIPTS/jarvis_deep_sweep.py", "sweep"], False),
    ("autoship_status", ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "autoship", "status"], True),
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
        "output_tail": (result.stdout + result.stderr).strip()[-1800:],
    }


def profile() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    blockers = []

    for name, cmd, soft_fail in COMMANDS:
        item = run_timed(cmd)
        item["name"] = name
        item["soft_fail"] = soft_fail
        results.append(item)

        if item["exit_code"] != 0 and not soft_fail:
            blockers.append(f"{name} failed")

    total_seconds = round(sum(item["seconds"] for item in results), 4)
    slowest = sorted(results, key=lambda item: item["seconds"], reverse=True)[:8]
    fastest = sorted(results, key=lambda item: item["seconds"])[:5]

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "mode": "direct-fast",
        "blockers": blockers,
        "total_seconds": total_seconds,
        "slowest": slowest,
        "fastest": fastest,
        "results": results,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Command Profiler — Direct Fast",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Mode: `{payload['mode']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Results",
        "",
    ]

    for item in results:
        lines.append(
            f"- `{item['name']}` exit=`{item['exit_code']}` seconds=`{item['seconds']}` "
            f"output_chars=`{item['output_chars']}` soft_fail=`{item['soft_fail']}`"
        )

    lines += [
        "",
        "## Slowest",
        "",
    ]

    for item in slowest:
        lines.append(f"- `{item['name']}` seconds=`{item['seconds']}`")

    lines += [
        "",
        "## Fastest",
        "",
    ]

    for item in fastest:
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
        "mode": payload["mode"],
        "blockers": payload["blockers"],
        "total_seconds": payload["total_seconds"],
        "slowest": [{"name": x["name"], "seconds": x["seconds"]} for x in slowest],
        "fastest": [{"name": x["name"], "seconds": x["seconds"]} for x in fastest],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Command Profiler")
    parser.add_argument("action", choices=["profile"], default="profile")
    args = parser.parse_args()

    if args.action == "profile":
        return profile()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
