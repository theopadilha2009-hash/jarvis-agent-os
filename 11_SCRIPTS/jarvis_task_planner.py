from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "123_TASK_PLANNER"
REPORT = OUT / "TASK_PLANNER_REPORT.md"
TASK_STATE = REPO / "05_EXECUCAO" / "121_TASK_ENGINE" / "TASK_STATE.json"

PLANNED_TASKS = [
    {
        "title": "Decision engine autonomous pass",
        "goal": "deixar o Jarvis escolher a próxima ação segura sozinho",
        "command": ["decide", "melhorar autonomia do Jarvis"],
        "risk": "low",
    },
    {
        "title": "Launch operator cycle",
        "goal": "executar ciclo completo de operador com snapshot, grow e autopilot",
        "command": ["launch", "melhorar autonomia do Jarvis", "--limit", "1"],
        "risk": "medium",
    },
    {
        "title": "Power loop controlled pass",
        "goal": "rodar missão + review + snapshot sem autoship",
        "command": ["power", "melhorar autonomia do Jarvis", "--steps", "1"],
        "risk": "low",
    },
    {
        "title": "Nightly close validation",
        "goal": "validar fechamento, progresso e status final",
        "command": ["nightly"],
        "risk": "low",
    },
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def load_state() -> dict:
    TASK_STATE.parent.mkdir(parents=True, exist_ok=True)
    if TASK_STATE.exists():
        return json.loads(TASK_STATE.read_text(encoding="utf-8"))
    return {"created_at": datetime.now().isoformat(timespec="seconds"), "done": [], "tasks": []}


def save_state(state: dict) -> None:
    TASK_STATE.parent.mkdir(parents=True, exist_ok=True)
    TASK_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def task_key(task: dict) -> str:
    return f"{task.get('title')}::{task.get('command')}"


def seed() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    state = load_state()
    tasks = state.setdefault("tasks", [])
    existing = {task_key(t) for t in tasks}

    added = []
    for task in PLANNED_TASKS:
        if task_key(task) in existing:
            continue

        task_id = f"T123-{len(tasks) + 1:03d}"
        new_task = {"id": task_id, **task}
        tasks.append(new_task)
        added.append(new_task)

    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state["planner_last_added"] = added
    save_state(state)

    _, status = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "added_count": len(added),
        "added": added,
        "total_tasks": len(tasks),
        "done": state.get("done", []),
        "status": status,
        "diff": diff or "clean",
    }

    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("TASK_PLANNER_DONE")
    print(REPORT)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 123 Task Planner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")

    args = parser.parse_args()

    if args.cmd == "seed":
        return seed()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
