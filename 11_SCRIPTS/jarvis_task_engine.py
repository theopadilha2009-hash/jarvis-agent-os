from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "121_TASK_ENGINE"
STATE = OUT / "TASK_STATE.json"
REPORT = OUT / "TASK_REPORT.md"

DEFAULT_TASKS = [
    {"id": "T121-001", "title": "Run stable autonomous mission", "goal": "melhorar autonomia do Jarvis sem mexer em produ??o", "command": ["mission", "melhorar autonomia do Jarvis", "--steps", "1"], "risk": "low"},
    {"id": "T121-002", "title": "Run operator review", "goal": "validar status local e gerar relat?rio", "command": ["review"], "risk": "low"},
    {"id": "T121-003", "title": "Run power loop without autoship", "goal": "executar ciclo de for?a sem commit autom?tico", "command": ["power", "melhorar autonomia do Jarvis", "--steps", "1"], "risk": "low"},
]


def run(cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False, env=merged_env)
    return result.returncode, (result.stdout + result.stderr).strip()


def py_ops(args: list[str], task_id: str = "") -> tuple[int, str]:
    return run([sys.executable, "11_SCRIPTS/jarvis_ops.py", *args], env={
        "JARVIS_TASK_ENGINE_RUNNING": "1",
        "JARVIS_ACTIVE_TASK_ID": task_id,
    })


def load_state() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
    else:
        state = {"created_at": datetime.now().isoformat(timespec="seconds"), "done": [], "running": [], "failed": [], "tasks": DEFAULT_TASKS}
    state.setdefault("done", [])
    state.setdefault("running", [])
    state.setdefault("failed", [])
    state.setdefault("tasks", DEFAULT_TASKS)
    return state


def save_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def git_clean() -> bool:
    _, out = run(["git", "status", "--porcelain"])
    return not bool(out.strip())


def next_task() -> dict | None:
    state = load_state()
    done = set(state.get("done", []))
    running = set(state.get("running", []))
    for task in state.get("tasks", DEFAULT_TASKS):
        if task["id"] not in done and task["id"] not in running:
            return task
    return None


def list_tasks() -> int:
    state = load_state()
    print(json.dumps({
        "tasks": state.get("tasks", DEFAULT_TASKS),
        "done": state.get("done", []),
        "running": state.get("running", []),
        "failed": state.get("failed", []),
        "next": next_task(),
    }, ensure_ascii=False, indent=2))
    return 0


def write_report(task: dict, code: int, out: str) -> None:
    _, status = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-10"])
    REPORT.write_text(
        "\n".join([
            "# JARVIS Task Engine ? Block 124 Hardened",
            "",
            f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
            f"Task: **{task['id']} ? {task['title']}**",
            f"Risk: `{task['risk']}`",
            f"Exit code: `{code}`",
            "",
            "## Command",
            "",
            "```bash",
            "python3 11_SCRIPTS/jarvis_ops.py " + " ".join(task["command"]),
            "```",
            "",
            "## Output",
            "",
            "```text",
            out[-6000:] if out else "-",
            "```",
            "",
            "## Git Status",
            "",
            "```text",
            status or "-",
            "```",
            "",
            "## Diff",
            "",
            "```text",
            diff or "clean",
            "```",
            "",
            "## Last Commits",
            "",
            "```text",
            commits or "-",
            "```",
            "",
        ]),
        encoding="utf-8",
    )


def run_next() -> int:
    task = next_task()
    if not task:
        print("NO_TASKS_LEFT")
        return 0

    state = load_state()
    running = state.setdefault("running", [])
    if task["id"] not in running:
        running.append(task["id"])
    save_state(state)

    code, out = py_ops(task["command"], task_id=task["id"])

    state = load_state()
    if task["id"] in state.setdefault("running", []):
        state["running"].remove(task["id"])

    if code == 0:
        if task["id"] not in state.setdefault("done", []):
            state["done"].append(task["id"])
    else:
        if task["id"] not in state.setdefault("failed", []):
            state["failed"].append(task["id"])

    state["last_run"] = {"task": task, "code": code, "time": datetime.now().isoformat(timespec="seconds")}
    save_state(state)

    write_report(task, code, out)

    _, status = run(["git", "status", "-sb"])
    print("TASK_ENGINE_DONE")
    print(REPORT)
    print(status)
    return code


def run_many(limit: int = 3) -> int:
    max_code = 0
    for _ in range(max(1, limit)):
        if not git_clean():
            print("TASK_RUN_STOPPED_GIT_DIRTY")
            return max(max_code, 1)
        if not next_task():
            print("NO_TASKS_LEFT")
            return max_code
        code = run_next()
        max_code = max(max_code, code)
        if code != 0:
            return max_code
    return max_code


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 124 Hardened Task Engine")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("next")
    p_run = sub.add_parser("run")
    p_run.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    if args.cmd == "list":
        return list_tasks()
    if args.cmd == "next":
        return run_next()
    if args.cmd == "run":
        return run_many(limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
