from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "121_TASK_ENGINE"
STATE = OUT / "TASK_STATE.json"
REPORT = OUT / "TASK_REPORT.md"

DEFAULT_TASKS = [
    {
        "id": "T121-001",
        "title": "Run stable autonomous mission",
        "goal": "melhorar autonomia do Jarvis sem mexer em produção",
        "command": ["mission", "melhorar autonomia do Jarvis", "--steps", "1"],
        "risk": "low",
    },
    {
        "id": "T121-002",
        "title": "Run operator review",
        "goal": "validar status local e gerar relatório",
        "command": ["review"],
        "risk": "low",
    },
    {
        "id": "T121-003",
        "title": "Run power loop without autoship",
        "goal": "executar ciclo de força sem commit automático",
        "command": ["power", "melhorar autonomia do Jarvis", "--steps", "1"],
        "risk": "low",
    },
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py_ops(args: list[str]) -> tuple[int, str]:
    return run([sys.executable, "11_SCRIPTS/jarvis_ops.py", *args])


def load_state() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "done": [],
        "tasks": DEFAULT_TASKS,
    }


def save_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def next_task() -> dict | None:
    state = load_state()
    done = set(state.get("done", []))
    for task in state.get("tasks", DEFAULT_TASKS):
        if task["id"] not in done:
            return task
    return None


def list_tasks() -> int:
    state = load_state()
    payload = {
        "tasks": state.get("tasks", DEFAULT_TASKS),
        "done": state.get("done", []),
        "next": next_task(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def add_task(title: str, goal: str, command: list[str], risk: str = "low") -> int:
    state = load_state()
    tasks = state.setdefault("tasks", DEFAULT_TASKS.copy())

    task_id = f"T121-{len(tasks) + 1:03d}"
    task = {
        "id": task_id,
        "title": title,
        "goal": goal,
        "command": command,
        "risk": risk,
    }

    tasks.append(task)
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)

    print(json.dumps(task, ensure_ascii=False, indent=2))
    return 0


def run_next() -> int:
    task = next_task()
    if not task:
        print("NO_TASKS_LEFT")
        return 0

    code, out = py_ops(task["command"])

    state = load_state()
    done = state.setdefault("done", [])
    if task["id"] not in done:
        done.append(task["id"])
    state["last_run"] = {
        "task": task,
        "code": code,
        "time": datetime.now().isoformat(timespec="seconds"),
    }
    save_state(state)

    _, status = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-10"])

    report = [
        "# JARVIS Task Engine — Block 121",
        "",
        f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"Task: **{task['id']} — {task['title']}**",
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
        out[-5000:] if out else "-",
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
    ]

    REPORT.write_text("\n".join(report), encoding="utf-8")

    print("TASK_ENGINE_DONE")
    print(REPORT)
    print(status)

    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 121 Task Engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")
    sub.add_parser("next")

    p_add = sub.add_parser("add")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--goal", required=True)
    p_add.add_argument("--risk", default="low")
    p_add.add_argument("command", nargs="+")

    args = parser.parse_args()

    if args.cmd == "list":
        return list_tasks()

    if args.cmd == "next":
        return run_next()

    if args.cmd == "add":
        return add_task(args.title, args.goal, args.command, risk=args.risk)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
