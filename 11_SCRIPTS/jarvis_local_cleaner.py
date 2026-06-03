from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXCLUDE = REPO / ".git" / "info" / "exclude"
OUT = REPO / "05_EXECUCAO" / "103_LOCAL_EXECUTION_CLEANER"

BEGIN = "# JARVIS LOCAL EXECUTION CLEANER BEGIN"
END = "# JARVIS LOCAL EXECUTION CLEANER END"

PATTERNS = [
    "05_EXECUCAO/97_OWNER_DEV_MODE/",
    "05_EXECUCAO/98_WINDOWS_LAUNCHER/",
    "05_EXECUCAO/99_VISUAL_FEATURE_BUILDER/",
    "05_EXECUCAO/100_JARVIS_SPRINT_BUILDER/",
    "05_EXECUCAO/101_JARVIS_POLISH_QUEUE/",
    "05_EXECUCAO/103_LOCAL_EXECUTION_CLEANER/",
    "05_EXECUCAO/105_TERMINAL_CLOSEOUT_OS/",
    "05_EXECUCAO/106_TERMINAL_OPS_HUB/",
    "05_EXECUCAO/107_FEATURE_FORGE_CLI/",
    "05_EXECUCAO/108_PROGRESS_DASHBOARD_CLI/",
    "05_EXECUCAO/109_AUTOSHIP_RUNNER/",
    "05_EXECUCAO/110_AUTO_IMPROVE_LOOP/",
    "05_EXECUCAO/111_SELF_PATCH_PLANNER/",
    "05_EXECUCAO/112_AUTO_CYCLE_RUNNER/",
    "05_EXECUCAO/113_SELF_PATCH_CATALOG/",
    "05_EXECUCAO/114_PATCH_RUNNER/",
    "05_EXECUCAO/115_EXPANDED_SELF_PATCH_CATALOG/",
    "05_EXECUCAO/116_GROWTH_LOOP/",
    "05_EXECUCAO/117_AUTONOMOUS_BACKLOG/",
    "05_EXECUCAO/118_OPERATOR_EXPANSION/",
    "05_EXECUCAO/119_MISSION_ENGINE/",
    "05_EXECUCAO/120_POWER_LOOP/",
    "05_EXECUCAO/121_TASK_ENGINE/",
    "05_EXECUCAO/122_DECISION_ENGINE/",
    "05_EXECUCAO/123_TASK_PLANNER/",
    "05_EXECUCAO/124_TASK_DECISION_HARDENING/",
    "05_EXECUCAO/125_MACHINE_SYNC/",
    "05_EXECUCAO/126_SESSION_RUNNER/",
    "05_EXECUCAO/127_RESUME_COMMAND/",
    "05_EXECUCAO/128_OPERATOR_ONE/",
    "05_EXECUCAO/129_PARALLEL_WORKTREE/",
    "05_EXECUCAO/130_WORKER_AUTO_RUNNER/",
    "05_EXECUCAO/132_MAIN_CLI/",
    "05_EXECUCAO/133_BRAIN_ROUTER/",
    "05_EXECUCAO/134_BRAIN_SETUP_DOCTOR/",
    "05_EXECUCAO/135_FREE_BRAIN_BOOTSTRAP/",
    "05_EXECUCAO/136_LOCAL_BRAIN_SMOKE/",
    "05_EXECUCAO/137_BRAIN_QUALITY_GUARD/",
    "05_EXECUCAO/138_BRAIN_CONTRACT/",
    "05_EXECUCAO/139_PATCH_PROPOSAL/",
    "05_EXECUCAO/140_SAFE_APPLY_ENGINE/",
    "05_EXECUCAO/141_SAFE_APPLY_V2/",
    "05_EXECUCAO/142_DIFF_REVIEW_GATE/",
    "05_EXECUCAO/144_SHIP_GUARD/",
    "05_EXECUCAO/145_AUTOSHIP/",
    "*.pid",
    "*.tmp",
    "*.local.log",
]


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    return (result.stdout + result.stderr).strip()


def install_ignore() -> None:
    EXCLUDE.parent.mkdir(parents=True, exist_ok=True)
    current = EXCLUDE.read_text(encoding="utf-8", errors="replace") if EXCLUDE.exists() else ""

    if BEGIN in current and END in current:
        before = current.split(BEGIN)[0].rstrip()
        after = current.split(END, 1)[1].lstrip()
        current = (before + "\n" + after).strip()

    section = "\n".join([BEGIN, *PATTERNS, END])
    final = current.rstrip()
    if final:
        final += "\n\n"
    final += section + "\n"

    EXCLUDE.write_text(final, encoding="utf-8")
    print("LOCAL_IGNORE_INSTALLED")
    print(EXCLUDE)


def status_report() -> str:
    porcelain = run_git(["status", "--porcelain"])
    branch = run_git(["status", "-sb"])
    log = run_git(["log", "--oneline", "-5"])

    lines = [
        "# JARVIS Local Execution Cleaner — Block 103",
        "",
        f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## Branch Status",
        "",
        "```text",
        branch or "clean",
        "```",
        "",
        "## Last Commits",
        "",
        "```text",
        log,
        "```",
        "",
        "## Porcelain Status",
        "",
        "```text",
        porcelain or "clean",
        "```",
        "",
        "## Safe Local Noise Patterns",
        "",
    ]

    for p in PATTERNS:
        lines.append(f"- `{p}`")

    lines += [
        "",
        "## Guidance",
        "",
        "- Commit code/scripts only.",
        "- Do not commit local execution reports unless intentionally documenting a release.",
        "- Keep `.git/info/exclude` local; it is not pushed.",
        "- Do not delete generated folders automatically from this tool.",
        "",
    ]

    return "\n".join(lines)


def write_report() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "LOCAL_EXECUTION_CLEANER_REPORT.md"
    path.write_text(status_report(), encoding="utf-8")
    print("REPORT_SAVED")
    print(path)


def print_status() -> None:
    print(run_git(["status", "-sb"]) or "clean")


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 103 Local Execution Cleaner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("install-ignore")
    sub.add_parser("status")
    sub.add_parser("report")
    sub.add_parser("doctor-advice")

    args = parser.parse_args()

    if args.cmd == "install-ignore":
        install_ignore()
        return 0

    if args.cmd == "status":
        print_status()
        return 0

    if args.cmd == "report":
        write_report()
        return 0

    if args.cmd == "doctor-advice":
        print("SAFE_CLOSEOUT_COMMANDS")
        print("python3 -m py_compile 11_SCRIPTS/jarvis_cli.py 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py")
        print("python3 11_SCRIPTS/jarvis_cli.py doctor")
        print("python3 11_SCRIPTS/jarvis_cli.py diff-review")
        print("python3 11_SCRIPTS/jarvis_local_cleaner.py report")
        print("git diff --stat")
        print("git status -sb")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
