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

HARD_ERROR_MARKERS = [
    "Traceback (most recent call last)",
    "SyntaxError",
    "NameError",
    "ModuleNotFoundError",
    "ImportError",
    "PARE:",
    "MAIN_NOT_CLEAN",
    "WORKER_DIRTY_STOPPING",
    "Missing script:",
    "error: unrecognized arguments",
    "fatal:",
    "FAILED",
    "BLOCKED",
]


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


def classify_result(code: int, tail: str, worker_clean: bool) -> dict:
    hard_markers = [marker for marker in HARD_ERROR_MARKERS if marker in tail]

    if code == 124:
        return {
            "class": "hard_fail",
            "reason": "timeout",
            "hard_markers": hard_markers,
        }

    if not worker_clean:
        return {
            "class": "hard_fail",
            "reason": "worker_dirty_after_run",
            "hard_markers": hard_markers,
        }

    if hard_markers:
        return {
            "class": "hard_fail",
            "reason": "hard_error_marker_found",
            "hard_markers": hard_markers,
        }

    if code != 0:
        return {
            "class": "soft_warn",
            "reason": "nonzero_exit_but_worker_clean",
            "hard_markers": [],
        }

    return {
        "class": "ok",
        "reason": "zero_exit_and_clean",
        "hard_markers": [],
    }


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
            "command": cmd,
            "powershell": f'cd "{path}"; py -3 11_SCRIPTS/jarvis_ops.py one "{goal}"',
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

    raw_max_code = 0
    results = []

    for item in processes:
        proc = item["proc"]
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = 124

        item["log_file"].close()

        log_text = Path(item["log"]).read_text(encoding="utf-8", errors="replace")
        tail = log_text[-7000:] if log_text else ""

        raw_max_code = max(raw_max_code, code)

        results.append({
            "worker": item["worker"],
            "path": item["path"],
            "cmd": item["cmd"],
            "code": code,
            "log": item["log"],
            "tail": tail,
        })

    duration = round(time.time() - started_at, 2)
    status_after = collect_status(workers)
    clean_map = {item.get("worker"): bool(item.get("clean")) for item in status_after}

    for result in results:
        result["classification"] = classify_result(
            int(result["code"]),
            str(result.get("tail") or ""),
            clean_map.get(result["worker"], False),
        )

    hard_failures = [r for r in results if r["classification"]["class"] == "hard_fail"]
    soft_warnings = [r for r in results if r["classification"]["class"] == "soft_warn"]

    effective_exit_code = 1 if hard_failures else 0

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": "run",
        "workers": workers,
        "goal": goal,
        "mode": mode,
        "timeout": timeout,
        "duration_seconds": duration,
        "raw_exit_code": raw_max_code,
        "effective_exit_code": effective_exit_code,
        "hard_failures": len(hard_failures),
        "soft_warnings": len(soft_warnings),
        "status_before": status_before,
        "status_after": status_after,
        "results": results,
    }

    write_outputs(payload)

    print("WORKER_AUTO_RUN_DONE")
    print(REPORT)
    print(json.dumps({
        "raw_exit_code": raw_max_code,
        "effective_exit_code": effective_exit_code,
        "hard_failures": len(hard_failures),
        "soft_warnings": len(soft_warnings),
        "duration_seconds": duration,
        "status_after": status_after,
    }, ensure_ascii=False, indent=2))

    return effective_exit_code


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


def collect(workers: int, goal: str, mode: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    logs = []
    for log_path in sorted(OUT.glob("worker_*.log"))[-20:]:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        logs.append({
            "file": str(log_path),
            "size": log_path.stat().st_size,
            "tail": text[-5000:] if text else "",
        })

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": "collect",
        "workers": workers,
        "goal": goal,
        "mode": mode,
        "status": collect_status(workers),
        "logs": logs,
    }

    write_outputs(payload)

    print("WORKER_AUTO_COLLECT_DONE")
    print(REPORT)
    print(json.dumps({
        "workers": payload["status"],
        "logs_collected": len(logs),
    }, ensure_ascii=False, indent=2))

    return 0


def status(workers: int, goal: str, mode: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": "status",
        "workers": workers,
        "goal": goal,
        "mode": mode,
        "status": collect_status(workers),
    }

    write_outputs(payload)

    print("WORKER_AUTO_STATUS")
    print(REPORT)
    print(json.dumps(payload["status"], ensure_ascii=False, indent=2))
    return 0


def write_outputs(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Worker Auto Runner — Block 131",
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
    parser = argparse.ArgumentParser(description="JARVIS Block 131 Worker Auto Runner Hardening")
    parser.add_argument("action", choices=["plan", "run", "open", "status", "collect"])
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
        return status(workers, args.goal, args.mode)

    if args.action == "collect":
        return collect(workers, args.goal, args.mode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
