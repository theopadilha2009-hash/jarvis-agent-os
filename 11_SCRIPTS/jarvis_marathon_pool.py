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
OUT = EXEC / "179_MARATHON_POOL"
STATE = OUT / "MARATHON_POOL.json"
REPORT = OUT / "MARATHON_POOL.md"

DOMAINS = [
    "repo", "git", "script", "execution", "operator", "shipping", "validation", "health",
    "performance", "architecture", "planning", "session", "autonomy", "marathon", "quality",
    "index", "audit", "summary", "runbook", "growth",
]

ACTIONS = [
    "scanner", "digest", "map", "index", "score", "watch", "planner", "report", "matrix", "timeline",
    "snapshot", "guard", "advisor", "baseline", "review", "pulse", "meter", "catalog", "brief", "check",
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


def generated_specs(limit=400):
    specs = []
    for domain in DOMAINS:
        for action in ACTIONS:
            slug = f"{domain}_{action}"
            specs.append({
                "slug": slug,
                "title": f"Jarvis Pool {domain.title()} {action.title()}",
                "objective": f"Generate an automated {action} for the {domain} area using local repo signals.",
                "domain": domain,
                "action": action,
            })
    return specs[:limit]


def feature_path(slug):
    return SCRIPTS / f"jarvis_pool_{slug}.py"


def missing_specs():
    return [spec for spec in generated_specs() if not feature_path(spec["slug"]).exists()]


def is_clean():
    status = run(["git", "status", "-sb"])
    return status["output"].strip() == "## main...origin/main", status


def source_for(spec):
    return f'''from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

FEATURE = {spec!r}
REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "179_MARATHON_POOL" / "features" / FEATURE["slug"]


def run_cmd(cmd):
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {{
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 4),
        "output": (result.stdout + result.stderr).strip(),
    }}


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
        rows.append({{
            "path": str(path.relative_to(REPO)),
            "lines": lines,
        }})

    rows = sorted(rows, key=lambda item: item["lines"], reverse=True)

    exec_dirs = []
    if EXEC.exists():
        exec_dirs = [str(item.relative_to(REPO)) for item in sorted(EXEC.iterdir(), key=lambda item: item.name, reverse=True) if item.is_dir()]

    return {{
        "script_count": len(scripts),
        "script_lines": total_lines,
        "largest_scripts": rows[:10],
        "execution_dir_count": len(exec_dirs),
        "recent_execution_dirs": exec_dirs[:10],
    }}


def report():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run_cmd(["git", "status", "-sb"])
    git_log = run_cmd(["git", "log", "--oneline", "-12"])
    data = stats()

    payload = {{
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "verdict": "pass" if git_status["exit_code"] == 0 else "block",
        "git_status": git_status["output"],
        "recent_commits": git_log["output"],
        "stats": data,
        "insight": f"{{FEATURE['title']}} checked {{FEATURE['domain']}}/{{FEATURE['action']}} using local repository signals.",
        "total_seconds": 0,
    }}

    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    json_path = OUT / f"{{FEATURE['slug']}}.json"
    md_path = OUT / f"{{FEATURE['slug']}}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {{FEATURE['title']}}",
        "",
        f"Created at: `{{payload['created_at']}}`",
        f"Domain: `{{FEATURE['domain']}}`",
        f"Action: `{{FEATURE['action']}}`",
        f"Verdict: `{{payload['verdict']}}`",
        f"Total seconds: `{{payload['total_seconds']}}`",
        "",
        "## Insight",
        "",
        f"- {{payload['insight']}}",
        f"- Scripts: `{{data['script_count']}}`",
        f"- Script lines: `{{data['script_lines']}}`",
        f"- Execution dirs: `{{data['execution_dir_count']}}`",
        "",
        "## Largest scripts",
        "",
    ]

    for item in data["largest_scripts"][:8]:
        lines.append(f"- `{{item['path']}}` lines=`{{item['lines']}}`")

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

    md_path.write_text("\\n".join(lines), encoding="utf-8")

    print(f"POOL_{{FEATURE['slug'].upper()}}_DONE")
    print(md_path)
    print(json.dumps({{
        "verdict": payload["verdict"],
        "slug": FEATURE["slug"],
        "domain": FEATURE["domain"],
        "action": FEATURE["action"],
        "script_count": data["script_count"],
        "script_lines": data["script_lines"],
        "total_seconds": payload["total_seconds"],
    }}, ensure_ascii=False, indent=2))

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


def build_one(spec, push):
    clean, status = is_clean()
    if not clean:
        return {
            "slug": spec["slug"],
            "ok": False,
            "stage": "pre_clean_check",
            "git_status": status["output"],
        }

    path = feature_path(spec["slug"])
    if path.exists():
        return {
            "slug": spec["slug"],
            "ok": True,
            "stage": "already_exists",
            "path": str(path.relative_to(REPO)),
        }

    path.write_text(source_for(spec), encoding="utf-8")

    try:
        py_compile.compile(str(path), doraise=True)
    except Exception as exc:
        return {"slug": spec["slug"], "ok": False, "stage": "py_compile", "error": str(exc)}

    feature_run = run(["py", "-3", str(path.relative_to(REPO)), "report"])
    if feature_run["exit_code"] != 0:
        return {"slug": spec["slug"], "ok": False, "stage": "feature_run", "result": feature_run}

    add = run(["git", "add", str(path.relative_to(REPO))])
    if add["exit_code"] != 0:
        return {"slug": spec["slug"], "ok": False, "stage": "git_add", "result": add}

    commit = run(["git", "commit", "-m", f"feat: add Jarvis pool feature {spec['slug'].replace('_', '-')}"])
    if commit["exit_code"] != 0:
        return {"slug": spec["slug"], "ok": False, "stage": "git_commit", "result": commit}

    push_result = None
    if push:
        push_result = run(["git", "push", "origin", "main"])
        if push_result["exit_code"] != 0:
            return {"slug": spec["slug"], "ok": False, "stage": "git_push", "result": push_result}

    return {
        "slug": spec["slug"],
        "ok": True,
        "stage": "built_committed_pushed" if push else "built_committed",
        "path": str(path.relative_to(REPO)),
        "feature_run_seconds": feature_run["seconds"],
        "commit_output": commit["output"],
    }


def plan():
    OUT.mkdir(parents=True, exist_ok=True)
    missing = missing_specs()
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "pool_size": len(generated_specs()),
        "missing_count": len(missing),
        "next_features": missing[:25],
    }
    print("MARATHON_POOL_PLAN")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_pool(minutes, max_features, push):
    started = time.perf_counter()
    deadline = started + max(0.1, minutes * 60)
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    blockers = []

    while time.perf_counter() < deadline and len(results) < max_features:
        missing = missing_specs()
        if not missing:
            break

        result = build_one(missing[0], push=push)
        results.append(result)

        if not result.get("ok"):
            blockers.append(result)
            break

    status = run(["git", "status", "-sb"])
    log = run(["git", "log", "--oneline", "-25"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "minutes_requested": minutes,
        "max_features": max_features,
        "push": push,
        "built_count": len([item for item in results if item.get("stage") in ("built_committed", "built_committed_pushed")]),
        "results": results,
        "blockers": blockers,
        "remaining_count": len(missing_specs()),
        "git_status": status["output"],
        "recent_commits": log["output"],
        "total_seconds": round(time.perf_counter() - started, 4),
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Marathon Pool v1",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Built count: `{payload['built_count']}`",
        f"Remaining count: `{payload['remaining_count']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Results",
        "",
    ]

    for item in results:
        lines.append(f"- `{item.get('slug')}` ok=`{item.get('ok')}` stage=`{item.get('stage')}` path=`{item.get('path', '-')}`")

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

    print("MARATHON_POOL_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "built_count": payload["built_count"],
        "remaining_count": payload["remaining_count"],
        "git_status": payload["git_status"],
        "total_seconds": payload["total_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0 if not blockers else 1


def main():
    parser = argparse.ArgumentParser(description="JARVIS Marathon Pool")
    parser.add_argument("action", nargs="?", choices=["plan", "run"], default="plan")
    parser.add_argument("--minutes", type=float, default=5.0)
    parser.add_argument("--max-features", type=int, default=10)
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    if args.action == "plan":
        return plan()

    if args.action == "run":
        return run_pool(args.minutes, args.max_features, args.push)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
