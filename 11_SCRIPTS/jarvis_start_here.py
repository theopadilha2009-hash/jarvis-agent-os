from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
OUT = REPO / "05_EXECUCAO" / "161_START_HERE"
OUT.mkdir(parents=True, exist_ok=True)

COMMAND_MAP_JSON = REPO / "05_EXECUCAO" / "197_COMMAND_MAP" / "COMMAND_MAP.json"

def run_cmd(args: list[str], timeout: int = 10) -> dict:
    try:
        result = subprocess.run(args, cwd=REPO, text=True, capture_output=True, timeout=timeout)
        return {
            "exit_code": result.returncode,
            "output": (result.stdout or result.stderr or "").strip(),
        }
    except Exception as exc:
        return {"exit_code": 1, "output": f"error: {exc}"}

def git(args: list[str]) -> str:
    return run_cmd(["git", *args], timeout=8)["output"]

def ensure_command_map() -> dict:
    subprocess.run([sys.executable, str(SCRIPTS / "jarvis_command_map.py")], cwd=REPO, check=False)

    if COMMAND_MAP_JSON.exists():
        try:
            return json.loads(COMMAND_MAP_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {"verdict": "fallback", "total": 0, "commands": [], "groups": {}}

def extract_top_commands(command_map: dict) -> list[dict]:
    commands = command_map.get("commands", [])
    return sorted(commands, key=lambda x: x.get("priority", 0), reverse=True)[:8]

def build_status_cards(git_status: str, command_count: int) -> list[dict]:
    clean = git_status.strip() == "## main...origin/main"
    return [
        {
            "label": "Repo",
            "value": "clean" if clean else "dirty",
            "detail": git_status or "-",
        },
        {
            "label": "Commands",
            "value": str(command_count),
            "detail": "from command-map",
        },
        {
            "label": "Mode",
            "value": "local-first",
            "detail": "no production touched",
        },
        {
            "label": "Next",
            "value": "product/UX",
            "detail": "avoid marathon/cleanup unless gate fails",
        },
    ]

def main() -> int:
    command_map = ensure_command_map()
    commands = command_map.get("commands", [])
    groups = command_map.get("groups", {})
    top_commands = extract_top_commands(command_map)

    git_status = git(["status", "-sb"])
    last_commit = git(["log", "--oneline", "-1"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass",
        "last_commit": last_commit,
        "git_status": git_status,
        "command_count": len(commands),
        "group_count": len(groups),
        "status_cards": build_status_cards(git_status, len(commands)),
        "recommended_flow": [
            "py -3 11_SCRIPTS/jarvis_ops.py start-here build",
            "py -3 11_SCRIPTS/jarvis_ops.py home-dashboard home",
            "py -3 11_SCRIPTS/jarvis_ops.py next-action",
            "py -3 11_SCRIPTS/jarvis_ops.py command-profiler profile",
            "py -3 11_SCRIPTS/jarvis_ops.py autoship status",
        ],
        "operator_decision": {
            "recommended_next_direction": "product/UX or operator experience",
            "avoid_now": [
                "more marathon",
                "large core refactor",
                "new command without validation",
                "cleanup-only work unless quality gate fails",
            ],
        },
        "top_commands": top_commands,
        "groups": groups,
    }

    (OUT / "START_HERE.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Start Here",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Last commit: `{payload['last_commit']}`",
        "",
        "## Status cards",
        "",
    ]

    for card in payload["status_cards"]:
        lines.append(f"- **{card['label']}**: `{card['value']}` — {card['detail']}")

    lines += [
        "",
        "## Recommended flow",
        "",
    ]

    for command in payload["recommended_flow"]:
        lines.append(f"- `{command}`")

    lines += [
        "",
        "## Top commands",
        "",
    ]

    for item in payload["top_commands"]:
        lines.append(f"- `py -3 11_SCRIPTS/jarvis_ops.py {item.get('command', '')}`")
        lines.append(f"  - {item.get('use', '')}")
        lines.append(f"  - When: {item.get('when', '')}")
        lines.append(f"  - Risk: {item.get('risk', 'unknown')}")

    lines += [
        "",
        "## Commands by group",
        "",
    ]

    for group, items in payload["groups"].items():
        lines.append(f"### {group}")
        for item in items:
            lines.append(f"- `{item.get('command', '')}` — {item.get('use', '')}")
        lines.append("")

    lines += [
        "## Operator decision",
        "",
        f"- Recommended next direction: `{payload['operator_decision']['recommended_next_direction']}`",
        "",
        "### Avoid now",
        "",
    ]

    for item in payload["operator_decision"]["avoid_now"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Copy-paste quick start",
        "",
        "```bash",
        "clear",
        'REPO="$HOME/Theo/JARVIS/jarvis-agent-os"',
        'cd "$REPO"',
        'export PATH="$HOME/.local/bin:$PATH"',
        "py -3 11_SCRIPTS/jarvis_ops.py start-here build",
        "py -3 11_SCRIPTS/jarvis_ops.py home-dashboard home",
        "```",
        "",
        "Status real: Start Here generated locally. No production touched.",
    ]

    (OUT / "START_HERE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("START_HERE_DONE")
    print(OUT / "START_HERE.md")
    print(json.dumps({
        "verdict": "pass",
        "last_commit": last_commit,
        "git_status": git_status,
        "command_count": len(commands),
        "group_count": len(groups),
        "recommended_next_direction": payload["operator_decision"]["recommended_next_direction"],
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
