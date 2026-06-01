#!/usr/bin/env python3
"""
JARVIS Terminal Command Center v1
Local-only CLI for the JARVIS API.

No external calls.
No .env reads.
No commit/push/deploy.
Uses only http://127.0.0.1:8787 local endpoints.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8787"
OUT_DIR = ROOT / "05_EXECUCAO" / "92_JARVIS_TERMINAL_COMMAND_CENTER"
REPORTS = OUT_DIR / "reports"


def call_json(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            raw = res.read().decode("utf-8", "replace")
            return json.loads(raw)
    except Exception as exc:
        return {
            "ok": False,
            "endpoint": f"{method.upper()} {path}",
            "error": str(exc),
            "hint": "Check if JARVIS is running on 127.0.0.1:8787",
        }


def git(args: list[str]) -> str:
    allowed = {
        ("status", "--short"),
        ("log", "--oneline", "-5"),
        ("branch", "--show-current"),
        ("rev-parse", "--short", "HEAD"),
    }
    tup = tuple(args)
    if tup not in allowed:
        return "blocked_git_command"
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, timeout=5)
        return (r.stdout or r.stderr or "").strip()
    except Exception as exc:
        return f"git_error: {exc}"


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def line(title: str) -> None:
    print("\n" + "=" * 12 + f" {title} " + "=" * 12)


def compact_brief(data: dict[str, Any]) -> None:
    if not data.get("ok"):
        print_json(data)
        return

    git_data = data.get("git", {})
    src = data.get("sources", {})

    print("JARVIS LOCAL BRIEF")
    print("- generated_at:", data.get("generated_at", ""))
    print("- git:", "clean" if git_data.get("clean") else "dirty", "|", git_data.get("last_commit", ""))
    print("- sources:", src.get("total_sources"), "total /", src.get("total_files_indexed"), "indexed")
    print("- health:", src.get("health_status"))
    print("- sensitive_skipped:", src.get("sensitive_skipped"))
    print("- large_files:", src.get("large_files"))
    print("- duplicate_groups:", src.get("duplicate_groups"))

    signals = data.get("signals", [])[:6]
    if signals:
        print("\nSignals:")
        for s in signals:
            print("-", s.get("level", ""), "|", s.get("signal", ""))


def cmd_status(_: argparse.Namespace) -> None:
    print_json(call_json("GET", "/status"))


def cmd_health(_: argparse.Namespace) -> None:
    print_json(call_json("GET", "/sources-health"))


def cmd_insight(_: argparse.Namespace) -> None:
    print_json(call_json("GET", "/sources-insight"))


def cmd_brief(args: argparse.Namespace) -> None:
    data = call_json("GET", "/jarvis-brief")
    if args.json:
        print_json(data)
    else:
        compact_brief(data)


def cmd_report(_: argparse.Namespace) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    data = call_json("GET", "/jarvis-brief-report")

    if not data.get("ok"):
        print_json(data)
        return

    md = data.get("report_md", "")
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = REPORTS / f"jarvis_brief_report_{stamp}.md"
    out.write_text(md, encoding="utf-8")

    print("REPORT_SAVED:", out.relative_to(ROOT))
    print("")
    print(md[:1600])


def cmd_search(args: argparse.Namespace) -> None:
    q = " ".join(args.query).strip()
    if not q:
        print("Usage: jarvis_quick.sh search <term>")
        return

    path = "/sources-search?q=" + urllib.parse.quote(q) + f"&limit={args.limit}"
    data = call_json("GET", path)

    if args.json:
        print_json(data)
        return

    print(f"SOURCES SEARCH: {q}")
    print("count:", data.get("count"), "| returned:", data.get("returned"))

    for r in data.get("results", [])[: args.limit]:
        print("")
        print("-", r.get("path"))
        print("  match:", ",".join(r.get("matched_in", [])))
        print("  meta:", r.get("category"), r.get("ext"), r.get("size_human"))
        snip = (r.get("snippet") or "").strip()
        if snip:
            print("  snippet:", snip[:260])


def cmd_git(_: argparse.Namespace) -> None:
    line("Git")
    print("branch:", git(["branch", "--show-current"]))
    print("head:", git(["rev-parse", "--short", "HEAD"]))
    print("last commits:")
    print(git(["log", "--oneline", "-5"]))
    status = git(["status", "--short"])
    print("status:", status if status else "clean")


def cmd_all(_: argparse.Namespace) -> None:
    line("Git")
    print("branch:", git(["branch", "--show-current"]))
    print("head:", git(["rev-parse", "--short", "HEAD"]))
    status = git(["status", "--short"])
    print("status:", status if status else "clean")

    line("Brief")
    compact_brief(call_json("GET", "/jarvis-brief"))

    line("Sources health")
    h = call_json("GET", "/sources-health")
    print("ok:", h.get("ok"), "| health:", h.get("health_status"), "| sources:", h.get("total_sources"), "| indexed:", h.get("total_files_indexed"))

    line("Apply guard")
    ag = call_json("GET", "/forge-apply-guard-dashboard")
    print("ok:", ag.get("ok"), "| status:", ag.get("status_real"), "| confirmation:", ag.get("required_confirmation"))

    line("Useful commands")
    print("./11_SCRIPTS/jarvis_quick.sh brief")
    print("./11_SCRIPTS/jarvis_quick.sh search jarvis")
    print("./11_SCRIPTS/jarvis_quick.sh health")
    print("./11_SCRIPTS/jarvis_quick.sh report")


def cmd_routes(_: argparse.Namespace) -> None:
    print("JARVIS QUICK COMMANDS")
    print("  all                  Full terminal summary")
    print("  brief                Compact local brief")
    print("  brief --json         Raw /jarvis-brief JSON")
    print("  report               Save markdown report into 05_EXECUCAO/92...")
    print("  health               Raw /sources-health JSON")
    print("  insight              Raw /sources-insight JSON")
    print("  search <term>        Search local sources")
    print("  search <term> --json Raw search JSON")
    print("  status               Raw /status JSON")
    print("  git                  Git summary")
    print("  daily                Save daily intelligence report")
    print("  audit                Run local audit checks")
    print("  mass-search <terms>  Search several terms and save report")
    print("  export-pack          Export local JSON state pack")
    print("  start                Save session start report")
    print("  close <note>         Save session close report")
    print("  doctor               Quick local stability doctor")
    print("  next-block           Recommend the next build block")
    print("  queue-add <task>     Add task to local queue")
    print("  queue-status         Show queue summary")
    print("  queue-list           List all queued tasks")
    print("  queue-run            Process pending queue tasks into reports")
    print("  queue-clear-done     Remove completed tasks from queue")
    print("  -- ultra operator suite (block 96) --")
    print("  feature-pack <idea>  Generate a full implementation package")
    print("  cleanup-advice       Advisory cleanup report (never deletes)")
    print("  repo-map             Map core scripts/UI/exec folders/reports")
    print("  diff-review          Review uncommitted changes + risk")
    print("  queue-pack           Turn the task queue into an execution plan")
    print("  mission <idea>       Full mission pack (brief+audit+plan+queue)")
    print("  ultra <idea>         Run the whole suite into one master report")
    print("  open-latest [--open] Show latest reports (open md on macOS)")
    print("  routes               Show this help")




# === JARVIS_CLI_BLOCK_93_BATCH_INTELLIGENCE ===
# Batch local intelligence commands.
# Local-only. No external calls. No .env. No commit/push/deploy.

def _j93_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _j93_dir() -> Path:
    d = ROOT / "05_EXECUCAO" / "93_JARVIS_BATCH_INTELLIGENCE_RUNNER"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j93_reports() -> Path:
    d = _j93_dir() / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j93_exports() -> Path:
    d = _j93_dir() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j93_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def _j93_write_report(prefix: str, content: str) -> Path:
    out = _j93_reports() / f"{prefix}_{_j93_stamp()}.md"
    out.write_text(content, encoding="utf-8")
    return out


def _j93_git_snapshot() -> str:
    return "\n".join([
        "branch: " + git(["branch", "--show-current"]),
        "head: " + git(["rev-parse", "--short", "HEAD"]),
        "",
        "last commits:",
        git(["log", "--oneline", "-5"]),
        "",
        "status:",
        git(["status", "--short"]) or "clean",
    ])


def _j93_run_local_check(name: str, cmd: list[str]) -> dict[str, Any]:
    try:
        r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=20)
        return {
            "name": name,
            "ok": r.returncode == 0,
            "exit_code": r.returncode,
            "stdout": (r.stdout or "").strip()[-900:],
            "stderr": (r.stderr or "").strip()[-900:],
        }
    except Exception as exc:
        return {"name": name, "ok": False, "error": str(exc)}


def cmd_daily(_: argparse.Namespace) -> None:
    brief = call_json("GET", "/jarvis-brief")
    health = call_json("GET", "/sources-health")
    insight = call_json("GET", "/sources-insight")
    guard = call_json("GET", "/forge-apply-guard-dashboard")

    src = brief.get("sources", {}) if brief.get("ok") else {}

    lines = [
        "# JARVIS Daily Intelligence",
        "",
        "- Status real: local batch report",
        "- External calls: false",
        "- Commit/push/deploy: false",
        "",
        "## Git",
        "```text",
        _j93_git_snapshot(),
        "```",
        "",
        "## Brief",
        f"- Brief OK: `{brief.get('ok')}`",
        f"- Health: `{src.get('health_status', health.get('health_status', 'unknown'))}`",
        f"- Sources: `{src.get('total_sources', health.get('total_sources', 0))}`",
        f"- Indexed: `{src.get('total_files_indexed', health.get('total_files_indexed', 0))}`",
        f"- Sensitive skipped: `{src.get('sensitive_skipped', health.get('sensitive_skipped', 0))}`",
        f"- Duplicate groups: `{src.get('duplicate_groups', insight.get('duplicate_groups', 0))}`",
        "",
        "## Guard",
        f"- Apply guard OK: `{guard.get('ok')}`",
        f"- Status real: `{guard.get('status_real', '')}`",
        f"- Required confirmation: `{guard.get('required_confirmation', '')}`",
        "",
        "## Signals",
    ]

    for sig in (brief.get("signals") or health.get("signals") or [])[:12]:
        lines.append(f"- `{sig.get('level', '')}` {sig.get('signal', '')}")

    lines += [
        "",
        "## Largest files",
    ]

    for f in (insight.get("largest_files") or brief.get("largest_files") or [])[:8]:
        lines.append(f"- `{f.get('path', '')}` — {f.get('size_human', '')}")

    lines += [
        "",
        "## Next commands",
        "```bash",
        "./11_SCRIPTS/jarvis_quick.sh audit",
        "./11_SCRIPTS/jarvis_quick.sh mass-search jarvis forge sources",
        "./11_SCRIPTS/jarvis_quick.sh export-pack",
        "```",
        "",
    ]

    out = _j93_write_report("daily_intelligence", "\n".join(lines))
    print("DAILY_REPORT_SAVED:", _j93_rel(out))
    print("")
    print("\n".join(lines[:70]))


def cmd_audit(_: argparse.Namespace) -> None:
    checks = []
    checks.append(_j93_run_local_check("py_compile core/api/cli", [
        sys.executable,
        "-m",
        "py_compile",
        "11_SCRIPTS/jarvis_api.py",
        "11_SCRIPTS/jarvis_core.py",
        "11_SCRIPTS/jarvis_cli.py",
    ]))

    endpoints = [
        ("GET /status", "GET", "/status"),
        ("GET /jarvis-brief", "GET", "/jarvis-brief"),
        ("GET /sources-health", "GET", "/sources-health"),
        ("GET /sources-insight", "GET", "/sources-insight"),
        ("GET /forge-apply-guard-dashboard", "GET", "/forge-apply-guard-dashboard"),
    ]

    for name, method, path in endpoints:
        data = call_json(method, path)
        checks.append({
            "name": name,
            "ok": bool(data.get("ok")),
            "endpoint": data.get("endpoint", path),
            "status_real": data.get("status_real", ""),
            "error": data.get("error", ""),
        })

    passed = sum(1 for c in checks if c.get("ok"))
    total = len(checks)

    lines = [
        "# JARVIS Local Audit",
        "",
        f"- Passed: `{passed}/{total}`",
        "- External calls: false",
        "- Commit/push/deploy: false",
        "",
        "## Git",
        "```text",
        _j93_git_snapshot(),
        "```",
        "",
        "## Checks",
    ]

    for c in checks:
        status = "OK" if c.get("ok") else "FAIL"
        lines.append(f"- `{status}` {c.get('name')}")
        if c.get("error"):
            lines.append(f"  - error: `{c.get('error')}`")
        if c.get("stderr"):
            lines.append("  - stderr tail:")
            lines.append("```text")
            lines.append(str(c.get("stderr"))[:900])
            lines.append("```")

    out = _j93_write_report("local_audit", "\n".join(lines))
    print("AUDIT_REPORT_SAVED:", _j93_rel(out))
    print(f"PASSED: {passed}/{total}")
    for c in checks:
        print(("OK   " if c.get("ok") else "FAIL "), c.get("name"))


def cmd_mass_search(args: argparse.Namespace) -> None:
    terms = [t.strip() for t in args.terms if t.strip()]
    if not terms:
        print("Usage: jarvis_quick.sh mass-search <term1> <term2> ...")
        return

    lines = [
        "# JARVIS Mass Search",
        "",
        "- Status real: local sources search batch",
        f"- Terms: `{', '.join(terms)}`",
        "",
    ]

    print("MASS SEARCH")
    for term in terms:
        data = call_json("GET", "/sources-search?q=" + urllib.parse.quote(term) + f"&limit={args.limit}")
        print(f"- {term}: {data.get('count')} match(es), returned {data.get('returned')}")

        lines += [
            f"## {term}",
            "",
            f"- Count: `{data.get('count')}`",
            f"- Returned: `{data.get('returned')}`",
            "",
        ]

        for r in data.get("results", [])[: args.limit]:
            lines.append(f"### `{r.get('path', '')}`")
            lines.append(f"- Match: `{','.join(r.get('matched_in', []))}`")
            lines.append(f"- Meta: `{r.get('category', '')}` `{r.get('ext', '')}` `{r.get('size_human', '')}`")
            snip = (r.get("snippet") or "").strip()
            if snip:
                lines.append("")
                lines.append("> " + snip[:500].replace("\n", " "))
            lines.append("")

    out = _j93_write_report("mass_search", "\n".join(lines))
    print("MASS_SEARCH_REPORT_SAVED:", _j93_rel(out))


def cmd_export_pack(_: argparse.Namespace) -> None:
    base = _j93_exports() / f"jarvis_export_pack_{_j93_stamp()}"
    base.mkdir(parents=True, exist_ok=True)

    payloads = {
        "status.json": call_json("GET", "/status"),
        "brief.json": call_json("GET", "/jarvis-brief"),
        "health.json": call_json("GET", "/sources-health"),
        "insight.json": call_json("GET", "/sources-insight"),
        "apply_guard.json": call_json("GET", "/forge-apply-guard-dashboard"),
    }

    for name, data in payloads.items():
        (base / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    (base / "git.txt").write_text(_j93_git_snapshot(), encoding="utf-8")

    readme = [
        "# JARVIS Export Pack",
        "",
        "- Status real: local export pack",
        "- External calls: false",
        "- Commit/push/deploy: false",
        "- Secrets/env read: false",
        "",
        "## Files",
    ]

    for name in sorted(payloads):
        readme.append(f"- `{name}`")
    readme.append("- `git.txt`")
    readme.append("")
    readme.append("Use this pack to inspect local state without opening the cockpit UI.")

    (base / "README.md").write_text("\n".join(readme), encoding="utf-8")

    print("EXPORT_PACK_SAVED:", _j93_rel(base))
    for item in sorted(base.iterdir()):
        print("-", _j93_rel(item))

# === END JARVIS_CLI_BLOCK_93_BATCH_INTELLIGENCE ===



# === JARVIS_CLI_BLOCK_94_SESSION_CONTROL ===
# Session start/close/doctor/next-block commands.
# Local-only. No external calls. No .env. No commit/push/deploy.

def _j94_dir() -> Path:
    d = ROOT / "05_EXECUCAO" / "94_JARVIS_SESSION_CONTROL"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j94_sessions() -> Path:
    d = _j94_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j94_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _j94_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def _j94_brief_metrics() -> dict[str, Any]:
    brief = call_json("GET", "/jarvis-brief")
    health = call_json("GET", "/sources-health")
    src = brief.get("sources", {}) if brief.get("ok") else {}
    return {
        "brief_ok": brief.get("ok"),
        "health": src.get("health_status", health.get("health_status", "unknown")),
        "sources": src.get("total_sources", health.get("total_sources", 0)),
        "indexed": src.get("total_files_indexed", health.get("total_files_indexed", 0)),
        "sensitive_skipped": src.get("sensitive_skipped", health.get("sensitive_skipped", 0)),
        "large_files": src.get("large_files", health.get("large_files", 0)),
        "duplicate_groups": src.get("duplicate_groups", 0),
        "signals": brief.get("signals", health.get("signals", [])),
    }


def _j94_git_md() -> list[str]:
    return [
        "## Git",
        "```text",
        "branch: " + git(["branch", "--show-current"]),
        "head: " + git(["rev-parse", "--short", "HEAD"]),
        "",
        "last commits:",
        git(["log", "--oneline", "-5"]),
        "",
        "status:",
        git(["status", "--short"]) or "clean",
        "```",
        "",
    ]


def cmd_start(_: argparse.Namespace) -> None:
    m = _j94_brief_metrics()
    out = _j94_sessions() / f"session_start_{_j94_stamp()}.md"

    lines = [
        "# JARVIS Session Start",
        "",
        "- Status real: local session start",
        "- External calls: false",
        "- Commit/push/deploy: false",
        "",
    ]
    lines += _j94_git_md()
    lines += [
        "## System",
        f"- Brief OK: `{m['brief_ok']}`",
        f"- Health: `{m['health']}`",
        f"- Sources: `{m['sources']}`",
        f"- Indexed: `{m['indexed']}`",
        f"- Sensitive skipped: `{m['sensitive_skipped']}`",
        f"- Large files: `{m['large_files']}`",
        f"- Duplicate groups: `{m['duplicate_groups']}`",
        "",
        "## Recommended commands",
        "```bash",
        "./11_SCRIPTS/jarvis_quick.sh audit",
        "./11_SCRIPTS/jarvis_quick.sh daily",
        "./11_SCRIPTS/jarvis_quick.sh next-block",
        "```",
        "",
        "## Notes",
        "- Write what you want to build next before editing.",
        "- Keep commits small.",
        "- Do not push/deploy unless explicitly decided.",
        "",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")
    print("SESSION_START_SAVED:", _j94_rel(out))
    print("")
    print("\n".join(lines[:60]))


def cmd_close(args: argparse.Namespace) -> None:
    note = " ".join(args.note).strip() or "Session closed without manual note."
    m = _j94_brief_metrics()
    out = _j94_sessions() / f"session_close_{_j94_stamp()}.md"

    lines = [
        "# JARVIS Session Close",
        "",
        "- Status real: local session close",
        "- External calls: false",
        "- Commit/push/deploy: false",
        "",
        "## Human note",
        note,
        "",
    ]
    lines += _j94_git_md()
    lines += [
        "## Final system snapshot",
        f"- Health: `{m['health']}`",
        f"- Sources: `{m['sources']}`",
        f"- Indexed: `{m['indexed']}`",
        f"- Sensitive skipped: `{m['sensitive_skipped']}`",
        f"- Duplicate groups: `{m['duplicate_groups']}`",
        "",
        "## Next resume command",
        "```bash",
        "./11_SCRIPTS/jarvis_quick.sh start",
        "./11_SCRIPTS/jarvis_quick.sh daily",
        "```",
        "",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")
    print("SESSION_CLOSE_SAVED:", _j94_rel(out))
    print("")
    print("\n".join(lines[:70]))


def cmd_doctor(_: argparse.Namespace) -> None:
    checks = []
    checks.append(("git clean", not bool(git(["status", "--short"]))))
    checks.append(("api status", bool(call_json("GET", "/status").get("ok"))))
    checks.append(("brief endpoint", bool(call_json("GET", "/jarvis-brief").get("ok"))))
    checks.append(("sources health", bool(call_json("GET", "/sources-health").get("ok"))))
    checks.append(("sources insight", bool(call_json("GET", "/sources-insight").get("ok"))))
    checks.append(("apply guard", bool(call_json("GET", "/forge-apply-guard-dashboard").get("ok"))))

    compile_check = _j93_run_local_check("py_compile", [
        sys.executable,
        "-m",
        "py_compile",
        "11_SCRIPTS/jarvis_api.py",
        "11_SCRIPTS/jarvis_core.py",
        "11_SCRIPTS/jarvis_cli.py",
    ])
    checks.append(("py_compile", bool(compile_check.get("ok"))))

    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)

    print(f"JARVIS DOCTOR: {passed}/{total}")
    for name, ok in checks:
        print(("OK   " if ok else "WARN "), name)

    if passed != total:
        print("")
        print("Next safe step: run ./11_SCRIPTS/jarvis_quick.sh audit and inspect the generated report.")
    else:
        print("")
        print("System looks stable for local work.")


def cmd_next_block(_: argparse.Namespace) -> None:
    status = git(["status", "--short"])
    m = _j94_brief_metrics()

    candidates = [
        {
            "block": "95",
            "name": "Task Queue Runner",
            "why": "Run many requested local tasks as a queue without opening the UI.",
            "commands": ["queue-add", "queue-run", "queue-status"],
        },
        {
            "block": "96",
            "name": "Source Cleanup Advisor",
            "why": "Detect duplicate/backups/noisy files and produce cleanup suggestions without deleting anything.",
            "commands": ["cleanup-advice", "noise-map"],
        },
        {
            "block": "97",
            "name": "Feature Pack Generator",
            "why": "Generate ready implementation packages from one terminal command.",
            "commands": ["feature-pack"],
        },
    ]

    print("NEXT BLOCK RECOMMENDATION")
    print("- git:", "dirty" if status else "clean")
    print("- health:", m.get("health"))
    print("- sources:", m.get("sources"), "indexed:", m.get("indexed"))
    print("")
    print("Recommended: Block", candidates[0]["block"], "—", candidates[0]["name"])
    print("Why:", candidates[0]["why"])
    print("Commands:", ", ".join(candidates[0]["commands"]))
    print("")
    print("Other good options:")
    for c in candidates[1:]:
        print(f"- Block {c['block']} — {c['name']}: {c['why']}")

# === END JARVIS_CLI_BLOCK_94_SESSION_CONTROL ===



# === JARVIS_CLI_BLOCK_95_TASK_QUEUE_RUNNER ===
# Queue multiple local tasks and generate execution packages.
# Local-only. No external calls. No .env. No commit/push/deploy. No arbitrary shell.

def _j95_dir() -> Path:
    d = ROOT / "05_EXECUCAO" / "95_JARVIS_TASK_QUEUE_RUNNER"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j95_reports() -> Path:
    d = _j95_dir() / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j95_queue_file() -> Path:
    return _j95_dir() / "queue.json"


def _j95_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _j95_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def _j95_load() -> list[dict[str, Any]]:
    qf = _j95_queue_file()
    if not qf.exists():
        return []
    try:
        data = json.loads(qf.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _j95_save(items: list[dict[str, Any]]) -> None:
    qf = _j95_queue_file()
    qf.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _j95_next_id(items: list[dict[str, Any]]) -> int:
    ids = []
    for item in items:
        try:
            ids.append(int(item.get("id", 0)))
        except Exception:
            pass
    return (max(ids) + 1) if ids else 1


def _j95_classify(task: str) -> str:
    t = task.lower()
    if any(w in t for w in ["buscar", "search", "procurar", "fonte", "source"]):
        return "source_research"
    if any(w in t for w in ["audit", "auditar", "validar", "doctor", "check"]):
        return "local_audit"
    if any(w in t for w in ["feature", "criar", "build", "implementar", "adicionar"]):
        return "feature_package"
    if any(w in t for w in ["limpar", "cleanup", "duplicado", "backup", "noise"]):
        return "cleanup_advice"
    if any(w in t for w in ["resumo", "brief", "daily", "report"]):
        return "brief_report"
    return "general_task"


def _j95_keywords(task: str) -> list[str]:
    raw = []
    for part in task.replace(",", " ").replace(";", " ").replace("/", " ").split():
        word = "".join(ch for ch in part.lower() if ch.isalnum() or ch in "-_")
        if len(word) >= 4 and word not in {"para", "com", "que", "uma", "esse", "isso", "criar", "fazer"}:
            raw.append(word)
    out = []
    for w in raw:
        if w not in out:
            out.append(w)
    return out[:5]


def _j95_report_for_task(item: dict[str, Any]) -> Path:
    task = str(item.get("task", "")).strip()
    kind = str(item.get("type", "general_task"))
    metrics = _j94_brief_metrics() if "_j94_brief_metrics" in globals() else {}
    search_terms = _j95_keywords(task)

    lines = [
        f"# JARVIS Queue Task #{item.get('id')} — {task}",
        "",
        "- Status real: local queue package",
        "- External calls: false",
        "- Commit/push/deploy: false",
        "- Arbitrary shell: false",
        f"- Task type: `{kind}`",
        "",
        "## Git snapshot",
        "```text",
        _j93_git_snapshot() if "_j93_git_snapshot" in globals() else (git(["status", "--short"]) or "clean"),
        "```",
        "",
        "## System snapshot",
        f"- Health: `{metrics.get('health', 'unknown')}`",
        f"- Sources: `{metrics.get('sources', 0)}`",
        f"- Indexed: `{metrics.get('indexed', 0)}`",
        f"- Sensitive skipped: `{metrics.get('sensitive_skipped', 0)}`",
        "",
        "## Execution plan",
    ]

    if kind == "feature_package":
        lines += [
            "1. Clarify expected behavior.",
            "2. Identify if this is CLI, API, UI, source, or automation work.",
            "3. Prefer one local deterministic patch.",
            "4. Validate with py_compile and existing endpoints.",
            "5. Commit only after clean local evidence.",
        ]
    elif kind == "source_research":
        lines += [
            "1. Search local sources first.",
            "2. Use only allow-listed source endpoints.",
            "3. Summarize findings with paths and snippets.",
            "4. Do not read .env or sensitive paths.",
        ]
    elif kind == "cleanup_advice":
        lines += [
            "1. Detect duplicate/noisy/backups only.",
            "2. Produce advice report.",
            "3. Do not delete anything.",
            "4. Require human approval before any cleanup.",
        ]
    elif kind == "local_audit":
        lines += [
            "1. Run local audit command.",
            "2. Check API, sources, compile, and guard status.",
            "3. Save report under 05_EXECUCAO.",
        ]
    else:
        lines += [
            "1. Convert task into a safe local package.",
            "2. Use existing JARVIS endpoints.",
            "3. Avoid broad repo changes.",
            "4. Keep status real.",
        ]

    lines += [
        "",
        "## Local source search hints",
    ]

    if not search_terms:
        lines.append("- No strong search term extracted.")
    else:
        for term in search_terms:
            data = call_json("GET", "/sources-search?q=" + urllib.parse.quote(term) + "&limit=3")
            lines.append(f"### `{term}`")
            lines.append(f"- Count: `{data.get('count')}`")
            for r in data.get("results", [])[:3]:
                lines.append(f"- `{r.get('path', '')}` — {r.get('category', '')} — {r.get('size_human', '')}")
            lines.append("")

    lines += [
        "## Safe next command",
        "```bash",
        "./11_SCRIPTS/jarvis_quick.sh audit",
        "```",
        "",
        "Status real: report generated only. No implementation was applied.",
        "",
    ]

    out = _j95_reports() / f"queue_task_{item.get('id')}_{_j95_stamp()}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def cmd_queue_add(args: argparse.Namespace) -> None:
    task = " ".join(args.task).strip()
    if not task:
        print('Usage: ./11_SCRIPTS/jarvis_quick.sh queue-add "task description"')
        return

    items = _j95_load()
    item = {
        "id": _j95_next_id(items),
        "task": task,
        "type": _j95_classify(task),
        "status": "pending",
        "created_at": _j95_stamp(),
        "updated_at": _j95_stamp(),
        "report": "",
    }
    items.append(item)
    _j95_save(items)

    print("QUEUE_ADDED:", item["id"])
    print("type:", item["type"])
    print("task:", item["task"])


def cmd_queue_status(_: argparse.Namespace) -> None:
    items = _j95_load()
    pending = [x for x in items if x.get("status") == "pending"]
    done = [x for x in items if x.get("status") == "done"]
    failed = [x for x in items if x.get("status") == "failed"]

    print("JARVIS TASK QUEUE")
    print("- total:", len(items))
    print("- pending:", len(pending))
    print("- done:", len(done))
    print("- failed:", len(failed))
    print("- file:", _j95_rel(_j95_queue_file()))

    for item in items[-12:]:
        print(f"#{item.get('id')} [{item.get('status')}] {item.get('type')} — {item.get('task')}")
        if item.get("report"):
            print("   report:", item.get("report"))


def cmd_queue_list(_: argparse.Namespace) -> None:
    items = _j95_load()
    if not items:
        print("QUEUE_EMPTY")
        return
    for item in items:
        print(f"#{item.get('id')} [{item.get('status')}] {item.get('type')}")
        print("  task:", item.get("task"))
        if item.get("report"):
            print("  report:", item.get("report"))


def cmd_queue_run(args: argparse.Namespace) -> None:
    items = _j95_load()
    pending = [x for x in items if x.get("status") == "pending"]
    limit = max(1, int(args.limit or 1))
    selected = pending[:limit]

    if not selected:
        print("NO_PENDING_TASKS")
        return

    print("RUNNING_QUEUE_TASKS:", len(selected))

    by_id = {x.get("id"): x for x in items}
    for item in selected:
        try:
            report = _j95_report_for_task(item)
            current = by_id.get(item.get("id"), item)
            current["status"] = "done"
            current["updated_at"] = _j95_stamp()
            current["report"] = _j95_rel(report)
            print(f"OK #{item.get('id')} -> {_j95_rel(report)}")
        except Exception as exc:
            current = by_id.get(item.get("id"), item)
            current["status"] = "failed"
            current["updated_at"] = _j95_stamp()
            current["error"] = str(exc)
            print(f"FAIL #{item.get('id')}: {exc}")

    _j95_save(items)


def cmd_queue_clear_done(_: argparse.Namespace) -> None:
    items = _j95_load()
    kept = [x for x in items if x.get("status") != "done"]
    removed = len(items) - len(kept)
    _j95_save(kept)
    print("CLEARED_DONE:", removed)
    print("remaining:", len(kept))

# === END JARVIS_CLI_BLOCK_95_TASK_QUEUE_RUNNER ===



# === JARVIS_CLI_BLOCK_96_ULTRA_OPERATOR_SUITE ===
# Terminal-first operator suite: feature-pack, cleanup-advice, repo-map,
# diff-review, queue-pack, mission, ultra, open-latest.
# Local-only. No external calls. No .env/secrets read. No commit/push/deploy.
# No file deletion. No arbitrary shell. Git is read-only via allow-list.
# Reuses call_json, git, ROOT, Path, datetime, json, urllib.parse, subprocess.

J96_BLOCK = "96_JARVIS_ULTRA_OPERATOR_SUITE"

# Directories never descended into during local scans.
_J96_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".next", "dist", "build", ".cache", ".mypy_cache", ".pytest_cache",
    ".idea", ".vscode", ".turbo", ".parcel-cache", "coverage", ".terraform",
    ".gradle", ".tox", "site-packages",
}

# Credential/secret directories never descended into (paths inside them must
# never be surfaced, even though we only ever stat — never open — files).
_J96_SENSITIVE_DIRS = {
    ".ssh", ".aws", ".gnupg", ".gpg", ".config", ".docker", ".kube",
    ".gcloud", ".azure", ".cabal", ".password-store", "secrets", ".secrets",
}

# Filename fragments that mark sensitive files we must never open or surface.
_J96_SENSITIVE = (
    ".env", "secret", "token", "credential", "cookie", "password",
    "id_rsa", "id_ed25519", ".pem", ".key", ".keystore", ".p12", ".pfx", ".crt",
)

# Extensions / names treated as noise.
_J96_NOISE_EXT = {".log", ".tmp", ".temp", ".cache", ".pyc", ".pyo", ".swp", ".swo", ".lock"}
_J96_NOISE_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}

# Backup-looking suffixes.
_J96_BACKUP_HINTS = (".bak", ".backup", ".old", ".orig", "~", ".save")

# Files that must be kept (core of the system).
_J96_KEEP_CORE = {
    "11_SCRIPTS/jarvis_cli.py",
    "11_SCRIPTS/jarvis_api.py",
    "11_SCRIPTS/jarvis_core.py",
    "11_SCRIPTS/jarvis_quick.sh",
    "11_SCRIPTS/jarvis_ui_assets/cockpit.html",
}

# Core files whose modification raises diff-review risk.
_J96_CORE_FILES = {
    "11_SCRIPTS/jarvis_cli.py",
    "11_SCRIPTS/jarvis_api.py",
    "11_SCRIPTS/jarvis_core.py",
    "11_SCRIPTS/jarvis_ui_assets/cockpit.html",
}

_J96_LARGE_BYTES = 5 * 1024 * 1024      # 5 MB
_J96_OLD_DAYS = 45                       # old execution-artifact threshold (days)
_J96_MAX_SCAN = 60000                    # hard cap on files walked

_J96_WALK_CACHE: list[dict[str, Any]] | None = None


def _j96_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _j96_dir() -> Path:
    d = ROOT / "05_EXECUCAO" / J96_BLOCK
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j96_sub(name: str) -> Path:
    d = _j96_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _j96_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def _j96_write(subdir: str, prefix: str, content: str) -> Path:
    folder = _j96_sub(subdir)
    stamp = _j96_stamp()
    out = folder / f"{prefix}_{stamp}.md"
    n = 2
    while out.exists():  # never silently overwrite a same-second rerun
        out = folder / f"{prefix}_{stamp}_{n}.md"
        n += 1
    out.write_text(content, encoding="utf-8")
    return out


def _j96_human_size(num: float) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _j96_safety_lines() -> list[str]:
    return [
        "- Scope: local only",
        "- External calls: false",
        "- Commit/push/deploy: false",
        "- File deletion: false",
        "- .env / secrets read: false",
    ]


def _j96_git(args: list[str]) -> str:
    """Read-only git via an explicit allow-list (adds diff inspection)."""
    allowed = {
        ("status", "--short"),
        ("branch", "--show-current"),
        ("rev-parse", "--short", "HEAD"),
        ("log", "--oneline", "-5"),
        ("log", "--oneline", "-10"),
        ("diff", "--stat"),
        ("diff", "--shortstat"),
        ("diff", "--name-only"),
        ("diff", "--name-status"),
        ("diff", "--cached", "--stat"),
        ("diff", "--cached", "--shortstat"),
        ("diff", "--cached", "--name-status"),
    }
    tup = tuple(args)
    if tup not in allowed:
        return "blocked_git_command"
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or r.stderr or "").strip()
    except Exception as exc:
        return f"git_error: {exc}"


def _j96_git_snapshot() -> str:
    if "_j93_git_snapshot" in globals():
        return _j93_git_snapshot()
    return "\n".join([
        "branch: " + git(["branch", "--show-current"]),
        "head: " + git(["rev-parse", "--short", "HEAD"]),
        "",
        "last commits:",
        git(["log", "--oneline", "-5"]),
        "",
        "status:",
        git(["status", "--short"]) or "clean",
    ])


def _j96_metrics() -> dict[str, Any]:
    if "_j94_brief_metrics" in globals():
        return _j94_brief_metrics()
    brief = call_json("GET", "/jarvis-brief")
    health = call_json("GET", "/sources-health")
    src = brief.get("sources", {}) if brief.get("ok") else {}
    return {
        "brief_ok": brief.get("ok"),
        "health": src.get("health_status", health.get("health_status", "unknown")),
        "sources": src.get("total_sources", health.get("total_sources", 0)),
        "indexed": src.get("total_files_indexed", health.get("total_files_indexed", 0)),
        "sensitive_skipped": src.get("sensitive_skipped", health.get("sensitive_skipped", 0)),
        "large_files": src.get("large_files", health.get("large_files", 0)),
        "duplicate_groups": src.get("duplicate_groups", 0),
        "signals": brief.get("signals", []),
    }


def _j96_health_md() -> list[str]:
    m = _j96_metrics()
    return [
        f"- Brief OK: `{m.get('brief_ok')}`",
        f"- Health: `{m.get('health')}`",
        f"- Sources: `{m.get('sources')}`",
        f"- Indexed: `{m.get('indexed')}`",
        f"- Sensitive skipped: `{m.get('sensitive_skipped')}`",
        f"- Large files (reported): `{m.get('large_files')}`",
        f"- Duplicate groups (reported): `{m.get('duplicate_groups')}`",
    ]


def _j96_keywords(text: str) -> list[str]:
    if "_j95_keywords" in globals():
        return _j95_keywords(text)
    out: list[str] = []
    for part in text.replace(",", " ").replace(";", " ").replace("/", " ").split():
        w = "".join(ch for ch in part.lower() if ch.isalnum() or ch in "-_")
        if len(w) >= 4 and w not in out:
            out.append(w)
    return out[:5]


def _j96_infer_type(idea: str) -> str:
    t = idea.lower()
    table = [
        ("cleanup", ["cleanup", "limpar", "limpeza", "duplicad", "backup", "noise",
                     "noisy", "declutter", "deletar", "delete", "remov"]),
        ("audit", ["audit", "auditar", "validar", "validate", "doctor", "check",
                   "verif", "smoke", " test", "teste"]),
        ("ui", ["ui", "cockpit", "interface", "frontend", "front-end", "html", "css",
                "visual", "tela", "dashboard", "layout", "painel"]),
        ("api", ["api", "endpoint", "rota", "route", "backend", "server", "webhook"]),
        ("source", ["source", "fonte", "fontes", "index", "indexar", "search",
                    "busca", "buscar", "embedding"]),
        ("cli", ["cli", "command", "comando", "comandos", "terminal", "script",
                 "runner", "queue", "fila", "operator", "operador"]),
    ]
    for label, hints in table:
        if any(h in t for h in hints):
            return label
    return "general"


def _j96_likely_files(ftype: str) -> list[str]:
    base = {
        "cli": ["11_SCRIPTS/jarvis_cli.py",
                "11_SCRIPTS/jarvis_quick.sh (only if a new wrapper is truly needed)"],
        "api": ["11_SCRIPTS/jarvis_api.py",
                "11_SCRIPTS/jarvis_cli.py (to expose a terminal command)"],
        "ui": ["11_SCRIPTS/jarvis_ui_assets/cockpit.html",
               "11_SCRIPTS/jarvis_api.py (only if new data is required)"],
        "source": ["11_SCRIPTS/jarvis_core.py",
                   "11_SCRIPTS/jarvis_api.py (if a new source endpoint is needed)",
                   "11_SCRIPTS/jarvis_cli.py (terminal access)"],
        "cleanup": ["11_SCRIPTS/jarvis_cli.py (advisory only — never deletes)"],
        "audit": ["11_SCRIPTS/jarvis_cli.py (add/extend an audit command)"],
        "general": ["11_SCRIPTS/jarvis_cli.py"],
    }
    return base.get(ftype, base["general"])


def _j96_architecture(ftype: str, idea: str) -> list[str]:
    common = [
        "- Add work inside a clearly marked CLI block, reusing `call_json`, `git`, `ROOT`, `Path`.",
        "- Keep every action local and deterministic; write reports under `05_EXECUCAO/<block>/`.",
        "- Guard cross-block helper reuse with `globals()` checks (same pattern as blocks 93-95).",
    ]
    specific = {
        "cli": ["- New `cmd_*` function + `build_parser()` subparser + a line in `cmd_routes`."],
        "api": ["- New read-only route in `jarvis_api.py`, surfaced through a CLI command via `call_json`."],
        "ui": ["- Extend `cockpit.html` with a panel bound to an existing endpoint; keep the locked AI-OS look."],
        "source": ["- Extend source indexing/search in `jarvis_core.py`; keep sensitive-path skipping intact."],
        "cleanup": ["- Pure advisory scan over allow-listed paths; classify by name/size/mtime only; never open or delete files."],
        "audit": ["- Compose existing endpoint checks + `py_compile`; emit a pass/fail report."],
        "general": ["- Wrap the idea into a safe local command that produces a markdown package."],
    }
    return specific.get(ftype, specific["general"]) + common


def _j96_impl_plan(ftype: str) -> list[str]:
    tail = [
        "4. Run the validation commands below; capture real output.",
        "5. Only commit after clean local evidence (no push/deploy).",
    ]
    head = {
        "cli": [
            "1. Add a marked CLI block in `jarvis_cli.py` with `_jNN_` helpers.",
            "2. Implement `cmd_*`, register a subparser, add a `cmd_routes` line.",
            "3. Reuse `call_json`, `git`, `ROOT`, `Path`; write reports under `05_EXECUCAO`.",
        ],
        "api": [
            "1. Add a read-only route in `jarvis_api.py` returning JSON with `ok` + `status_real`.",
            "2. Keep sensitive paths skipped; expose no secret/env data.",
            "3. Surface it through a CLI command using `call_json`.",
        ],
        "ui": [
            "1. Add a cockpit panel in `cockpit.html` bound to an existing endpoint.",
            "2. Preserve the locked premium AI-OS look (no dashboard/landing drift).",
            "3. Avoid new build tooling; keep it static + fetch-based.",
        ],
        "source": [
            "1. Extend indexing/search in `jarvis_core.py`, keeping sensitive-skip rules.",
            "2. Expose results via an existing or new read-only endpoint.",
            "3. Add terminal access via `jarvis_cli.py`.",
        ],
        "cleanup": [
            "1. Scan allow-listed paths by name/size/mtime only (never open contents).",
            "2. Classify and report; never delete or move files.",
            "3. Require explicit human action for any removal.",
        ],
        "audit": [
            "1. Compose endpoint checks + `py_compile` into one command.",
            "2. Emit a pass/fail markdown report under `05_EXECUCAO`.",
            "3. Keep it idempotent and side-effect free.",
        ],
        "general": [
            "1. Translate the idea into a safe local command.",
            "2. Reuse existing endpoints/helpers; avoid broad repo changes.",
            "3. Produce a markdown package as output.",
        ],
    }
    return head.get(ftype, head["general"]) + tail


def _j96_acceptance(ftype: str) -> list[str]:
    base = [
        "- [ ] `python3 -m py_compile` passes for cli/api/core.",
        "- [ ] `./11_SCRIPTS/jarvis_quick.sh routes` lists the new command.",
        "- [ ] All existing commands still work.",
        "- [ ] Output is clean and the status shown is real.",
        "- [ ] No external calls, no .env read, no deletion, no commit/push/deploy.",
    ]
    extra = {
        "ui": ["- [ ] Cockpit still loads and matches the locked look."],
        "api": ["- [ ] New endpoint returns `ok:true` locally."],
        "cleanup": ["- [ ] Report states clearly that no files were deleted."],
        "source": ["- [ ] Sensitive paths remain skipped in results."],
    }
    return base + extra.get(ftype, [])


def _j96_validation_cmds(ftype: str) -> list[str]:
    cmds = [
        "python3 -m py_compile 11_SCRIPTS/jarvis_cli.py 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py",
        "./11_SCRIPTS/jarvis_quick.sh routes",
        "./11_SCRIPTS/jarvis_quick.sh doctor",
    ]
    if ftype in {"source", "api"}:
        cmds += ["./11_SCRIPTS/jarvis_quick.sh health", "./11_SCRIPTS/jarvis_quick.sh insight"]
    if ftype == "cleanup":
        cmds.append("./11_SCRIPTS/jarvis_quick.sh cleanup-advice | head -120")
    return cmds


def _j96_safety_gates(ftype: str) -> list[str]:
    gates = [
        "- No push, no deploy, no commit performed by tooling.",
        "- No `.env`, secrets, tokens, cookies, or private keys are read.",
        "- No file deletion; advisory only.",
        "- No arbitrary shell; git is read-only via an allow-list.",
        "- No new dependencies, no node_modules, no package managers.",
    ]
    if ftype == "cleanup":
        gates.append("- Cleanup is advisory: a human must delete manually if desired.")
    if ftype == "ui":
        gates.append("- Cockpit edits must not break the existing locked UI.")
    return gates


def _j96_claude_verdict(ftype: str) -> list[str]:
    if ftype in {"cleanup", "audit"}:
        verdict, reason = ("Optional", "Mostly deterministic local analysis; use Claude for the initial scaffold, then run it yourself.")
    elif ftype in {"api", "ui", "source"}:
        verdict, reason = ("Yes", "Touches backend/UI/source logic with integration surface — worth an extra Claude pass for design + review.")
    else:
        verdict, reason = ("Yes (light)", "A single focused Claude pass should produce the command; keep iterations small.")
    return [f"- Verdict: **{verdict}**", f"- Reason: {reason}"]


def _j96_commit_suggestion(idea: str) -> str:
    short = " ".join(idea.split()[:9]).strip().rstrip(".").lower()
    return f"feat: {short or 'jarvis operator improvement'}"


def _j96_source_search_md(terms: list[str], limit: int = 3) -> list[str]:
    if not terms:
        return ["- No strong search term extracted from the idea.", ""]
    lines: list[str] = []
    for term in terms:
        data = call_json("GET", "/sources-search?q=" + urllib.parse.quote(term) + f"&limit={limit}")
        lines.append(f"### `{term}`")
        lines.append(f"- Count: `{data.get('count', 0)}` | Returned: `{data.get('returned', 0)}`")
        for r in data.get("results", [])[:limit]:
            lines.append(f"- `{r.get('path', '')}` — {r.get('category', '')} — {r.get('size_human', '')}")
        lines.append("")
    return lines


def _j96_is_sensitive(name_lower: str) -> bool:
    return any(frag in name_lower for frag in _J96_SENSITIVE)


def _j96_walk(max_files: int = _J96_MAX_SCAN) -> list[dict[str, Any]]:
    """Safe metadata-only walk under ROOT. Never opens file contents.
    Skips heavy/internal dirs and sensitive-looking filenames. Cached per run."""
    global _J96_WALK_CACHE
    if _J96_WALK_CACHE is not None:
        return _J96_WALK_CACHE
    import os
    files: list[dict[str, Any]] = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d for d in dirnames
            if d.lower() not in _J96_SKIP_DIRS
            and d.lower() not in _J96_SENSITIVE_DIRS
            and not d.startswith(".git")
            and not _j96_is_sensitive(d.lower())
        ]
        for fn in filenames:
            name_lower = fn.lower()
            if _j96_is_sensitive(name_lower):
                continue  # never surface sensitive files
            full = Path(dirpath) / fn
            try:
                st = full.stat()
            except Exception:
                continue
            files.append({
                "rel": _j96_rel(full),
                "name": fn,
                "ext": full.suffix.lower(),
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
            count += 1
            if count >= max_files:
                _J96_WALK_CACHE = files
                return files
    _J96_WALK_CACHE = files
    return files


# --- feature-pack ---------------------------------------------------------

def _j96_build_feature_pack(idea: str) -> tuple[Path, dict[str, Any]]:
    ftype = _j96_infer_type(idea)
    terms = _j96_keywords(idea)

    lines = [
        f"# JARVIS Feature Pack — {idea}",
        "",
        "## Scope & safety",
    ] + _j96_safety_lines() + [
        "",
        "## Goal",
        idea,
        "",
        "## Inferred feature type",
        f"- Type: `{ftype}`  (one of: cli / api / ui / source / cleanup / audit / general)",
        "",
        "## Current Git snapshot",
        "```text",
        _j96_git_snapshot(),
        "```",
        "",
        "## Current JARVIS health snapshot",
    ] + _j96_health_md() + [
        "",
        "## Likely files to edit",
    ] + [f"- `{p}`" for p in _j96_likely_files(ftype)] + [
        "",
        "## Local source search results",
    ] + _j96_source_search_md(terms) + [
        "## Architecture",
    ] + _j96_architecture(ftype, idea) + [
        "",
        "## Implementation plan",
    ] + _j96_impl_plan(ftype) + [
        "",
        "## Acceptance criteria",
    ] + _j96_acceptance(ftype) + [
        "",
        "## Validation commands",
        "```bash",
    ] + _j96_validation_cmds(ftype) + [
        "```",
        "",
        "## Safety gates",
    ] + _j96_safety_gates(ftype) + [
        "",
        "## Is Claude worth using again?",
    ] + _j96_claude_verdict(ftype) + [
        "",
        "## Suggested commit message",
        "```text",
        _j96_commit_suggestion(idea),
        "```",
        "",
        "_No files were changed. This is an advisory implementation package only._",
        "",
    ]
    out = _j96_write("feature_packs", "feature_pack", "\n".join(lines))
    return out, {"type": ftype, "terms": terms, "path": _j96_rel(out)}


def cmd_feature_pack(args: argparse.Namespace) -> None:
    idea = " ".join(args.idea).strip()
    if not idea:
        print('Usage: ./11_SCRIPTS/jarvis_quick.sh feature-pack "feature idea"')
        return
    out, info = _j96_build_feature_pack(idea)
    print("FEATURE_PACK_SAVED:", _j96_rel(out))
    print("- type:", info["type"])
    print("- terms:", ", ".join(info["terms"]) or "(none)")
    print("- likely files:", ", ".join(_j96_likely_files(info["type"])[:2]))
    print("")
    print("No files were changed. Advisory implementation package only.")


# --- cleanup-advice -------------------------------------------------------

def _j96_build_cleanup_advice() -> tuple[Path, dict[str, Any]]:
    import re
    files = _j96_walk()
    now = datetime.now().timestamp()
    old_cutoff = _J96_OLD_DAYS * 86400

    backups: list[dict[str, Any]] = []
    noise: list[dict[str, Any]] = []
    large: list[dict[str, Any]] = []
    old_artifacts: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    keep_present: list[str] = []
    report_groups: dict[tuple[str, str], list[str]] = {}

    for f in files:
        rel = f["rel"]
        name_l = f["name"].lower()
        ext = f["ext"]
        size = f["size"]
        age = now - f["mtime"]
        in_exec = rel.startswith("05_EXECUCAO/") or rel.startswith("09_LOGS/")

        if rel in _J96_KEEP_CORE:
            keep_present.append(rel)

        is_backup = (
            any(name_l.endswith(h) for h in _J96_BACKUP_HINTS)
            or ".bak" in name_l
            or "backup" in name_l
            or name_l.endswith(" copy")
            or " copy." in name_l
        )
        if is_backup:
            backups.append(f)
            continue
        if ext in _J96_NOISE_EXT or name_l in _J96_NOISE_NAMES:
            noise.append(f)
            continue

        if size >= _J96_LARGE_BYTES:
            large.append(f)
            if rel not in _J96_KEEP_CORE:
                review.append({**f, "why": "large file — confirm it is still needed"})
        if in_exec and age > old_cutoff:
            old_artifacts.append(f)

        if ext == ".md" and in_exec:
            parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
            stem = re.sub(r"\.[A-Za-z0-9]+$", "", f["name"])
            stem = re.sub(r"[_-]?\d{4}-\d{2}-\d{2}[_-]\d{2}-\d{2}-\d{2}$", "", stem)
            stem = re.sub(r"[_-]?\d{4}-\d{2}-\d{2}$", "", stem)
            key = (parent, stem.strip("_- ").lower())
            report_groups.setdefault(key, []).append(rel)

    dup_flagged = {k: v for k, v in report_groups.items() if len(v) >= 3}

    backups.sort(key=lambda x: x["size"], reverse=True)
    large.sort(key=lambda x: x["size"], reverse=True)
    noise.sort(key=lambda x: x["size"], reverse=True)
    old_artifacts.sort(key=lambda x: x["mtime"])

    def block(title: str, items: list[dict[str, Any]], fmt) -> list[str]:
        out_lines = [f"## {title}"]
        if not items:
            out_lines.append("- None found.")
        else:
            for it in items[:40]:
                out_lines.append(fmt(it))
            if len(items) > 40:
                out_lines.append(f"- … and {len(items) - 40} more.")
        out_lines.append("")
        return out_lines

    lines = [
        "# JARVIS Cleanup Advice",
        "",
        "## Scope & safety",
    ] + _j96_safety_lines() + [
        "",
        "> **No files were deleted. This is advisory only.**",
        "",
        "## Summary",
        f"- Files scanned (safe set): `{len(files)}`",
        f"- Backup-looking files: `{len(backups)}`",
        f"- Noise candidates: `{len(noise)}`",
        f"- Large files (>= {_j96_human_size(_J96_LARGE_BYTES)}): `{len(large)}`",
        f"- Old execution artifacts (> {_J96_OLD_DAYS}d): `{len(old_artifacts)}`",
        f"- Duplicate-looking report groups: `{len(dup_flagged)}`",
        "",
    ]

    lines += block("Backup files", backups,
                    lambda x: f"- `{x['rel']}` — {_j96_human_size(x['size'])}")

    lines.append("## Duplicate-looking reports")
    if not dup_flagged:
        lines.append("- None found.")
    else:
        for (parent, stem), members in sorted(dup_flagged.items(),
                                              key=lambda kv: len(kv[1]), reverse=True)[:25]:
            lines.append(f"- `{parent}/` — `{stem or '(report)'}` × {len(members)} variants")
            for mrel in sorted(members)[-3:]:
                lines.append(f"    - `{mrel}`")
    lines.append("")

    lines += block("Old execution artifacts", old_artifacts,
                    lambda x: f"- `{x['rel']}` — {_j96_human_size(x['size'])} — ~{int((now - x['mtime']) / 86400)}d old")
    lines += block("Large files", large,
                    lambda x: f"- `{x['rel']}` — {_j96_human_size(x['size'])}")
    lines += block("Noise candidates", noise,
                    lambda x: f"- `{x['rel']}` — {_j96_human_size(x['size'])}")

    lines.append("## Files that must be kept")
    if keep_present:
        for k in sorted(set(keep_present)):
            lines.append(f"- `{k}`")
    else:
        lines.append("- Core files not found in scan (unexpected) — verify manually.")
    lines.append("- Also keep: anything under `.git/` and real source data you still use.")
    lines.append("")

    lines.append("## Files requiring human review")
    if not review:
        lines.append("- None flagged.")
    else:
        seen: set[str] = set()
        shown = 0
        for it in review:
            if it["rel"] in seen:
                continue
            seen.add(it["rel"])
            lines.append(f"- `{it['rel']}` — {it.get('why', 'review')}")
            shown += 1
            if shown >= 30:
                break
    lines.append("")

    lines += [
        "## Suggested (manual) next steps",
        "1. Review the backup / noise lists above.",
        "2. Manually delete only what you recognize as safe — JARVIS will not do it for you.",
        "3. Re-run `./11_SCRIPTS/jarvis_quick.sh cleanup-advice` to confirm.",
        "",
        "_No files were deleted. This is advisory only._",
        "",
    ]

    out = _j96_write("cleanup_advice", "cleanup_advice", "\n".join(lines))
    return out, {
        "scanned": len(files), "backups": len(backups), "noise": len(noise),
        "large": len(large), "old": len(old_artifacts), "dup_groups": len(dup_flagged),
        "path": _j96_rel(out),
    }


def cmd_cleanup_advice(_: argparse.Namespace) -> None:
    out, info = _j96_build_cleanup_advice()
    print("CLEANUP_ADVICE_SAVED:", _j96_rel(out))
    print(f"- scanned: {info['scanned']} files")
    print(f"- backups: {info['backups']} | noise: {info['noise']} | large: {info['large']} | "
          f"old: {info['old']} | dup groups: {info['dup_groups']}")
    print("")
    print("No files were deleted. This is advisory only.")


# --- repo-map -------------------------------------------------------------

def _j96_build_repo_map() -> tuple[Path, dict[str, Any]]:
    files = _j96_walk()

    def top_level(rel: str) -> str:
        return rel.split("/", 1)[0] if "/" in rel else rel

    core_scripts = sorted(
        f["rel"] for f in files
        if f["rel"].startswith("11_SCRIPTS/")
        and f["ext"] in {".py", ".sh"}
        and "/_ARCHIVE/" not in f["rel"]
        and not f["name"].lower().endswith(".bak")
        and f["rel"].count("/") == 1
    )
    ui_assets = sorted(
        f["rel"] for f in files
        if f["rel"].startswith("11_SCRIPTS/jarvis_ui_assets/")
        and not f["name"].lower().endswith(".bak")
    )

    exec_counts: dict[str, int] = {}
    report_md = 0
    for f in files:
        if f["rel"].startswith("05_EXECUCAO/"):
            parts = f["rel"].split("/")
            if len(parts) >= 2:
                exec_counts[parts[1]] = exec_counts.get(parts[1], 0) + 1
            if f["ext"] == ".md":
                report_md += 1

    largest = sorted(files, key=lambda x: x["size"], reverse=True)[:12]
    recent = sorted(files, key=lambda x: x["mtime"], reverse=True)[:12]

    tl_counts: dict[str, int] = {}
    for f in files:
        tl = top_level(f["rel"])
        tl_counts[tl] = tl_counts.get(tl, 0) + 1
    source_roots = sorted(tl_counts.items(), key=lambda kv: kv[1], reverse=True)[:12]

    backups_n = sum(
        1 for f in files
        if f["name"].lower().endswith(".bak")
        or any(f["name"].lower().endswith(h) for h in _J96_BACKUP_HINTS)
    )
    large_n = sum(1 for f in files if f["size"] >= _J96_LARGE_BYTES)
    noise_n = sum(1 for f in files if f["ext"] in _J96_NOISE_EXT)

    area_desc = {
        "11_SCRIPTS": "Core CLI/API/automation scripts (jarvis_cli.py, jarvis_api.py, jarvis_core.py) + UI assets.",
        "05_EXECUCAO": "Generated execution artifacts and per-block reports.",
        "02_SOURCES": "Local knowledge/source files indexed by JARVIS.",
        "04_PROJETOS": "Project working files.",
        "03_MEMORIA": "Memory/state files.",
        "06_PROMPTS": "Prompt templates.",
        "07_RELATORIOS": "Higher-level reports.",
        "01_SISTEMA": "System configuration and docs.",
        "08_REFERENCIAS": "Reference material.",
        "09_LOGS": "Local logs.",
        "10_TESTES": "Tests.",
        "99_ARQUIVO_MORTO": "Archived/dead files — candidate for review.",
    }

    lines = [
        "# JARVIS Repo Map",
        "",
        "## Scope & safety",
    ] + _j96_safety_lines() + [
        "",
        "## Summary",
        f"- Files scanned (safe set): `{len(files)}`",
        f"- Core scripts (11_SCRIPTS/*.py|sh): `{len(core_scripts)}`",
        f"- UI assets: `{len(ui_assets)}`",
        f"- 05_EXECUCAO subfolders: `{len(exec_counts)}`",
        f"- Generated reports (.md under 05_EXECUCAO): `{report_md}`",
        "",
        "## Core scripts",
    ]
    for p in core_scripts[:40]:
        lines.append(f"- `{p}`")
    if len(core_scripts) > 40:
        lines.append(f"- … and {len(core_scripts) - 40} more.")

    lines += ["", "## UI assets"]
    if ui_assets:
        for p in ui_assets[:30]:
            lines.append(f"- `{p}`")
    else:
        lines.append("- None found.")

    lines += ["", "## Execution folders (05_EXECUCAO)"]
    for name, c in sorted(exec_counts.items()):
        lines.append(f"- `05_EXECUCAO/{name}/` — {c} file(s)")

    lines += ["", "## Likely source roots (by file count)"]
    for name, c in source_roots:
        desc = area_desc.get(name, "")
        lines.append(f"- `{name}/` — {c} file(s)" + (f" — {desc}" if desc else ""))

    lines += ["", "## Largest files"]
    for f in largest:
        lines.append(f"- `{f['rel']}` — {_j96_human_size(f['size'])}")

    lines += ["", "## Recent files"]
    for f in recent:
        lines.append(f"- `{f['rel']}`")

    lines += [
        "",
        "## Risks / noise",
        f"- Backup-looking files: `{backups_n}`",
        f"- Large files (>= {_j96_human_size(_J96_LARGE_BYTES)}): `{large_n}`",
        f"- Noise files (logs/tmp/etc.): `{noise_n}`",
        "- See `cleanup-advice` for an advisory breakdown (no deletion).",
        "",
        "## What each important area does",
    ]
    for name in sorted(set(list(area_desc.keys()) + [n for n, _ in source_roots])):
        if name in area_desc:
            lines.append(f"- `{name}/` — {area_desc[name]}")

    lines += ["", "_No files were changed or deleted. Local only._", ""]

    out = _j96_write("repo_maps", "repo_map", "\n".join(lines))
    return out, {
        "files": len(files), "core": len(core_scripts),
        "exec_folders": len(exec_counts), "reports": report_md, "path": _j96_rel(out),
    }


def cmd_repo_map(_: argparse.Namespace) -> None:
    out, info = _j96_build_repo_map()
    print("REPO_MAP_SAVED:", _j96_rel(out))
    print(f"- files: {info['files']} | core scripts: {info['core']} | "
          f"exec folders: {info['exec_folders']} | reports: {info['reports']}")


# --- diff-review ----------------------------------------------------------

def _j96_build_diff_review() -> tuple[Path, dict[str, Any]]:
    import re
    status = _j96_git(["status", "--short"])
    stat = _j96_git(["diff", "--stat"])
    cached_stat = _j96_git(["diff", "--cached", "--stat"])
    shortstat = _j96_git(["diff", "--shortstat"])
    cached_shortstat = _j96_git(["diff", "--cached", "--shortstat"])
    name_status = _j96_git(["diff", "--name-status"])
    cached = _j96_git(["diff", "--cached", "--name-status"])

    def _ok(blob: str) -> bool:
        return bool(blob) and blob != "blocked_git_command" and not blob.startswith("git_error")

    # Dedupe changed files by path; staged status code wins on conflict.
    changed_map: dict[str, str] = {}
    for blob in (cached, name_status):  # staged first so it takes precedence
        if _ok(blob):
            for ln in blob.splitlines():
                parts = ln.split("\t")
                if len(parts) >= 2 and parts[-1] not in changed_map:
                    changed_map[parts[-1]] = parts[0]

    untracked: list[str] = []
    if _ok(status):
        for ln in status.splitlines():
            if ln.startswith("??"):
                untracked.append(ln[3:].strip())

    all_paths = sorted(set(list(changed_map.keys()) + untracked))
    core_touched = [p for p in all_paths if p in _J96_CORE_FILES]
    sensitive_touched = [p for p in all_paths if _j96_is_sensitive(p.lower())]

    # Sum churn across staged + unstaged so staged-only work is not under-counted.
    ins = dels = 0
    for blob in (shortstat, cached_shortstat):
        if _ok(blob):
            mi = re.search(r"(\d+) insertion", blob)
            md = re.search(r"(\d+) deletion", blob)
            ins += int(mi.group(1)) if mi else 0
            dels += int(md.group(1)) if md else 0

    n = len(all_paths)
    churn = ins + dels
    if n == 0:
        risk = "none"
    elif sensitive_touched:
        risk = "high"
    elif len(core_touched) > 1 or churn > 800 or n > 12:
        risk = "high"
    elif core_touched or n > 4 or churn > 150:
        risk = "medium"
    else:
        risk = "low"

    if n == 0:
        recommend = "Nothing to commit — working tree is clean."
    elif sensitive_touched:
        recommend = "DO NOT COMMIT until sensitive files are removed or git-ignored."
    elif risk == "high":
        recommend = "Review carefully and run full validation before committing; consider splitting the change."
    elif risk == "medium":
        recommend = "Looks reasonable — run validation, then commit a small focused change."
    else:
        recommend = "Safe to commit after py_compile + routes + doctor pass."

    lines = [
        "# JARVIS Diff Review",
        "",
        "## Scope & safety",
    ] + _j96_safety_lines() + [
        "- This command only reads git and writes this report; it changes no source files.",
        "",
        "## Git status",
        "```text",
        status or "clean",
        "```",
        "",
        "## Diff stat (unstaged)",
        "```text",
        stat or "(no unstaged changes)",
        "```",
        "",
        "## Diff stat (staged)",
        "```text",
        cached_stat or "(no staged changes)",
        "```",
        "",
        "## Changed files",
    ]
    if not all_paths:
        lines.append("- None. Working tree is clean.")
    else:
        for p in sorted(changed_map):
            lines.append(f"- `{changed_map[p]}` `{p}`")
        for p in untracked:
            lines.append(f"- `??` `{p}` (untracked)")

    lines += [
        "",
        "## Risk assessment",
        f"- Changed files: `{n}`",
        f"- Insertions: `{ins}` | Deletions: `{dels}`",
        f"- Core files touched: `{len(core_touched)}`" + (f" ({', '.join(core_touched)})" if core_touched else ""),
        f"- Sensitive paths touched: `{len(sensitive_touched)}`",
        f"- **Risk level: `{risk}`**",
        "",
        "## Validation checklist",
        "- [ ] `python3 -m py_compile 11_SCRIPTS/jarvis_cli.py 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py`",
        "- [ ] `./11_SCRIPTS/jarvis_quick.sh routes` lists every command",
        "- [ ] `./11_SCRIPTS/jarvis_quick.sh doctor` is green",
        "- [ ] Read the full diff for secrets/tokens before committing",
        "- [ ] Relevant endpoints still return `ok:true`",
        "",
        "## Recommendation",
        f"- {recommend}",
        "",
        "_This review changed no files. No commit/push/deploy was performed._",
        "",
    ]

    out = _j96_write("diff_reviews", "diff_review", "\n".join(lines))
    return out, {"changed": n, "risk": risk, "recommend": recommend, "path": _j96_rel(out)}


def cmd_diff_review(_: argparse.Namespace) -> None:
    out, info = _j96_build_diff_review()
    print("DIFF_REVIEW_SAVED:", _j96_rel(out))
    print(f"- changed files: {info['changed']} | risk: {info['risk']}")
    print(f"- recommendation: {info['recommend']}")


# --- queue-pack -----------------------------------------------------------

def _j96_load_queue() -> list[dict[str, Any]]:
    if "_j95_load" in globals():
        return _j95_load()
    qf = ROOT / "05_EXECUCAO" / "95_JARVIS_TASK_QUEUE_RUNNER" / "queue.json"
    if not qf.exists():
        return []
    try:
        data = json.loads(qf.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _j96_build_queue_pack() -> tuple[Path, dict[str, Any]]:
    items = _j96_load_queue()
    pending = [x for x in items if x.get("status") == "pending"]
    done = [x for x in items if x.get("status") == "done"]
    failed = [x for x in items if x.get("status") == "failed"]

    order = ["local_audit", "source_research", "cleanup_advice",
             "feature_package", "brief_report", "general_task"]
    rationale = {
        "local_audit": "Run first — confirm the system is stable before changing anything.",
        "source_research": "Gather local references so later work is grounded.",
        "cleanup_advice": "Advisory scan (no deletion) before structural changes.",
        "feature_package": "Build features once the context is clear.",
        "brief_report": "Summaries/reports after the work is done.",
        "general_task": "Everything else — schedule around the above.",
    }

    by_type: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_type.setdefault(it.get("type", "general_task"), []).append(it)

    lines = [
        "# JARVIS Queue Pack",
        "",
        "## Scope & safety",
    ] + _j96_safety_lines() + [
        "",
        "## Summary",
        f"- Total tasks: `{len(items)}`",
        f"- Pending: `{len(pending)}` | Done: `{len(done)}` | Failed: `{len(failed)}`",
        "",
    ]

    if not items:
        lines += [
            "No queued tasks yet.",
            "",
            "Add some with:",
            "```bash",
            './11_SCRIPTS/jarvis_quick.sh queue-add "your task"',
            "```",
            "",
        ]
    else:
        lines.append("## Tasks grouped by type (recommended order)")
        for t in order + [k for k in by_type if k not in order]:
            group = by_type.get(t)
            if not group:
                continue
            lines.append(f"### `{t}` — {len(group)} task(s)")
            lines.append(f"- Why this slot: {rationale.get(t, 'Schedule with related work.')}")
            for it in group:
                lines.append(f"  - #{it.get('id')} [{it.get('status')}] {it.get('task')}")
            lines.append("")

        def prio(it: dict[str, Any]) -> tuple[int, int]:
            t = it.get("type", "general_task")
            try:
                idx = order.index(t)
            except ValueError:
                idx = len(order)
            try:
                tid = int(it.get("id", 0))
            except Exception:
                tid = 0
            return (idx, tid)

        pend_sorted = sorted(pending, key=prio)
        lines.append("## Suggested execution order (pending first)")
        if not pend_sorted:
            lines.append("- No pending tasks — all caught up.")
        else:
            for i, it in enumerate(pend_sorted, 1):
                lines.append(f"{i}. #{it.get('id')} `{it.get('type')}` — {it.get('task')}")
        lines += [
            "",
            "## Next command",
            "```bash",
            "./11_SCRIPTS/jarvis_quick.sh queue-run",
            "```",
            "",
        ]

    lines += ["_Plan only. No tasks were executed and no files were changed._", ""]

    out = _j96_write("queue_packs", "queue_pack", "\n".join(lines))
    return out, {
        "total": len(items), "pending": len(pending),
        "done": len(done), "path": _j96_rel(out),
    }


def cmd_queue_pack(_: argparse.Namespace) -> None:
    out, info = _j96_build_queue_pack()
    print("QUEUE_PACK_SAVED:", _j96_rel(out))
    print(f"- total: {info['total']} | pending: {info['pending']} | done: {info['done']}")


# --- mission --------------------------------------------------------------

def _j96_next_action(idea: str, doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if doc.get("passed", 0) != doc.get("total", 0):
        out.append("1. Fix the warnings first (`./11_SCRIPTS/jarvis_quick.sh audit`).")
    else:
        out.append("1. System is green — safe to build.")
    out.append(f"2. Open the feature pack for: {idea}")
    out.append("3. Queue the suggested tasks and run `./11_SCRIPTS/jarvis_quick.sh queue-run`.")
    out.append("4. After changes: `diff-review` → validate → commit one small focused change.")
    return out


def _j96_build_mission(idea: str) -> tuple[Path, dict[str, Any]]:
    ftype = _j96_infer_type(idea)
    terms = _j96_keywords(idea)

    eps = [
        ("status", "/status"),
        ("brief", "/jarvis-brief"),
        ("sources health", "/sources-health"),
        ("sources insight", "/sources-insight"),
        ("apply guard", "/forge-apply-guard-dashboard"),
    ]
    ep_ok = 0
    ep_lines: list[str] = []
    for name, path in eps:
        ok = bool(call_json("GET", path).get("ok"))
        ep_ok += 1 if ok else 0
        ep_lines.append(f"- `{name}`: {'OK' if ok else 'WARN'}")

    short = idea[:48]
    qsugg = [
        f'./11_SCRIPTS/jarvis_quick.sh queue-add "auditar antes de: {short}"',
        f'./11_SCRIPTS/jarvis_quick.sh queue-add "buscar fontes sobre {(" ".join(terms[:3]) or short)}"',
        f'./11_SCRIPTS/jarvis_quick.sh queue-add "criar feature: {short}"',
    ]

    lines = [
        f"# JARVIS Mission — {idea}",
        "",
        "## Scope & safety",
    ] + _j96_safety_lines() + [
        "",
        "## Brief snapshot",
    ] + _j96_health_md() + [
        "",
        "## Git snapshot",
        "```text",
        _j96_git_snapshot(),
        "```",
        "",
        "## Audit summary (quick endpoint check)",
        f"- Endpoints OK: `{ep_ok}/{len(eps)}`",
    ] + ep_lines + [
        "- For a full audit run `./11_SCRIPTS/jarvis_quick.sh audit`.",
        "",
        "## Source search terms",
    ] + (["- " + ", ".join(f"`{t}`" for t in terms)] if terms else ["- (none extracted)"]) + [
        "",
        "## Local source findings",
    ] + _j96_source_search_md(terms) + [
        "## Feature plan (inferred)",
        f"- Inferred type: `{ftype}`",
        "- Likely files: " + ", ".join(f"`{p}`" for p in _j96_likely_files(ftype)),
        "",
    ] + _j96_impl_plan(ftype) + [
        "",
        "## Queue suggestions",
        "```bash",
    ] + qsugg + [
        "```",
        "",
        "## Next recommended action",
    ] + _j96_next_action(idea, {"passed": ep_ok, "total": len(eps)}) + [
        "",
        "_Mission pack is advisory. No files changed, no commit/push/deploy._",
        "",
    ]

    out = _j96_write("missions", "mission", "\n".join(lines))
    return out, {
        "type": ftype, "terms": terms, "ep_ok": ep_ok,
        "ep_total": len(eps), "path": _j96_rel(out),
    }


def cmd_mission(args: argparse.Namespace) -> None:
    idea = " ".join(args.idea).strip()
    if not idea:
        print('Usage: ./11_SCRIPTS/jarvis_quick.sh mission "mission idea"')
        return
    out, info = _j96_build_mission(idea)
    print("MISSION_SAVED:", _j96_rel(out))
    print(f"- type: {info['type']} | endpoints OK: {info['ep_ok']}/{info['ep_total']}")
    print(f"- terms: {', '.join(info['terms']) or '(none)'}")


# --- ultra ----------------------------------------------------------------

def _j96_doctor_snapshot() -> dict[str, Any]:
    checks: list[tuple[str, bool]] = []
    checks.append(("git clean", not bool(_j96_git(["status", "--short"]))))
    for name, path in [
        ("api status", "/status"),
        ("brief endpoint", "/jarvis-brief"),
        ("sources health", "/sources-health"),
        ("sources insight", "/sources-insight"),
        ("apply guard", "/forge-apply-guard-dashboard"),
    ]:
        checks.append((name, bool(call_json("GET", path).get("ok"))))
    if "_j93_run_local_check" in globals():
        cc = _j93_run_local_check("py_compile", [
            sys.executable, "-m", "py_compile",
            "11_SCRIPTS/jarvis_api.py", "11_SCRIPTS/jarvis_core.py", "11_SCRIPTS/jarvis_cli.py",
        ])
        checks.append(("py_compile", bool(cc.get("ok"))))
    passed = sum(1 for _, ok in checks if ok)
    return {"passed": passed, "total": len(checks), "checks": checks}


def cmd_ultra(args: argparse.Namespace) -> None:
    idea = " ".join(getattr(args, "idea", []) or []).strip() or "improve JARVIS as a local operator"
    print("ULTRA SUITE — running all operator generators…")

    doc = _j96_doctor_snapshot()
    print(f"- doctor: {doc['passed']}/{doc['total']}")
    repo_out, repo_info = _j96_build_repo_map()
    print("- repo-map:", _j96_rel(repo_out))
    clean_out, clean_info = _j96_build_cleanup_advice()
    print("- cleanup-advice:", _j96_rel(clean_out))
    feat_out, feat_info = _j96_build_feature_pack(idea)
    print("- feature-pack:", _j96_rel(feat_out))
    queue_out, queue_info = _j96_build_queue_pack()
    print("- queue-pack:", _j96_rel(queue_out))
    mission_out, mission_info = _j96_build_mission(idea)
    print("- mission:", _j96_rel(mission_out))

    lines = [
        f"# JARVIS Ultra Operator Report — {idea}",
        "",
        "## Scope & safety",
    ] + _j96_safety_lines() + [
        "",
        "This master report was generated by `ultra` — a one-command daily / strategy generator.",
        "",
        "## Doctor snapshot",
        f"- Result: `{doc['passed']}/{doc['total']}`",
    ] + [f"- {'OK' if ok else 'WARN'} {name}" for name, ok in doc["checks"]] + [
        "",
        "## Git snapshot",
        "```text",
        _j96_git_snapshot(),
        "```",
        "",
        "## Generated sub-reports",
        f"- Repo map: `{_j96_rel(repo_out)}`  ({repo_info['files']} files, {repo_info['core']} core scripts)",
        f"- Cleanup advice: `{_j96_rel(clean_out)}`  ({clean_info['scanned']} scanned, "
        f"{clean_info['backups']} backups, {clean_info['dup_groups']} dup groups)",
        f"- Feature pack: `{_j96_rel(feat_out)}`  (type: {feat_info['type']})",
        f"- Queue pack: `{_j96_rel(queue_out)}`  ({queue_info['pending']} pending / {queue_info['total']} total)",
        f"- Mission: `{_j96_rel(mission_out)}`  (endpoints {mission_info['ep_ok']}/{mission_info['ep_total']} OK)",
        "",
        "## Health snapshot",
    ] + _j96_health_md() + [
        "",
        "## Recommended next action",
    ] + _j96_next_action(idea, doc) + [
        "",
        "_No files were deleted. No commit/push/deploy. Local only._",
        "",
    ]

    out = _j96_write("ultra_reports", "ultra_report", "\n".join(lines))
    print("")
    print("ULTRA_REPORT_SAVED:", _j96_rel(out))


# --- open-latest ----------------------------------------------------------

def cmd_open_latest(args: argparse.Namespace) -> None:
    base = _j96_dir()
    subdirs = ["ultra_reports", "missions", "feature_packs", "queue_packs",
               "repo_maps", "cleanup_advice", "diff_reviews"]

    print("JARVIS ULTRA — latest reports")
    latest_overall: Path | None = None
    latest_mtime = -1.0
    for sd in subdirs:
        d = base / sd
        newest: Path | None = None
        if d.exists():
            mds = [p for p in d.glob("*.md") if p.is_file()]
            if mds:
                newest = max(mds, key=lambda p: p.stat().st_mtime)
        if newest:
            print(f"- {sd}: {_j96_rel(newest)}")
            mt = newest.stat().st_mtime
            if mt > latest_mtime:
                latest_mtime = mt
                latest_overall = newest
        else:
            print(f"- {sd}: (none yet)")

    if latest_overall is None:
        print("")
        print('No reports yet. Run `./11_SCRIPTS/jarvis_quick.sh ultra "..."` first.')
        return

    print("")
    print("LATEST_OVERALL:", _j96_rel(latest_overall))

    if getattr(args, "do_open", False):
        try:
            resolved = latest_overall.resolve()
            base_resolved = base.resolve()
            inside = str(resolved) == str(base_resolved) or str(resolved).startswith(str(base_resolved) + "/")
        except Exception:
            resolved = latest_overall
            inside = False
        if sys.platform != "darwin":
            print("open skipped: not macOS.")
        elif not (inside and resolved.suffix.lower() == ".md"):
            print("open skipped: path failed the safety check.")
        else:
            try:
                subprocess.run(["open", str(resolved)], cwd=ROOT, timeout=5)
                print("OPENED:", _j96_rel(resolved))
            except Exception as exc:
                print("open failed:", exc)
    else:
        print("Tip: add --open to open the latest markdown on macOS.")

# === END JARVIS_CLI_BLOCK_96_ULTRA_OPERATOR_SUITE ===


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jarvis", description="JARVIS local terminal command center")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("all")
    s.set_defaults(fn=cmd_all)

    s = sub.add_parser("brief")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_brief)

    s = sub.add_parser("report")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("health")
    s.set_defaults(fn=cmd_health)

    s = sub.add_parser("insight")
    s.set_defaults(fn=cmd_insight)

    s = sub.add_parser("search")
    s.add_argument("query", nargs="*")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("git")
    s.set_defaults(fn=cmd_git)

    s = sub.add_parser("routes")
    s.set_defaults(fn=cmd_routes)

    s = sub.add_parser("daily")
    s.set_defaults(fn=cmd_daily)

    s = sub.add_parser("audit")
    s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("mass-search")
    s.add_argument("terms", nargs="+")
    s.add_argument("--limit", type=int, default=3)
    s.set_defaults(fn=cmd_mass_search)

    s = sub.add_parser("export-pack")
    s.set_defaults(fn=cmd_export_pack)

    s = sub.add_parser("start")
    s.set_defaults(fn=cmd_start)

    s = sub.add_parser("close")
    s.add_argument("note", nargs="*")
    s.set_defaults(fn=cmd_close)

    s = sub.add_parser("doctor")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("next-block")
    s.set_defaults(fn=cmd_next_block)

    s = sub.add_parser("queue-add")
    s.add_argument("task", nargs="+")
    s.set_defaults(fn=cmd_queue_add)

    s = sub.add_parser("queue-status")
    s.set_defaults(fn=cmd_queue_status)

    s = sub.add_parser("queue-list")
    s.set_defaults(fn=cmd_queue_list)

    s = sub.add_parser("queue-run")
    s.add_argument("--limit", type=int, default=3)
    s.set_defaults(fn=cmd_queue_run)

    s = sub.add_parser("queue-clear-done")
    s.set_defaults(fn=cmd_queue_clear_done)

    # --- Block 96: Ultra Operator Suite ---
    s = sub.add_parser("feature-pack")
    s.add_argument("idea", nargs="+")
    s.set_defaults(fn=cmd_feature_pack)

    s = sub.add_parser("cleanup-advice")
    s.set_defaults(fn=cmd_cleanup_advice)

    s = sub.add_parser("repo-map")
    s.set_defaults(fn=cmd_repo_map)

    s = sub.add_parser("diff-review")
    s.set_defaults(fn=cmd_diff_review)

    s = sub.add_parser("queue-pack")
    s.set_defaults(fn=cmd_queue_pack)

    s = sub.add_parser("mission")
    s.add_argument("idea", nargs="+")
    s.set_defaults(fn=cmd_mission)

    s = sub.add_parser("ultra")
    s.add_argument("idea", nargs="*")
    s.set_defaults(fn=cmd_ultra)

    s = sub.add_parser("open-latest")
    s.add_argument("--open", action="store_true", dest="do_open")
    s.set_defaults(fn=cmd_open_latest)

    return p


def main() -> int:
    args = build_parser().parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
