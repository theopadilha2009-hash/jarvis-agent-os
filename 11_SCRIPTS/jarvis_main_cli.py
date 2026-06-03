from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "132_MAIN_CLI"
REPORT = OUT / "JARVIS_MAIN_CLI_REPORT.md"
STATE = OUT / "JARVIS_MAIN_CLI_STATE.json"

DEFAULT_GOAL = "melhorar autonomia do Jarvis"


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        cwd=cwd or REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def ops(*args: str) -> tuple[int, str]:
    return run([sys.executable, "11_SCRIPTS/jarvis_ops.py", *args])


def py_compile_core() -> tuple[int, str]:
    files = [
        "11_SCRIPTS/jarvis_safe_apply_v2.py",
        "11_SCRIPTS/jarvis_safe_apply.py",
        "11_SCRIPTS/jarvis_patch_proposal.py",
        "11_SCRIPTS/jarvis_brain_contract.py",
        "11_SCRIPTS/jarvis_brain_quality_guard.py",
        "11_SCRIPTS/jarvis_local_brain_smoke.py",
        "11_SCRIPTS/jarvis_free_brain_bootstrap.py",
        "11_SCRIPTS/jarvis_brain_setup_doctor.py",
        "11_SCRIPTS/jarvis_brain_router.py",
        "11_SCRIPTS/jarvis_worker_auto_runner.py",
        "11_SCRIPTS/jarvis_parallel_worktree.py",
        "11_SCRIPTS/jarvis_operator_one.py",
        "11_SCRIPTS/jarvis_resume.py",
        "11_SCRIPTS/jarvis_session_runner.py",
        "11_SCRIPTS/jarvis_machine_sync.py",
        "11_SCRIPTS/jarvis_ops.py",
        "11_SCRIPTS/jarvis_local_cleaner.py",
        "11_SCRIPTS/jarvis_cli.py",
        "11_SCRIPTS/jarvis_api.py",
        "11_SCRIPTS/jarvis_core.py",
        "11_SCRIPTS/jarvis_main_cli.py",
    ]
    existing = [f for f in files if (REPO / f).exists()]
    return run([sys.executable, "-m", "py_compile", *existing])


def step(name: str, args: list[str]) -> dict:
    code, out = ops(*args)
    return {
        "name": name,
        "command": ["jarvis_ops.py", *args],
        "code": code,
        "output": out[-7000:] if out else "",
    }


def shell_step(name: str, cmd: list[str]) -> dict:
    code, out = run(cmd)
    return {
        "name": name,
        "command": cmd,
        "code": code,
        "output": out[-7000:] if out else "",
    }


def execute(action: str, goal: str, workers: int, timeout: int, message: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    steps: list[dict] = []

    if action == "start":
        steps.append(step("machine", ["machine"]))
        steps.append(step("brain-bootstrap", ["brain-bootstrap", "status"]))
        steps.append(step("brain-setup", ["brain-setup"]))
        steps.append(step("parallel-status", ["parallel", "status", "--workers", str(workers)]))
        steps.append(step("resume", ["resume", goal]))
        steps.append(step("session-start", ["session", "start", goal]))

    elif action == "think":
        steps.append(step("brain-route", ["brain", "route", goal, "--task", "research"]))
        steps.append(step("brain-prompt-local", ["brain", "prompt", goal, "--task", "research", "--prefer", "auto", "--allow-calls"]))
        steps.append(step("brain-quality-guard", ["brain-guard", goal]))
        steps.append(step("brain-contract", ["brain-contract", goal, "--attempts", "2"]))
        steps.append(step("resume", ["resume", goal]))
        steps.append(step("decision-plan", ["decide", goal, "--plan-only"]))
        steps.append(step("worker-think-plan", ["worker", "plan", "--workers", str(workers), "--goal", goal, "--mode", "think"]))

    elif action == "build":
        steps.append(step("brain-route", ["brain", "route", goal, "--task", "code"]))
        steps.append(step("brain-prompt-local", ["brain", "prompt", goal, "--task", "code", "--prefer", "auto", "--allow-calls"]))
        steps.append(step("brain-quality-guard-code", ["brain-guard", goal]))
        steps.append(step("brain-contract-code", ["brain-contract", goal, "--attempts", "2"]))
        steps.append(step("patch-proposal", ["patch-proposal", goal]))
        steps.append(step("safe-apply-check", ["safe-apply", "check", goal]))
        steps.append(step("safe-apply-v2-check", ["safe-apply-v2", "check", goal]))
        steps.append(step("safe-apply-plan", ["safe-apply", "plan", goal]))
        steps.append(step("safe-apply-v2-prepare", ["safe-apply-v2", "prepare", goal]))
        steps.append(step("parallel-init", ["parallel", "init", "--workers", str(workers)]))
        steps.append(step("worker-safe-run", ["worker", "run", "--workers", str(workers), "--goal", goal, "--mode", "safe", "--timeout", str(timeout)]))
        steps.append(step("worker-collect", ["worker", "collect", "--workers", str(workers), "--goal", goal, "--mode", "safe"]))

    elif action == "fix":
        steps.append(shell_step("py-compile-core", [sys.executable, "-m", "py_compile", "11_SCRIPTS/jarvis_ops.py", "11_SCRIPTS/jarvis_main_cli.py"]))
        steps.append(step("worker-collect", ["worker", "collect", "--workers", str(workers), "--goal", goal, "--mode", "safe"]))
        steps.append(step("worker-status", ["worker", "status", "--workers", str(workers)]))
        steps.append(step("status", ["status"]))

    elif action == "ship":
        code, out = py_compile_core()
        steps.append({
            "name": "py-compile-core",
            "command": ["python", "-m", "py_compile", "core scripts"],
            "code": code,
            "output": out[-7000:] if out else "",
        })
        steps.append(step("status-before-ship", ["status"]))
        steps.append(step("ship", ["ship", message or f"chore: Jarvis {goal}"]))
        steps.append(step("status-after-ship", ["status"]))

    else:
        raise ValueError(f"unknown action: {action}")

    _, git_status = run(["git", "status", "-sb"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-8"])

    hard_codes = [item["code"] for item in steps if item["code"] not in (0,)]
    exit_code = 1 if hard_codes else 0

    # Ship may return non-zero when there is nothing to ship; keep that as soft if repo is clean.
    if action == "ship":
        combined = "\n".join(item.get("output", "") for item in steps)
        if "NOTHING_TO_SHIP" in combined or "nothing to commit" in combined:
            exit_code = 0

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "goal": goal,
        "workers": workers,
        "timeout": timeout,
        "message": message,
        "exit_code": exit_code,
        "git_status": git_status,
        "commits": commits,
        "steps": steps,
    }

    write_outputs(payload)

    print("JARVIS_MAIN_DONE")
    print(REPORT)
    print(json.dumps({
        "action": action,
        "exit_code": exit_code,
        "git_status": git_status,
    }, ensure_ascii=False, indent=2))

    return exit_code


def write_outputs(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Main CLI — Block 132",
        "",
        f"Generated at: `{payload.get('created_at')}`",
        f"Action: `{payload.get('action')}`",
        f"Goal: `{payload.get('goal')}`",
        f"Exit code: `{payload.get('exit_code')}`",
        "",
        "## Git Status",
        "",
        "```text",
        payload.get("git_status") or "-",
        "```",
        "",
        "## Steps",
        "",
    ]

    for item in payload.get("steps", []):
        lines += [
            f"### {item.get('name')}",
            "",
            f"Code: `{item.get('code')}`",
            "",
            "```text",
            item.get("output") or "-",
            "```",
            "",
        ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="JARVIS Main CLI: 5 comandos principais"
    )

    parser.add_argument(
        "action",
        choices=["start", "think", "build", "fix", "ship"],
        help="Comando principal do Jarvis",
    )
    parser.add_argument("goal", nargs="*", default=[DEFAULT_GOAL])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--message", default="")

    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or DEFAULT_GOAL
    workers = max(1, min(args.workers, 5))

    return execute(
        args.action,
        goal,
        workers=workers,
        timeout=args.timeout,
        message=args.message,
    )


if __name__ == "__main__":
    raise SystemExit(main())
