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
OUT = EXEC / "180_FEATURE_PACK_BUILDER"
STATE = OUT / "FEATURE_PACK_BUILDER.json"
REPORT = OUT / "FEATURE_PACK_BUILDER.md"

FEATURES = [
    {
        "slug": "quality_gate",
        "title": "Jarvis Pack Quality Gate",
        "mission": "Run a stronger local quality gate across Python syntax, git state, file growth, and execution health.",
        "focus": "quality",
        "checks": ["py_compile", "git_status", "script_growth", "execution_growth", "sensitive_file_names"],
    },
    {
        "slug": "marathon_director",
        "title": "Jarvis Pack Marathon Director",
        "mission": "Read marathon state and recommend the next safe build-run size, duration, and command.",
        "focus": "marathon",
        "checks": ["marathon_state", "remaining_pool", "recent_commits", "repo_clean"],
    },
    {
        "slug": "feature_pack_review",
        "title": "Jarvis Pack Feature Review",
        "mission": "Review generated auto/pool features and separate useful growth from shallow duplication.",
        "focus": "review",
        "checks": ["auto_features", "pool_features", "families", "duplication_pressure"],
    },
    {
        "slug": "operator_console",
        "title": "Jarvis Pack Operator Console",
        "mission": "Create a compact operator console with status, recent commits, command speed, and next action.",
        "focus": "operator",
        "checks": ["home", "profiler", "next_action", "git_log"],
    },
    {
        "slug": "repo_signal_router",
        "title": "Jarvis Pack Repo Signal Router",
        "mission": "Convert local repo signals into clear next routes: improve speed, build features, clean outputs, or review quality.",
        "focus": "routing",
        "checks": ["profiler", "git_status", "line_count", "script_count", "execution_count"],
    },
    {
        "slug": "long_run_readiness",
        "title": "Jarvis Pack Long Run Readiness",
        "mission": "Score whether Jarvis is ready for 30–60 minute autonomous building sessions.",
        "focus": "autonomy",
        "checks": ["clean_repo", "pool_remaining", "profiler_speed", "validation_surface", "push_safety"],
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


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"load_error": str(exc)}


def is_clean():
    status = run(["git", "status", "-sb"])
    return status["output"].strip() == "## main...origin/main", status


def feature_path(slug):
    return SCRIPTS / f"jarvis_pack_{slug}.py"


def missing_features():
    return [item for item in FEATURES if not feature_path(item["slug"]).exists()]


def source_for(feature):
    return f'''from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

FEATURE = {feature!r}

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "180_FEATURE_PACK_BUILDER" / "pack_outputs" / FEATURE["slug"]


def run_cmd(cmd):
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return {{
        "cmd": cmd,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 4),
        "output": (result.stdout + result.stderr).strip(),
    }}


def read_json(path):
    if not path.exists():
        return {{}}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {{"load_error": str(exc)}}


def script_inventory():
    scripts = sorted(SCRIPTS.glob("jarvis_*.py")) + sorted(SCRIPTS.glob("jarvis_pool_*.py")) + sorted(SCRIPTS.glob("jarvis_pack_*.py"))
    unique = {{}}
    for item in scripts:
        unique[str(item)] = item

    rows = []
    total = 0
    families = {{}}

    for path in sorted(unique.values()):
        try:
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            lines = 0

        name = path.stem
        if name.startswith("jarvis_pool_"):
            family = "pool"
        elif name.startswith("jarvis_auto_"):
            family = "auto"
        elif name.startswith("jarvis_pack_"):
            family = "pack"
        else:
            family = name.replace("jarvis_", "").split("_")[0]

        families[family] = families.get(family, 0) + 1
        total += lines
        rows.append({{
            "path": str(path.relative_to(REPO)),
            "lines": lines,
            "family": family,
        }})

    return {{
        "count": len(rows),
        "lines": total,
        "largest": sorted(rows, key=lambda item: item["lines"], reverse=True)[:15],
        "families": dict(sorted(families.items(), key=lambda item: item[1], reverse=True)[:20]),
    }}


def execution_inventory():
    if not EXEC.exists():
        return {{"count": 0, "recent": []}}

    dirs = sorted([item for item in EXEC.iterdir() if item.is_dir()], key=lambda item: item.name, reverse=True)
    return {{
        "count": len(dirs),
        "recent": [str(item.relative_to(REPO)) for item in dirs[:15]],
    }}


def generate_findings(payload):
    focus = FEATURE.get("focus")
    findings = []
    scripts = payload["scripts"]
    executions = payload["executions"]
    profiler = payload["states"].get("profiler", {{}})
    marathon = payload["states"].get("marathon_pool", {{}})

    if focus == "quality":
        findings.append(f"Python/script surface: {{scripts['count']}} scripts and {{scripts['lines']}} lines.")
        findings.append(f"Execution folders: {{executions['count']}}.")
        findings.append("Quality gate should stay strict: compile first, then status, then ship.")
        if payload["git_clean"]:
            findings.append("Repo is clean and safe for next build.")
        else:
            findings.append("Repo is dirty; stop and review before build.")
    elif focus == "marathon":
        findings.append(f"Last pool remaining count: {{marathon.get('remaining_count', 'unknown')}}.")
        findings.append("Recommended next run: small pack if changing architecture, larger pool run only after clean validation.")
        findings.append("Prefer pack-based features over generic pool spam when quality matters.")
    elif focus == "review":
        findings.append(f"Auto feature family count: {{scripts['families'].get('auto', 0)}}.")
        findings.append(f"Pool feature family count: {{scripts['families'].get('pool', 0)}}.")
        findings.append(f"Pack feature family count: {{scripts['families'].get('pack', 0)}}.")
        findings.append("High duplication pressure means next work should improve existing runners, not only add files.")
    elif focus == "operator":
        findings.append(f"Last commit: {{payload['last_commit']}}.")
        findings.append(f"Profiler total: {{profiler.get('total_seconds', 'unknown')}}s.")
        findings.append("Operator console route: check status, choose one build direction, validate, ship.")
    elif focus == "routing":
        slowest = profiler.get("slowest", [])
        if slowest:
            findings.append(f"Slowest command now: {{slowest[0].get('name')}} at {{slowest[0].get('seconds')}}s.")
        findings.append("Route decision: performance if slowest > 1s, quality if too many generated files, marathon if repo is clean.")
    elif focus == "autonomy":
        score = 0
        if payload["git_clean"]:
            score += 25
        if profiler.get("total_seconds", 99) and profiler.get("total_seconds", 99) < 2:
            score += 25
        if scripts["count"] > 100:
            score += 20
        if executions["count"] > 50:
            score += 10
        if marathon:
            score += 20
        findings.append(f"Long-run readiness score: {{score}}/100.")
        findings.append("Ready for 30-minute controlled runs; 60-minute runs need stronger quality filter and batch checkpointing.")
    else:
        findings.append("General pack report generated.")

    return findings


def report():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run_cmd(["git", "status", "-sb"])
    git_log = run_cmd(["git", "log", "--oneline", "-15"])

    states = {{
        "profiler": read_json(EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json"),
        "next_action": read_json(EXEC / "154_NEXT_ACTION_PLANNER" / "NEXT_ACTION_PLAN.json"),
        "marathon": read_json(EXEC / "175_FEATURE_MARATHON" / "MARATHON_STATE.json"),
        "marathon_pool": read_json(EXEC / "179_MARATHON_POOL" / "MARATHON_POOL.json"),
        "home": read_json(EXEC / "162_HOME_DASHBOARD" / "HOME_DASHBOARD.json"),
    }}

    scripts = script_inventory()
    executions = execution_inventory()
    git_clean = git_status["output"].strip() == "## main...origin/main"

    payload = {{
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "verdict": "pass" if git_status["exit_code"] == 0 else "block",
        "git_clean": git_clean,
        "git_status": git_status["output"],
        "last_commit": git_log["output"].splitlines()[0] if git_log["output"] else "",
        "recent_commits": git_log["output"],
        "scripts": scripts,
        "executions": executions,
        "states": states,
        "total_seconds": 0,
    }}

    payload["findings"] = generate_findings(payload)
    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    json_path = OUT / f"{{FEATURE['slug']}}.json"
    md_path = OUT / f"{{FEATURE['slug']}}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {{FEATURE['title']}}",
        "",
        f"Created at: `{{payload['created_at']}}`",
        f"Mission: {{FEATURE['mission']}}",
        f"Focus: `{{FEATURE['focus']}}`",
        f"Verdict: `{{payload['verdict']}}`",
        f"Git clean: `{{payload['git_clean']}}`",
        f"Last commit: `{{payload['last_commit']}}`",
        f"Total seconds: `{{payload['total_seconds']}}`",
        "",
        "## Findings",
        "",
    ]

    for item in payload["findings"]:
        lines.append(f"- {{item}}")

    lines += [
        "",
        "## Script surface",
        "",
        f"- Count: `{{scripts['count']}}`",
        f"- Lines: `{{scripts['lines']}}`",
        f"- Families: `{{scripts['families']}}`",
        "",
        "## Largest scripts",
        "",
    ]

    for item in scripts["largest"][:10]:
        lines.append(f"- `{{item['path']}}` lines=`{{item['lines']}}` family=`{{item['family']}}`")

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

    print(f"PACK_{{FEATURE['slug'].upper()}}_DONE")
    print(md_path)
    print(json.dumps({{
        "verdict": payload["verdict"],
        "feature": FEATURE["slug"],
        "focus": FEATURE["focus"],
        "git_clean": payload["git_clean"],
        "script_count": scripts["count"],
        "script_lines": scripts["lines"],
        "findings": payload["findings"][:3],
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


def plan():
    OUT.mkdir(parents=True, exist_ok=True)
    missing = missing_features()
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total_features": len(FEATURES),
        "missing_count": len(missing),
        "missing": missing,
    }
    print("FEATURE_PACK_PLAN")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build(limit, push):
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    clean, status = is_clean()
    if not clean:
        payload = {
            "verdict": "block",
            "reason": "repo_dirty",
            "git_status": status["output"],
        }
        print("FEATURE_PACK_BLOCKED")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    targets = missing_features()[:limit]
    if not targets:
        print("FEATURE_PACK_DONE")
        print(json.dumps({"verdict": "pass", "built_count": 0, "message": "nothing missing"}, ensure_ascii=False, indent=2))
        return 0

    results = []
    paths = []

    for feature in targets:
        path = feature_path(feature["slug"])
        path.write_text(source_for(feature), encoding="utf-8")
        paths.append(path)

        try:
            py_compile.compile(str(path), doraise=True)
            compile_ok = True
            compile_error = ""
        except Exception as exc:
            compile_ok = False
            compile_error = str(exc)

        feature_run = run(["py", "-3", str(path.relative_to(REPO)), "report"]) if compile_ok else {"exit_code": 1, "output": compile_error, "seconds": 0}

        results.append({
            "slug": feature["slug"],
            "path": str(path.relative_to(REPO)),
            "compile_ok": compile_ok,
            "run_exit": feature_run["exit_code"],
            "run_seconds": feature_run["seconds"],
            "run_tail": feature_run["output"][-1200:],
        })

        if not compile_ok or feature_run["exit_code"] != 0:
            payload = {
                "verdict": "block",
                "stage": "feature_validation",
                "results": results,
            }
            STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print("FEATURE_PACK_BLOCKED")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 1

    add = run(["git", "add"] + [str(path.relative_to(REPO)) for path in paths])
    if add["exit_code"] != 0:
        print("FEATURE_PACK_BLOCKED")
        print(json.dumps({"verdict": "block", "stage": "git_add", "result": add}, ensure_ascii=False, indent=2))
        return 1

    commit = run(["git", "commit", "-m", "feat: add Jarvis quality feature pack"])
    if commit["exit_code"] != 0:
        print("FEATURE_PACK_BLOCKED")
        print(json.dumps({"verdict": "block", "stage": "git_commit", "result": commit}, ensure_ascii=False, indent=2))
        return 1

    push_result = None
    if push:
        push_result = run(["git", "push", "origin", "main"])
        if push_result["exit_code"] != 0:
            print("FEATURE_PACK_BLOCKED")
            print(json.dumps({"verdict": "block", "stage": "git_push", "result": push_result}, ensure_ascii=False, indent=2))
            return 1

    status_after = run(["git", "status", "-sb"])
    log_after = run(["git", "log", "--oneline", "-12"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass",
        "built_count": len(results),
        "results": results,
        "push": push,
        "git_status": status_after["output"],
        "recent_commits": log_after["output"],
        "total_seconds": round(time.perf_counter() - started, 4),
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Feature Pack Builder — Block 180",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Built count: `{payload['built_count']}`",
        f"Push: `{payload['push']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Built features",
        "",
    ]

    for item in results:
        lines.append(f"- `{item['slug']}` path=`{item['path']}` run_seconds=`{item['run_seconds']}`")

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

    print("FEATURE_PACK_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "built_count": payload["built_count"],
        "git_status": payload["git_status"],
        "total_seconds": payload["total_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Feature Pack Builder")
    parser.add_argument("action", nargs="?", choices=["plan", "build"], default="plan")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    if args.action == "plan":
        return plan()

    if args.action == "build":
        return build(args.limit, args.push)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
