from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "157_COMMAND_MENU"
REPORT = OUT / "COMMAND_MENU.md"
STATE = OUT / "COMMAND_MENU.json"

COMMANDS = [
    {"group": "status", "name": "autoship status", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py autoship status"},
    {"group": "status", "name": "ship guard", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py ship-guard preflight"},
    {"group": "status", "name": "repo snapshot", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py repo-snapshot snapshot"},
    {"group": "status", "name": "execution index", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py execution-index index"},
    {"group": "planning", "name": "operator brief", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py operator-brief brief"},
    {"group": "planning", "name": "daily checkpoint", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py daily-checkpoint checkpoint"},
    {"group": "planning", "name": "next action", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py next-action plan"},
    {"group": "planning", "name": "patch catalog next", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py patch-catalog next"},
    {"group": "health", "name": "command health", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py command-health run"},
    {"group": "health", "name": "maintenance cycle", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py maintenance-cycle run"},
    {"group": "health", "name": "auto cycle runner", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py auto-cycle-runner run"},
    {"group": "ship", "name": "autoship commit", "cmd": "py -3 11_SCRIPTS\\jarvis_ops.py autoship commit \"chore: ship guarded Jarvis changes\" --push"},
]


def build_payload() -> dict:
    groups: dict[str, list[dict]] = {}
    for item in COMMANDS:
        groups.setdefault(item["group"], []).append(item)

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "count": len(COMMANDS),
        "groups": groups,
        "commands": COMMANDS,
    }


def write(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Command Menu — Block 157",
        "",
        f"Created at: `{data['created_at']}`",
        f"Commands: `{data['count']}`",
        "",
    ]

    for group, items in data["groups"].items():
        lines += [
            f"## {group}",
            "",
        ]
        for item in items:
            lines += [
                f"### {item['name']}",
                "",
                "```powershell",
                item["cmd"],
                "```",
                "",
            ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def menu() -> int:
    data = build_payload()
    write(data)

    print("COMMAND_MENU_DONE")
    print(REPORT)
    print(json.dumps({
        "count": data["count"],
        "groups": list(data["groups"].keys()),
        "first_command": data["commands"][0]["cmd"] if data["commands"] else None,
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 157 Command Menu")
    parser.add_argument("action", choices=["menu"], default="menu")
    args = parser.parse_args()

    if args.action == "menu":
        return menu()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
