from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "181_SMART_MARATHON"
STATE = OUT / "SMART_MARATHON.json"
REPORT = OUT / "SMART_MARATHON.md"


def run(cmd: list[str]) -> dict:
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 4),
        "output": (result.stdout + result.stderr).strip(),
    }


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"load_error": str(exc)}


def clean_status() -> tuple[bool, str]:
    result = run(["git", "status", "-sb"])
    return result["output"].strip() == "## main...origin/main", result["output"]


def validate(label: str) -> dict:
    checks = {
        "git_status": run(["git", "status", "-sb"]),
        "home_dashboard": run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "home-dashboard", "home"]),
        "command_profiler": run(["py", "-3", "11_SCRIPTS/jarvis_ops.py", "command-profiler", "profile"]),
        "quality_gate": run(["py", "-3", "11_SCRIPTS/jarvis_pack_quality_gate.py", "report"]),
        "long_run_readiness": run(["py", "-3", "11_SCRIPTS/jarvis_pack_long_run_readiness.py", "report"]),
    }

    blockers = []
    for name, item in checks.items():
        if item["exit_code"] != 0:
            blockers.append(f"{label}:{name} failed")

    clean = checks["git_status"]["output"].strip() == "## main...origin/main"
    if not clean:
        blockers.append(f"{label}:repo dirty")

    profiler = read_json(EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json")
    profiler_total = profiler.get("total_seconds")

    return {
        "label": label,
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "repo_clean": clean,
        "profiler_total_seconds": profiler_total,
        "checks": checks,
    }


def run_smart(minutes: float, batch_size: int, max_batches: int, push: bool) -> int:
    started = time.perf_counter()
    deadline = started + max(0.1, minutes * 60)
    OUT.mkdir(parents=True, exist_ok=True)

    batches = []
    blockers = []

    pre = validate("preflight")
    if pre["verdict"] != "pass":
        blockers.extend(pre["blockers"])
        payload = finish(started, minutes, batch_size, max_batches, push, batches, blockers, preflight=pre)
        print_result(payload)
        return 1

    batch_index = 0

    while time.perf_counter() < deadline and (max_batches <= 0 or batch_index < max_batches):
        batch_index += 1

        clean, status = clean_status()
        if not clean:
            blockers.append(f"batch {batch_index}: repo dirty before run")
            break

        remaining_before = read_json(EXEC / "179_MARATHON_POOL" / "MARATHON_POOL.json").get("remaining_count")

        command = [
            "py", "-3", "11_SCRIPTS/jarvis_ops.py",
            "marathon-pool", "run",
            "--minutes", str(max(1, min(10, minutes))),
            "--max-features", str(batch_size),
        ]

        if push:
            command.append("--push")

        run_result = run(command)
        pool_state = read_json(EXEC / "179_MARATHON_POOL" / "MARATHON_POOL.json")
        post = validate(f"batch_{batch_index}_post")

        built_count = pool_state.get("built_count", 0)
        remaining_after = pool_state.get("remaining_count")

        batch = {
            "batch": batch_index,
            "command": command,
            "run_exit": run_result["exit_code"],
            "run_seconds": run_result["seconds"],
            "built_count": built_count,
            "remaining_before": remaining_before,
            "remaining_after": remaining_after,
            "post_verdict": post["verdict"],
            "post_blockers": post["blockers"],
            "profiler_total_seconds": post.get("profiler_total_seconds"),
            "output_tail": run_result["output"][-2200:],
        }

        batches.append(batch)

        if run_result["exit_code"] != 0:
            blockers.append(f"batch {batch_index}: marathon-pool failed")
            break

        if post["verdict"] != "pass":
            blockers.extend(post["blockers"])
            break

        if built_count == 0:
            break

    payload = finish(started, minutes, batch_size, max_batches, push, batches, blockers, preflight=pre)
    print_result(payload)
    return 0 if payload["verdict"] == "pass" else 1


def finish(started, minutes, batch_size, max_batches, push, batches, blockers, preflight):
    status = run(["git", "status", "-sb"])
    log = run(["git", "log", "--oneline", "-30"])
    pool = read_json(EXEC / "179_MARATHON_POOL" / "MARATHON_POOL.json")
    home = read_json(EXEC / "162_HOME_DASHBOARD" / "HOME_DASHBOARD.json")
    profiler = read_json(EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json")
    readiness = read_json(EXEC / "180_FEATURE_PACK_BUILDER" / "pack_outputs" / "long_run_readiness" / "long_run_readiness.json")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "minutes_requested": minutes,
        "batch_size": batch_size,
        "max_batches": max_batches,
        "push": push,
        "batches_completed": len(batches),
        "features_built_total": sum(int(item.get("built_count") or 0) for item in batches),
        "blockers": blockers,
        "preflight": {
            "verdict": preflight["verdict"],
            "blockers": preflight["blockers"],
            "profiler_total_seconds": preflight.get("profiler_total_seconds"),
        },
        "batches": batches,
        "pool_remaining": pool.get("remaining_count"),
        "script_count": home.get("script_count"),
        "script_lines": home.get("script_lines"),
        "profiler_total_seconds": profiler.get("total_seconds"),
        "readiness_findings": readiness.get("findings", []),
        "git_status": status["output"],
        "recent_commits": log["output"],
        "total_seconds": round(time.perf_counter() - started, 4),
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Smart Marathon Controller — Block 181",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Minutes requested: `{payload['minutes_requested']}`",
        f"Batch size: `{payload['batch_size']}`",
        f"Max batches: `{payload['max_batches']}`",
        f"Push: `{payload['push']}`",
        f"Batches completed: `{payload['batches_completed']}`",
        f"Features built total: `{payload['features_built_total']}`",
        f"Pool remaining: `{payload['pool_remaining']}`",
        f"Scripts: `{payload['script_count']}`",
        f"Lines: `{payload['script_lines']}`",
        f"Profiler total: `{payload['profiler_total_seconds']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Batches",
        "",
    ]

    for batch in batches:
        lines += [
            f"### Batch {batch['batch']}",
            "",
            f"- Run exit: `{batch['run_exit']}`",
            f"- Run seconds: `{batch['run_seconds']}`",
            f"- Built count: `{batch['built_count']}`",
            f"- Remaining before: `{batch['remaining_before']}`",
            f"- Remaining after: `{batch['remaining_after']}`",
            f"- Post verdict: `{batch['post_verdict']}`",
            f"- Profiler total: `{batch['profiler_total_seconds']}`",
            "",
        ]

    lines += [
        "## Blockers",
        "",
    ]

    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- No blockers.")

    lines += [
        "",
        "## Readiness findings",
        "",
    ]

    for item in payload["readiness_findings"][:8]:
        lines.append(f"- {item}")

    lines += [
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
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return payload


def print_result(payload: dict) -> None:
    print("SMART_MARATHON_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "batches_completed": payload["batches_completed"],
        "features_built_total": payload["features_built_total"],
        "pool_remaining": payload["pool_remaining"],
        "script_count": payload["script_count"],
        "script_lines": payload["script_lines"],
        "profiler_total_seconds": payload["profiler_total_seconds"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
        "total_seconds": payload["total_seconds"],
    }, ensure_ascii=False, indent=2))


def plan() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pool = read_json(EXEC / "179_MARATHON_POOL" / "MARATHON_POOL.json")
    readiness = read_json(EXEC / "180_FEATURE_PACK_BUILDER" / "pack_outputs" / "long_run_readiness" / "long_run_readiness.json")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "pool_remaining": pool.get("remaining_count"),
        "readiness_findings": readiness.get("findings", []),
        "suggested_30_min_command": "py -3 11_SCRIPTS/jarvis_ops.py smart-marathon run --minutes 30 --batch-size 8 --max-batches 0 --push",
        "suggested_60_min_command": "py -3 11_SCRIPTS/jarvis_ops.py smart-marathon run --minutes 60 --batch-size 8 --max-batches 0 --push",
    }

    print("SMART_MARATHON_PLAN")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Smart Marathon Controller")
    parser.add_argument("action", nargs="?", choices=["plan", "run"], default="plan")
    parser.add_argument("--minutes", type=float, default=10)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-batches", type=int, default=2)
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    if args.action == "plan":
        return plan()

    if args.action == "run":
        return run_smart(args.minutes, args.batch_size, args.max_batches, args.push)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
