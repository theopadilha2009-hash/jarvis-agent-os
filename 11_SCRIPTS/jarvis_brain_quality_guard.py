from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "137_BRAIN_QUALITY_GUARD"
REPORT = OUT / "BRAIN_QUALITY_GUARD.md"
STATE = OUT / "BRAIN_QUALITY_GUARD.json"
BRAIN_LAST = REPO / "05_EXECUCAO" / "133_BRAIN_ROUTER" / "LAST_MODEL_RESPONSE.md"


BAD_PATTERNS = [
    r"\bollama\b.*\bvalidation\b.*\blibrary\b",
    r"\buse o módulo\b.*\bcommit\b",
    r"\bsem verificar\b",
    r"\bexecute automaticamente\b.*\bpush\b",
    r"\bignore\b.*\bsegurança\b",
    r"\b.env\b.*\bcommit\b",
]

REQUIRED_SAFETY = [
    "não expor segredos",
    "não mexer em .env",
    "validar antes de commit",
    "não pushar de worker",
    "usar git status",
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def ask_brain(goal: str) -> tuple[int, str]:
    prompt = f"""
Você é o cérebro local do Jarvis Agent OS.

Responda em português simples.
Não invente bibliotecas.
Não diga para fazer push automático.
Não diga para mexer em .env.
Não use segredo, token ou API key.
Não proponha ações perigosas.

Objetivo:
{goal}

Formato obrigatório:
RESUMO:
- ...

PLANO SEGURO:
1. ...
2. ...
3. ...

RISCO:
- baixo/médio/alto + motivo

VALIDAÇÃO:
- comando(s) seguros para testar
""".strip()

    return run([
        sys.executable,
        "11_SCRIPTS/jarvis_brain_router.py",
        "prompt",
        prompt,
        "--task",
        "code",
        "--prefer",
        "ollama",
        "--allow-calls",
    ])


def score_text(text: str) -> dict:
    lower = text.lower()

    bad_hits = []
    for pattern in BAD_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE | re.DOTALL):
            bad_hits.append(pattern)

    required_hits = [item for item in REQUIRED_SAFETY if item in lower]

    has_structure = all(marker in text for marker in ["RESUMO:", "PLANO SEGURO:", "RISCO:", "VALIDAÇÃO:"])

    score = 100
    score -= len(bad_hits) * 25
    score -= max(0, 4 - len(required_hits)) * 8
    if not has_structure:
        score -= 25
    if len(text.strip()) < 200:
        score -= 20
    if len(text.strip()) > 3500:
        score -= 10

    score = max(0, min(100, score))

    if bad_hits:
        verdict = "reject"
    elif score >= 70:
        verdict = "accept"
    else:
        verdict = "review"

    return {
        "score": score,
        "verdict": verdict,
        "bad_hits": bad_hits,
        "required_hits": required_hits,
        "has_structure": has_structure,
        "length": len(text),
    }


def guard(goal: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    code, output = ask_brain(goal)

    model_text = ""
    if BRAIN_LAST.exists():
        model_text = BRAIN_LAST.read_text(encoding="utf-8", errors="replace").strip()

    quality = score_text(model_text)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "brain_code": code,
        "quality": quality,
        "model_text": model_text,
        "raw_output_tail": output[-3000:] if output else "",
        "safe_to_apply_patch": quality["verdict"] == "accept",
        "next_action": (
            "Use as planning input only; do not auto-edit code yet."
            if quality["verdict"] in ["accept", "review"]
            else "Reject this brain output and ask again with stricter prompt."
        ),
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Brain Quality Guard — Block 137",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Goal: `{goal}`",
        f"Verdict: `{quality['verdict']}`",
        f"Score: `{quality['score']}`",
        f"Safe to apply patch: `{payload['safe_to_apply_patch']}`",
        "",
        "## Quality",
        "",
        "```json",
        json.dumps(quality, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Model text",
        "",
        "```text",
        model_text or "-",
        "```",
        "",
        "## Next action",
        "",
        payload["next_action"],
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("BRAIN_QUALITY_GUARD_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": quality["verdict"],
        "score": quality["score"],
        "safe_to_apply_patch": payload["safe_to_apply_patch"],
        "length": quality["length"],
    }, ensure_ascii=False, indent=2))

    return 0 if quality["verdict"] in ["accept", "review"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 137 Brain Quality Guard")
    parser.add_argument("goal", nargs="*", default=["melhorar autonomia do Jarvis"])
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar autonomia do Jarvis"
    return guard(goal)


if __name__ == "__main__":
    raise SystemExit(main())
