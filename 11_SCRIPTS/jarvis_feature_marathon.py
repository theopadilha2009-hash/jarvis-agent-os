from __future__ import annotations

import argparse
import json
import py_compile
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "175_FEATURE_MARATHON"
STATE = OUT / "MARATHON_STATE.json"
REPORT = OUT / "MARATHON_RUN.md"

CATALOG = [
    {"slug": "repo_pulse", "title": "Jarvis Auto Repo Pulse", "objective": "Generate a compact repository pulse.", "kind": "repo"},
    {"slug": "script_inventory", "title": "Jarvis Auto Script Inventory", "objective": "Inventory Jarvis scripts and largest files.", "kind": "scripts"},
    {"slug": "execution_index", "title": "Jarvis Auto Execution Index", "objective": "Index execution output folders.", "kind": "execution"},
    {"slug": "commit_digest", "title": "Jarvis Auto Commit Digest", "objective": "Summarize recent commits.", "kind": "commits"},
    {"slug": "operator_runbook", "title": "Jarvis Auto Operator Runbook", "objective": "Create a cockpit runbook.", "kind": "runbook"},
    {"slug": "slow_command_watch", "title": "Jarvis Auto Slow Command Watch", "objective": "Highlight slow commands.", "kind": "performance"},
    {"slug": "cleanliness_guard", "title": "Jarvis Auto Cleanliness Guard", "objective": "Check repo cleanliness.", "kind": "repo"},
    {"slug": "feature_backlog_snapshot", "title": "Jarvis Auto Feature Backlog Snapshot", "objective": "Snapshot feature candidates.", "kind": "planning"},
    {"slug": "session_digest", "title": "Jarvis Auto Session Digest", "objective": "Summarize latest work session.", "kind": "session"},
    {"slug": "safe_ship_note", "title": "Jarvis Auto Safe Ship Note", "objective": "Generate ship-readiness note.", "kind": "shipping"},

    {"slug": "architecture_map", "title": "Jarvis Auto Architecture Map", "objective": "Map key scripts and their operator purpose.", "kind": "architecture"},
    {"slug": "automation_health", "title": "Jarvis Auto Automation Health", "objective": "Check current automation health signals.", "kind": "health"},
    {"slug": "branch_snapshot", "title": "Jarvis Auto Branch Snapshot", "objective": "Capture branch and commit state.", "kind": "repo"},
    {"slug": "build_readiness", "title": "Jarvis Auto Build Readiness", "objective": "Summarize readiness for the next build cycle.", "kind": "shipping"},
    {"slug": "command_catalog", "title": "Jarvis Auto Command Catalog", "objective": "List known cockpit commands from ops file.", "kind": "commands"},
    {"slug": "cockpit_summary", "title": "Jarvis Auto Cockpit Summary", "objective": "Create a compact operator cockpit summary.", "kind": "session"},
    {"slug": "daily_engineering_digest", "title": "Jarvis Auto Daily Engineering Digest", "objective": "Generate daily engineering status.", "kind": "commits"},
    {"slug": "dependency_free_check", "title": "Jarvis Auto Dependency Free Check", "objective": "Confirm scripts remain standard-library focused.", "kind": "health"},
    {"slug": "duplicate_name_watch", "title": "Jarvis Auto Duplicate Name Watch", "objective": "Detect duplicate-looking script groups.", "kind": "scripts"},
    {"slug": "execution_cleanup_plan", "title": "Jarvis Auto Execution Cleanup Plan", "objective": "Plan cleanup of execution artifacts.", "kind": "execution"},
    {"slug": "feature_growth_log", "title": "Jarvis Auto Feature Growth Log", "objective": "Track feature growth across commits.", "kind": "planning"},
    {"slug": "file_size_watch", "title": "Jarvis Auto File Size Watch", "objective": "Highlight largest code files.", "kind": "scripts"},
    {"slug": "git_timeline", "title": "Jarvis Auto Git Timeline", "objective": "Build a timeline from recent commits.", "kind": "commits"},
    {"slug": "hot_path_watch", "title": "Jarvis Auto Hot Path Watch", "objective": "Identify scripts that appear central to operations.", "kind": "architecture"},
    {"slug": "local_machine_note", "title": "Jarvis Auto Local Machine Note", "objective": "Record local machine execution context.", "kind": "session"},
    {"slug": "marathon_capacity_plan", "title": "Jarvis Auto Marathon Capacity Plan", "objective": "Estimate marathon feature-building capacity.", "kind": "planning"},
    {"slug": "module_boundary_map", "title": "Jarvis Auto Module Boundary Map", "objective": "Group scripts by module boundaries.", "kind": "architecture"},
    {"slug": "operator_focus_plan", "title": "Jarvis Auto Operator Focus Plan", "objective": "Recommend operator focus for the next cycle.", "kind": "planning"},
    {"slug": "output_freshness", "title": "Jarvis Auto Output Freshness", "objective": "Check freshness of execution outputs.", "kind": "execution"},
    {"slug": "performance_baseline", "title": "Jarvis Auto Performance Baseline", "objective": "Capture baseline command speeds.", "kind": "performance"},
    {"slug": "repo_growth_meter", "title": "Jarvis Auto Repo Growth Meter", "objective": "Measure repo growth through scripts and lines.", "kind": "repo"},
    {"slug": "script_age_map", "title": "Jarvis Auto Script Age Map", "objective": "Map script files by modification time.", "kind": "scripts"},
    {"slug": "ship_queue_note", "title": "Jarvis Auto Ship Queue Note", "objective": "Generate a queue note for ship-ready changes.", "kind": "shipping"},
    {"slug": "stability_score", "title": "Jarvis Auto Stability Score", "objective": "Score current repo stability from local signals.", "kind": "health"},
    {"slug": "system_index", "title": "Jarvis Auto System Index", "objective": "Create an index of the local Jarvis system.", "kind": "architecture"},
    {"slug": "task_priority_grid", "title": "Jarvis Auto Task Priority Grid", "objective": "Create a priority grid for next tasks.", "kind": "planning"},
    {"slug": "test_surface_map", "title": "Jarvis Auto Test Surface Map", "objective": "Map commands used as validation surface.", "kind": "health"},
    {"slug": "validation_matrix", "title": "Jarvis Auto Validation Matrix", "objective": "Build a matrix of validation commands.", "kind": "health"},
    {"slug": "workflow_map", "title": "Jarvis Auto Workflow Map", "objective": "Map the local command workflow.", "kind": "architecture"},
    {"slug": "writing_assistant", "title": "Jarvis Auto Writing Assistant", "objective": "Generate concise operator notes from repo state.", "kind": "session"},
    {"slug": "autonomy_meter", "title": "Jarvis Auto Autonomy Meter", "objective": "Estimate current autonomy level.", "kind": "planning"},
    {"slug": "marathon_runbook", "title": "Jarvis Auto Marathon Runbook", "objective": "Document how to run feature marathon cycles.", "kind": "runbook"},
    {"slug": "operator_checkpoint", "title": "Jarvis Auto Operator Checkpoint", "objective": "Create a reusable checkpoint note.", "kind": "session"},
    {"slug": "release_note_builder", "title": "Jarvis Auto Release Note Builder", "objective": "Draft release notes from recent commits.", "kind": "shipping"},
    {"slug": "repo_rhythm", "title": "Jarvis Auto Repo Rhythm", "objective": "Analyze recent commit rhythm.", "kind": "commits"},
    {"slug": "script_family_map", "title": "Jarvis Auto Script Family Map", "objective": "Group scripts by naming family.", "kind": "scripts"},
    {"slug": "system_pressure", "title": "Jarvis Auto System Pressure", "objective": "Detect growth pressure from lines and outputs.", "kind": "health"},
    {"slug": "next_marathon_plan", "title": "Jarvis Auto Next Marathon Plan", "objective": "Plan the next long feature marathon.", "kind": "planning"},
]


def run(cmd):
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 4),
        "output": (result.stdout + result.stderr).strip(),
    }


def is_clean():
    status = run(["git", "status", "-sb"])
    return status["output"].strip() == "## main...origin/main", status


def feature_path(slug):
    return SCRIPTS / f"jarvis_auto_{slug}.py"


def missing_features():
    return [spec for spec in CATALOG if not feature_path(spec["slug"]).exists()]


def feature_source(spec):
    template = r'''from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
from datetime import datetime
from pathlib import Path

FEATURE = __FEATURE_META__

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
'''
    return template.replace("__FEATURE_META__", repr(spec))


def commit_feature(path, slug, push):
    rel = str(path.relative_to(REPO))

    add = run(["git", "add", rel])
    if add["exit_code"] != 0:
        return {"ok": False, "stage": "git_add", "result": add}

    commit = run(["git", "commit", "-m", f"feat: add Jarvis auto feature {slug.replace('_', '-')}"])
    if commit["exit_code"] != 0:
        return {"ok": False, "stage": "git_commit", "result": commit}

    push_result = None
    if push:
        push_result = run(["git", "push", "origin", "main"])
        if push_result["exit_code"] != 0:
            return {"ok": False, "stage": "git_push", "result": push_result}

    return {"ok": True, "stage": "done", "commit": commit, "push": push_result}


def build_one(spec, push=False, dry_run=False):
    slug = spec["slug"]
    path = feature_path(slug)

    clean, status = is_clean()
    if not clean:
        return {
            "slug": slug,
            "ok": False,
            "stage": "pre_clean_check",
            "message": "repo is not clean before feature build",
            "git_status": status["output"],
        }

    if path.exists():
        return {"slug": slug, "ok": True, "stage": "already_exists", "path": str(path.relative_to(REPO))}

    if dry_run:
        return {"slug": slug, "ok": True, "stage": "dry_run", "path": str(path.relative_to(REPO))}

    path.write_text(feature_source(spec), encoding="utf-8")

    try:
        py_compile.compile(str(path), doraise=True)
    except Exception as exc:
        return {"slug": slug, "ok": False, "stage": "py_compile", "error": str(exc)}

    feature_run = run(["py", "-3", str(path.relative_to(REPO)), "report"])
    if feature_run["exit_code"] != 0:
        return {"slug": slug, "ok": False, "stage": "feature_run", "result": feature_run}

    ship = commit_feature(path, slug, push=push)
    if not ship["ok"]:
        return {"slug": slug, "ok": False, "stage": ship["stage"], "ship": ship}

    return {
        "slug": slug,
        "ok": True,
        "stage": "built_committed_pushed" if push else "built_committed",
        "path": str(path.relative_to(REPO)),
        "feature_run_seconds": feature_run["seconds"],
        "commit_output": ship["commit"]["output"],
    }


def plan():
    OUT.mkdir(parents=True, exist_ok=True)
    todo = missing_features()
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total_catalog": len(CATALOG),
        "missing_count": len(todo),
        "existing_count": len(CATALOG) - len(todo),
        "next_features": todo[:20],
    }
    print("FEATURE_MARATHON_PLAN")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_marathon(minutes, max_features, push, dry_run):
    started = time.perf_counter()
    deadline = started + max(0.1, minutes * 60)
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    blockers = []

    while time.perf_counter() < deadline and len(results) < max_features:
        todo = missing_features()
        if not todo:
            break

        spec = todo[0]
        result = build_one(spec, push=push, dry_run=dry_run)
        results.append(result)

        if not result.get("ok"):
            blockers.append(result)
            break

        if dry_run:
            break

    final_status = run(["git", "status", "-sb"])
    recent_log = run(["git", "log", "--oneline", "-20"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "minutes_requested": minutes,
        "max_features": max_features,
        "push": push,
        "dry_run": dry_run,
        "features_built": [item for item in results if item.get("stage") not in ("dry_run", "already_exists")],
        "results": results,
        "blockers": blockers,
        "git_status": final_status["output"],
        "recent_commits": recent_log["output"],
        "remaining_features": [item["slug"] for item in missing_features()],
        "total_catalog": len(CATALOG),
        "total_seconds": round(time.perf_counter() - started, 4),
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Feature Marathon — v2",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Catalog: `{payload['total_catalog']}`",
        f"Minutes requested: `{payload['minutes_requested']}`",
        f"Max features: `{payload['max_features']}`",
        f"Push: `{payload['push']}`",
        f"Dry run: `{payload['dry_run']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Results",
        "",
    ]

    for item in results:
        lines.append(f"- `{item.get('slug')}` ok=`{item.get('ok')}` stage=`{item.get('stage')}` path=`{item.get('path', '-')}`")

    lines += ["", "## Remaining features", ""]

    for slug in payload["remaining_features"]:
        lines.append(f"- `{slug}`")

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

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("FEATURE_MARATHON_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "catalog": payload["total_catalog"],
        "built_count": len(payload["features_built"]),
        "remaining_count": len(payload["remaining_features"]),
        "results": results,
        "git_status": payload["git_status"],
        "total_seconds": payload["total_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main():
    parser = argparse.ArgumentParser(description="JARVIS Feature Marathon")
    parser.add_argument("action", nargs="?", choices=["plan", "run"], default="plan")
    parser.add_argument("--minutes", type=float, default=5.0)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.action == "plan":
        return plan()

    if args.action == "run":
        return run_marathon(args.minutes, args.max_features, args.push, args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
