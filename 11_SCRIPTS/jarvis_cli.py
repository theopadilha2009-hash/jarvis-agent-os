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
    print("  routes               Show this help")


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

    return p


def main() -> int:
    args = build_parser().parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
