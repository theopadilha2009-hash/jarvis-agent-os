from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "140_SAFE_APPLY_ENGINE"
REPORT = OUT / "SAFE_APPLY_ENGINE.md"
STATE = OUT / "SAFE_APPLY_ENGINE.json"
PROPOSAL_STATE = REPO / "05_EXECUCAO" / "139_PATCH_PROPOSAL" / "PATCH_PROPOSAL.json"

ALLOWED_PREFIXES = [
    "11_SCRIPTS/",
    "05_EXECUCAO/",
]

BLOCKED_PARTS = [
    ".env",
    ".git/",
    "secret",
    "secrets",
    "token",
    "credential",
    "credentials",
    "password",
    "node_modules/",
    "__pycache__/",
]

DEFAULT_VALIDATIONS = [
    "git status -sb",
    "py -3 -m py_compile 11_SCRIPTS\\jarvis_ops.py",
    ".\\jarvis.bat think \"melhorar autonomia do Jarvis\"",
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def normalize_path(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("/")


def is_allowed_path(path: str) -> bool:
    p = normalize_path(path)
    lower = p.lower()

    if not p:
        return False

    if any(blocked in lower for blocked in BLOCKED_PARTS):
        return False

    return any(p.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def load_or_create_proposal(goal: str) -> dict:
    if not PROPOSAL_STATE.exists():
        run([
            sys.executable,
            "11_SCRIPTS/jarvis_patch_proposal.py",
            goal,
        ])

    if PROPOSAL_STATE.exists():
        return json.loads(PROPOSAL_STATE.read_text(encoding="utf-8", errors="replace"))

    return {
        "mode": "fallback",
        "goal": goal,
        "proposed_files": [],
        "blockers": ["PATCH_PROPOSAL_NOT_FOUND"],
        "can_apply_now": False,
    }


def git_status() -> str:
    _, out = run(["git", "status", "-sb"])
    return out


def build_safe_plan(goal: str) -> dict:
    proposal = load_or_create_proposal(goal)
    proposed_files = proposal.get("proposed_files") or []

    checked_files = []
    blockers = []

    for item in proposed_files:
        path = normalize_path(item.get("path", ""))
        allowed = is_allowed_path(path)

        checked_files.append({
            "path": path,
            "action": item.get("action", "unknown"),
            "reason": item.get("reason", ""),
            "allowed": allowed,
            "tracked_write_allowed_now": False,
        })

        if not allowed:
            blockers.append(f"Blocked path: {path}")

    if proposal.get("can_apply_now") is True:
        blockers.append("Proposal attempted can_apply_now=true; overridden by safe apply gate.")

    if proposal.get("blockers"):
        blockers.extend([str(x) for x in proposal.get("blockers")])

    status = git_status()

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "mode": "safe_gate",
        "proposal_mode": proposal.get("mode"),
        "checked_files": checked_files,
        "blockers": blockers,
        "tracked_patch_allowed": False,
        "template_output_allowed": True,
        "validations": DEFAULT_VALIDATIONS,
        "git_status": status,
        "next_action": (
            "Use apply-template only. Tracked code application remains blocked until Safe Apply v2."
        ),
    }

    return payload


def write(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Safe Apply Engine — Block 140",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Goal: `{payload['goal']}`",
        f"Mode: `{payload['mode']}`",
        f"Tracked patch allowed: `{payload['tracked_patch_allowed']}`",
        f"Template output allowed: `{payload['template_output_allowed']}`",
        "",
        "## Checked files",
        "",
        "```json",
        json.dumps(payload["checked_files"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Blockers",
        "",
    ]

    if payload["blockers"]:
        for item in payload["blockers"]:
            lines.append(f"- {item}")
    else:
        lines.append("- No hard blockers for planning/template output.")

    lines += [
        "",
        "## Validations",
        "",
        "```powershell",
        "\n".join(payload["validations"]),
        "```",
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
        "## Next action",
        "",
        payload["next_action"],
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def plan(goal: str) -> int:
    payload = build_safe_plan(goal)
    write(payload)

    print("SAFE_APPLY_PLAN_DONE")
    print(REPORT)
    print(json.dumps({
        "tracked_patch_allowed": payload["tracked_patch_allowed"],
        "template_output_allowed": payload["template_output_allowed"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return 0


def check(goal: str) -> int:
    payload = build_safe_plan(goal)

    dirty = "\n" in payload["git_status"] or " M " in payload["git_status"] or "??" in payload["git_status"]
    if dirty:
        payload["blockers"].append("Git working tree is not clean.")

    write(payload)

    hard_block = any("Blocked path:" in item for item in payload["blockers"])
    exit_code = 1 if hard_block else 0

    print("SAFE_APPLY_CHECK_DONE")
    print(REPORT)
    print(json.dumps({
        "exit_code": exit_code,
        "tracked_patch_allowed": payload["tracked_patch_allowed"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return exit_code


def apply_template(goal: str) -> int:
    payload = build_safe_plan(goal)

    template_path = OUT / "SAFE_TEMPLATE_OUTPUT.md"
    template_lines = [
        "# Safe Template Output",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Goal: `{goal}`",
        "",
        "This is a safe local output generated by Jarvis.",
        "It does not modify tracked source code.",
        "",
        "## Planned validations",
        "",
    ]

    for cmd in payload["validations"]:
        template_lines.append(f"- `{cmd}`")

    template_path.write_text("\n".join(template_lines), encoding="utf-8")

    payload["template_output"] = str(template_path)
    write(payload)

    print("SAFE_APPLY_TEMPLATE_DONE")
    print(REPORT)
    print(json.dumps({
        "template_output": str(template_path),
        "tracked_patch_allowed": False,
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 140 Safe Apply Engine")
    parser.add_argument("action", choices=["plan", "check", "apply-template"])
    parser.add_argument("goal", nargs="*", default=["melhorar autonomia do Jarvis"])
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar autonomia do Jarvis"

    if args.action == "plan":
        return plan(goal)

    if args.action == "check":
        return check(goal)

    if args.action == "apply-template":
        return apply_template(goal)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
