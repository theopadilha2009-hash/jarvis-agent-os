from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "138_BRAIN_CONTRACT"
REPORT = OUT / "BRAIN_CONTRACT.md"
STATE = OUT / "BRAIN_CONTRACT.json"
BRAIN_LAST = REPO / "05_EXECUCAO" / "133_BRAIN_ROUTER" / "LAST_MODEL_RESPONSE.md"

BAD_PATTERNS = [
    r"\bcommit\b.*\b.env\b",
    r"\bapi key\b.*\bcommit\b",
    r"\btoken\b.*\bcommit\b",
    r"\bpush\b.*\bsem\b.*\bvalid",
    r"\bexecute\b.*\bprodução\b",
    r"\bignore\b.*\bsegurança\b",
    r"\bollama\b.*\bvalidation\b.*\blibrary\b",
    r"\bmódulo\b.*\bcommit\b",
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def build_prompt(goal: str, attempt: int) -> str:
    strictness = "normal" if attempt == 1 else "mais rígido; corrija qualquer resposta genérica ou inventada"

    return f"""
Você é o cérebro local do Jarvis Agent OS.

Objetivo:
{goal}

Modo: {strictness}

Responda SOMENTE com JSON válido. Não use markdown.
Não invente bibliotecas, módulos, comandos ou ferramentas.
Não mencione API keys, tokens ou segredos.
Não mexa em .env.
Não mande fazer push automático.
Não mande alterar produção.
Não diga que validou se não validou.

Schema obrigatório:
{{
  "summary": "resumo curto",
  "plan": ["passo seguro 1", "passo seguro 2", "passo seguro 3"],
  "risks": ["risco real 1"],
  "validation": ["git status -sb", "py -3 -m py_compile ..."],
  "forbidden_actions": ["não mexer em .env", "não commitar segredo", "não pushar de worker"],
  "safe_to_patch": false,
  "next_action": "próximo passo seguro"
}}

Regra final:
safe_to_patch deve ser false, a menos que exista validação clara e nenhuma ação arriscada.
""".strip()


def call_brain(goal: str, attempt: int) -> dict:
    prompt = build_prompt(goal, attempt)

    code, output = run([
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

    text = ""
    if BRAIN_LAST.exists():
        text = BRAIN_LAST.read_text(encoding="utf-8", errors="replace").strip()

    return {
        "attempt": attempt,
        "code": code,
        "raw_output_tail": output[-3000:] if output else "",
        "text": text,
    }


def extract_json(text: str) -> tuple[dict | None, str]:
    if not text.strip():
        return None, "EMPTY_RESPONSE"

    cleaned = text.strip()

    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None, "NO_JSON_OBJECT_FOUND"

    candidate = cleaned[start:end + 1]

    try:
        parsed = json.loads(candidate)
    except Exception as exc:
        return None, f"JSON_PARSE_ERROR: {exc}"

    if not isinstance(parsed, dict):
        return None, "JSON_NOT_OBJECT"

    return parsed, ""


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_contract(data: dict) -> dict:
    return {
        "summary": str(data.get("summary") or "").strip(),
        "plan": as_list(data.get("plan")),
        "risks": as_list(data.get("risks")),
        "validation": as_list(data.get("validation")),
        "forbidden_actions": as_list(data.get("forbidden_actions")),
        "safe_to_patch": bool(data.get("safe_to_patch") is True),
        "next_action": str(data.get("next_action") or "").strip(),
    }


def score_contract(contract: dict, source_text: str) -> dict:
    joined = json.dumps(contract, ensure_ascii=False).lower()
    source_lower = source_text.lower()

    bad_hits = []
    for pattern in BAD_PATTERNS:
        if re.search(pattern, joined + "\n" + source_lower, flags=re.IGNORECASE | re.DOTALL):
            bad_hits.append(pattern)

    score = 100

    if not contract["summary"]:
        score -= 15
    if len(contract["plan"]) < 3:
        score -= 20
    if not contract["risks"]:
        score -= 10
    if not contract["validation"]:
        score -= 20
    if not contract["forbidden_actions"]:
        score -= 15
    if not contract["next_action"]:
        score -= 10
    if bad_hits:
        score -= 40
    if contract["safe_to_patch"]:
        score -= 25

    validation_text = " ".join(contract["validation"]).lower()
    if "git status" not in validation_text:
        score -= 8
    if "py_compile" not in validation_text and "test" not in validation_text and "pytest" not in validation_text:
        score -= 8

    score = max(0, min(100, score))

    if bad_hits:
        verdict = "reject"
    elif score >= 75:
        verdict = "accept_as_plan"
    elif score >= 50:
        verdict = "review"
    else:
        verdict = "fallback"

    return {
        "score": score,
        "verdict": verdict,
        "bad_hits": bad_hits,
    }


def fallback_contract(goal: str) -> dict:
    return {
        "summary": f"Fallback seguro para: {goal}",
        "plan": [
            "Usar a resposta do modelo apenas como rascunho, não como executor.",
            "Gerar patch pequeno e validável em arquivo separado antes de alterar fluxo principal.",
            "Rodar git status e py_compile antes de qualquer commit.",
        ],
        "risks": [
            "Modelo local pequeno pode inventar biblioteca, comando ou validação.",
            "Resposta do modelo pode parecer convincente sem estar correta.",
        ],
        "validation": [
            "git status -sb",
            "py -3 -m py_compile 11_SCRIPTS\\jarvis_ops.py",
            ".\\jarvis.bat think \"melhorar autonomia do Jarvis\"",
        ],
        "forbidden_actions": [
            "não mexer em .env",
            "não commitar segredo",
            "não pushar de worker",
            "não aplicar patch automático baseado só em modelo local",
        ],
        "safe_to_patch": False,
        "next_action": "Criar patch proposal engine com validação antes de qualquer edição real.",
    }


def execute(goal: str, attempts: int) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    attempts = max(1, min(attempts, 3))
    records = []
    selected_contract = None
    selected_quality = None

    for attempt in range(1, attempts + 1):
        record = call_brain(goal, attempt)
        parsed, error = extract_json(record["text"])
        record["parse_error"] = error

        if parsed is not None:
            contract = normalize_contract(parsed)
            quality = score_contract(contract, record["text"])
            record["contract"] = contract
            record["quality"] = quality

            if quality["verdict"] in ["accept_as_plan", "review"]:
                selected_contract = contract
                selected_quality = quality
                records.append(record)
                break

        records.append(record)

    if selected_contract is None:
        selected_contract = fallback_contract(goal)
        selected_quality = {
            "score": 65,
            "verdict": "fallback",
            "bad_hits": [],
        }

    # Hard rule: never let local small model directly authorize patching yet.
    selected_contract["safe_to_patch"] = False

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "attempts_requested": attempts,
        "selected_quality": selected_quality,
        "selected_contract": selected_contract,
        "safe_to_apply_patch": False,
        "records": records,
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Brain Contract Loop — Block 138",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Goal: `{goal}`",
        f"Verdict: `{selected_quality['verdict']}`",
        f"Score: `{selected_quality['score']}`",
        "Safe to apply patch: `False`",
        "",
        "## Selected contract",
        "",
        "```json",
        json.dumps(selected_contract, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Attempts summary",
        "",
        "```json",
        json.dumps([
            {
                "attempt": r.get("attempt"),
                "code": r.get("code"),
                "parse_error": r.get("parse_error"),
                "quality": r.get("quality"),
                "text_preview": str(r.get("text") or "")[:600],
            }
            for r in records
        ], ensure_ascii=False, indent=2),
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("BRAIN_CONTRACT_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": selected_quality["verdict"],
        "score": selected_quality["score"],
        "safe_to_apply_patch": False,
        "next_action": selected_contract["next_action"],
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 138 Brain Contract Loop")
    parser.add_argument("goal", nargs="*", default=["melhorar autonomia do Jarvis"])
    parser.add_argument("--attempts", type=int, default=2)
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar autonomia do Jarvis"
    return execute(goal, attempts=args.attempts)


if __name__ == "__main__":
    raise SystemExit(main())
