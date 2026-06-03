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









def backlog(action: str = "apply-next") -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_autonomous_backlog.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_autonomous_backlog.py")
        return 1

    code, out = py("11_SCRIPTS/jarvis_autonomous_backlog.py", action)
    print(out)
    return code


def grow(limit: int = 2) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_growth_loop.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_growth_loop.py")
        return 1

    code, out = py("11_SCRIPTS/jarvis_growth_loop.py", "apply", "--limit", str(limit))
    print(out)
    return code


def patch_run(action: str = "apply-next", limit: int = 1) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_patch_runner.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_patch_runner.py")
        return 1

    args = [action]
    if action == "apply-next":
        args.extend(["--limit", str(limit)])

    code, out = py("11_SCRIPTS/jarvis_patch_runner.py", *args)
    print(out)
    return code


def auto_cycle(goal: str, no_apply: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_auto_cycle.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_auto_cycle.py")
        return 1

    args = [goal]
    if no_apply:
        args.append("--no-apply")

    code, out = py("11_SCRIPTS/jarvis_auto_cycle.py", *args)
    print(out)
    return code


def self_patch(action: str, patch: str = "cycle-command") -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_self_patch.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_self_patch.py")
        return 1

    args = [action]
    if action != "list":
        args.append(patch)

    code, out = py("11_SCRIPTS/jarvis_self_patch.py", *args)
    print(out)
    return code



def cycle(goal: str, print_full: bool = False) -> int:
    print("JARVIS CYCLE — IMPROVE")
    code1 = improve(goal, print_full=print_full)

    print("")
    print("JARVIS CYCLE — CLOSEOUT")
    code2 = closeout(print_full=False)

    return max(code1, code2)


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



def fast(goal: str, no_apply: bool = False) -> int:
    print("JARVIS FAST — AUTO CYCLE")
    code1 = auto_cycle(goal, no_apply=no_apply)

    print("")
    print("JARVIS FAST — STATUS")
    code2 = status()

    return max(code1, code2)




def health() -> int:
    print("JARVIS HEALTH — STATUS")
    code1 = status()

    print("")
    print("JARVIS HEALTH — PROGRESS")
    code2 = progress(save=False)

    return max(code1, code2)




def work(goal: str) -> int:
    print("JARVIS WORK — HEALTH")
    code1 = health() if "health" in globals() else status()

    print("")
    print("JARVIS WORK — IMPROVE")
    code2 = improve(goal, print_full=False)

    print("")
    print("JARVIS WORK — PATCH NEXT")
    code3 = patch_run("next", limit=1) if "patch_run" in globals() else 0

    return max(code1, code2, code3)




def sync_check() -> int:
    print("JARVIS SYNC CHECK — FETCH")
    code_fetch, out_fetch = run(["git", "fetch", "origin"])
    print(out_fetch or "fetch ok")

    print("")
    print("JARVIS SYNC CHECK — LOCAL")
    _, local = run(["git", "rev-parse", "--short", "HEAD"])
    print(local)

    print("")
    print("JARVIS SYNC CHECK — REMOTE")
    _, remote = run(["git", "rev-parse", "--short", "origin/main"])
    print(remote)

    print("")
    print("JARVIS SYNC CHECK — STATUS")
    code_status = status()

    return max(code_fetch, code_status)




def done() -> int:
    print("JARVIS DONE — CLOSEOUT")
    code1 = closeout(print_full=False)

    print("")
    print("JARVIS DONE — STATUS")
    code2 = status()

    return max(code1, code2)




def morning() -> int:
    print("JARVIS MORNING — SYNC CHECK")
    code1 = sync_check() if "sync_check" in globals() else status()

    print("")
    print("JARVIS MORNING — HEALTH")
    code2 = health() if "health" in globals() else status()

    print("")
    print("JARVIS MORNING — WORK")
    code3 = work("melhorar Jarvis") if "work" in globals() else improve("melhorar Jarvis", print_full=False)

    return max(code1, code2, code3)




def nightly() -> int:
    print("JARVIS NIGHTLY — DONE")
    code1 = done() if "done" in globals() else closeout(print_full=False)

    print("")
    print("JARVIS NIGHTLY — PROGRESS")
    code2 = progress(save=True) if "progress" in globals() else 0

    print("")
    print("JARVIS NIGHTLY — STATUS")
    code3 = status()

    return max(code1, code2, code3)




def autopilot(goal: str, limit: int = 2) -> int:
    print("JARVIS AUTOPILOT — GROW")
    code1 = grow(limit=limit) if "grow" in globals() else 0

    print("")
    print("JARVIS AUTOPILOT — WORK")
    code2 = work(goal) if "work" in globals() else improve(goal, print_full=False)

    print("")
    print("JARVIS AUTOPILOT — DONE")
    code3 = done() if "done" in globals() else closeout(print_full=False)

    return max(code1, code2, code3)




def snapshot(label: str = "manual") -> int:
    from datetime import datetime
    import json

    out_dir = REPO / "05_EXECUCAO" / "118_OPERATOR_EXPANSION"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / "SNAPSHOT_REPORT.md"

    _, status_out = run(["git", "status", "-sb"])
    _, porcelain_out = run(["git", "status", "--porcelain"])
    _, diff_out = run(["git", "diff", "--stat"])
    _, commits_out = run(["git", "log", "--oneline", "--decorate", "-12"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "git_clean": not bool(porcelain_out.strip()),
        "status": status_out,
        "diff": diff_out or "clean",
        "commits": commits_out,
    }

    lines = [
        "# JARVIS Snapshot — Block 118",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Label: **{label}**",
        f"Git clean: `{'yes' if payload['git_clean'] else 'no'}`",
        "",
        "## Status",
        "",
        "```text",
        status_out or "-",
        "```",
        "",
        "## Diff",
        "",
        "```text",
        diff_out or "clean",
        "```",
        "",
        "## Last Commits",
        "",
        "```text",
        commits_out or "-",
        "```",
        "",
        "## Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]

    report.write_text("\n".join(lines), encoding="utf-8")

    print("SNAPSHOT_SAVED")
    print(report)
    print(status_out)
    return 0




def review() -> int:
    print("JARVIS REVIEW — STATUS")
    code1 = status()

    print("")
    print("JARVIS REVIEW — PROGRESS")
    code2 = progress(save=True) if "progress" in globals() else 0

    print("")
    print("JARVIS REVIEW — CLOSEOUT")
    code3 = closeout(print_full=False)

    return max(code1, code2, code3)




def launch(goal: str, limit: int = 2) -> int:
    print("JARVIS LAUNCH — SNAPSHOT")
    code1 = snapshot("launch-start")

    print("")
    print("JARVIS LAUNCH — GROW")
    code2 = grow(limit=limit) if "grow" in globals() else 0

    print("")
    print("JARVIS LAUNCH — AUTOPILOT")
    code3 = autopilot(goal, limit=limit) if "autopilot" in globals() else work(goal)

    print("")
    print("JARVIS LAUNCH — FINAL SNAPSHOT")
    code4 = snapshot("launch-end")

    return max(code1, code2, code3, code4)




def mission(goal: str, steps: int = 2, plan_only: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_mission_engine.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_mission_engine.py")
        return 1

    args = [goal, "--steps", str(steps)]
    if plan_only:
        args.append("--plan-only")

    code, out = py("11_SCRIPTS/jarvis_mission_engine.py", *args)
    print(out)
    return code



def power(goal: str, steps: int = 2, autoship: bool = False, message: str = "") -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_power_loop.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_power_loop.py")
        return 1

    args = [goal, "--steps", str(steps)]
    if autoship:
        args.append("--ship")
    if message:
        args.extend(["--message", message])

    code, out = py("11_SCRIPTS/jarvis_power_loop.py", *args)
    print(out)
    return code



def task(action: str = "list", extra: list[str] | None = None) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_task_engine.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_task_engine.py")
        return 1

    args = [action]
    if extra:
        args.extend(extra)

    code, out = py("11_SCRIPTS/jarvis_task_engine.py", *args)
    print(out)
    return code



def decide(goal: str, plan_only: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_decision_engine.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_decision_engine.py")
        return 1

    args = [goal]
    if plan_only:
        args.append("--plan-only")

    code, out = py("11_SCRIPTS/jarvis_decision_engine.py", *args)
    print(out)
    return code



def plan_tasks() -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_task_planner.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_task_planner.py")
        return 1

    code, out = py("11_SCRIPTS/jarvis_task_planner.py", "seed")
    print(out)
    return code



def machine() -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_machine_sync.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_machine_sync.py")
        return 1

    code, out = py("11_SCRIPTS/jarvis_machine_sync.py", "check")
    print(out)
    return code



def session(action: str, goal: str, limit: int = 1, auto: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_session_runner.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_session_runner.py")
        return 1

    args = [action, goal, "--limit", str(limit)]
    if auto:
        args.append("--auto")

    code, out = py("11_SCRIPTS/jarvis_session_runner.py", *args)
    print(out)
    return code



def one(goal: str, auto: bool = False, limit: int = 1) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_operator_one.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_operator_one.py")
        return 1

    args = [goal, "--limit", str(limit)]
    if auto:
        args.append("--auto")

    code, out = py("11_SCRIPTS/jarvis_operator_one.py", *args)
    print(out)
    return code



def parallel(cmd: str, workers: int = 2) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_parallel_worktree.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_parallel_worktree.py")
        return 1

    code, out = py("11_SCRIPTS/jarvis_parallel_worktree.py", cmd, "--workers", str(workers))
    print(out)
    return code



def worker(action: str, workers: int = 2, goal: str = "melhorar autonomia do Jarvis", mode: str = "safe", timeout: int = 900) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_worker_auto_runner.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_worker_auto_runner.py")
        return 1

    code, out = py(
        "11_SCRIPTS/jarvis_worker_auto_runner.py",
        action,
        "--workers",
        str(workers),
        "--goal",
        goal,
        "--mode",
        mode,
        "--timeout",
        str(timeout),
    )
    print(out)
    return code



def brain(action: str, goal: str = "", task: str = "general", prefer: str = "auto", allow_calls: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_brain_router.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_brain_router.py")
        return 1

    args = [action]
    if goal:
        args.append(goal)
    args.extend(["--task", task, "--prefer", prefer])
    if allow_calls:
        args.append("--allow-calls")

    code, out = py("11_SCRIPTS/jarvis_brain_router.py", *args)
    print(out)
    return code



def brain_setup() -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_brain_setup_doctor.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_brain_setup_doctor.py")
        return 1

    code, out = py("11_SCRIPTS/jarvis_brain_setup_doctor.py", "doctor")
    print(out)
    return code



def brain_bootstrap(mode: str = "status") -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_free_brain_bootstrap.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_free_brain_bootstrap.py")
        return 1

    code, out = py("11_SCRIPTS/jarvis_free_brain_bootstrap.py", mode)
    print(out)
    return code



def brain_smoke(goal: str = "") -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_local_brain_smoke.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_local_brain_smoke.py")
        return 1

    args = []
    if goal:
        args.append(goal)

    code, out = py("11_SCRIPTS/jarvis_local_brain_smoke.py", *args)
    print(out)
    return code



def brain_guard(goal: str = "") -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_brain_quality_guard.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_brain_quality_guard.py")
        return 1

    args = []
    if goal:
        args.append(goal)

    code, out = py("11_SCRIPTS/jarvis_brain_quality_guard.py", *args)
    print(out)
    return code



def brain_contract(goal: str = "", attempts: int = 2) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_brain_contract.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_brain_contract.py")
        return 1

    args = []
    if goal:
        args.append(goal)
    args.extend(["--attempts", str(attempts)])

    code, out = py("11_SCRIPTS/jarvis_brain_contract.py", *args)
    print(out)
    return code



def patch_proposal(goal: str = "") -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_patch_proposal.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_patch_proposal.py")
        return 1

    args = []
    if goal:
        args.append(goal)

    code, out = py("11_SCRIPTS/jarvis_patch_proposal.py", *args)
    print(out)
    return code



def safe_apply(action: str = "plan", goal: str = "") -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_safe_apply.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_safe_apply.py")
        return 1

    args = [action]
    if goal:
        args.append(goal)

    code, out = py("11_SCRIPTS/jarvis_safe_apply.py", *args)
    print(out)
    return code



def safe_apply_v2(action: str = "prepare", goal: str = "", allow_bootstrap_dirty: bool = False) -> int:
    script = REPO / "11_SCRIPTS" / "jarvis_safe_apply_v2.py"
    if not script.exists():
        print("Missing script: 11_SCRIPTS/jarvis_safe_apply_v2.py")
        return 1

    args = [action]
    if goal:
        args.append(goal)
    if allow_bootstrap_dirty:
        args.append("--allow-bootstrap-dirty")

    code, out = py("11_SCRIPTS/jarvis_safe_apply_v2.py", *args)
    print(out)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 106 Terminal Ops Hub")
    sub = parser.add_subparsers(dest="cmd", required=True)






    p_fast = sub.add_parser("fast")
    p_fast.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_fast.add_argument("--no-apply", action="store_true")


    sub.add_parser("health")



    p_work = sub.add_parser("work")
    p_work.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])


    sub.add_parser("sync-check")


    sub.add_parser("done")




    sub.add_parser("morning")


    sub.add_parser("nightly")


    p_autopilot = sub.add_parser("autopilot")
    p_autopilot.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_autopilot.add_argument("--limit", type=int, default=2)







    sub.add_parser("plan-tasks")


    p_session = sub.add_parser("session")
    p_session.add_argument("action", choices=["start", "finish"])
    p_session.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_session.add_argument("--limit", type=int, default=1)
    p_session.add_argument("--auto", action="store_true")

    sub.add_parser("machine")

    p_decide = sub.add_parser("decide")
    p_decide.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_decide.add_argument("--plan-only", action="store_true")

    p_task = sub.add_parser("task")
    p_task.add_argument("action", nargs="?", choices=["list", "next", "run"], default="list")
    p_task.add_argument("--limit", type=int, default=3)

    p_power = sub.add_parser("power")
    p_power.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_power.add_argument("--steps", type=int, default=2)
    p_power.add_argument("--ship", action="store_true")
    p_power.add_argument("--message", default="")

    p_mission = sub.add_parser("mission")
    p_mission.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_mission.add_argument("--steps", type=int, default=2)
    p_mission.add_argument("--plan-only", action="store_true")

    p_snapshot = sub.add_parser("snapshot")
    p_snapshot.add_argument("label", nargs="*", default=["manual"])

    sub.add_parser("review")

    p_launch = sub.add_parser("launch")
    p_launch.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_launch.add_argument("--limit", type=int, default=2)

    p_backlog = sub.add_parser("backlog")
    p_backlog.add_argument("action", nargs="?", choices=["list", "apply-next"], default="apply-next")

    p_grow = sub.add_parser("grow")
    p_grow.add_argument("--limit", type=int, default=2)

    p_patch_run = sub.add_parser("patch-run")
    p_patch_run.add_argument("action", nargs="?", choices=["next", "apply-next"], default="apply-next")
    p_patch_run.add_argument("--limit", type=int, default=1)

    p_auto_cycle = sub.add_parser("auto-cycle")
    p_auto_cycle.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_auto_cycle.add_argument("--no-apply", action="store_true")

    p_self_patch = sub.add_parser("self-patch")
    p_self_patch.add_argument("action", choices=["list", "plan", "apply"])
    p_self_patch.add_argument("patch", nargs="?", default="cycle-command")


    p_cycle = sub.add_parser("cycle")
    p_cycle.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_cycle.add_argument("--print", action="store_true")

    p_improve = sub.add_parser("improve")
    p_improve.add_argument("goal", nargs="*", default=["melhorar", "autonomia", "do", "Jarvis"])
    p_improve.add_argument("--print", action="store_true")

    p_ship = sub.add_parser("ship")
    p_ship.add_argument("message", nargs="*", default=["chore: autoship Jarvis update"])
    p_ship.add_argument("--dry-run", action="store_true")
    p_ship.add_argument("--no-push", action="store_true")

    sub.add_parser("status")














    p_safe_apply_v2 = sub.add_parser("safe-apply-v2")
    p_safe_apply_v2.add_argument("action", choices=["prepare", "check", "apply-generated", "validate"])
    p_safe_apply_v2.add_argument("goal", nargs="*", default=[])
    p_safe_apply_v2.add_argument("--allow-bootstrap-dirty", action="store_true")

    p_safe_apply = sub.add_parser("safe-apply")
    p_safe_apply.add_argument("action", choices=["plan", "check", "apply-template"])
    p_safe_apply.add_argument("goal", nargs="*", default=[])

    p_patch_proposal = sub.add_parser("patch-proposal")
    p_patch_proposal.add_argument("goal", nargs="*", default=[])

    p_brain_contract = sub.add_parser("brain-contract")
    p_brain_contract.add_argument("goal", nargs="*", default=[])
    p_brain_contract.add_argument("--attempts", type=int, default=2)

    p_brain_guard = sub.add_parser("brain-guard")
    p_brain_guard.add_argument("goal", nargs="*", default=[])

    p_brain_smoke = sub.add_parser("brain-smoke")
    p_brain_smoke.add_argument("goal", nargs="*", default=[])

    p_brain_bootstrap = sub.add_parser("brain-bootstrap")
    p_brain_bootstrap.add_argument("mode", choices=["status", "ollama-plan", "groq-plan"], nargs="?", default="status")

    sub.add_parser("brain-setup")

    p_brain = sub.add_parser("brain")
    p_brain.add_argument("action", choices=["status", "route", "prompt"])
    p_brain.add_argument("goal", nargs="*", default=[])
    p_brain.add_argument("--task", default="general")
    p_brain.add_argument("--prefer", default="auto")
    p_brain.add_argument("--allow-calls", action="store_true")

    p_worker = sub.add_parser("worker")
    p_worker.add_argument("action", choices=["plan", "run", "open", "status", "collect"])
    p_worker.add_argument("--workers", type=int, default=2)
    p_worker.add_argument("--goal", default="melhorar autonomia do Jarvis")
    p_worker.add_argument("--mode", choices=["safe", "think", "session"], default="safe")
    p_worker.add_argument("--timeout", type=int, default=900)

    p_parallel = sub.add_parser("parallel")
    p_parallel.add_argument("action", choices=["init", "status", "clean"])
    p_parallel.add_argument("--workers", type=int, default=2)

    p_one = sub.add_parser("one")
    p_one.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_one.add_argument("--auto", action="store_true")
    p_one.add_argument("--limit", type=int, default=1)

    p_resume = sub.add_parser("resume")
    p_resume.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])

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






    if args.cmd == "fast":
        return fast(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            no_apply=args.no_apply,
        )


    if args.cmd == "health":
        return health()



    if args.cmd == "work":
        return work(" ".join(args.goal).strip() or "melhorar Jarvis")


    if args.cmd == "sync-check":
        return sync_check()


    if args.cmd == "done":
        return done()




    if args.cmd == "morning":
        return morning()


    if args.cmd == "nightly":
        return nightly()


    if args.cmd == "autopilot":
        return autopilot(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            limit=args.limit,
        )







    if args.cmd == "plan-tasks":
        return plan_tasks()


    if args.cmd == "session":
        return session(
            args.action,
            " ".join(args.goal).strip() or "melhorar Jarvis",
            limit=args.limit,
            auto=args.auto,
        )

    if args.cmd == "machine":
        return machine()

    if args.cmd == "decide":
        return decide(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            plan_only=args.plan_only,
        )

    if args.cmd == "task":
        extra = ["--limit", str(args.limit)] if args.action == "run" else None
        return task(args.action, extra=extra)

    if args.cmd == "power":
        return power(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            steps=args.steps,
            autoship=args.ship,
            message=args.message,
        )

    if args.cmd == "mission":
        return mission(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            steps=args.steps,
            plan_only=args.plan_only,
        )

    if args.cmd == "snapshot":
        return snapshot(" ".join(args.label).strip() or "manual")

    if args.cmd == "review":
        return review()

    if args.cmd == "launch":
        return launch(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            limit=args.limit,
        )

    if args.cmd == "backlog":
        return backlog(args.action)

    if args.cmd == "grow":
        return grow(limit=args.limit)

    if args.cmd == "patch-run":
        return patch_run(args.action, limit=args.limit)

    if args.cmd == "auto-cycle":
        return auto_cycle(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            no_apply=args.no_apply,
        )

    if args.cmd == "self-patch":
        return self_patch(args.action, args.patch)


    if args.cmd == "cycle":
        return cycle(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            print_full=args.print,
        )

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














    if args.cmd == "safe-apply-v2":
        return safe_apply_v2(
            args.action,
            " ".join(args.goal).strip(),
            allow_bootstrap_dirty=args.allow_bootstrap_dirty,
        )

    if args.cmd == "safe-apply":
        return safe_apply(args.action, " ".join(args.goal).strip())

    if args.cmd == "patch-proposal":
        return patch_proposal(" ".join(args.goal).strip())

    if args.cmd == "brain-contract":
        return brain_contract(" ".join(args.goal).strip(), attempts=args.attempts)

    if args.cmd == "brain-guard":
        return brain_guard(" ".join(args.goal).strip())

    if args.cmd == "brain-smoke":
        return brain_smoke(" ".join(args.goal).strip())

    if args.cmd == "brain-bootstrap":
        return brain_bootstrap(args.mode)

    if args.cmd == "brain-setup":
        return brain_setup()

    if args.cmd == "brain":
        return brain(
            args.action,
            " ".join(args.goal).strip(),
            task=args.task,
            prefer=args.prefer,
            allow_calls=args.allow_calls,
        )

    if args.cmd == "worker":
        return worker(
            args.action,
            workers=args.workers,
            goal=args.goal,
            mode=args.mode,
            timeout=args.timeout,
        )

    if args.cmd == "parallel":
        return parallel(args.action, workers=args.workers)

    if args.cmd == "one":
        return one(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            auto=args.auto,
            limit=args.limit,
        )

    if args.cmd == "resume":
        return resume(" ".join(args.goal).strip() or "melhorar Jarvis")

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
