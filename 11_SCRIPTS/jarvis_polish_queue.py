from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "05_EXECUCAO" / "101_JARVIS_POLISH_QUEUE"
QUEUE_PATH = BASE / "polish_queue.json"
REPORT_PATH = BASE / "POLISH_QUEUE_REPORT.md"

DEFAULT_ITEMS = [
    {
        "title": "Polish launcher Python detection",
        "priority": "high",
        "why": "Launcher currently assumes python exists; should detect python, py -3, or give clear install guidance.",
        "target_files": ["11_SCRIPTS/start_jarvis_windows.ps1"],
    },
    {
        "title": "Improve local execution cleanliness",
        "priority": "high",
        "why": "Keep generated folders out of git status and reduce noise during fast school/computer switching.",
        "target_files": [".git/info/exclude", "05_EXECUCAO/"],
    },
    {
        "title": "Add project resume command",
        "priority": "medium",
        "why": "One command should show last commits, doctor status, latest reports, and next safe action.",
        "target_files": ["11_SCRIPTS/jarvis_cli.py"],
    },
    {
        "title": "Add feature closeout checklist",
        "priority": "medium",
        "why": "Every feature should finish with compile, doctor, diff-review, git status, commit suggestion.",
        "target_files": ["11_SCRIPTS/"],
    },
    {
        "title": "Polish terminal-first workflow",
        "priority": "medium",
        "why": "User prefers creating/polishing features without repeatedly opening the cockpit.",
        "target_files": ["11_SCRIPTS/"],
    },
]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_queue() -> dict:
    if not QUEUE_PATH.exists():
        return {"ok": True, "created_at": now(), "updated_at": now(), "items": []}
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def save_queue(data: dict) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = now()
    QUEUE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(render_report(data), encoding="utf-8")


def next_id(data: dict) -> str:
    nums = []
    for item in data.get("items", []):
        raw = str(item.get("id", "P101-000")).split("-")[-1]
        if raw.isdigit():
            nums.append(int(raw))
    return f"P101-{(max(nums) + 1 if nums else 1):03d}"


def seed() -> dict:
    data = load_queue()
    existing_titles = {item.get("title") for item in data["items"]}

    for item in DEFAULT_ITEMS:
        if item["title"] in existing_titles:
            continue
        data["items"].append({
            "id": next_id(data),
            "title": item["title"],
            "priority": item["priority"],
            "status": "todo",
            "why": item["why"],
            "target_files": item["target_files"],
            "created_at": now(),
            "updated_at": now(),
            "notes": [],
        })

    save_queue(data)
    return data


def add_item(title: str, priority: str, why: str, files: list[str]) -> dict:
    data = load_queue()
    data["items"].append({
        "id": next_id(data),
        "title": title.strip(),
        "priority": priority,
        "status": "todo",
        "why": why.strip() or "Polish/improvement item.",
        "target_files": files,
        "created_at": now(),
        "updated_at": now(),
        "notes": [],
    })
    save_queue(data)
    return data


def set_status(item_id: str, status: str, note: str = "") -> dict:
    data = load_queue()
    found = False
    for item in data["items"]:
        if item["id"].lower() == item_id.lower():
            item["status"] = status
            item["updated_at"] = now()
            if note:
                item.setdefault("notes", []).append({"at": now(), "note": note})
            found = True
            break

    if not found:
        raise SystemExit(f"Item not found: {item_id}")

    save_queue(data)
    return data


def sorted_items(data: dict) -> list[dict]:
    priority_order = {"high": 0, "medium": 1, "low": 2}
    status_order = {"doing": 0, "todo": 1, "done": 2, "skipped": 3}
    return sorted(
        data.get("items", []),
        key=lambda x: (
            status_order.get(x.get("status", "todo"), 9),
            priority_order.get(x.get("priority", "medium"), 9),
            x.get("id", ""),
        ),
    )


def get_next(data: dict) -> dict | None:
    candidates = [i for i in sorted_items(data) if i.get("status") in {"doing", "todo"}]
    return candidates[0] if candidates else None


def render_item(item: dict) -> str:
    files = ", ".join(item.get("target_files", [])) or "-"
    lines = [
        f"{item['id']} | {item['priority']} | {item['status']} | {item['title']}",
        f"why: {item.get('why', '-')}",
        f"files: {files}",
    ]
    return "\n".join(lines)


def render_report(data: dict) -> str:
    items = sorted_items(data)
    counts = {}
    for item in items:
        counts[item.get("status", "unknown")] = counts.get(item.get("status", "unknown"), 0) + 1

    lines = [
        "# JARVIS Polish Queue ? Block 101",
        "",
        f"Updated at: `{data.get('updated_at')}`",
        "",
        "## Counts",
        "",
    ]

    for status in ["doing", "todo", "done", "skipped"]:
        lines.append(f"- {status}: {counts.get(status, 0)}")

    lines += ["", "## Items", ""]

    for item in items:
        lines += [
            f"### {item['id']} ? {item['title']}",
            "",
            f"- Priority: `{item.get('priority')}`",
            f"- Status: `{item.get('status')}`",
            f"- Why: {item.get('why', '-')}",
            f"- Files: {', '.join(item.get('target_files', [])) or '-'}",
            "",
        ]

    lines += [
        "## Safe Commands",
        "",
        "```powershell",
        "python 11_SCRIPTS/jarvis_polish_queue.py list",
        "python 11_SCRIPTS/jarvis_polish_queue.py next",
        "python 11_SCRIPTS/jarvis_polish_queue.py doing P101-001",
        "python 11_SCRIPTS/jarvis_polish_queue.py done P101-001 --note \"implemented and validated\"",
        "python 11_SCRIPTS/jarvis_polish_queue.py report",
        "```",
        "",
    ]

    return "\n".join(lines)


def print_list(data: dict) -> None:
    for item in sorted_items(data):
        print(render_item(item))
        print("-" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 101 Polish Queue")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed")
    sub.add_parser("list")
    sub.add_parser("next")
    sub.add_parser("report")

    p_add = sub.add_parser("add")
    p_add.add_argument("title", nargs="+")
    p_add.add_argument("--priority", choices=["high", "medium", "low"], default="medium")
    p_add.add_argument("--why", default="")
    p_add.add_argument("--file", action="append", default=[])

    for name in ["doing", "done", "skip", "todo"]:
        p = sub.add_parser(name)
        p.add_argument("item_id")
        p.add_argument("--note", default="")

    args = parser.parse_args()

    if args.cmd == "seed":
        data = seed()
        print(f"QUEUE_SEEDED: {QUEUE_PATH}")
        print_list(data)
        return 0

    data = load_queue()

    if args.cmd == "add":
        data = add_item(" ".join(args.title), args.priority, args.why, args.file)
        print("ITEM_ADDED")
        print_list(data)
        return 0

    if args.cmd == "list":
        print_list(data)
        return 0

    if args.cmd == "next":
        item = get_next(data)
        if not item:
            print("NO_OPEN_ITEMS")
        else:
            print(render_item(item))
        return 0

    if args.cmd == "report":
        save_queue(data)
        print(f"REPORT_SAVED: {REPORT_PATH}")
        print(REPORT_PATH.read_text(encoding="utf-8"))
        return 0

    status_map = {"doing": "doing", "done": "done", "skip": "skipped", "todo": "todo"}
    data = set_status(args.item_id, status_map[args.cmd], args.note)
    print(f"ITEM_UPDATED: {args.item_id} -> {status_map[args.cmd]}")
    print_list(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
