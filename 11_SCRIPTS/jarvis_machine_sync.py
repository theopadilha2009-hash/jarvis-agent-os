from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "125_MACHINE_SYNC"
REPORT = OUT / "MACHINE_SYNC_REPORT.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def first_ok(commands: list[list[str]]) -> dict:
    attempts = []
    for cmd in commands:
        code, out = run(cmd)
        attempts.append({"cmd": cmd, "code": code, "output": out})
        if code == 0:
            return {"ok": True, "selected": cmd, "output": out, "attempts": attempts}
    return {"ok": False, "selected": None, "output": "", "attempts": attempts}


def machine_sync() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    _, status = run(["git", "status", "-sb"])
    _, porcelain = run(["git", "status", "--porcelain"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-8"])
    _, branch = run(["git", "branch", "--show-current"])
    _, remote = run(["git", "remote", "-v"])
    _, git_name = run(["git", "config", "--global", "user.name"])
    _, git_email = run(["git", "config", "--global", "user.email"])

    python_probe = first_ok([
        [sys.executable, "--version"],
        ["py", "-3", "--version"],
        ["python", "--version"],
        ["python3", "--version"],
    ])

    exclude_path = REPO / ".git" / "info" / "exclude"
    exclude_text = exclude_path.read_text(encoding="utf-8", errors="replace") if exclude_path.exists() else ""

    checks = {
        "git_clean": not bool(porcelain.strip()),
        "on_main": branch.strip() == "main",
        "execution_outputs_ignored": "05_EXECUCAO/" in exclude_text,
        "python_ok": bool(python_probe["ok"]),
        "git_identity_set": bool(git_name.strip()) and bool(git_email.strip()),
    }

    next_actions = []
    if not checks["git_clean"]:
        next_actions.append("Review/commit/stash local changes before running automation.")
    if not checks["execution_outputs_ignored"]:
        next_actions.append("Add 05_EXECUCAO/ to .git/info/exclude on this machine.")
    if not checks["git_identity_set"]:
        next_actions.append("Configure git user.name and user.email for this computer.")
    if checks["git_clean"] and checks["python_ok"]:
        next_actions.append("Safe to continue with: py -3 11_SCRIPTS/jarvis_ops.py status")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "probe": python_probe,
        },
        "git": {
            "branch": branch,
            "status": status,
            "clean": checks["git_clean"],
            "commits": commits,
            "remote": remote,
            "user_name": git_name,
            "user_email": git_email,
        },
        "checks": checks,
        "next_actions": next_actions,
    }

    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("MACHINE_SYNC_DONE")
    print(REPORT)
    print(json.dumps({"checks": checks, "next_actions": next_actions}, ensure_ascii=False, indent=2))
    return 0 if checks["python_ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 125 Machine Sync")
    parser.add_argument("cmd", nargs="?", choices=["check"], default="check")
    args = parser.parse_args()

    if args.cmd == "check":
        return machine_sync()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
