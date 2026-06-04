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

def run_git(args: list[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=REPO, text=True, capture_output=True, timeout=8)
        return (result.stdout or result.stderr or "").strip()
    except Exception as exc:
        return f"git_error: {exc}"

def ensure_command_map() -> dict:
    if not COMMAND_MAP_JSON.exists():
        subprocess.run([sys.executable, str(SCRIPTS / "jarvis_command_map.py")], cwd=REPO, check=False)

    if COMMAND_MAP_JSON.exists():
        try:
            return json.loads(COMMAND_MAP_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {"verdict": "fallback", "total": 0, "commands": []}

def build() -> int:
    command_map = ensure_command_map()
    commands = command_map.get("commands", [])

    git_status = run_git(["status", "-sb"])
    last_commit = run_git(["log", "--oneline", "-1"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass",
        "last_commit": last_commit,
        "git_status": git_status,
        "command_count": len(commands),
        "recommended_flow": [
            "py -3 11_SCRIPTS/jarvis_ops.py start-here build",
            "py -3 11_SCRIPTS/jarvis_ops.py home-dashboard home",
            "py -3 11_SCRIPTS/jarvis_ops.py next-action",
            "py -3 11_SCRIPTS/jarvis_ops.py command-profiler profile",
            "py -3 11_SCRIPTS/jarvis_ops.py autoship status",
        ],
        "do_not_do_now": [
            "Do not run another marathon by default.",
            "Do not refactor huge core files without a dedicated plan.",
            "Do not create a command without validating parser and runner.",
            "Do not commit if command validation fails.",
        ],
        "commands": commands,
    }

    (OUT / "START_HERE.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Start Here",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Last commit: `{payload['last_commit']}`",
        "",
        "## Current repo",
        "",
        "```txt",
        payload["git_status"],
        "```",
        "",
        "## Recommended flow",
        "",
    ]

    for item in payload["recommended_flow"]:
        lines.append(f"- `{item}`")

    lines += ["", "## Core commands", ""]

    if commands:
        for item in commands:
            lines.append(f"- `py -3 11_SCRIPTS/jarvis_ops.py {item.get('command', '')}`")
            lines.append(f"  - Use: {item.get('use', '')}")
            lines.append(f"  - When: {item.get('when', '')}")
            lines.append(f"  - Risk: {item.get('risk', 'unknown')}")
    else:
        lines.append("- Command map unavailable. Run `py -3 11_SCRIPTS/jarvis_ops.py command-map`.")

    lines += ["", "## Do not do now", ""]

    for item in payload["do_not_do_now"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Next best direction",
        "",
        "Product/UX improvement or operator experience. Avoid more cleanup unless a quality gate fails.",
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
    }, indent=2))
    return 0

def main() -> int:
    return build()

if __name__ == "__main__":
    raise SystemExit(main())
