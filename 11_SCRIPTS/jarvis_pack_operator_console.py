from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

FEATURE = {'slug': 'operator_console', 'title': 'Jarvis Pack Operator Console', 'mission': 'Create a compact operator console with status, recent commits, command speed, and next action.', 'focus': 'operator', 'checks': ['home', 'profiler', 'next_action', 'git_log']}

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "11_SCRIPTS"
EXEC = REPO / "05_EXECUCAO"
OUT = EXEC / "180_FEATURE_PACK_BUILDER" / "pack_outputs" / FEATURE["slug"]


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


def script_inventory():
    scripts = sorted(SCRIPTS.glob("jarvis_*.py")) + sorted(SCRIPTS.glob("jarvis_pool_*.py")) + sorted(SCRIPTS.glob("jarvis_pack_*.py"))
    unique = {}
    for item in scripts:
        unique[str(item)] = item

    rows = []
    total = 0
    families = {}

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
        rows.append({
            "path": str(path.relative_to(REPO)),
            "lines": lines,
            "family": family,
        })

    return {
        "count": len(rows),
        "lines": total,
        "largest": sorted(rows, key=lambda item: item["lines"], reverse=True)[:15],
        "families": dict(sorted(families.items(), key=lambda item: item[1], reverse=True)[:20]),
    }


def execution_inventory():
    if not EXEC.exists():
        return {"count": 0, "recent": []}

    dirs = sorted([item for item in EXEC.iterdir() if item.is_dir()], key=lambda item: item.name, reverse=True)
    return {
        "count": len(dirs),
        "recent": [str(item.relative_to(REPO)) for item in dirs[:15]],
    }


def generate_findings(payload):
    focus = FEATURE.get("focus")
    findings = []
    scripts = payload["scripts"]
    executions = payload["executions"]
    profiler = payload["states"].get("profiler", {})
    marathon = payload["states"].get("marathon_pool", {})

    if focus == "quality":
        findings.append(f"Python/script surface: {scripts['count']} scripts and {scripts['lines']} lines.")
        findings.append(f"Execution folders: {executions['count']}.")
        findings.append("Quality gate should stay strict: compile first, then status, then ship.")
        if payload["git_clean"]:
            findings.append("Repo is clean and safe for next build.")
        else:
            findings.append("Repo is dirty; stop and review before build.")
    elif focus == "marathon":
        findings.append(f"Last pool remaining count: {marathon.get('remaining_count', 'unknown')}.")
        findings.append("Recommended next run: small pack if changing architecture, larger pool run only after clean validation.")
        findings.append("Prefer pack-based features over generic pool spam when quality matters.")
    elif focus == "review":
        findings.append(f"Auto feature family count: {scripts['families'].get('auto', 0)}.")
        findings.append(f"Pool feature family count: {scripts['families'].get('pool', 0)}.")
        findings.append(f"Pack feature family count: {scripts['families'].get('pack', 0)}.")
        findings.append("High duplication pressure means next work should improve existing runners, not only add files.")
    elif focus == "operator":
        findings.append(f"Last commit: {payload['last_commit']}.")
        findings.append(f"Profiler total: {profiler.get('total_seconds', 'unknown')}s.")
        findings.append("Operator console route: check status, choose one build direction, validate, ship.")
    elif focus == "routing":
        slowest = profiler.get("slowest", [])
        if slowest:
            findings.append(f"Slowest command now: {slowest[0].get('name')} at {slowest[0].get('seconds')}s.")
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
        findings.append(f"Long-run readiness score: {score}/100.")
        findings.append("Ready for 30-minute controlled runs; 60-minute runs need stronger quality filter and batch checkpointing.")
    else:
        findings.append("General pack report generated.")

    return findings


def report():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)

    git_status = run_cmd(["git", "status", "-sb"])
    git_log = run_cmd(["git", "log", "--oneline", "-15"])

    states = {
        "profiler": read_json(EXEC / "166_COMMAND_PROFILER" / "COMMAND_PROFILER.json"),
        "next_action": read_json(EXEC / "154_NEXT_ACTION_PLANNER" / "NEXT_ACTION_PLAN.json"),
        "marathon": read_json(EXEC / "175_FEATURE_MARATHON" / "MARATHON_STATE.json"),
        "marathon_pool": read_json(EXEC / "179_MARATHON_POOL" / "MARATHON_POOL.json"),
        "home": read_json(EXEC / "162_HOME_DASHBOARD" / "HOME_DASHBOARD.json"),
    }

    scripts = script_inventory()
    executions = execution_inventory()
    git_clean = git_status["output"].strip() == "## main...origin/main"

    payload = {
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
    }

    payload["findings"] = generate_findings(payload)
    payload["total_seconds"] = round(time.perf_counter() - started, 4)

    json_path = OUT / f"{FEATURE['slug']}.json"
    md_path = OUT / f"{FEATURE['slug']}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {FEATURE['title']}",
        "",
        f"Created at: `{payload['created_at']}`",
        f"Mission: {FEATURE['mission']}",
        f"Focus: `{FEATURE['focus']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Git clean: `{payload['git_clean']}`",
        f"Last commit: `{payload['last_commit']}`",
        f"Total seconds: `{payload['total_seconds']}`",
        "",
        "## Findings",
        "",
    ]

    for item in payload["findings"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Script surface",
        "",
        f"- Count: `{scripts['count']}`",
        f"- Lines: `{scripts['lines']}`",
        f"- Families: `{scripts['families']}`",
        "",
        "## Largest scripts",
        "",
    ]

    for item in scripts["largest"][:10]:
        lines.append(f"- `{item['path']}` lines=`{item['lines']}` family=`{item['family']}`")

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

    print(f"PACK_{FEATURE['slug'].upper()}_DONE")
    print(md_path)
    print(json.dumps({
        "verdict": payload["verdict"],
        "feature": FEATURE["slug"],
        "focus": FEATURE["focus"],
        "git_clean": payload["git_clean"],
        "script_count": scripts["count"],
        "script_lines": scripts["lines"],
        "findings": payload["findings"][:3],
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
