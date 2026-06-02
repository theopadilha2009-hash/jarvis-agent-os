from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "117_AUTONOMOUS_BACKLOG"
STATE = OUT / "BACKLOG_STATE.json"
REPORT = OUT / "BACKLOG_REPORT.md"

IDEAS = [
    {"id": "B117-001", "title": "Add morning command", "goal": "sync-check + health + work"},
    {"id": "B117-002", "title": "Add nightly command", "goal": "done + progress + status"},
    {"id": "B117-003", "title": "Add autopilot command", "goal": "grow + work + done"},
]


def load_state() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"created_at": datetime.now().isoformat(timespec="seconds"), "done": []}


def save_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def next_idea() -> dict | None:
    state = load_state()
    done = set(state.get("done", []))
    for idea in IDEAS:
        if idea["id"] not in done:
            return idea
    return None


def ops_text() -> str:
    return (REPO / "11_SCRIPTS" / "jarvis_ops.py").read_text(encoding="utf-8", errors="replace")


def write_ops(text: str) -> None:
    (REPO / "11_SCRIPTS" / "jarvis_ops.py").write_text(text, encoding="utf-8")


def insert_before_main(text: str, block: str) -> str:
    marker = "\ndef main() -> int:"
    if marker not in text:
        raise RuntimeError("main insertion point not found")
    return text.replace(marker, "\n" + block + marker, 1)


def insert_parser(text: str, block: str) -> str:
    for marker in [
        '    p_backlog = sub.add_parser("backlog")',
        '    p_grow = sub.add_parser("grow")',
        '    p_patch_run = sub.add_parser("patch-run")',
        '    p_auto_cycle = sub.add_parser("auto-cycle")',
    ]:
        if marker in text:
            return text.replace(marker, block + marker, 1)
    raise RuntimeError("parser insertion point not found")


def insert_route(text: str, block: str) -> str:
    for marker in [
        '    if args.cmd == "backlog":',
        '    if args.cmd == "grow":',
        '    if args.cmd == "patch-run":',
        '    if args.cmd == "auto-cycle":',
    ]:
        if marker in text:
            return text.replace(marker, block + marker, 1)
    raise RuntimeError("route insertion point not found")


def apply_morning(text: str) -> tuple[str, bool]:
    changed = False

    if "def morning(" not in text:
        text = insert_before_main(text, '''
def morning() -> int:
    print("JARVIS MORNING — SYNC CHECK")
    code1 = sync_check() if "sync_check" in globals() else status()

    print("")
    print("JARVIS MORNING — HEALTH")
    code2 = health() if "health" in globals() else status()

    print("")
    print("JARVIS MORNING — WORK")
    code3 = work("melhorar Jarvis") if "work" in globals() else improve("melhorar Jarvis", print_full=False)

    return max(code1, code2, code3)


''')
        changed = True

    if 'sub.add_parser("morning")' not in text:
        text = insert_parser(text, '''
    sub.add_parser("morning")

''')
        changed = True

    if 'if args.cmd == "morning":' not in text:
        text = insert_route(text, '''
    if args.cmd == "morning":
        return morning()

''')
        changed = True

    return text, changed


def apply_nightly(text: str) -> tuple[str, bool]:
    changed = False

    if "def nightly(" not in text:
        text = insert_before_main(text, '''
def nightly() -> int:
    print("JARVIS NIGHTLY — DONE")
    code1 = done() if "done" in globals() else closeout(print_full=False)

    print("")
    print("JARVIS NIGHTLY — PROGRESS")
    code2 = progress(save=True) if "progress" in globals() else 0

    print("")
    print("JARVIS NIGHTLY — STATUS")
    code3 = status()

    return max(code1, code2, code3)


''')
        changed = True

    if 'sub.add_parser("nightly")' not in text:
        text = insert_parser(text, '''
    sub.add_parser("nightly")

''')
        changed = True

    if 'if args.cmd == "nightly":' not in text:
        text = insert_route(text, '''
    if args.cmd == "nightly":
        return nightly()

''')
        changed = True

    return text, changed


def apply_autopilot(text: str) -> tuple[str, bool]:
    changed = False

    if "def autopilot(" not in text:
        text = insert_before_main(text, '''
def autopilot(goal: str, limit: int = 2) -> int:
    print("JARVIS AUTOPILOT — GROW")
    code1 = grow(limit=limit) if "grow" in globals() else 0

    print("")
    print("JARVIS AUTOPILOT — WORK")
    code2 = work(goal) if "work" in globals() else improve(goal, print_full=False)

    print("")
    print("JARVIS AUTOPILOT — DONE")
    code3 = done() if "done" in globals() else closeout(print_full=False)

    return max(code1, code2, code3)


''')
        changed = True

    if 'p_autopilot = sub.add_parser("autopilot")' not in text:
        text = insert_parser(text, '''
    p_autopilot = sub.add_parser("autopilot")
    p_autopilot.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_autopilot.add_argument("--limit", type=int, default=2)

''')
        changed = True

    if 'if args.cmd == "autopilot":' not in text:
        text = insert_route(text, '''
    if args.cmd == "autopilot":
        return autopilot(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            limit=args.limit,
        )

''')
        changed = True

    return text, changed


def apply_next() -> int:
    idea = next_idea()
    if not idea:
        print("NO_BACKLOG_IDEAS_LEFT")
        return 0

    text = ops_text()

    if idea["id"] == "B117-001":
        text, changed = apply_morning(text)
    elif idea["id"] == "B117-002":
        text, changed = apply_nightly(text)
    elif idea["id"] == "B117-003":
        text, changed = apply_autopilot(text)
    else:
        changed = False

    write_ops(text)

    state = load_state()
    if idea["id"] not in state["done"]:
        state["done"].append(idea["id"])
    state["last_applied"] = idea
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)

    REPORT.write_text(
        "# JARVIS Autonomous Backlog — Block 117\n\n"
        + f"Applied: `{idea['id']}`\n"
        + f"Title: **{idea['title']}**\n"
        + f"Changed: `{changed}`\n",
        encoding="utf-8",
    )

    print("BACKLOG_APPLIED")
    print(json.dumps(idea, ensure_ascii=False, indent=2))
    return 0


def list_items() -> int:
    state = load_state()
    print(json.dumps({"ideas": IDEAS, "done": state.get("done", []), "next": next_idea()}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 117 Autonomous Backlog")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")
    sub.add_parser("apply-next")

    args = parser.parse_args()

    if args.cmd == "list":
        return list_items()
    if args.cmd == "apply-next":
        return apply_next()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
