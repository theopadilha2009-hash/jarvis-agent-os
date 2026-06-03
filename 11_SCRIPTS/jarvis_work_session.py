from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "174_WORK_SESSION"


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


def start(goal: str) -> int:
    started = time.perf_counter()
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir = OUT / f"session_{stamp}"
    session_dir.mkdir(parents=True, exist_ok=True)

    checks = {
        "git_status": run(["git", "status", "-sb"]),
        "fast_status": run(["py", "-3", "11_SCRIPTS/jarvis_fast_status.py", "status"]),
        "home_dashboard": run(["py", "-3", "11_SCRIPTS/jarvis_home_dashboard.py", "home"]),
        "next_action": run(["py", "-3", "11_SCRIPTS/jarvis_next_action_planner.py", "plan"]),
        "command_profiler": run(["py", "-3", "11_SCRIPTS/jarvis_command_profiler.py", "profile"]),
    }

    states = {
        "fast_status": load_json(EXEC / "168_FAST_STATUS" / "FAST_STATUS.json"),
        "home_dashboard": load_json(EXEC / "162_HOME_DASHBOARD" / "HOME_DASHBOARD.json"),
        "next_action": load_json(EXEC / "154_NEXT_ACTION_PLANNER" / "NEXT_ACTION_PLAN.json"),
        "command_profiler": load_json(EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json"),
        "quick_home": load_json(EXEC / "169_QUICK_HOME" / "QUICK_HOME.json"),
    }

    blockers = []
    for name in ["fast_status", "home_dashboard", "next_action", "command_profiler"]:
        if checks[name]["exit_code"] != 0:
            blockers.append(f"{name} failed")

    git_status = checks["git_status"]["output"]
    repo_clean = git_status.strip() == "## main...origin/main"

    actions = states.get("next_action", {}).get("actions", [])
    slowest = states.get("command_profiler", {}).get("slowest", [])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "repo_clean": repo_clean,
        "git_status": git_status,
        "last_commit": states.get("home_dashboard", {}).get("last_commit") or states.get("fast_status", {}).get("last_commit"),
        "script_count": states.get("quick_home", {}).get("script_count") or states.get("fast_status", {}).get("script_count"),
        "script_lines": states.get("quick_home", {}).get("script_lines"),
        "execution_dir_count": states.get("quick_home", {}).get("execution_dir_count") or states.get("fast_status", {}).get("execution_dir_count"),
        "top_actions": actions[:5],
        "slowest": slowest[:5],
        "checks": checks,
        "total_seconds": 0,
    }

    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    state_path = session_dir / "WORK_SESSION.json"
    report_path = session_dir / "WORK_SESSION.md"

    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Work Session — Block 174",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Goal: `{payload['goal']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Repo clean: `{payload['repo_clean']}`",
        f"Last commit: `{payload['last_commit']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Current system",
        "",
        f"- Scripts: `{payload['script_count']}`",
        f"- Script lines: `{payload['script_lines']}`",
        f"- Execution dirs: `{payload['execution_dir_count']}`",
        "",
        "## Top next actions",
        "",
    ]

    if payload["top_actions"]:
        for idx, item in enumerate(payload["top_actions"], start=1):
            lines += [
                f"### {idx}. {item.get('title', '-')}",
                "",
                f"- Reason: {item.get('reason', '-')}",
                f"- Command: `{item.get('command', '-')}`",
                f"- Priority: `{item.get('priority', '-')}`",
                "",
            ]
    else:
        lines.append("- No action data.")

    lines += [
        "",
        "## Slowest commands",
        "",
    ]

    if payload["slowest"]:
        for item in payload["slowest"]:
            lines.append(f"- `{item.get('name')}` seconds=`{item.get('seconds')}`")
    else:
        lines.append("- No profiler data.")

    lines += [
        "",
        "## Check timings",
        "",
    ]

    for name, item in checks.items():
        lines.append(f"- `{name}` exit=`{item['exit_code']}` seconds=`{item['seconds']}`")

    lines += [
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
    report_path.write_text("\n".join(lines), encoding="utf-8")

    latest_md = OUT / "LATEST_WORK_SESSION.md"
    latest_json = OUT / "LATEST_WORK_SESSION.json"
    latest_md.parent.mkdir(parents=True, exist_ok=True)
    latest_md.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_json.write_text(state_path.read_text(encoding="utf-8"), encoding="utf-8")

    print("WORK_SESSION_DONE")
    print(report_path)
    print(json.dumps({
        "verdict": payload["verdict"],
        "goal": payload["goal"],
        "repo_clean": payload["repo_clean"],
        "last_commit": payload["last_commit"],
        "top_action": payload["top_actions"][0] if payload["top_actions"] else None,
        "slowest": payload["slowest"][:3],
        "total_seconds": payload["total_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Work Session")
    parser.add_argument("action", choices=["start"], default="start")
    parser.add_argument("goal", nargs="*")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "continue Jarvis build"

    if args.action == "start":
        return start(goal)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
