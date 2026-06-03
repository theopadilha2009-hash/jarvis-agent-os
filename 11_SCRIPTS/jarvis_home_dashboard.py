from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "162_HOME_DASHBOARD"
REPORT = OUT / "HOME_DASHBOARD.md"
STATE = OUT / "HOME_DASHBOARD.json"


def run(cmd: list[str]) -> dict:
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 4),
        "output": (result.stdout + result.stderr).strip(),
    }


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"load_error": str(exc)}


def home() -> int:
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    quick = run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "quick-home", "home"])
    fast = run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "fast-status", "status"])
    git_status = run(["git", "status", "-sb"])
    git_log = run(["git", "log", "--oneline", "-8"])

    quick_state = load_json(EXEC / "169_QUICK_HOME" / "QUICK_HOME.json")
    fast_state = load_json(EXEC / "168_FAST_STATUS" / "FAST_STATUS.json")

    blockers = []
    if quick["exit_code"] != 0:
        blockers.append("quick_home failed")
    if fast["exit_code"] != 0:
        blockers.append("fast_status failed")
    if git_status["exit_code"] != 0:
        blockers.append("git_status failed")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "mode": "accelerated",
        "blockers": blockers,
        "git_status": git_status["output"],
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
        "quick_home_seconds": quick["seconds"],
        "fast_status_seconds": fast["seconds"],
        "script_count": quick_state.get("script_count", fast_state.get("script_count")),
        "script_lines": quick_state.get("script_lines"),
        "execution_dir_count": quick_state.get("execution_dir_count", fast_state.get("execution_dir_count")),
        "quick_home": {
            "exit_code": quick["exit_code"],
            "seconds": quick["seconds"],
        },
        "fast_status": {
            "exit_code": fast["exit_code"],
            "seconds": fast["seconds"],
        },
    }

    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Home Dashboard — Accelerated",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Mode: `{payload['mode']}`",
        f"Last commit: `{payload['last_commit']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Signals",
        "",
        f"- Quick Home seconds: `{payload['quick_home_seconds']}`",
        f"- Fast Status seconds: `{payload['fast_status_seconds']}`",
        f"- Scripts: `{payload['script_count']}`",
        f"- Script lines: `{payload['script_lines']}`",
        f"- Execution dirs: `{payload['execution_dir_count']}`",
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
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

    print("HOME_DASHBOARD_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "mode": payload["mode"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
        "last_commit": payload["last_commit"],
        "total_seconds": payload["total_seconds"],
        "quick_home_seconds": payload["quick_home_seconds"],
        "fast_status_seconds": payload["fast_status_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Home Dashboard")
    parser.add_argument("action", choices=["home"], default="home")
    args = parser.parse_args()

    if args.action == "home":
        return home()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
