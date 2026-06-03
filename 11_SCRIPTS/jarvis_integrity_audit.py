from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "163_INTEGRITY_AUDIT"
REPORT = OUT / "INTEGRITY_AUDIT.md"
STATE = OUT / "INTEGRITY_AUDIT.json"

CORE_SCRIPTS = [
    "11_SCRIPTS/jarvis_ops.py",
    "11_SCRIPTS/jarvis_main_cli.py",
    "11_SCRIPTS/jarvis_local_cleaner.py",
    "11_SCRIPTS/jarvis_autoship.py",
    "11_SCRIPTS/jarvis_ship_guard.py",
    "11_SCRIPTS/jarvis_diff_review_gate.py",
    "11_SCRIPTS/jarvis_home_dashboard.py",
    "11_SCRIPTS/jarvis_start_here.py",
    "11_SCRIPTS/jarvis_status_board.py",
    "11_SCRIPTS/jarvis_control_center.py",
    "11_SCRIPTS/jarvis_capability_map.py",
    "11_SCRIPTS/jarvis_command_menu.py",
    "11_SCRIPTS/jarvis_auto_cycle_runner.py",
    "11_SCRIPTS/jarvis_next_action_planner.py",
    "11_SCRIPTS/jarvis_execution_index.py",
    "11_SCRIPTS/jarvis_command_health.py",
    "11_SCRIPTS/jarvis_maintenance_cycle.py",
    "11_SCRIPTS/jarvis_daily_checkpoint.py",
    "11_SCRIPTS/jarvis_operator_brief.py",
    "11_SCRIPTS/jarvis_repo_snapshot.py",
    "11_SCRIPTS/jarvis_patch_catalog.py",
]


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def duplicates(items: list[str]) -> list[str]:
    counts = Counter(items)
    return sorted([item for item, count in counts.items() if count > 1])


def audit() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    ops_text = read(REPO / "11_SCRIPTS" / "jarvis_ops.py")
    cli_text = read(REPO / "11_SCRIPTS" / "jarvis_main_cli.py")

    parsers = re.findall(r'add_parser\("([^"]+)"', ops_text)
    routes = re.findall(r'if args\.cmd == "([^"]+)"', ops_text)
    script_refs = sorted(set(re.findall(r'"(11_SCRIPTS/[^"]+\.py)"', cli_text)))

    parser_set = set(parsers)
    route_set = set(routes)

    missing_routes = sorted(parser_set - route_set)
    missing_parsers = sorted(route_set - parser_set)
    duplicate_parsers = duplicates(parsers)
    duplicate_routes = duplicates(routes)

    missing_script_refs = []
    for ref in script_refs:
        if not (REPO / ref).exists():
            missing_script_refs.append(ref)

    existing_core = [script for script in CORE_SCRIPTS if (REPO / script).exists()]
    compile_check = run(["py", "-3", "-m", "py_compile", *existing_core])
    git_status = run(["git", "status", "-sb"])
    git_log = run(["git", "log", "--oneline", "-8"])

    blockers = []
    warnings = []

    if compile_check["exit_code"] != 0:
        blockers.append("core compile failed")

    if missing_script_refs:
        blockers.append("missing script refs")

    if missing_routes:
        warnings.append("parser without route")
    if missing_parsers:
        warnings.append("route without parser")
    if duplicate_parsers:
        warnings.append("duplicate parsers")
    if duplicate_routes:
        warnings.append("duplicate routes")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "warnings": warnings,
        "command_count": len(parser_set),
        "route_count": len(route_set),
        "script_ref_count": len(script_refs),
        "missing_routes": missing_routes,
        "missing_parsers": missing_parsers,
        "duplicate_parsers": duplicate_parsers,
        "duplicate_routes": duplicate_routes,
        "missing_script_refs": missing_script_refs,
        "compile_exit_code": compile_check["exit_code"],
        "compile_output": compile_check["output"],
        "git_status": git_status["output"],
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Integrity Audit — Block 163",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Commands: `{payload['command_count']}`",
        f"Routes: `{payload['route_count']}`",
        f"Script refs: `{payload['script_ref_count']}`",
        f"Last commit: `{payload['last_commit']}`",
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
        "## Blockers",
        "",
    ]

    if blockers:
        for item in blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- No blockers.")

    lines += [
        "",
        "## Warnings",
        "",
    ]

    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- No warnings.")

    lines += [
        "",
        "## Details",
        "",
        f"- missing_routes: `{len(missing_routes)}`",
        f"- missing_parsers: `{len(missing_parsers)}`",
        f"- duplicate_parsers: `{len(duplicate_parsers)}`",
        f"- duplicate_routes: `{len(duplicate_routes)}`",
        f"- missing_script_refs: `{len(missing_script_refs)}`",
        f"- compile_exit_code: `{compile_check['exit_code']}`",
        "",
    ]

    if compile_check["output"]:
        lines += [
            "## Compile output",
            "",
            "```text",
            compile_check["output"][-4000:],
            "```",
            "",
        ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("INTEGRITY_AUDIT_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "blockers": payload["blockers"],
        "warnings": payload["warnings"],
        "git_status": payload["git_status"],
        "last_commit": payload["last_commit"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 163 Integrity Audit")
    parser.add_argument("action", choices=["audit"], default="audit")
    args = parser.parse_args()

    if args.action == "audit":
        return audit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
