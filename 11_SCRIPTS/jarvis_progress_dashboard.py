from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "108_PROGRESS_DASHBOARD_CLI"
REPORT = OUT / "PROGRESS_DASHBOARD.md"


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return (result.stdout + result.stderr).strip()


def count_commits() -> int:
    out = run(["git", "rev-list", "--count", "HEAD"])
    try:
        return int(out.strip())
    except ValueError:
        return 0


def latest_reports(limit: int = 10) -> list[Path]:
    base = REPO / "05_EXECUCAO"
    if not base.exists():
        return []
    files = []
    for pattern in ["*.md", "*.txt", "*.json"]:
        files.extend(base.rglob(pattern))
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def block_dirs() -> list[str]:
    base = REPO / "05_EXECUCAO"
    if not base.exists():
        return []
    dirs = [p.name for p in base.iterdir() if p.is_dir() and p.name[:3].isdigit()]
    return sorted(dirs)


def risk_level(git_porcelain: str, doctor: str) -> str:
    if git_porcelain.strip():
        return "medium"
    if "7/7" not in doctor:
        return "medium"
    return "low"


def section(title: str, body: str) -> str:
    return f"## {title}\n\n```text\n{body.strip() or '-'}\n```\n"


def build_dashboard() -> str:
    branch = run(["git", "status", "-sb"])
    porcelain = run(["git", "status", "--porcelain"])
    commits = run(["git", "log", "--oneline", "--decorate", "-10"])
    diff = run(["git", "diff", "--stat"])
    doctor = run(["python3", "11_SCRIPTS/jarvis_cli.py", "doctor"])

    reports = latest_reports()
    blocks = block_dirs()
    risk = risk_level(porcelain, doctor)

    next_action = "Continue with one larger feature block."
    if porcelain.strip():
        next_action = "Review local changes, run closeout, then commit only expected files."
    elif "7/7" not in doctor:
        next_action = "Inspect doctor warning before building the next feature."

    lines = [
        "# JARVIS Progress Dashboard — Block 108",
        "",
        f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"Repo: `{REPO}`",
        f"Risk: `{risk}`",
        f"Git clean: `{'yes' if not porcelain.strip() else 'no'}`",
        f"Total commits: `{count_commits()}`",
        f"Execution block folders: `{len(blocks)}`",
        "",
        section("Branch", branch),
        section("Doctor", doctor),
        section("Diff Stat", diff or "clean"),
        section("Uncommitted Files", porcelain or "clean"),
        section("Last Commits", commits),
        "## Latest Reports",
        "",
    ]

    if reports:
        for p in reports:
            lines.append(f"- `{p.relative_to(REPO)}`")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Block Folders",
        "",
    ]

    if blocks:
        for b in blocks[-15:]:
            lines.append(f"- `{b}`")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Next Action",
        "",
        next_action,
        "",
        "## Useful Commands",
        "",
        "```bash",
        "python3 11_SCRIPTS/jarvis_ops.py status",
        "python3 11_SCRIPTS/jarvis_ops.py forge \"nova ideia\"",
        "python3 11_SCRIPTS/jarvis_ops.py progress",
        "python3 11_SCRIPTS/jarvis_ops.py closeout",
        "git diff --stat",
        "git status -sb",
        "```",
        "",
    ]

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 108 Progress Dashboard CLI")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    dashboard = build_dashboard()

    if args.save:
        OUT.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(dashboard, encoding="utf-8")
        print("PROGRESS_DASHBOARD_SAVED")
        print(REPORT)
    else:
        print(dashboard)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
