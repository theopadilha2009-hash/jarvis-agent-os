from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "197_COMMAND_MAP"
OUT.mkdir(parents=True, exist_ok=True)

COMMANDS = [
    {"command": "start-here build", "use": "main human entry point", "when": "start or resume work", "risk": "safe"},
    {"command": "command-map", "use": "show useful commands", "when": "when you forget what to run", "risk": "safe"},
    {"command": "home-dashboard home", "use": "quick project health", "when": "start/end of session", "risk": "safe"},
    {"command": "quick-home home", "use": "ultra-fast home check", "when": "light check", "risk": "safe"},
    {"command": "fast-status status", "use": "fast repo/project status", "when": "before a patch", "risk": "safe"},
    {"command": "next-action", "use": "suggest next local step", "when": "after finishing a block", "risk": "safe"},
    {"command": "command-profiler profile", "use": "measure slow commands", "when": "after growth or performance changes", "risk": "safe"},
    {"command": "deep-sweep sweep", "use": "compile and quality sweep", "when": "before shipping", "risk": "safe"},
    {"command": "marathon-consolidator", "use": "inventory scripts/domains/warnings", "when": "after marathon or cleanup", "risk": "safe"},
    {"command": "smart-marathon plan", "use": "check remaining pool/readiness", "when": "before feature marathon", "risk": "medium"},
    {"command": "autoship status", "use": "check if guarded commit is allowed", "when": "before commit", "risk": "safe"},
    {"command": "ship-guard preflight", "use": "preflight before sensitive ship", "when": "before commit/push-sensitive work", "risk": "safe"},
]

payload = {
    "created_at": datetime.now().isoformat(timespec="seconds"),
    "verdict": "pass",
    "total": len(COMMANDS),
    "commands": COMMANDS,
    "note": "Local documentation only. No deploy, no production, no secrets.",
}

(OUT / "COMMAND_MAP.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

lines = [
    "# JARVIS Command Map",
    "",
    f"Created at: `{payload['created_at']}`",
    "",
    "## Core commands",
    "",
]

for item in COMMANDS:
    lines.append(f"- `py -3 11_SCRIPTS/jarvis_ops.py {item['command']}`")
    lines.append(f"  - Use: {item['use']}")
    lines.append(f"  - When: {item['when']}")
    lines.append(f"  - Risk: {item['risk']}")

lines += [
    "",
    "## Simple rule",
    "",
    "- Start with `start-here build`.",
    "- Check with `home-dashboard home`.",
    "- Use `autoship status` before commit.",
    "- Do not run marathon by default.",
    "",
    "Status real: command map generated locally.",
]

(OUT / "COMMAND_MAP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("COMMAND_MAP_DONE")
print(OUT / "COMMAND_MAP.md")
print(json.dumps({"verdict": "pass", "total": len(COMMANDS)}, indent=2))
