from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
from datetime import datetime
from pathlib import Path

FEATURE = {'slug': 'task_priority_grid', 'title': 'Jarvis Auto Task Priority Grid', 'objective': 'Create a priority grid for next tasks.', 'kind': 'planning'}

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "175_FEATURE_MARATHON" / "auto_features" / FEATURE["slug"]


def run_cmd(cmd):
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 4),
        "output": (result.stdout + result.stderr).strip(),
    }


def read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"load_error": str(exc)}


def script_stats():
    files = sorted(SCRIPTS.glob("jarvis_*.py"))
    rows = []
    total_lines = 0
    families = {}

    for path in files:
        name = path.stem.replace("jarvis_", "")
        family = name.split("_")[0] if "_" in name else name
        families[family] = families.get(family, 0) + 1

        try:
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            lines = 0

        total_lines += lines
        rows.append({
            "path": str(path.relative_to(REPO)),
            "name": path.name,
            "family": family,
            "lines": lines,
            "mtime": path.stat().st_mtime,
        })

    rows = sorted(rows, key=lambda item: item["lines"], reverse=True)

    return {
        "script_count": len(files),
        "script_lines": total_lines,
        "largest_scripts": rows[:15],
        "families": dict(sorted(families.items(), key=lambda item: item[1], reverse=True)[:15]),
    }


def execution_stats():
    if not EXEC.exists():
        return {"execution_dir_count": 0, "recent_dirs": []}

    dirs = sorted([item for item in EXEC.iterdir() if item.is_dir()], key=lambda item: item.name, reverse=True)
    return {
        "execution_dir_count": len(dirs),
        "recent_dirs": [str(item.relative_to(REPO)) for item in dirs[:15]],
    }


def command_catalog():
    ops = SCRIPTS / "jarvis_ops.py"
    text = ops.read_text(encoding="utf-8", errors="replace") if ops.exists() else ""
    commands = []
    marker = 'sub.add_parser("'
    for line in text.splitlines():
        if marker in line:
            cmd = line.split(marker, 1)[1].split('"', 1)[0]
            commands.append(cmd)
    return sorted(set(commands))


def kind_findings(payload):
    kind = FEATURE.get("kind", "general")
    stats = payload["script_stats"]
    exec_stats = payload["execution_stats"]
    findings = []

    if kind == "performance":
        for item in payload.get("profiler_slowest", [])[:5]:
            findings.append(f"Command {item.get('name')} measured around {item.get('seconds')}s.")
    elif kind == "scripts":
        for item in stats["largest_scripts"][:5]:
            findings.append(f"{item['path']} is one of the largest scripts with {item['lines']} lines.")
    elif kind == "commits":
        for line in payload.get("recent_commits", "").splitlines()[:5]:
            findings.append(f"Recent commit: {line}")
    elif kind == "execution":
        for item in exec_stats["recent_dirs"][:5]:
            findings.append(f"Recent execution folder: {item}")
    elif kind == "commands":
        for cmd in payload.get("commands", [])[:10]:
            findings.append(f"Available command: {cmd}")
    elif kind == "health":
        findings.append(f"Repo status: {payload.get('git_status') or '-'}")
        findings.append(f"Scripts: {stats['script_count']} / Lines: {stats['script_lines']}")
    elif kind == "architecture":
        for family, count in stats["families"].items():
            findings.append(f"Script family {family}: {count} files")
    elif kind == "planning":
        findings.append("Next safe cycle: clean repo, choose one improvement, validate, then ship.")
        findings.append(f"Current automation scale: {stats['script_count']} scripts.")
    elif kind == "shipping":
        findings.append(f"Ship readiness starts from git status: {payload.get('git_status') or '-'}")
        findings.append("Validation surface: py_compile, dashboard, profiler, work-session.")
    elif kind == "session":
        findings.append(f"Machine: {platform.system()} {platform.machine()}")
        findings.append(f"Working directory: {REPO}")
    else:
        findings.append(f"Feature kind: {kind}")
        findings.append(f"Scripts: {stats['script_count']}")

    return findings


def report():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run_cmd(["git", "status", "-sb"])
    git_log = run_cmd(["git", "log", "--oneline", "-12"])

    stats = script_stats()
    exec_stats = execution_stats()
    profiler = read_json(EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "verdict": "pass" if git_status["exit_code"] == 0 else "block",
        "git_status": git_status["output"],
        "recent_commits": git_log["output"],
        "script_stats": stats,
        "execution_stats": exec_stats,
        "commands": command_catalog(),
        "profiler_slowest": profiler.get("slowest", [])[:8],
        "python": platform.python_version(),
        "system": {
            "platform": platform.system(),
            "machine": platform.machine(),
            "cwd": str(REPO),
        },
        "total_seconds": 0,
    }

    payload["findings"] = kind_findings(payload)
    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    json_path = OUT / f"{FEATURE['slug']}.json"
    md_path = OUT / f"{FEATURE['slug']}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {FEATURE['title']}",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Objective: {FEATURE['objective']}",
        f"Kind: `{FEATURE.get('kind')}`",
        f"Verdict: `{payload['verdict']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Key findings",
        "",
    ]

    for item in payload["findings"][:12]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Current repo",
        "",
        f"- Scripts: `{stats['script_count']}`",
        f"- Script lines: `{stats['script_lines']}`",
        f"- Execution dirs: `{exec_stats['execution_dir_count']}`",
        f"- Commands detected: `{len(payload['commands'])}`",
        "",
        "## Largest scripts",
        "",
    ]

    for item in stats["largest_scripts"][:8]:
        lines.append(f"- `{item['path']}` lines=`{item['lines']}`")

    lines += [
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
        "## Recent commits",
        "",
        "```text",
        payload["recent_commits"] or "-",
        "```",
        "",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"{FEATURE['slug'].upper()}_DONE")
    print(md_path)
    print(json.dumps({
        "verdict": payload["verdict"],
        "feature": FEATURE["slug"],
        "kind": FEATURE.get("kind"),
        "script_count": stats["script_count"],
        "script_lines": stats["script_lines"],
        "execution_dir_count": exec_stats["execution_dir_count"],
        "commands": len(payload["commands"]),
        "total_seconds": payload["total_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0 if payload["verdict"] == "pass" else 1


def main():
    parser = argparse.ArgumentParser(description=FEATURE["title"])
    parser.add_argument("action", nargs="?", choices=["report"], default="report")
    args = parser.parse_args()

    if args.action == "report":
        return report()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
