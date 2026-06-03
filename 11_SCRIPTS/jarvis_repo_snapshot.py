from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "148_REPO_SNAPSHOT"
REPORT = OUT / "REPO_SNAPSHOT.md"
STATE = OUT / "REPO_SNAPSHOT.json"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def collect() -> dict:
    checks = {}

    commands = {
        "branch": ["git", "branch", "--show-current"],
        "status_short": ["git", "status", "-sb"],
        "status_porcelain": ["git", "status", "--porcelain"],
        "last_commits": ["git", "log", "--oneline", "-8"],
        "remote": ["git", "remote", "-v"],
        "diff_stat": ["git", "diff", "--stat"],
        "staged_diff_stat": ["git", "diff", "--cached", "--stat"],
    }

    for name, cmd in commands.items():
        code, out = run(cmd)
        checks[name] = {
            "exit_code": code,
            "output": out,
        }

    porcelain = checks["status_porcelain"]["output"]

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "branch": checks["branch"]["output"],
        "clean": len(porcelain.strip()) == 0,
        "checks": checks,
    }


def write_report(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Repo Snapshot — Block 148",
        "",
        f"Created at: `{data['created_at']}`",
        f"Repo: `{data['repo']}`",
        f"Branch: `{data['branch']}`",
        f"Clean: `{data['clean']}`",
        "",
        "## Status",
        "",
        "```text",
        data["checks"]["status_short"]["output"] or "-",
        "```",
        "",
        "## Last commits",
        "",
        "```text",
        data["checks"]["last_commits"]["output"] or "-",
        "```",
        "",
        "## Diff stat",
        "",
        "```text",
        data["checks"]["diff_stat"]["output"] or "-",
        "```",
        "",
        "## Staged diff stat",
        "",
        "```text",
        data["checks"]["staged_diff_stat"]["output"] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def snapshot() -> int:
    data = collect()
    write_report(data)

    print("REPO_SNAPSHOT_DONE")
    print(REPORT)
    print(json.dumps({
        "branch": data["branch"],
        "clean": data["clean"],
        "git_status": data["checks"]["status_short"]["output"],
        "last_commit": data["checks"]["last_commits"]["output"].splitlines()[0] if data["checks"]["last_commits"]["output"] else "",
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 148 Repo Snapshot")
    parser.add_argument("action", choices=["snapshot"], default="snapshot")
    args = parser.parse_args()

    if args.action == "snapshot":
        return snapshot()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
