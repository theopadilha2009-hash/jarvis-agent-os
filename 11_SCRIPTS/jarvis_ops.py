from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "106_TERMINAL_OPS_HUB"
REPORT = OUT / "OPS_HUB_REPORT.md"

LOCAL_IGNORE_BEGIN = "# JARVIS TERMINAL OPS HUB BEGIN"
LOCAL_IGNORE_END = "# JARVIS TERMINAL OPS HUB END"
LOCAL_IGNORE_PATTERNS = [
    "05_EXECUCAO/106_TERMINAL_OPS_HUB/",
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py(script: str, *args: str) -> tuple[int, str]:
    return run([sys.executable, script, *args])


def print_block(title: str, body: str) -> None:
    print("")
    print(f"== {title} ==")
    print(body.strip() or "-")


def install_local_ignore() -> None:
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




def improve(goal: str, print_full: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_auto_improve.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_auto_improve.py")
        return 1

    args = [goal]
    if print_full:
        args.append("--print")

    code, out = py("11_SCRIPTS/jarvis_auto_improve.py", *args)
    print(out)
    return code


def autoship(message: str, dry_run: bool = False, no_push: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_autoship.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_autoship.py")
        return 1

    args = [message]
    if dry_run:
        args.append("--dry-run")
    if no_push:
        args.append("--no-push")

    code, out = py("11_SCRIPTS/jarvis_autoship.py", *args)
    print(out)
    return code


def status() -> int:
    print("JARVIS OPS HUB — STATUS")
    print(f"Repo: {REPO}")
    print(f"Time: {datetime.now().isoformat(timespec='seconds')}")

    _, branch = run(["git", "status", "-sb"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-8"])
    _, diff = run(["git", "diff", "--stat"])
    _, porcelain = run(["git", "status", "--porcelain"])
    code, doctor = py("11_SCRIPTS/jarvis_cli.py", "doctor")

    print_block("Branch", branch)
    print_block("Doctor", doctor)
    print_block("Diff Stat", diff or "clean")
    print_block("Uncommitted Files", porcelain or "clean")
    print_block("Last Commits", commits)

    return code


def resume(save: bool = True) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_project_resume.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_project_resume.py")
        return 1

    args = ["--save"] if save else []
    code, out = py("11_SCRIPTS/jarvis_project_resume.py", *args)
    print(out)
    return code


def closeout(print_full: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_closeout.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_closeout.py")
        return 1

    args = ["--print"] if print_full else []
    code, out = py("11_SCRIPTS/jarvis_closeout.py", *args)
    print(out)
    return code


def sprint(goal: str, save: bool = True) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_sprint_builder.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_sprint_builder.py")
        return 1

    args = [goal]
    if save:
        args.append("--save")

    code, out = py("11_SCRIPTS/jarvis_sprint_builder.py", *args)
    print(out)
    return code



def forge(goal: str, save: bool = True) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_forge_cli.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_forge_cli.py")
        return 1

    args = [goal]
    if save:
        args.append("--save")

    code, out = py("11_SCRIPTS/jarvis_forge_cli.py", *args)
    print(out)
    return code


def clean() -> int:
    install_local_ignore()

    local_cleaner = REPO / "11_SCRIPTS" / "jarvis_local_cleaner.py"
    if local_cleaner.exists():
        code1, out1 = py("11_SCRIPTS/jarvis_local_cleaner.py", "install-ignore")
        code2, out2 = py("11_SCRIPTS/jarvis_local_cleaner.py", "report")
        code3, out3 = py("11_SCRIPTS/jarvis_local_cleaner.py", "status")
        print_block("Local Ignore", out1)
        print_block("Cleaner Report", out2)
        print_block("Git Status", out3)
        return max(code1, code2, code3)

    _, status_out = run(["git", "status", "-sb"])
    print("Local ignore installed for Ops Hub.")
    print(status_out)
    return 0


def next_action() -> int:
    queue = REPO / "11_SCRIPTS" / "jarvis_polish_queue.py"
    print("JARVIS OPS HUB — NEXT ACTION")

    if queue.exists():
        py("11_SCRIPTS/jarvis_polish_queue.py", "seed")
        _, out = py("11_SCRIPTS/jarvis_polish_queue.py", "next")
        print_block("Queue Suggestion", out)

    print_block(
        "Bigger Block Recommendation",
        "Create one larger feature block, validate with ops closeout, then commit expected files only."
    )

    print_block(
        "Useful Commands",
        "\n".join([
            f"{sys.executable} 11_SCRIPTS/jarvis_ops.py status",
            f"{sys.executable} 11_SCRIPTS/jarvis_ops.py sprint \"polir fluxo terminal do Jarvis\"",
            f"{sys.executable} 11_SCRIPTS/jarvis_ops.py closeout --print",
            "git diff --stat",
            "git status -sb",
        ])
    )

    return 0



def progress(save: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_progress_dashboard.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_progress_dashboard.py")
        return 1

    args = ["--save"] if save else []
    code, out = py("11_SCRIPTS/jarvis_progress_dashboard.py", *args)
    print(out)
    return code


def report() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    parts = []
    parts.append("# JARVIS Terminal Ops Hub — Block 106")
    parts.append("")
    parts.append(f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`")
    parts.append(f"Repo: `{REPO}`")
    parts.append("")

    for title, cmd in [
        ("Branch", ["git", "status", "-sb"]),
        ("Last Commits", ["git", "log", "--oneline", "--decorate", "-8"]),
        ("Diff Stat", ["git", "diff", "--stat"]),
        ("Uncommitted Files", ["git", "status", "--porcelain"]),
    ]:
        _, out = run(cmd)
        parts.append(f"## {title}")
        parts.append("")
        parts.append("```text")
        parts.append(out or "clean")
        parts.append("```")
        parts.append("")

    _, doctor = py("11_SCRIPTS/jarvis_cli.py", "doctor")
    parts.append("## Doctor")
    parts.append("")
    parts.append("```text")
    parts.append(doctor)
    parts.append("```")
    parts.append("")

    parts.append("## Ops Commands")
    parts.append("")
    parts.append("```bash")
    parts.append("python3 11_SCRIPTS/jarvis_ops.py status")
    parts.append("python3 11_SCRIPTS/jarvis_ops.py resume")
    parts.append("python3 11_SCRIPTS/jarvis_ops.py closeout")
    parts.append("python3 11_SCRIPTS/jarvis_ops.py closeout --print")
    parts.append("python3 11_SCRIPTS/jarvis_ops.py sprint \"melhorar Jarvis\"")
    parts.append("python3 11_SCRIPTS/jarvis_ops.py clean")
    parts.append("python3 11_SCRIPTS/jarvis_ops.py next")
    parts.append("```")
    parts.append("")

    REPORT.write_text("\n".join(parts), encoding="utf-8")
    print("OPS_REPORT_SAVED")
    print(REPORT)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 106 Terminal Ops Hub")
    sub = parser.add_subparsers(dest="cmd", required=True)



    p_improve = sub.add_parser("improve")
    p_improve.add_argument("goal", nargs="*", default=["melhorar", "autonomia", "do", "Jarvis"])
    p_improve.add_argument("--print", action="store_true")

    p_ship = sub.add_parser("ship")
    p_ship.add_argument("message", nargs="*", default=["chore: autoship Jarvis update"])
    p_ship.add_argument("--dry-run", action="store_true")
    p_ship.add_argument("--no-push", action="store_true")

    sub.add_parser("status")

    p_resume = sub.add_parser("resume")
    p_resume.add_argument("--print", action="store_true")

    p_closeout = sub.add_parser("closeout")
    p_closeout.add_argument("--print", action="store_true")

    p_sprint = sub.add_parser("sprint")
    p_sprint.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])


    p_forge = sub.add_parser("forge")
    p_forge.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_forge.add_argument("--print", action="store_true")

    sub.add_parser("clean")
    sub.add_parser("next")

    p_progress = sub.add_parser("progress")
    p_progress.add_argument("--save", action="store_true")

    sub.add_parser("report")

    args = parser.parse_args()



    if args.cmd == "improve":
        return improve(
            " ".join(args.goal).strip() or "melhorar autonomia do Jarvis",
            print_full=args.print,
        )

    if args.cmd == "ship":
        return autoship(
            " ".join(args.message).strip() or "chore: autoship Jarvis update",
            dry_run=args.dry_run,
            no_push=args.no_push,
        )

    if args.cmd == "status":
        return status()

    if args.cmd == "resume":
        return resume(save=not args.print)

    if args.cmd == "closeout":
        return closeout(print_full=args.print)

    if args.cmd == "sprint":
        return sprint(" ".join(args.goal).strip() or "melhorar Jarvis")


    if args.cmd == "forge":
        return forge(" ".join(args.goal).strip() or "melhorar Jarvis", save=not args.print)

    if args.cmd == "clean":
        return clean()

    if args.cmd == "next":
        return next_action()


    if args.cmd == "progress":
        return progress(save=args.save)

    if args.cmd == "report":
        return report()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
