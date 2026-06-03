from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "144_SHIP_GUARD"
REPORT = OUT / "SHIP_GUARD.md"
STATE = OUT / "SHIP_GUARD.json"

VALIDATION_COMMANDS = [
    ["py", "-3", "-m", "py_compile", "11_SCRIPTS\\jarvis_ops.py"],
    ["py", "-3", "-m", "py_compile", "11_SCRIPTS\\jarvis_main_cli.py"],
    ["py", "-3", "-m", "py_compile", "11_SCRIPTS\\jarvis_diff_review_gate.py"],
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def git_status() -> str:
    _, out = run(["git", "status", "-sb"])
    return out


def git_porcelain() -> str:
    _, out = run(["git", "status", "--porcelain"])
    return out


def write_report(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Ship Guard — Block 144",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Action: `{payload['action']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Can continue: `{payload['can_continue']}`",
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload["checks"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Blockers",
        "",
    ]

    if payload["blockers"]:
        for item in payload["blockers"]:
            lines.append(f"- {item}")
    else:
        lines.append("- No blockers.")

    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def preflight() -> int:
    status = git_status()
    porcelain = git_porcelain()

    checks = []
    blockers = []

    if not porcelain.strip():
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "action": "preflight",
            "verdict": "nothing_to_ship",
            "can_continue": True,
            "git_status": status,
            "checks": checks,
            "blockers": [],
        }
        write_report(payload)

        print("SHIP_GUARD_NOTHING_TO_SHIP")
        print(REPORT)
        print(json.dumps({
            "verdict": payload["verdict"],
            "can_continue": payload["can_continue"],
            "git_status": payload["git_status"],
        }, ensure_ascii=False, indent=2))
        return 0

    gate_code, gate_out = run(["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "diff-gate", "commit-gate"])
    checks.append({
        "name": "diff-gate commit-gate",
        "exit_code": gate_code,
        "output_tail": gate_out[-2000:],
    })

    if gate_code != 0:
        blockers.append("diff-gate blocked this ship.")

    for cmd in VALIDATION_COMMANDS:
        code, out = run(cmd)
        checks.append({
            "name": " ".join(cmd),
            "exit_code": code,
            "output_tail": out[-1000:],
        })
        if code != 0:
            blockers.append(f"validation failed: {' '.join(cmd)}")

    can_continue = len(blockers) == 0

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": "preflight",
        "verdict": "pass" if can_continue else "block",
        "can_continue": can_continue,
        "git_status": status,
        "checks": checks,
        "blockers": blockers,
    }

    write_report(payload)

    print("SHIP_GUARD_PREFLIGHT_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "can_continue": payload["can_continue"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return 0 if can_continue else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 144 Ship Guard")
    parser.add_argument("action", choices=["preflight"], default="preflight")
    args = parser.parse_args()

    if args.action == "preflight":
        return preflight()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
