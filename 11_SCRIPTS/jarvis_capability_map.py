from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "158_CAPABILITY_MAP"
REPORT = OUT / "CAPABILITY_MAP.md"
STATE = OUT / "CAPABILITY_MAP.json"


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def collect() -> dict:
    ops_text = read(REPO / "11_SCRIPTS" / "jarvis_ops.py")
    cli_text = read(REPO / "11_SCRIPTS" / "jarvis_main_cli.py")

    commands = sorted(set(re.findall(r'add_parser\("([^"]+)"', ops_text)))
    functions = sorted(set(re.findall(r"^def ([a-zA-Z_][a-zA-Z0-9_]*)\(", ops_text, flags=re.M)))
    script_refs = sorted(set(re.findall(r'"(11_SCRIPTS/[^"]+\.py)"', cli_text)))

    categories = {
        "core": [],
        "brain": [],
        "safety": [],
        "planning": [],
        "cycle": [],
        "other": [],
    }

    for cmd in commands:
        if cmd in ["doctor", "start", "build", "fix", "ship"]:
            categories["core"].append(cmd)
        elif "brain" in cmd:
            categories["brain"].append(cmd)
        elif cmd in ["autoship", "ship-guard", "diff-gate", "safe-apply", "safe-apply-v2"]:
            categories["safety"].append(cmd)
        elif cmd in ["patch-catalog", "patch-cycle", "next-action", "operator-brief", "daily-checkpoint", "repo-snapshot", "execution-index", "command-menu"]:
            categories["planning"].append(cmd)
        elif "cycle" in cmd or "health" in cmd or "maintenance" in cmd:
            categories["cycle"].append(cmd)
        else:
            categories["other"].append(cmd)

    missing_scripts = []
    for ref in script_refs:
        if not (REPO / ref).exists():
            missing_scripts.append(ref)

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "command_count": len(commands),
        "function_count": len(functions),
        "script_ref_count": len(script_refs),
        "missing_script_refs": missing_scripts,
        "categories": categories,
        "commands": commands,
        "functions": functions,
        "script_refs": script_refs,
    }


def write(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Capability Map — Block 158",
        "",
        f"Created at: `{data['created_at']}`",
        f"Commands: `{data['command_count']}`",
        f"Functions: `{data['function_count']}`",
        f"Script refs: `{data['script_ref_count']}`",
        f"Missing script refs: `{len(data['missing_script_refs'])}`",
        "",
        "## Categories",
        "",
    ]

    for category, commands in data["categories"].items():
        lines.append(f"### {category}")
        lines.append("")
        if commands:
            for cmd in commands:
                lines.append(f"- `{cmd}`")
        else:
            lines.append("- none")
        lines.append("")

    lines += [
        "## Missing script refs",
        "",
    ]

    if data["missing_script_refs"]:
        for ref in data["missing_script_refs"]:
            lines.append(f"- `{ref}`")
    else:
        lines.append("- none")

    lines += [
        "",
        "## All commands",
        "",
    ]

    for cmd in data["commands"]:
        lines.append(f"- `{cmd}`")

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def run_map() -> int:
    data = collect()
    write(data)

    print("CAPABILITY_MAP_DONE")
    print(REPORT)
    print(json.dumps({
        "command_count": data["command_count"],
        "script_ref_count": data["script_ref_count"],
        "missing_script_refs": data["missing_script_refs"],
        "categories": {k: len(v) for k, v in data["categories"].items()},
    }, ensure_ascii=False, indent=2))

    return 0 if not data["missing_script_refs"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 158 Capability Map")
    parser.add_argument("action", choices=["map"], default="map")
    args = parser.parse_args()

    if args.action == "map":
        return run_map()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
