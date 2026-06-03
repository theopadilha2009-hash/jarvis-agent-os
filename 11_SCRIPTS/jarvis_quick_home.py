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
OUT = EXEC / "169_QUICK_HOME"
REPORT = OUT / "QUICK_HOME.md"
STATE = OUT / "QUICK_HOME.json"

STATE_FILES = {
    "fast_status": EXEC / "168_FAST_STATUS" / "FAST_STATUS.json",
    "command_profiler": EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json",
    "deep_sweep": EXEC / "165_DEEP_SWEEP" / "DEEP_SWEEP.json",
    "integrity_audit": EXEC / "163_INTEGRITY_AUDIT" / "INTEGRITY_AUDIT.json",
    "autoship": EXEC / "145_AUTOSHIP" / "AUTOSHIP.json",
}


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


def line_count() -> int:
    total = 0
    for path in SCRIPTS.glob("jarvis_*.py"):
        try:
            total += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            pass
    return total


def home() -> int:
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run(["git", "status", "-sb"])
    git_log = run(["git", "log", "--oneline", "-8"])
    branch = run(["git", "branch", "--show-current"])

    loaded = {name: load_json(path) for name, path in STATE_FILES.items()}

    status_text = git_status["output"]
    is_clean = bool(status_text.strip().endswith("origin/main")) and "\n" not in status_text.strip()

    latest = {
        "fast_status": loaded.get("fast_status", {}).get("last_commit", ""),
        "deep_sweep": loaded.get("deep_sweep", {}).get("last_commit", ""),
        "integrity_audit": loaded.get("integrity_audit", {}).get("last_commit", ""),
        "command_profiler_seconds": loaded.get("command_profiler", {}).get("total_seconds", None),
    }

    blockers = []
    if git_status["exit_code"] != 0:
        blockers.append("git status failed")
    if branch["exit_code"] != 0:
        blockers.append("branch check failed")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "mode": "quick",
        "repo": str(REPO),
        "branch": branch["output"],
        "is_clean": is_clean,
        "git_status": status_text,
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
        "recent_commits": git_log["output"],
        "script_count": sum(1 for _ in SCRIPTS.glob("jarvis_*.py")),
        "script_lines": line_count(),
        "execution_dir_count": sum(1 for item in EXEC.iterdir() if item.is_dir()) if EXEC.exists() else 0,
        "latest": latest,
        "blockers": blockers,
        "total_seconds": 0,
    }

    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Quick Home — Block 169",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Mode: `{payload['mode']}`",
        f"Branch: `{payload['branch']}`",
        f"Clean: `{payload['is_clean']}`",
        f"Last commit: `{payload['last_commit']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## System",
        "",
        f"- Scripts: `{payload['script_count']}`",
        f"- Script lines: `{payload['script_lines']}`",
        f"- Execution dirs: `{payload['execution_dir_count']}`",
        "",
        "## Latest known signals",
        "",
        f"- Fast status commit: `{latest['fast_status'] or '-'}`",
        f"- Deep sweep commit: `{latest['deep_sweep'] or '-'}`",
        f"- Integrity audit commit: `{latest['integrity_audit'] or '-'}`",
        f"- Command profiler seconds: `{latest['command_profiler_seconds']}`",
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

    print("QUICK_HOME_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "mode": payload["mode"],
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
    parser = argparse.ArgumentParser(description="JARVIS Block 169 Quick Home")
    parser.add_argument("action", choices=["home"], default="home")
    args = parser.parse_args()

    if args.action == "home":
        return home()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
