from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "197_COMMAND_MAP"
OUT.mkdir(parents=True, exist_ok=True)

COMMANDS = [
    {
        "group": "Start",
        "command": "start-here build",
        "use": "main human entry point",
        "when": "start/resume work",
        "risk": "safe",
        "priority": 100,
    },
    {
        "group": "Start",
        "command": "home-dashboard home",
        "use": "current project health",
        "when": "start/end of session",
        "risk": "safe",
        "priority": 95,
    },
    {
        "group": "Start",
        "command": "command-map",
        "use": "show useful commands",
        "when": "when you forget what to run",
        "risk": "safe",
        "priority": 90,
    },
    {
        "group": "Decision",
        "command": "next-action",
        "use": "suggest next local step",
        "when": "after finishing a block",
        "risk": "safe",
        "priority": 85,
    },
    {
        "group": "Decision",
        "command": "fast-status status",
        "use": "fast repo/project status",
        "when": "before a patch",
        "risk": "safe",
        "priority": 80,
    },
    {
        "group": "Health",
        "command": "quick-home home",
        "use": "ultra-fast home check",
        "when": "light check",
        "risk": "safe",
        "priority": 75,
    },
    {
        "group": "Health",
        "command": "command-profiler profile",
        "use": "measure slow commands",
        "when": "after growth/performance changes",
        "risk": "safe",
        "priority": 70,
    },
    {
        "group": "Health",
        "command": "deep-sweep sweep",
        "use": "compile and quality sweep",
        "when": "before shipping",
        "risk": "safe",
        "priority": 68,
    },
    {
        "group": "Inventory",
        "command": "marathon-consolidator",
        "use": "inventory scripts/domains/warnings",
        "when": "after marathon or cleanup",
        "risk": "safe",
        "priority": 65,
    },
    {
        "group": "Generation",
        "command": "smart-marathon plan",
        "use": "check remaining pool/readiness",
        "when": "before feature marathon only",
        "risk": "medium",
        "priority": 45,
    },
    {
        "group": "Ship",
        "command": "autoship status",
        "use": "check if guarded commit is allowed",
        "when": "before commit",
        "risk": "safe",
        "priority": 60,
    },
    {
        "group": "Ship",
        "command": "ship-guard preflight",
        "use": "preflight before sensitive ship",
        "when": "before commit/push-sensitive work",
        "risk": "safe",
        "priority": 55,
    },
]

GROUP_ORDER = ["Start", "Decision", "Health", "Inventory", "Generation", "Ship"]

def grouped_commands() -> dict:
    groups = {name: [] for name in GROUP_ORDER}
    for item in sorted(COMMANDS, key=lambda x: x["priority"], reverse=True):
        groups.setdefault(item["group"], []).append(item)
    return groups

def main() -> int:
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass",
        "total": len(COMMANDS),
        "groups": grouped_commands(),
        "commands": COMMANDS,
        "operator_rule": [
            "Start with start-here build.",
            "Check with home-dashboard home.",
            "Use next-action before inventing new work.",
            "Use autoship status before commit.",
            "Do not run marathon by default.",
        ],
        "note": "Local documentation only. No deploy, no production, no secrets.",
    }

    (OUT / "COMMAND_MAP.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Command Map",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Total commands: `{payload['total']}`",
        "",
        "## Operator rule",
        "",
    ]

    for rule in payload["operator_rule"]:
        lines.append(f"- {rule}")

    lines += ["", "## Commands by group", ""]

    for group in GROUP_ORDER:
        items = payload["groups"].get(group, [])
        if not items:
            continue
        lines.append(f"### {group}")
        lines.append("")
        for item in items:
            lines.append(f"- `py -3 11_SCRIPTS/jarvis_ops.py {item['command']}`")
            lines.append(f"  - Use: {item['use']}")
            lines.append(f"  - When: {item['when']}")
            lines.append(f"  - Risk: {item['risk']}")
        lines.append("")

    lines += [
        "## Safe operating loop",
        "",
        "```bash",
        "py -3 11_SCRIPTS/jarvis_ops.py start-here build",
        "py -3 11_SCRIPTS/jarvis_ops.py home-dashboard home",
        "py -3 11_SCRIPTS/jarvis_ops.py next-action",
        "py -3 11_SCRIPTS/jarvis_ops.py command-profiler profile",
        "py -3 11_SCRIPTS/jarvis_ops.py autoship status",
        "```",
        "",
        "Status real: command map generated locally.",
    ]

    (OUT / "COMMAND_MAP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("COMMAND_MAP_DONE")
    print(OUT / "COMMAND_MAP.md")
    print(json.dumps({"verdict": "pass", "total": len(COMMANDS), "groups": len(GROUP_ORDER)}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
