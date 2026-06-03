from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

FEATURE = {'slug': 'slow_command_watch', 'title': 'Jarvis Auto Slow Command Watch', 'objective': 'Read profiler state and highlight the slowest current commands.'}

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
