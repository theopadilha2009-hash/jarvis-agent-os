from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "112_AUTO_CYCLE_RUNNER"
REPORT = OUT / "AUTO_CYCLE_REPORT.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py(script: str, *args: str) -> tuple[int, str]:
    return run([sys.executable, script, *args])


def git_status() -> str:
    _, out = run(["git", "status", "-sb"])
    return out


def git_porcelain() -> str:
    _, out = run(["git", "status", "--porcelain"])
    return out


def safe_patch_available() -> bool:
    return (REPO / "11_SCRIPTS" / "jarvis_self_patch.py").exists()


def run_self_patch(apply_patch: bool) -> tuple[int, str]:
    if not safe_patch_available():
        return 0, "self patch unavailable"

    outputs = []

    code, out = py("11_SCRIPTS/jarvis_self_patch.py", "plan", "next")
    outputs.append("SELF_PATCH_PLAN\n" + (out or "-"))

    if apply_patch:
        code2, out2 = py("11_SCRIPTS/jarvis_self_patch.py", "apply", "next")
        outputs.append("SELF_PATCH_APPLY\n" + (out2 or "-"))
        return max(code, code2), "\n\n".join(outputs)

    return code, "\n\n".join(outputs)


def build_report(goal: str, outputs: list[str]) -> str:
    _, commits = run(["git", "log", "--oneline", "--decorate", "-10"])
    _, diff = run(["git", "diff", "--stat"])
    porcelain = git_porcelain()

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "git_clean": not bool(porcelain.strip()),
        "status": git_status(),
        "diff": diff,
    }

    lines = [
        "# JARVIS Auto Cycle Runner — Block 112",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Goal: **{goal}**",
        f"Git clean: `{'yes' if payload['git_clean'] else 'no'}`",
        "",
        "## Command Output",
        "",
        "```text",
        "\n\n".join(outputs).strip() or "-",
        "```",
        "",
        "## Git Status",
        "",
        "```text",
        payload["status"] or "-",
        "```",
        "",
        "## Diff",
        "",
        "```text",
        diff or "clean",
        "```",
        "",
        "## Uncommitted",
        "",
        "```text",
        porcelain or "clean",
        "```",
        "",
        "## Last Commits",
        "",
        "```text",
        commits or "-",
        "```",
        "",
        "## Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]

    return "\n".join(lines)


def auto_cycle(goal: str, apply_patch: bool = True) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []

    code, out = py("11_SCRIPTS/jarvis_ops.py", "improve", goal)
    outputs.append("IMPROVE\n" + (out or "-"))

    code_patch, out_patch = run_self_patch(apply_patch)
    outputs.append(out_patch)

    code_cycle, out_cycle = py("11_SCRIPTS/jarvis_ops.py", "cycle", goal)
    outputs.append("CYCLE\n" + (out_cycle or "-"))

    code_closeout, out_closeout = py("11_SCRIPTS/jarvis_ops.py", "closeout")
    outputs.append("CLOSEOUT\n" + (out_closeout or "-"))

    report = build_report(goal, outputs)
    REPORT.write_text(report, encoding="utf-8")

    print("AUTO_CYCLE_DONE")
    print(REPORT)
    print(git_status())

    return max(code, code_patch, code_cycle, code_closeout)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 112 Auto Cycle Runner")
    parser.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    parser.add_argument("--no-apply", action="store_true")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar Jarvis"
    return auto_cycle(goal, apply_patch=not args.no_apply)


if __name__ == "__main__":
    raise SystemExit(main())
