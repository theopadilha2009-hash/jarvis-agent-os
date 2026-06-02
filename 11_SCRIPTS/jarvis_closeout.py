from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "105_TERMINAL_CLOSEOUT_OS"
REPORT = OUT / "CLOSEOUT_REPORT.md"

LOCAL_IGNORE_BEGIN = "# JARVIS TERMINAL CLOSEOUT OS BEGIN"
LOCAL_IGNORE_END = "# JARVIS TERMINAL CLOSEOUT OS END"
LOCAL_IGNORE_PATTERNS = [
    "05_EXECUCAO/105_TERMINAL_CLOSEOUT_OS/",
]

PY_FILES = [
    "11_SCRIPTS/jarvis_cli.py",
    "11_SCRIPTS/jarvis_api.py",
    "11_SCRIPTS/jarvis_core.py",
    "11_SCRIPTS/jarvis_sprint_builder.py",
    "11_SCRIPTS/jarvis_polish_queue.py",
    "11_SCRIPTS/jarvis_local_cleaner.py",
    "11_SCRIPTS/jarvis_project_resume.py",
    "11_SCRIPTS/jarvis_closeout.py",
]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def ensure_local_ignore() -> None:
    exclude = REPO / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    current = exclude.read_text(encoding="utf-8", errors="replace") if exclude.exists() else ""

    if LOCAL_IGNORE_BEGIN in current and LOCAL_IGNORE_END in current:
        before = current.split(LOCAL_IGNORE_BEGIN)[0].rstrip()
        after = current.split(LOCAL_IGNORE_END, 1)[1].lstrip()
        current = (before + "\n" + after).strip()

    section = "\n".join([LOCAL_IGNORE_BEGIN, *LOCAL_IGNORE_PATTERNS, LOCAL_IGNORE_END])
    final = current.rstrip()
    if final:
        final += "\n\n"
    final += section + "\n"
    exclude.write_text(final, encoding="utf-8")


def existing_py_files() -> list[str]:
    return [p for p in PY_FILES if (REPO / p).exists()]


def section(title: str, body: str, lang: str = "text") -> str:
    body = body.strip() or "-"
    return f"## {title}\n\n```{lang}\n{body}\n```\n"


def git_clean() -> bool:
    _, out = run(["git", "status", "--porcelain"])
    return not out.strip()


def changed_files() -> list[str]:
    _, out = run(["git", "status", "--porcelain"])
    files = []
    for line in out.splitlines():
        raw = line[3:] if len(line) > 3 else line
        files.append(raw.strip())
    return files


def commit_suggestions(files: list[str]) -> list[str]:
    suggestions = []

    if not files:
        return ["No commit needed. Working tree is clean."]

    joined = " ".join(files)

    if "jarvis_closeout.py" in joined:
        suggestions.append("feat: add Jarvis terminal closeout OS")
    if "jarvis_cli.py" in joined:
        suggestions.append("feat: improve Jarvis CLI commands")
    if "jarvis_ui_assets/cockpit.html" in joined:
        suggestions.append("style: polish Jarvis cockpit UI")
    if "jarvis_api.py" in joined:
        suggestions.append("feat: improve Jarvis local API")
    if "jarvis_local_cleaner.py" in joined:
        suggestions.append("feat: improve Jarvis local cleanup")
    if "README" in joined or ".md" in joined:
        suggestions.append("docs: update Jarvis documentation")

    if not suggestions:
        suggestions.append("chore: polish Jarvis local workflow")

    deduped = []
    for s in suggestions:
        if s not in deduped:
            deduped.append(s)
    return deduped


def next_safe_action(py_ok: bool, doctor_text: str, clean: bool) -> str:
    if not py_ok:
        return "Fix Python syntax before continuing. Do not commit."
    if not clean:
        return "Review changed files, check diff, then commit only expected code files."
    if "7/7" not in doctor_text:
        return "Repo is clean, but doctor is not fully green. Inspect warnings before next feature."
    return "System is clean and stable. Continue with the next larger feature block."


def build_report() -> tuple[str, bool]:
    ensure_local_ignore()

    py_files = existing_py_files()
    py_code, py_out = run([sys.executable, "-m", "py_compile", *py_files])
    doctor_code, doctor_out = run([sys.executable, "11_SCRIPTS/jarvis_cli.py", "doctor"])
    diff_review_code, diff_review_out = run([sys.executable, "11_SCRIPTS/jarvis_cli.py", "diff-review"])
    _, diff_stat = run(["git", "diff", "--stat"])
    _, branch = run(["git", "status", "-sb"])
    _, porcelain = run(["git", "status", "--porcelain"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-8"])

    files = changed_files()
    clean = git_clean()
    py_ok = py_code == 0

    lines = [
        "# JARVIS Terminal Closeout OS — Block 105",
        "",
        f"Generated at: `{now()}`",
        f"Repo: `{REPO}`",
        f"Python: `{sys.executable}`",
        f"Python syntax OK: `{py_ok}`",
        f"Git clean: `{clean}`",
        "",
        "## Result",
        "",
        next_safe_action(py_ok, doctor_out, clean),
        "",
        "## Commit Suggestions",
        "",
    ]

    for suggestion in commit_suggestions(files):
        lines.append(f"- `{suggestion}`")

    lines += [
        "",
        section("Branch Status", branch),
        section("Python Compile", py_out or "OK"),
        section("Doctor", doctor_out),
        section("Diff Review", diff_review_out),
        section("Diff Stat", diff_stat or "clean"),
        section("Uncommitted Files", porcelain or "clean"),
        section("Last Commits", commits),
        "## Manual Commit Flow",
        "",
        "```bash",
        "git add <expected-files-only>",
        "git commit -m \"<message-from-suggestion>\"",
        "git push origin main",
        "git status -sb",
        "```",
        "",
        "## Safety",
        "",
        "- No automatic commit.",
        "- No automatic push.",
        "- No deploy.",
        "- No secrets or .env reading.",
        "- Commit only expected files.",
        "",
    ]

    return "\n".join(lines), py_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 105 Terminal Closeout OS")
    parser.add_argument("--print", action="store_true", help="Print full report after saving")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    report, py_ok = build_report()
    REPORT.write_text(report, encoding="utf-8")

    print("CLOSEOUT_REPORT_SAVED")
    print(REPORT)

    if args.print:
        print(report)
    else:
        print("")
        print("Quick closeout saved. Use --print to show the full report.")
        print("Next:")
        print("  git diff --stat")
        print("  git status -sb")

    return 0 if py_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
