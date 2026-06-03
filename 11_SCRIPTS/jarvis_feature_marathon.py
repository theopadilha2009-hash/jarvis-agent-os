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
OUT = REPO / "05_EXECUCAO" / "175_FEATURE_MARATHON"
STATE = OUT / "MARATHON_STATE.json"
REPORT = OUT / "MARATHON_RUN.md"

CATALOG = [
    {
        "slug": "repo_pulse",
        "title": "Jarvis Auto Repo Pulse",
        "objective": "Generate a compact repository pulse with git status, recent commits, script count, and execution count.",
    },
    {
        "slug": "script_inventory",
        "title": "Jarvis Auto Script Inventory",
        "objective": "Generate an inventory of Jarvis scripts and identify the largest automation files.",
    },
    {
        "slug": "execution_index",
        "title": "Jarvis Auto Execution Index",
        "objective": "Index execution output folders so the operator can quickly see recent system artifacts.",
    },
    {
        "slug": "commit_digest",
        "title": "Jarvis Auto Commit Digest",
        "objective": "Summarize recent commits into a quick engineering digest.",
    },
    {
        "slug": "operator_runbook",
        "title": "Jarvis Auto Operator Runbook",
        "objective": "Create a simple runbook for the current Jarvis cockpit commands.",
    },
    {
        "slug": "slow_command_watch",
        "title": "Jarvis Auto Slow Command Watch",
        "objective": "Read profiler state and highlight the slowest current commands.",
    },
    {
        "slug": "cleanliness_guard",
        "title": "Jarvis Auto Cleanliness Guard",
        "objective": "Check if the repository is clean and generate a safe next-step note.",
    },
    {
        "slug": "feature_backlog_snapshot",
        "title": "Jarvis Auto Feature Backlog Snapshot",
        "objective": "Create a lightweight snapshot of generated feature candidates and next build direction.",
    },
    {
        "slug": "session_digest",
        "title": "Jarvis Auto Session Digest",
        "objective": "Summarize the latest work session and current cockpit state.",
    },
    {
        "slug": "safe_ship_note",
        "title": "Jarvis Auto Safe Ship Note",
        "objective": "Generate a ship-readiness note from git status, audit state, and profiler state.",
    },
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


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"load_error": str(exc)}


def feature_path(slug):
    return SCRIPTS / f"jarvis_auto_{slug}.py"


def missing_features():
    return [spec for spec in CATALOG if not feature_path(spec["slug"]).exists()]


def feature_source(spec):
    template = r'''from __future__ import annotations

import argparse
import json
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


def script_stats():
    files = sorted(SCRIPTS.glob("jarvis_*.py"))
    rows = []
    total_lines = 0

    for path in files:
        try:
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            lines = 0

        total_lines += lines
        rows.append({
            "path": str(path.relative_to(REPO)),
            "lines": lines,
        })

    rows = sorted(rows, key=lambda item: item["lines"], reverse=True)

    return {
        "script_count": len(files),
        "script_lines": total_lines,
        "largest_scripts": rows[:12],
    }


def execution_stats():
    if not EXEC.exists():
        return {"execution_dir_count": 0, "recent_dirs": []}

    dirs = sorted([item for item in EXEC.iterdir() if item.is_dir()], key=lambda item: item.name, reverse=True)
    return {
        "execution_dir_count": len(dirs),
        "recent_dirs": [str(item.relative_to(REPO)) for item in dirs[:12]],
    }


def report():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run_cmd(["git", "status", "-sb"])
    git_log = run_cmd(["git", "log", "--oneline", "-10"])

    stats = script_stats()
    exec_stats = execution_stats()

    profiler = {}
    profiler_path = EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json"
    if profiler_path.exists():
        try:
            profiler = json.loads(profiler_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            profiler = {}

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "verdict": "pass" if git_status["exit_code"] == 0 else "block",
        "git_status": git_status["output"],
        "recent_commits": git_log["output"],
        "script_stats": stats,
        "execution_stats": exec_stats,
        "profiler_slowest": profiler.get("slowest", [])[:5],
        "total_seconds": 0,
    }

    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    json_path = OUT / f"{FEATURE['slug']}.json"
    md_path = OUT / f"{FEATURE['slug']}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {FEATURE['title']}",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Objective: {FEATURE['objective']}",
        f"Verdict: `{payload['verdict']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Current repo",
        "",
        f"- Scripts: `{stats['script_count']}`",
        f"- Script lines: `{stats['script_lines']}`",
        f"- Execution dirs: `{exec_stats['execution_dir_count']}`",
        "",
        "## Largest scripts",
        "",
    ]

    for item in stats["largest_scripts"][:8]:
        lines.append(f"- `{item['path']}` lines=`{item['lines']}`")

    lines += [
        "",
        "## Recent execution dirs",
        "",
    ]

    for item in exec_stats["recent_dirs"][:8]:
        lines.append(f"- `{item}`")

    lines += [
        "",
        "## Slowest commands",
        "",
    ]

    slowest = payload["profiler_slowest"]
    if slowest:
        for item in slowest:
            lines.append(f"- `{item.get('name')}` seconds=`{item.get('seconds')}`")
    else:
        lines.append("- No profiler data.")

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
        "script_count": stats["script_count"],
        "script_lines": stats["script_lines"],
        "execution_dir_count": exec_stats["execution_dir_count"],
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

    return {
        "ok": True,
        "stage": "done",
        "commit": commit,
        "push": push_result,
    }


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
        return {
            "slug": slug,
            "ok": True,
            "stage": "already_exists",
            "path": str(path.relative_to(REPO)),
        }

    if dry_run:
        return {
            "slug": slug,
            "ok": True,
            "stage": "dry_run",
            "path": str(path.relative_to(REPO)),
        }

    path.write_text(feature_source(spec), encoding="utf-8")

    try:
        py_compile.compile(str(path), doraise=True)
    except Exception as exc:
        return {
            "slug": slug,
            "ok": False,
            "stage": "py_compile",
            "error": str(exc),
        }

    feature_run = run(["py", "-3", str(path.relative_to(REPO)), "report"])
    if feature_run["exit_code"] != 0:
        return {
            "slug": slug,
            "ok": False,
            "stage": "feature_run",
            "result": feature_run,
        }

    ship = commit_feature(path, slug, push=push)
    if not ship["ok"]:
        return {
            "slug": slug,
            "ok": False,
            "stage": ship["stage"],
            "ship": ship,
        }

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
        "next_features": todo[:10],
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
    recent_log = run(["git", "log", "--oneline", "-10"])

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
        "total_seconds": round(time.perf_counter() - started, 4),
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Feature Marathon — Block 175",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
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

    lines += [
        "",
        "## Remaining features",
        "",
    ]

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
        "built_count": len(payload["features_built"]),
        "results": results,
        "remaining_count": len(payload["remaining_features"]),
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
        return run_marathon(
            minutes=args.minutes,
            max_features=args.max_features,
            push=args.push,
            dry_run=args.dry_run,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
