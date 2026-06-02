from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "104_PROJECT_RESUME"
REPORT = OUT / "PROJECT_RESUME.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def section(title: str, body: str) -> str:
    body = body.strip() or "-"
    return f"## {title}\n\n```text\n{body}\n```\n"


def latest_reports(limit: int = 8) -> str:
    base = REPO / "05_EXECUCAO"
    if not base.exists():
        return "-"

    files = []
    for pattern in ["*.md", "*.txt", "*.json"]:
        files.extend(base.rglob(pattern))

    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    if not files:
        return "-"

    return "\n".join(str(p.relative_to(REPO)) for p in files)


def next_polish() -> str:
    queue = REPO / "11_SCRIPTS" / "jarvis_polish_queue.py"
    if not queue.exists():
        return "Polish queue script not found."

    code, out = run(["python3", str(queue.relative_to(REPO)), "next"])
    return out if out else f"Queue returned code {code}"


def doctor() -> str:
    code, out = run(["python3", "11_SCRIPTS/jarvis_cli.py", "doctor"])
    return out if out else f"doctor returned code {code}"


def build_resume() -> str:
    _, branch = run(["git", "status", "-sb"])
    _, last_commits = run(["git", "log", "--oneline", "--decorate", "-8"])
    _, remotes = run(["git", "remote", "-v"])
    _, diff = run(["git", "diff", "--stat"])
    _, porcelain = run(["git", "status", "--porcelain"])

    clean = "yes" if not porcelain else "no"

    lines = [
        "# JARVIS Project Resume — Block 104",
        "",
        f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"Repo: `{REPO}`",
        f"Git clean: `{clean}`",
        "",
        section("Branch Status", branch),
        section("Last Commits", last_commits),
        section("Remote", remotes),
        section("Doctor", doctor()),
        section("Current Diff", diff or "clean"),
        section("Uncommitted Files", porcelain or "clean"),
        section("Latest Local Reports", latest_reports()),
        section("Next Polish Item", next_polish()),
        "## Safe Next Action",
        "",
    ]

    if clean == "yes":
        lines.append("Continue with the next polish item or create a small feature. No commit needed right now.")
    else:
        lines.append("Review local changes before continuing. Run py_compile, doctor, diff-review, git diff --stat, git status -sb.")

    lines += [
        "",
        "## Closeout Commands",
        "",
        "```bash",
        "python3 -m py_compile 11_SCRIPTS/jarvis_cli.py 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py",
        "python3 11_SCRIPTS/jarvis_cli.py doctor",
        "python3 11_SCRIPTS/jarvis_cli.py diff-review",
        "git diff --stat",
        "git status -sb",
        "```",
        "",
    ]

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 104 Project Resume Command")
    parser.add_argument("--save", action="store_true", help="Save resume under 05_EXECUCAO")
    args = parser.parse_args()

    resume = build_resume()

    if args.save:
        OUT.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(resume, encoding="utf-8")
        print("PROJECT_RESUME_SAVED")
        print(REPORT)
    else:
        print(resume)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
