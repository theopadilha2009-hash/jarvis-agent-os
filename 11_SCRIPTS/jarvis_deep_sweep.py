from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
OUT = REPO / "05_EXECUCAO" / "165_DEEP_SWEEP"
REPORT = OUT / "DEEP_SWEEP.md"
STATE = OUT / "DEEP_SWEEP.json"


def run(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def duplicates(items: list[str]) -> list[str]:
    counts = Counter(items)
    return sorted([item for item, count in counts.items() if count > 1])


def scan_scripts() -> dict:
    py_files = sorted(SCRIPTS.glob("jarvis_*.py"))
    records = []
    total_lines = 0
    windows_path_hits = []

    bad_path_pattern = "11_SCRIPTS" + chr(92)

    for path in py_files:
        text = read(path)
        line_count = len(text.splitlines())
        total_lines += line_count

        rel = str(path.relative_to(REPO)).replace(chr(92), "/")
        if bad_path_pattern in text:
            windows_path_hits.append(rel)

        records.append({
            "path": rel,
            "lines": line_count,
            "size_bytes": path.stat().st_size,
        })

    return {
        "count": len(records),
        "total_lines": total_lines,
        "files": records,
        "windows_path_hits": windows_path_hits,
    }


def collect() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)

    ops_text = read(SCRIPTS / "jarvis_ops.py")
    cli_text = read(SCRIPTS / "jarvis_main_cli.py")

    parsers = re.findall(r'add_parser\("([^"]+)"', ops_text)
    routes = re.findall(r'if args\.cmd == "([^"]+)"', ops_text)
    script_refs = sorted(set(re.findall(r'"(11_SCRIPTS/[^"]+\.py)"', cli_text)))

    script_scan = scan_scripts()
    py_paths = [item["path"] for item in script_scan["files"]]

    compile_check = run(["py", "-3", "-m", "py_compile", *py_paths])
    git_status = run(["git", "status", "-sb"])
    git_log = run(["git", "log", "--oneline", "-12"])

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

    blockers = []
    warnings = []

    if compile_check["exit_code"] != 0:
        blockers.append("compile failed")
    if missing_script_refs:
        blockers.append("missing script refs")
    if duplicate_parsers:
        blockers.append("duplicate parsers")
    if duplicate_routes:
        blockers.append("duplicate routes")

    if missing_routes:
        warnings.append("parser without route")
    if missing_parsers:
        warnings.append("route without parser")
    if script_scan["windows_path_hits"]:
        warnings.append("windows path pattern still present")

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "warnings": warnings,
        "git_status": git_status["output"],
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
        "script_scan": script_scan,
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
        "last_commits": git_log["output"],
    }


def write(data: dict) -> None:
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Deep Sweep — Block 165",
        "",
        f"Created at: `{data['created_at']}`",
        f"Verdict: `{data['verdict']}`",
        f"Last commit: `{data['last_commit']}`",
        "",
        "## Summary",
        "",
        f"- Scripts: `{data['script_scan']['count']}`",
        f"- Script lines: `{data['script_scan']['total_lines']}`",
        f"- Commands: `{data['command_count']}`",
        f"- Routes: `{data['route_count']}`",
        f"- Script refs: `{data['script_ref_count']}`",
        f"- Compile exit: `{data['compile_exit_code']}`",
        "",
        "## Git status",
        "",
        "```text",
        data["git_status"] or "-",
        "```",
        "",
        "## Blockers",
        "",
    ]

    if data["blockers"]:
        for item in data["blockers"]:
            lines.append(f"- {item}")
    else:
        lines.append("- No blockers.")

    lines += [
        "",
        "## Warnings",
        "",
    ]

    if data["warnings"]:
        for item in data["warnings"]:
            lines.append(f"- {item}")
    else:
        lines.append("- No warnings.")

    lines += [
        "",
        "## Windows path hits",
        "",
    ]

    if data["script_scan"]["windows_path_hits"]:
        for item in data["script_scan"]["windows_path_hits"]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Largest scripts",
        "",
    ]

    largest = sorted(data["script_scan"]["files"], key=lambda x: x["lines"], reverse=True)[:20]
    for item in largest:
        lines.append(f"- `{item['path']}` lines=`{item['lines']}` size=`{item['size_bytes']}`")

    lines += [
        "",
        "## Last commits",
        "",
        "```text",
        data["last_commits"] or "-",
        "```",
        "",
    ]

    if data["compile_output"]:
        lines += [
            "## Compile output",
            "",
            "```text",
            data["compile_output"][-5000:],
            "```",
            "",
        ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def sweep() -> int:
    data = collect()
    write(data)

    print("DEEP_SWEEP_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": data["verdict"],
        "blockers": data["blockers"],
        "warnings": data["warnings"],
        "scripts": data["script_scan"]["count"],
        "lines": data["script_scan"]["total_lines"],
        "git_status": data["git_status"],
        "last_commit": data["last_commit"],
    }, ensure_ascii=False, indent=2))

    return 0 if not data["blockers"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 165 Deep Sweep")
    parser.add_argument("action", choices=["sweep"], default="sweep")
    args = parser.parse_args()

    if args.action == "sweep":
        return sweep()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
