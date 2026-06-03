from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

FEATURE = {'slug': 'performance_review', 'title': 'Jarvis Pool Performance Review', 'objective': 'Generate an automated review for the performance area using local repo signals.', 'domain': 'performance', 'action': 'review'}
REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "179_MARATHON_POOL" / "features" / FEATURE["slug"]


def run_cmd(cmd):
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 4),
        "output": (result.stdout + result.stderr).strip(),
    }


def stats():
    scripts = sorted(SCRIPTS.glob("jarvis_*.py")) + sorted(SCRIPTS.glob("jarvis_pool_*.py"))
    rows = []
    total_lines = 0

    for path in scripts:
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

    exec_dirs = []
    if EXEC.exists():
        exec_dirs = [str(item.relative_to(REPO)) for item in sorted(EXEC.iterdir(), key=lambda item: item.name, reverse=True) if item.is_dir()]

    return {
        "script_count": len(scripts),
        "script_lines": total_lines,
        "largest_scripts": rows[:10],
        "execution_dir_count": len(exec_dirs),
        "recent_execution_dirs": exec_dirs[:10],
    }


def report():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run_cmd(["git", "status", "-sb"])
    git_log = run_cmd(["git", "log", "--oneline", "-12"])
    data = stats()

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "verdict": "pass" if git_status["exit_code"] == 0 else "block",
        "git_status": git_status["output"],
        "recent_commits": git_log["output"],
        "stats": data,
        "insight": f"{FEATURE['title']} checked {FEATURE['domain']}/{FEATURE['action']} using local repository signals.",
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
        f"Domain: `{FEATURE['domain']}`",
        f"Action: `{FEATURE['action']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Insight",
        "",
        f"- {payload['insight']}",
        f"- Scripts: `{data['script_count']}`",
        f"- Script lines: `{data['script_lines']}`",
        f"- Execution dirs: `{data['execution_dir_count']}`",
        "",
        "## Largest scripts",
        "",
    ]

    for item in data["largest_scripts"][:8]:
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

    print(f"POOL_{FEATURE['slug'].upper()}_DONE")
    print(md_path)
    print(json.dumps({
        "verdict": payload["verdict"],
        "slug": FEATURE["slug"],
        "domain": FEATURE["domain"],
        "action": FEATURE["action"],
        "script_count": data["script_count"],
        "script_lines": data["script_lines"],
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
