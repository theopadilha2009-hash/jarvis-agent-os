from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "150_DAILY_CHECKPOINT"
REPORT = OUT / "DAILY_CHECKPOINT.md"
STATE = OUT / "DAILY_CHECKPOINT.json"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def collect() -> dict:
    commands = {
        "branch": ["git", "branch", "--show-current"],
        "status": ["git", "status", "-sb"],
        "porcelain": ["git", "status", "--porcelain"],
        "last_commits": ["git", "log", "--oneline", "-10"],
        "patch_catalog": ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "patch-catalog", "list"],
        "repo_snapshot": ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "repo-snapshot", "snapshot"],
        "operator_brief": ["py", "-3", "11_SCRIPTS/jarvis_ops.py", "operator-brief", "brief"],
    }

    checks = {}
    for name, cmd in commands.items():
        code, out = run(cmd)
        checks[name] = {
            "exit_code": code,
            "output": out,
        }

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "branch": checks["branch"]["output"],
        "clean": len(checks["porcelain"]["output"].strip()) == 0,
        "checks": checks,
    }


def write(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Daily Checkpoint — Block 150",
        "",
        f"Created at: `{data['created_at']}`",
        f"Repo: `{data['repo']}`",
        f"Branch: `{data['branch']}`",
        f"Clean: `{data['clean']}`",
        "",
        "## Status",
        "",
        "```text",
        data["checks"]["status"]["output"] or "-",
        "```",
        "",
        "## Last commits",
        "",
        "```text",
        data["checks"]["last_commits"]["output"] or "-",
        "```",
        "",
        "## Next patches",
        "",
        "```text",
        data["checks"]["patch_catalog"]["output"][-4000:] or "-",
        "```",
        "",
        "## Rule",
        "",
        "- Continue only with clean Git.",
        "- Use Autoship for commit/push.",
        "- Keep patches small.",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def checkpoint() -> int:
    data = collect()
    write(data)

    print("DAILY_CHECKPOINT_DONE")
    print(REPORT)
    print(json.dumps({
        "branch": data["branch"],
        "clean": data["clean"],
        "git_status": data["checks"]["status"]["output"],
        "last_commit": data["checks"]["last_commits"]["output"].splitlines()[0] if data["checks"]["last_commits"]["output"] else "",
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 150 Daily Checkpoint")
    parser.add_argument("action", choices=["checkpoint"], default="checkpoint")
    args = parser.parse_args()

    if args.action == "checkpoint":
        return checkpoint()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
