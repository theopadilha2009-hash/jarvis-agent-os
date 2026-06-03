from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "168_FAST_STATUS"
REPORT = OUT / "FAST_STATUS.md"
STATE = OUT / "FAST_STATUS.json"


def run(cmd: list[str]) -> dict:
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 4),
        "output": (result.stdout + result.stderr).strip(),
    }


def count_dirs(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.iterdir() if item.is_dir())


def count_files(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.glob(pattern))


def status() -> int:
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run(["git", "status", "-sb"])
    git_log = run(["git", "log", "--oneline", "-8"])
    branch = run(["git", "branch", "--show-current"])

    py_files = sorted(SCRIPTS.glob("jarvis_*.py"))

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if git_status["exit_code"] == 0 else "block",
        "repo": str(REPO),
        "branch": branch["output"],
        "git_status": git_status["output"],
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
        "script_count": len(py_files),
        "execution_dir_count": count_dirs(EXEC),
        "python_file_count": count_files(SCRIPTS, "jarvis_*.py"),
        "checks": {
            "git_status": git_status,
            "git_log": git_log,
            "branch": branch,
        },
    }

    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Fast Status — Block 168",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Branch: `{payload['branch']}`",
        f"Last commit: `{payload['last_commit']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Counts",
        "",
        f"- Scripts: `{payload['script_count']}`",
        f"- Execution dirs: `{payload['execution_dir_count']}`",
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
        "## Last commits",
        "",
        "```text",
        git_log["output"] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("FAST_STATUS_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "branch": payload["branch"],
        "git_status": payload["git_status"],
        "last_commit": payload["last_commit"],
        "script_count": payload["script_count"],
        "execution_dir_count": payload["execution_dir_count"],
        "total_seconds": payload["total_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0 if payload["verdict"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 168 Fast Status")
    parser.add_argument("action", choices=["status"], default="status")
    args = parser.parse_args()

    if args.action == "status":
        return status()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
