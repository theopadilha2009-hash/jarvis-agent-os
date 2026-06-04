from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "139_PATCH_PROPOSAL"
REPORT = OUT / "PATCH_PROPOSAL.md"
STATE = OUT / "PATCH_PROPOSAL.json"
CONTRACT_STATE = REPO / "05_EXECUCAO" / "138_BRAIN_CONTRACT" / "BRAIN_CONTRACT.json"

ALLOWED_DIRS = [
    "11_SCRIPTS/",
    "05_EXECUCAO/",
]

BLOCKED_PATH_PARTS = [
    ".env",
    "secrets",
    "token",
    "credential",
    ".git/",
    "node_modules/",
    "__pycache__/",
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def load_contract(goal: str) -> dict:
    if not CONTRACT_STATE.exists():
        run([
            sys.executable,
            "11_SCRIPTS/jarvis_brain_contract.py",
            goal,
            "--attempts",
            "2",
        ])

    if CONTRACT_STATE.exists():
        return json.loads(CONTRACT_STATE.read_text(encoding="utf-8", errors="replace"))

    return {
        "selected_contract": {
            "summary": "Fallback: contrato não encontrado.",
            "plan": [
                "Gerar proposta segura sem aplicar patch.",
                "Validar git status e py_compile.",
                "Aguardar autorização para aplicar.",
            ],
            "validation": [
                "git status -sb",
                "py -3 -m py_compile 11_SCRIPTS/jarvis_ops.py",
            ],
            "risks": ["Contrato ausente."],
            "forbidden_actions": ["não mexer em .env", "não commitar segredo"],
            "safe_to_patch": False,
            "next_action": "Criar proposta manual segura.",
        },
        "selected_quality": {
            "verdict": "fallback",
            "score": 50,
        },
    }


def path_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")

    if any(part.lower() in normalized.lower() for part in BLOCKED_PATH_PARTS):
        return False

    return any(normalized.startswith(prefix) for prefix in ALLOWED_DIRS)


def build_proposal(goal: str) -> dict:
    contract_payload = load_contract(goal)
    contract = contract_payload.get("selected_contract") or {}
    quality = contract_payload.get("selected_quality") or {}

    proposed_files = [
        {
            "path": "11_SCRIPTS/jarvis_patch_proposal.py",
            "action": "create_or_update",
            "reason": "Generate safe patch proposals from accepted brain contracts.",
            "allowed": True,
        },
        {
            "path": "11_SCRIPTS/jarvis_ops.py",
            "action": "update",
            "reason": "Expose proposal command in Jarvis ops CLI.",
            "allowed": True,
        },
        {
            "path": "11_SCRIPTS/jarvis_main_cli.py",
            "action": "update",
            "reason": "Connect proposal step to build flow.",
            "allowed": True,
        },
        {
            "path": "11_SCRIPTS/jarvis_local_cleaner.py",
            "action": "update",
            "reason": "Ignore local execution outputs for patch proposal reports.",
            "allowed": True,
        },
    ]

    for item in proposed_files:
        item["allowed"] = path_allowed(item["path"])

    blockers = []

    if not all(item["allowed"] for item in proposed_files):
        blockers.append("One or more proposed paths are not allowed.")

    if quality.get("verdict") not in ["accept_as_plan", "review", "fallback"]:
        blockers.append(f"Contract quality verdict not allowed: {quality.get('verdict')}")

    if contract.get("safe_to_patch") is True:
        blockers.append("Local brain tried to authorize patching directly; overridden to proposal-only.")

    code, status = run(["git", "status", "-sb"])

    proposal = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "mode": "proposal_only",
        "contract_quality": quality,
        "contract_summary": contract.get("summary"),
        "contract_plan": contract.get("plan") or [],
        "contract_validation": contract.get("validation") or [],
        "proposed_files": proposed_files,
        "blockers": blockers,
        "can_apply_now": False,
        "requires_human_or_safe_apply_engine": True,
        "git_status": status,
        "next_action": "Run validation, then use future safe-apply engine to apply only allowlisted proposals.",
    }

    return proposal


def write(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Patch Proposal Engine — Block 139",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Goal: `{payload['goal']}`",
        f"Mode: `{payload['mode']}`",
        f"Can apply now: `{payload['can_apply_now']}`",
        "",
        "## Contract quality",
        "",
        "```json",
        json.dumps(payload["contract_quality"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Proposed files",
        "",
        "```json",
        json.dumps(payload["proposed_files"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Blockers",
        "",
    ]

    if payload["blockers"]:
        for item in payload["blockers"]:
            lines.append(f"- {item}")
    else:
        lines.append("- No hard blockers, but proposal-only mode remains active.")

    lines += [
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


def execute(goal: str) -> int:
    payload = build_proposal(goal)
    write(payload)

    print("PATCH_PROPOSAL_DONE")
    print(REPORT)
    print(json.dumps({
        "mode": payload["mode"],
        "can_apply_now": payload["can_apply_now"],
        "proposed_files": len(payload["proposed_files"]),
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 139 Patch Proposal Engine")
    parser.add_argument("goal", nargs="*", default=["melhorar autonomia do Jarvis"])
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar autonomia do Jarvis"
    return execute(goal)


if __name__ == "__main__":
    raise SystemExit(main())
