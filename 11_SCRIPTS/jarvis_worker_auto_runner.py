from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO.parent
OUT = REPO / "05_EXECUCAO" / "130_WORKER_AUTO_RUNNER"
REPORT = OUT / "WORKER_AUTO_REPORT.md"
STATE = OUT / "WORKER_AUTO_STATE.json"


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        cwd=cwd or REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def worker_path(index: int) -> Path:
    return ROOT / f"jarvis-agent-os-worker-{index}"


def git_clean(path: Path) -> bool:
    _, out = run(["git", "status", "--porcelain"], cwd=path)
    return not bool(out.strip())


def git_status(path: Path) -> str:
    _, out = run(["git", "status", "-sb"], cwd=path)
    return out


def worker_command(index: int, goal: str, mode: str) -> list[str]:
    if mode == "safe":
        return [sys.executable, "11_SCRIPTS/jarvis_ops.py", "one", goal]

    if mode == "think":
        return [sys.executable, "11_SCRIPTS/jarvis_ops.py", "decide", goal, "--plan-only"]

    if mode == "session":
        return [sys.executable, "11_SCRIPTS/jarvis_ops.py", "session", "start", goal]

    raise ValueError(f"unknown worker mode: {mode}")


def collect_status(workers: int) -> list[dict]:
    items = []

    for index in range(1, workers + 1):
        path = worker_path(index)

        if not path.exists():
            items.append({
                "worker": index,
                "exists": False,
                "path": str(path),
            })
            continue

        _, commits = run(["git", "log", "--oneline", "-3"], cwd=path)

        items.append({
            "worker": index,
            "exists": True,
            "path": str(path),
            "clean": git_clean(path),
            "status": git_status(path),
            "commits": commits,
        })

    return items


def plan(workers: int, goal: str, mode: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    commands = []
    for index in range(1, workers + 1):
        path = worker_path(index)
        cmd = worker_command(index, goal, mode)
        commands.append({
            "worker": index,
            "path": str(path),
            "mode": mode,
            "goal": goal,
            "command": " ".join(cmd),
            "powershell": f'cd "{path}"; {" ".join(cmd)}',
        })

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": "plan",
        "workers": workers,
        "goal": goal,
        "mode": mode,
        "commands": commands,
        "status": collect_status(workers),
    }

    write_outputs(payload)

    print("WORKER_AUTO_PLAN_READY")
    print(REPORT)
    for item in commands:
        print(f"WORKER_{item['worker']}: {item['powershell']}")

    return 0


def run_workers(workers: int, goal: str, mode: str, timeout: int) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    if not git_clean(REPO):
        print("MAIN_NOT_CLEAN")
        print(git_status(REPO))
        return 1

    status_before = collect_status(workers)
    dirty = [item for item in status_before if item.get("exists") and not item.get("clean")]

    if dirty:
        print("WORKER_DIRTY_STOPPING")
        print(json.dumps(dirty, ensure_ascii=False, indent=2))
        return 1

    processes = []
    started_at = time.time()

    for index in range(1, workers + 1):
        path = worker_path(index)

        if not path.exists():
            print(f"WORKER_{index}_MISSING")
            return 1

        log_path = OUT / f"worker_{index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_file = log_path.open("w", encoding="utf-8")

        cmd = worker_command(index, goal, mode)

        proc = subprocess.Popen(
            cmd,
            cwd=path,
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        processes.append({
            "worker": index,
            "path": str(path),
            "cmd": cmd,
            "log": str(log_path),
            "proc": proc,
            "log_file": log_file,
        })

    results = []
    max_code = 0

    for item in processes:
        proc = item["proc"]
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = 124

        item["log_file"].close()

        log_text = Path(item["log"]).read_text(encoding="utf-8", errors="replace")

        result = {
            "worker": item["worker"],
            "path": item["path"],
            "cmd": item["cmd"],
            "code": code,
            "log": item["log"],
            "tail": log_text[-5000:] if log_text else "",
        }

        results.append(result)
        max_code = max(max_code, code)

    duration = round(time.time() - started_at, 2)
    status_after = collect_status(workers)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": "run",
        "workers": workers,
        "goal": goal,
        "mode": mode,
        "timeout": timeout,
        "duration_seconds": duration,
        "exit_code": max_code,
        "status_before": status_before,
        "status_after": status_after,
        "results": results,
    }

    write_outputs(payload)

    print("WORKER_AUTO_RUN_DONE")
    print(REPORT)
    print(json.dumps({
        "exit_code": max_code,
        "duration_seconds": duration,
        "status_after": status_after,
    }, ensure_ascii=False, indent=2))

    return max_code


def open_windows(workers: int, goal: str, mode: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    opened = []

    for index in range(1, workers + 1):
        path = worker_path(index)

        if not path.exists():
            print(f"WORKER_{index}_MISSING")
            return 1

        cmd = worker_command(index, goal, mode)
        ps = f'cd "{path}"; {" ".join(cmd)}; Write-Host ""; Write-Host "WORKER {index} FINALIZADO"; pause'

        subprocess.Popen([
            "powershell",
            "-NoExit",
            "-Command",
            ps,
        ])

        opened.append({
            "worker": index,
            "path": str(path),
            "command": ps,
        })

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": "open",
        "workers": workers,
        "goal": goal,
        "mode": mode,
        "opened": opened,
    }

    write_outputs(payload)

    print("WORKER_WINDOWS_OPENED")
    print(REPORT)

    return 0


def write_outputs(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Worker Auto Runner — Block 130",
        "",
        f"Generated at: `{payload.get('created_at')}`",
        f"Action: `{payload.get('action')}`",
        f"Workers: `{payload.get('workers')}`",
        f"Goal: `{payload.get('goal')}`",
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
    parser = argparse.ArgumentParser(description="JARVIS Block 130 Worker Auto Runner")
    parser.add_argument("action", choices=["plan", "run", "open", "status"])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--goal", default="melhorar autonomia do Jarvis")
    parser.add_argument("--mode", choices=["safe", "think", "session"], default="safe")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    workers = max(1, min(args.workers, 5))

    if args.action == "plan":
        return plan(workers, args.goal, args.mode)

    if args.action == "run":
        return run_workers(workers, args.goal, args.mode, args.timeout)

    if args.action == "open":
        return open_windows(workers, args.goal, args.mode)

    if args.action == "status":
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "action": "status",
            "workers": workers,
            "goal": args.goal,
            "mode": args.mode,
            "status": collect_status(workers),
        }
        write_outputs(payload)
        print("WORKER_AUTO_STATUS")
        print(REPORT)
        print(json.dumps(payload["status"], ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
