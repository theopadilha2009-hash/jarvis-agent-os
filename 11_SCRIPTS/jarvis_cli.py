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

    return p


def main() -> int:
    args = build_parser().parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
