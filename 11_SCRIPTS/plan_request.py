"""
plan_request.py — turn a natural-language request into a one-page local
execution plan WITHOUT calling any LLM.

Reuses ask_router's intent classifier + project resolver, then prints:
  - interpreted intent
  - safety level
  - exact next command JARVIS would run
  - suggested Claude mission type (informational; JARVIS does not run Claude)
  - expected validation gates
  - explicit "what JARVIS will not do" list

With --save, also writes the plan to
  05_EXECUCAO/33_PLANS/<timestamp>_<slug>.md

This is different from blueprint:
  - blueprint creates a full project spec package
  - plan answers "what should I do next about THIS request, and what is safe?"
"""
from pathlib import Path
from datetime import datetime
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PLANS_DIR = ROOT / "05_EXECUCAO" / "33_PLANS"

# Reuse classifier + project resolver from ask_router so plan and ask stay
# semantically consistent. No LLM call.
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
from ask_router import (  # type: ignore
    detect_intent,
    detect_project_alias,
    _next_command_for,
    _explain_intent,
    INTENT_SELF_EVOLVE,
    INTENT_PROJECT_FIX,
    INTENT_PROJECT_QA,
    INTENT_BROWSER_QA,
    INTENT_FINAL_GATE,
    INTENT_N8N_BLUEPRINT,
    INTENT_APP_BLUEPRINT,
    INTENT_AUTOMATION_BLUEPRINT,
    INTENT_RESEARCH_PLAN,
    INTENT_AGENDA_NOTE,
    INTENT_CAPTURE_NOTE,
    INTENT_OPEN_PROJECT,
    INTENT_NEXT_ACTION,
    INTENT_UNCLEAR,
)


def parse_args(argv):
    text_parts = []
    alias = None
    save = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            if i + 1 < len(argv):
                alias = argv[i + 1].strip().lower()
                i += 2
                continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--save":
            save = True
            i += 1
            continue
        text_parts.append(a)
        i += 1
    return " ".join(text_parts).strip(), alias, save


# Mapping intent -> (claude_mission_type, expected_validation_lines).
# Used only to advise Theo; JARVIS never runs Claude.
_MISSION_SUGGESTION = {
    INTENT_SELF_EVOLVE: ("self-evolve", [
        "env JARVIS_NO_REPORT=1 ./jarvis safety-gate",
        "env JARVIS_NO_REPORT=1 ./jarvis smoke-test",
        "./jarvis command-audit",
        "./jarvis doctrine-check",
    ]),
    INTENT_PROJECT_FIX: ("goal-sprint", [
        "./jarvis project-cockpit --project <ALIAS>",
        "./jarvis final-gate --project <ALIAS>  (após patch validado)",
    ]),
    INTENT_PROJECT_QA: ("qa-sprint", [
        "./jarvis project-cockpit --project <ALIAS>",
    ]),
    INTENT_BROWSER_QA: ("browser-qa", [
        "checagem manual no browser pelo Theo",
    ]),
    INTENT_FINAL_GATE: ("final-gate", [
        "./jarvis project-cockpit --project <ALIAS>",
        "decisão humana sobre push/PR/deploy",
    ]),
    INTENT_N8N_BLUEPRINT: ("(nenhuma — blueprint local primeiro)", [
        "ler 02_SPEC.md do blueprint",
        "validar 04_VALIDATION_CHECKLIST.md item por item",
    ]),
    INTENT_APP_BLUEPRINT: ("(nenhuma — blueprint local primeiro)", [
        "ler 02_SPEC.md do blueprint",
    ]),
    INTENT_AUTOMATION_BLUEPRINT: ("(nenhuma — blueprint local primeiro)", [
        "ler 02_SPEC.md do blueprint",
    ]),
    INTENT_RESEARCH_PLAN: ("(opcional — blueprint research primeiro)", [
        "preencher decision matrix em 02_SPEC.md",
    ]),
    INTENT_AGENDA_NOTE: ("(nenhuma — append-only local)", [
        "./jarvis agenda  (confirmar entrada)",
    ]),
    INTENT_CAPTURE_NOTE: ("(nenhuma — append-only local)", [
        "./jarvis inbox  (confirmar entrada)",
    ]),
    INTENT_OPEN_PROJECT: ("(nenhuma — só abrir projeto)", [
        "git status --short  (no projeto-alvo)",
        "./jarvis project-cockpit --project <ALIAS>",
    ]),
    INTENT_NEXT_ACTION: ("(nenhuma — só ler cockpit)", [
        "./jarvis self-cockpit",
    ]),
    INTENT_UNCLEAR: ("(nenhuma — request ambígua)", [
        "registrado em UNCLEAR_REQUESTS.md para tuning futuro",
    ]),
}

_NEVER_DO = [
    "executar Claude por conta própria",
    "chamar Anthropic/OpenAI ou qualquer API paga",
    "tocar produção / VPS / n8n real",
    "fazer push, PR, merge, deploy",
    "rodar migrations",
    "ler .env ou imprimir segredos",
    "editar arquivos do projeto-alvo",
    "instalar dependências",
]


def _slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "plan"


def _render_plan(text, intent, project, cmd_str, safety) -> str:
    mission_type, validations = _MISSION_SUGGESTION.get(
        intent, ("(nenhuma)", ["./jarvis self-cockpit"])
    )
    lines = [
        "# JARVIS — Execution Plan",
        "",
        "## Status real",
        "Apenas plano local. Nada delegado, nada executado, nada em produção.",
        "",
        "## Pedido",
        f'"{text}"',
        "",
        "## Interpretação",
        f"- intent: {intent}",
        f"- explain: {_explain_intent(intent)}",
        f"- project: {project or '(não detectado)'}",
        f"- safety: {safety}",
        "",
        "## Próximo comando seguro",
        f"  {cmd_str}",
        "",
        "## Missão Claude sugerida",
        f"- tipo: {mission_type}",
        "- gerada por: `./jarvis go \"{...}\"` ou pelo comando acima com `--copy`",
        "",
        "## Validação esperada (após Claude rodar manualmente)",
    ]
    for v in validations:
        lines.append(f"- {v}")
    lines += [
        "",
        "## O que JARVIS NÃO vai fazer",
    ]
    for n in _NEVER_DO:
        lines.append(f"- {n}")
    lines += [
        "",
        "Produção: nada alterado.",
        "",
    ]
    return "\n".join(lines)


def main():
    text, alias_override, save = parse_args(sys.argv[1:])

    print("JARVIS — Plan Request")
    print("Status real: plano local; nada delegado, nada executado.")
    print("")

    if not text:
        print('FALHA: pedido vazio. Uso: ./jarvis plan "pedido"')
        sys.exit(1)

    intent = detect_intent(text)
    project = detect_project_alias(text, alias_override)
    _cmd_list, cmd_str, safety, _safe = _next_command_for(intent, project, text, copy_flag=None)
    plan = _render_plan(text, intent, project, cmd_str, safety)

    print(plan)

    if save:
        PLANS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        slug = _slugify(text)
        target = PLANS_DIR / f"{ts}_{slug}.md"
        target.write_text(plan, encoding="utf-8")
        print(f"OK — plano salvo em {target.relative_to(ROOT)}")
    else:
        print("Modo: preview (default). Use --save para gravar em 05_EXECUCAO/33_PLANS/.")


if __name__ == "__main__":
    main()
