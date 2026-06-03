from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXEC = REPO / "05_EXECUCAO"
SCRIPTS = REPO / "11_SCRIPTS"
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


def script_stats() -> dict:
    files = list(SCRIPTS.glob("jarvis_*.py"))
    lines = 0
    for path in files:
        try:
            lines += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            pass
    return {
        "script_count": len(files),
        "script_lines": lines,
    }


def home() -> int:
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run(["git", "status", "-sb"])
    git_log = run(["git", "log", "--oneline", "-8"])
    branch = run(["git", "branch", "--show-current"])

    quick_state = load_json(EXEC / "169_QUICK_HOME" / "QUICK_HOME.json")
    fast_state = load_json(EXEC / "168_FAST_STATUS" / "FAST_STATUS.json")
    profiler_state = load_json(EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json")
    sweep_state = load_json(EXEC / "165_DEEP_SWEEP" / "DEEP_SWEEP.json")
    audit_state = load_json(EXEC / "163_INTEGRITY_AUDIT" / "INTEGRITY_AUDIT.json")

    stats = script_stats()

    blockers = []
    if git_status["exit_code"] != 0:
        blockers.append("git_status failed")
    if branch["exit_code"] != 0:
        blockers.append("branch failed")

    status_text = git_status["output"]
    is_clean = status_text.strip() == "## main...origin/main"

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "mode": "direct-fast",
        "blockers": blockers,
        "branch": branch["output"],
        "is_clean": is_clean,
        "git_status": status_text,
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
        "recent_commits": git_log["output"],
        "script_count": stats["script_count"],
        "script_lines": stats["script_lines"],
        "execution_dir_count": sum(1 for item in EXEC.iterdir() if item.is_dir()) if EXEC.exists() else 0,
        "signals": {
            "quick_home_last_commit": quick_state.get("last_commit"),
            "fast_status_last_commit": fast_state.get("last_commit"),
            "profiler_total_seconds": profiler_state.get("total_seconds"),
            "deep_sweep_verdict": sweep_state.get("verdict"),
            "integrity_audit_verdict": audit_state.get("verdict"),
        },
        "timings": {
            "git_status": git_status["seconds"],
            "git_log": git_log["seconds"],
            "branch": branch["seconds"],
        },
        "total_seconds": 0,
    }

    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Home Dashboard — Direct Fast",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Mode: `{payload['mode']}`",
        f"Branch: `{payload['branch']}`",
        f"Clean: `{payload['is_clean']}`",
        f"Last commit: `{payload['last_commit']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Counts",
        "",
        f"- Scripts: `{payload['script_count']}`",
        f"- Script lines: `{payload['script_lines']}`",
        f"- Execution dirs: `{payload['execution_dir_count']}`",
        "",
        "## Signals",
        "",
        "```json",
        json.dumps(payload["signals"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
        "## Recent commits",
        "",
        "```text",
        payload["recent_commits"] or "-",
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
        "branch": payload["branch"],
        "is_clean": payload["is_clean"],
        "git_status": payload["git_status"],
        "last_commit": payload["last_commit"],
        "script_count": payload["script_count"],
        "script_lines": payload["script_lines"],
        "execution_dir_count": payload["execution_dir_count"],
        "total_seconds": payload["total_seconds"],
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
