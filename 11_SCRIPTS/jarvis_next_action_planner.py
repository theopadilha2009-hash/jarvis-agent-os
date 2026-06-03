from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "154_NEXT_ACTION_PLANNER"
REPORT = OUT / "NEXT_ACTION_PLAN.md"
STATE = OUT / "NEXT_ACTION_PLAN.json"


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


def action(title: str, reason: str, command: str, priority: int) -> dict:
    return {
        "title": title,
        "reason": reason,
        "command": command,
        "priority": priority,
    }


def plan() -> int:
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run(["git", "status", "-sb"])
    git_log = run(["git", "log", "--oneline", "-8"])

    quick = load_json(EXEC / "169_QUICK_HOME" / "QUICK_HOME.json")
    fast = load_json(EXEC / "168_FAST_STATUS" / "FAST_STATUS.json")
    profiler = load_json(EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json")
    sweep = load_json(EXEC / "165_DEEP_SWEEP" / "DEEP_SWEEP.json")
    audit = load_json(EXEC / "163_INTEGRITY_AUDIT" / "INTEGRITY_AUDIT.json")

    blockers = []
    if git_status["exit_code"] != 0:
        blockers.append("git status failed")

    status_text = git_status["output"]
    repo_clean = status_text.strip() == "## main...origin/main"

    actions = []

    if not repo_clean:
        actions.append(action(
            "Review dirty repo before new work",
            "Git status is not clean.",
            "git status -sb && git diff --stat",
            100,
        ))

    if audit.get("verdict") != "pass":
        actions.append(action(
            "Run integrity audit",
            "Latest integrity audit is missing or not passing.",
            "py -3 11_SCRIPTS/jarvis_ops.py integrity-audit audit",
            90,
        ))

    if sweep.get("verdict") != "pass":
        actions.append(action(
            "Run deep sweep",
            "Latest deep sweep is missing or not passing.",
            "py -3 11_SCRIPTS/jarvis_ops.py deep-sweep sweep",
            80,
        ))

    slowest = profiler.get("slowest", []) if isinstance(profiler, dict) else []
    if slowest:
        top = slowest[0]
        actions.append(action(
            f"Optimize slow command: {top.get('name', 'unknown')}",
            f"Profiler marks this as the slowest command at {top.get('seconds')}s.",
            "py -3 11_SCRIPTS/jarvis_ops.py command-profiler profile",
            70,
        ))

    if repo_clean:
        actions.append(action(
            "Build next Jarvis capability",
            "Repo is clean and core checks are passing.",
            "py -3 11_SCRIPTS/jarvis_ops.py quick-home home",
            60,
        ))

    actions.append(action(
        "Keep fast operator loop",
        "Quick-home gives the fastest current cockpit status.",
        "py -3 11_SCRIPTS/jarvis_ops.py quick-home home",
        50,
    ))

    actions = sorted(actions, key=lambda item: item["priority"], reverse=True)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "mode": "accelerated",
        "blockers": blockers,
        "repo_clean": repo_clean,
        "git_status": status_text,
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
        "signals": {
            "quick_home_verdict": quick.get("verdict"),
            "fast_status_verdict": fast.get("verdict"),
            "profiler_verdict": profiler.get("verdict"),
            "deep_sweep_verdict": sweep.get("verdict"),
            "audit_verdict": audit.get("verdict"),
            "script_count": quick.get("script_count", fast.get("script_count")),
            "script_lines": quick.get("script_lines"),
        },
        "actions": actions[:8],
        "total_seconds": 0,
    }

    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Next Action Planner — Accelerated",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Mode: `{payload['mode']}`",
        f"Repo clean: `{payload['repo_clean']}`",
        f"Last commit: `{payload['last_commit']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Next actions",
        "",
    ]

    for idx, item in enumerate(payload["actions"], start=1):
        lines += [
            f"### {idx}. {item['title']}",
            "",
            f"- Reason: {item['reason']}",
            f"- Command: `{item['command']}`",
            f"- Priority: `{item['priority']}`",
            "",
        ]

    lines += [
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
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("NEXT_ACTION_PLAN_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "mode": payload["mode"],
        "repo_clean": payload["repo_clean"],
        "last_commit": payload["last_commit"],
        "action_count": len(payload["actions"]),
        "top_action": payload["actions"][0] if payload["actions"] else None,
        "total_seconds": payload["total_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Next Action Planner")
    parser.add_argument("action", choices=["plan"], default="plan")
    args = parser.parse_args()

    if args.action == "plan":
        return plan()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
