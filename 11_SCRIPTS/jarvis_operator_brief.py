from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "149_OPERATOR_BRIEF"
REPORT = OUT / "OPERATOR_BRIEF.md"
STATE = OUT / "OPERATOR_BRIEF.json"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def collect() -> dict:
    commands = {
        "branch": ["git", "branch", "--show-current"],
        "status": ["git", "status", "-sb"],
        "porcelain": ["git", "status", "--porcelain"],
        "last_commits": ["git", "log", "--oneline", "-6"],
        "autoship_status": ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "autoship", "status"],
        "ship_guard": ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "ship-guard", "preflight"],
        "patch_catalog_next": ["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "patch-catalog", "next"],
    }

    checks = {}
    for name, cmd in commands.items():
        code, out = run(cmd)
        checks[name] = {
            "exit_code": code,
            "output": out,
        }

    clean = len(checks["porcelain"]["output"].strip()) == 0

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "branch": checks["branch"]["output"],
        "clean": clean,
        "checks": checks,
    }


def brief_lines(data: dict) -> list[str]:
    status = data["checks"]["status"]["output"] or "-"
    commits = data["checks"]["last_commits"]["output"] or "-"
    catalog = data["checks"]["patch_catalog_next"]["output"] or "-"

    return [
        "# JARVIS Operator Brief — Block 149",
        "",
        f"Created at: `{data['created_at']}`",
        f"Branch: `{data['branch']}`",
        f"Clean: `{data['clean']}`",
        "",
        "## Current state",
        "",
        "```text",
        status,
        "```",
        "",
        "## Last commits",
        "",
        "```text",
        commits,
        "```",
        "",
        "## Next catalog item",
        "",
        "```text",
        catalog[-3000:],
        "```",
        "",
        "## Operator instruction",
        "",
        "- Continue only if Git is clean.",
        "- Use guarded commands.",
        "- Prefer small patches.",
        "- Ship only through Autoship.",
        "",
    ]


def write(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text("\n".join(brief_lines(data)), encoding="utf-8")


def run_brief() -> int:
    data = collect()
    write(data)

    print("OPERATOR_BRIEF_DONE")
    print(REPORT)
    print(json.dumps({
        "branch": data["branch"],
        "clean": data["clean"],
        "git_status": data["checks"]["status"]["output"],
        "last_commit": data["checks"]["last_commits"]["output"].splitlines()[0] if data["checks"]["last_commits"]["output"] else "",
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 149 Operator Brief")
    parser.add_argument("action", choices=["brief"], default="brief")
    args = parser.parse_args()

    if args.action == "brief":
        return run_brief()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
