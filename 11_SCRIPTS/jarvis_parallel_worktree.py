from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO.parent
OUT = REPO / "05_EXECUCAO" / "129_PARALLEL_WORKTREE"
REPORT = OUT / "PARALLEL_WORKTREE_REPORT.md"
STATE = OUT / "PARALLEL_WORKTREE_STATE.json"

DEFAULT_WORKERS = 2


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        cwd=cwd or REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def git_clean(path: Path) -> bool:
    _, out = run(["git", "status", "--porcelain"], cwd=path)
    return not bool(out.strip())


def worker_path(index: int) -> Path:
    return ROOT / f"jarvis-agent-os-worker-{index}"


def worker_branch(index: int) -> str:
    return f"jarvis-worker-{index}"


def ensure_ignore(path: Path) -> None:
    exclude = path / ".git"
    if exclude.is_file():
        # Worktree .git is a file pointing to the actual gitdir.
        text = exclude.read_text(encoding="utf-8", errors="replace")
        gitdir_line = next((line for line in text.splitlines() if line.startswith("gitdir:")), "")
        if gitdir_line:
            gitdir = Path(gitdir_line.replace("gitdir:", "").strip())
            if not gitdir.is_absolute():
                gitdir = (path / gitdir).resolve()
            info = gitdir / "info" / "exclude"
        else:
            return
    else:
        info = exclude / "info" / "exclude"

    info.parent.mkdir(parents=True, exist_ok=True)
    current = info.read_text(encoding="utf-8", errors="replace") if info.exists() else ""
    for item in ["05_EXECUCAO/", "__pycache__/", "*.pyc", ".jarvis_worker_lock"]:
        if item not in current:
            current += "\n" + item + "\n"
    info.write_text(current, encoding="utf-8")


def init_workers(count: int) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    code, _ = run(["git", "fetch", "origin", "main"])
    if code != 0:
        print("FETCH_FAILED")
        return code

    if not git_clean(REPO):
        print("MAIN_NOT_CLEAN")
        _, status = run(["git", "status", "-sb"])
        print(status)
        return 1

    workers = []

    for index in range(1, count + 1):
        path = worker_path(index)
        branch = worker_branch(index)

        if path.exists():
            ensure_ignore(path)
            run(["git", "fetch", "origin", "main"], cwd=path)
            run(["git", "checkout", branch], cwd=path)
            run(["git", "reset", "--hard", "origin/main"], cwd=path)
            run(["git", "clean", "-fd", "--", "11_SCRIPTS"], cwd=path)
        else:
            code, out = run([
                "git",
                "worktree",
                "add",
                "-B",
                branch,
                str(path),
                "origin/main",
            ])
            if code != 0:
                print("WORKTREE_CREATE_FAILED")
                print(out)
                return code
            ensure_ignore(path)

        root_lock = path / ".jarvis_worker_lock"
        if root_lock.exists():
            root_lock.unlink()

        lock_dir = path / "05_EXECUCAO" / "129_PARALLEL_WORKTREE"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock = lock_dir / ".jarvis_worker_lock.json"
        lock.write_text(
            json.dumps({
                "worker": index,
                "branch": branch,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "status": "ready",
                "push_allowed": False,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        command = f'cd "{path}"; py -3 11_SCRIPTS/jarvis_ops.py one "melhorar autonomia do Jarvis"'

        workers.append({
            "worker": index,
            "path": str(path),
            "branch": branch,
            "clean": git_clean(path),
            "command": command,
        })

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "init",
        "workers": workers,
        "rules": [
            "Workers are isolated git worktrees.",
            "Workers must not push directly.",
            "Main repo remains the only merge/commit/push orchestrator.",
            "If worker becomes dirty, stop and inspect before merging.",
        ],
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(payload)

    print("PARALLEL_WORKTREE_READY")
    print(REPORT)
    for worker in workers:
        print(f"WORKER_{worker['worker']}: {worker['command']}")

    return 0


def status_workers(count: int) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    workers = []
    for index in range(1, count + 1):
        path = worker_path(index)
        if not path.exists():
            workers.append({
                "worker": index,
                "exists": False,
                "path": str(path),
            })
            continue

        root_lock = path / ".jarvis_worker_lock"
        if root_lock.exists():
            root_lock.unlink()

        ensure_ignore(path)

        _, status = run(["git", "status", "-sb"], cwd=path)
        _, log = run(["git", "log", "--oneline", "-3"], cwd=path)

        workers.append({
            "worker": index,
            "exists": True,
            "path": str(path),
            "clean": git_clean(path),
            "status": status,
            "last_commits": log,
        })

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "status",
        "workers": workers,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(payload)

    print("PARALLEL_WORKTREE_STATUS")
    print(REPORT)
    print(json.dumps(workers, ensure_ascii=False, indent=2))

    return 0


def clean_workers(count: int) -> int:
    if not git_clean(REPO):
        print("MAIN_NOT_CLEAN_STOPPING")
        return 1

    cleaned = []

    for index in range(1, count + 1):
        path = worker_path(index)
        if not path.exists():
            cleaned.append({"worker": index, "exists": False})
            continue

        code1, out1 = run(["git", "reset", "--hard", "origin/main"], cwd=path)
        code2, out2 = run(["git", "clean", "-fd"], cwd=path)
        ensure_ignore(path)

        cleaned.append({
            "worker": index,
            "exists": True,
            "code_reset": code1,
            "code_clean": code2,
            "output": (out1 + "\n" + out2)[-3000:],
            "clean": git_clean(path),
        })

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "clean",
        "workers": cleaned,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(payload)

    print("PARALLEL_WORKTREE_CLEANED")
    print(REPORT)
    print(json.dumps(cleaned, ensure_ascii=False, indent=2))

    return 0


def write_report(payload: dict) -> None:
    lines = [
        "# JARVIS Parallel Worktree Runner — Block 129",
        "",
        f"Generated at: `{payload.get('created_at')}`",
        f"Mode: `{payload.get('mode')}`",
        "",
        "## Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 129 Parallel Worktree Runner")
    parser.add_argument("cmd", choices=["init", "status", "clean"])
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    count = max(1, min(args.workers, 5))

    if args.cmd == "init":
        return init_workers(count)

    if args.cmd == "status":
        return status_workers(count)

    if args.cmd == "clean":
        return clean_workers(count)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
