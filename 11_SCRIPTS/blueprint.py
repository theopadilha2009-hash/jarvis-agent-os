"""
blueprint.py — JARVIS local blueprint generator (no external APIs).

Creates a structured local spec/prompt/checklist bundle for a request,
so Theo can hand it to Claude Code without inventing the scaffolding by
hand. Never deploys, never calls APIs, never creates real n8n workflows
or webhooks.

Usage:
  ./jarvis blueprint --type n8n        --goal "..."  [--dry-run]
  ./jarvis blueprint --type app        --goal "..."  [--dry-run]
  ./jarvis blueprint --type automation --goal "..."  [--dry-run]
  ./jarvis blueprint --type research   --goal "..."  [--dry-run]

Directory layout (one folder per blueprint):
  05_EXECUCAO/40_BLUEPRINTS/<timestamp>_<type>_<slug>/
    01_REQUEST.md
    02_SPEC.md
    03_CLAUDE_PROMPT.md
    04_VALIDATION_CHECKLIST.md
    05_STATUS_REAL.md

Hard rules:
  - never installs anything
  - never opens .env
  - never prints secrets
  - never touches projects outside the JARVIS repo
  - --dry-run prints the plan and exits (no file created)
"""
from pathlib import Path
from datetime import datetime
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS_DIR = ROOT / "05_EXECUCAO" / "40_BLUEPRINTS"

SUPPORTED_TYPES = ("n8n", "app", "automation", "research")


def fail(msg, code=1):
    print(f"FALHA: {msg}")
    sys.exit(code)


def parse_args(argv):
    btype = None
    goal_parts = []
    dry_run = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--type":
            if i + 1 >= len(argv):
                fail("--type exige valor.")
            btype = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--type="):
            btype = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--goal":
            if i + 1 >= len(argv):
                fail("--goal exige texto.")
            goal_parts.append(argv[i + 1])
            i += 2
            continue
        if a.startswith("--goal="):
            goal_parts.append(a.split("=", 1)[1])
            i += 1
            continue
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        goal_parts.append(a)
        i += 1
    goal = " ".join(p for p in goal_parts if p).strip()
    if not btype:
        fail("Uso: ./jarvis blueprint --type <n8n|app|automation|research> --goal \"...\"")
    if btype not in SUPPORTED_TYPES:
        fail(f"Tipo desconhecido: {btype}. Use um de: {', '.join(SUPPORTED_TYPES)}.")
    if not goal:
        fail("--goal é obrigatório (descreva o que se quer construir).")
    return btype, goal, dry_run


def _slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "blueprint"


# ── templates ─────────────────────────────────────────────────────────────────

def _request_md(btype, goal, ts):
    return (
        f"# Blueprint Request — {btype}\n\n"
        f"## Status real\nGerado local em {ts}. Nada foi executado.\n\n"
        f"## Pedido original\n{goal}\n\n"
        f"## Tipo\n{btype}\n\n"
        f"## Escopo\n"
        f"- Apenas spec/prompt/checklist local.\n"
        f"- Nada de produção, deploy, push, PR, merge.\n"
        f"- Nenhuma API paga ou externa.\n"
        f"- Sem instalar dependências.\n"
    )


def _spec_n8n(goal):
    return (
        "# Spec — n8n workflow (LOCAL DRAFT)\n\n"
        "## Status real\n"
        "Apenas plano. Nada importado no n8n. Nada ativo. Sem credenciais reais.\n"
        "JARVIS NÃO gera o JSON de workflow aqui — apenas a spec/checklist.\n\n"
        f"## Objetivo\n{goal}\n\n"
        "## Inputs\n- (descreva entrada esperada: webhook payload, scheduler, etc.)\n\n"
        "## Outputs\n- (descreva saída esperada: mensagem WhatsApp, registro DB, etc.)\n\n"
        "## Camadas / nós recomendados (em ordem, todos inativos até validar)\n"
        "1. **Manual Trigger** — sempre primeiro (dispara só via Theo)\n"
        "2. **Webhook TEST only** — webhook desativado, modo *Test*; sem path em produção\n"
        "3. **Normalize Input** — Function/Code node padronizando schema do payload\n"
        "4. **Instance Guard** — checa que estamos no host esperado (não rodar em prod por engano)\n"
        "5. **Anti-loop** — guarda contra reentrada (correlation_id / visited set)\n"
        "6. **Dedupe** — chave + janela; descarta payload duplicado\n"
        "7. **Runtime Config** — node que lê config inerte (sem secrets reais)\n"
        "8. **Classifier** — IF/Switch para decidir branch lógica\n"
        "9. **Agent/LLM placeholder** — node desativado; sem chave de API real\n"
        "10. **Parser/Guardrail** — valida JSON, recusa output inseguro\n"
        "11. **Send Mock** — envia para sandbox/log, NUNCA para usuário final\n"
        "12. **Logs** — append em tabela/arquivo local; sem PII em texto claro\n"
        "13. **Error path** — explícito; sem `Continue On Fail = true` cego\n\n"
        "## Estado real (níveis até produção — só sobe um por vez)\n"
        "1. `drafted` — spec escrita; nada no n8n ainda\n"
        "2. `generated` — JSON gerado em arquivo local; nada importado\n"
        "3. `JSON valid` — passa `python -c 'import json; json.load(...)'`\n"
        "4. `imported inactive` — importado no n8n com `active=false`\n"
        "5. `dry-run tested` — Manual Trigger + payload mock; logs corretos\n"
        "6. `real webhook tested` — Webhook TEST only, em sandbox\n"
        "7. `production approved` — Theo deu OK explícito por escrito\n\n"
        "## DO NOT (regra forte)\n"
        "- NÃO ativar o workflow (`active = true`) antes do nível 7\n"
        "- NÃO incluir credenciais (API keys / tokens / cookies) no JSON\n"
        "- NÃO criar webhook *Production* path\n"
        "- NÃO ligar a um número WhatsApp / canal real até `dry-run tested`\n"
        "- NÃO usar `Continue On Fail = true` por padrão — falha deve falhar\n"
        "- NÃO logar payload bruto com PII em produção\n\n"
        "## Credenciais\n"
        "- placeholders only (`{{ $credentials.X }}`) — JARVIS NUNCA cola valor real.\n"
        "- secrets reais ficam no UI de credenciais do n8n, criados manualmente.\n\n"
        "## Riscos\n"
        "- enviar mensagem em produção sem ack humano → bloqueado (regra acima).\n"
        "- loop infinito se Anti-loop estiver ausente → exigido na camada 5.\n"
        "- vazamento de credenciais via export → exigido placeholder na camada 7.\n"
    )


def _spec_app(goal):
    return (
        "# Spec — App / repo plan (LOCAL DRAFT)\n\n"
        "## Status real\nApenas plano. Nada criado em produção. Nenhum repositório remoto criado por JARVIS.\n\n"
        f"## Objetivo\n{goal}\n\n"
        "## Repo plan\n"
        "- nome sugerido: (preencher)\n"
        "- local: ~/VAMOO_PROJETOS/<nome>\n"
        "- visibility: private por padrão\n"
        "- branch base: main (somente local até autorização)\n\n"
        "## Branch rule\n- toda alteração em branch dedicada `feature/<topic>` ou `fix/<topic>`.\n\n"
        "## Package manager detection\n- detectar package.json / pyproject.toml / Cargo.toml antes de assumir.\n\n"
        "## Testes / build / lint\n- adicionar primeiro `npm test` / `pytest` / similar antes de qualquer integração.\n\n"
        "## Não fazer\n- não publicar em registry público.\n- não fazer deploy.\n- não criar workflow CI sem revisão humana.\n"
    )


def _spec_automation(goal):
    return (
        "# Spec — Automation (LOCAL DRAFT)\n\n"
        "## Status real\nApenas plano. Nada agendado em produção.\n\n"
        f"## Objetivo\n{goal}\n\n"
        "## Trigger\n- (manual / cron / webhook / file watcher)\n\n"
        "## Estado\n- onde persistir (sqlite local, jsonl, markdown)\n\n"
        "## Logs\n- caminho local\n- rotacão simples (manual)\n\n"
        "## Aprovação humana\n- toda ação irreversível exige confirmação Theo.\n\n"
        "## Fallback\n- o que fazer se etapa N falhar?\n- como reverter parcialmente?\n\n"
        "## Error handling\n- estados de erro nomeados, não silenciar exceções.\n\n"
        "## Status real levels\n"
        "- created ≠ imported ≠ configured ≠ tested ≠ validated ≠ production\n"
    )


def _spec_research(goal):
    return (
        "# Spec — Research plan (LOCAL DRAFT)\n\n"
        "## Status real\nApenas plano de leitura/análise. Nada decidido.\n\n"
        f"## Tema\n{goal}\n\n"
        "## Research questions\n"
        "1. O que exatamente quero responder?\n"
        "2. Qual a decisão que esta pesquisa habilita?\n"
        "3. Qual é o critério de parada?\n\n"
        "## Sources to inspect\n"
        "- código local relacionado (lista)\n"
        "- docs internas (lista)\n"
        "- repositórios públicos (lista)\n"
        "- artigos / RFCs (lista)\n\n"
        "## Decision matrix\n"
        "| Opção | Esforço | Risco | Reversibilidade | Nota |\n"
        "|-------|---------|-------|------------------|------|\n"
        "| A     |         |       |                  |      |\n"
        "| B     |         |       |                  |      |\n\n"
        "## What not to build\n- evitar refactors grandes só porque é pesquisa.\n\n"
        "## Final output format\n- 1 página markdown com: contexto / opções / decisão / próximo passo seguro.\n"
    )


def _spec_for(btype, goal):
    return {
        "n8n": _spec_n8n,
        "app": _spec_app,
        "automation": _spec_automation,
        "research": _spec_research,
    }[btype](goal)


def _claude_prompt(btype, goal, ts):
    extra = ""
    if btype == "n8n":
        extra = (
            "\n## Específico para n8n\n"
            "- NÃO gere o JSON do workflow nesta iteração — só refine a spec.\n"
            "- Marque cada camada (1-13) como presente/ausente/parcial.\n"
            "- Declare o estado atual (drafted / generated / JSON valid / …) em 05_STATUS_REAL.md.\n"
            "- Se for sugerir JSON depois, gerar em arquivo separado, `active=false`, sem credenciais.\n"
        )
    return (
        f"# Claude Mission Prompt — Blueprint {btype}\n\n"
        f"## Status real\nGerado local em {ts}. Claude ainda não executou nada.\n\n"
        f"## Goal\n{goal}\n\n"
        "## Hard rules\n"
        "- não tocar produção, n8n real, VPS, deploy, push, PR, merge\n"
        "- não usar API paga\n"
        "- não ler .env\n"
        "- não imprimir tokens / cookies / segredos\n"
        "- trabalhar em arquivos LOCAIS deste blueprint (02_SPEC.md, 04_VALIDATION_CHECKLIST.md)\n"
        "- se faltar contexto, PARAR e listar perguntas\n\n"
        "## What to do\n"
        "1. Ler 02_SPEC.md\n"
        "2. Refinar a spec (preencher placeholders, alertar lacunas)\n"
        "3. Atualizar 04_VALIDATION_CHECKLIST.md com critérios mensuráveis\n"
        "4. Atualizar 05_STATUS_REAL.md com Created/Modified/Tested/Production\n"
        "5. Retornar relatório final no formato STATUS REAL / WHAT IMPROVED / RISKS / SAFE TO COMMIT / NEXT BEST ACTION\n"
        + extra
    )


def _checklist(btype):
    base = [
        "[ ] spec lida por humano",
        "[ ] checklist preenchido com critérios mensuráveis",
        "[ ] nada em produção",
        "[ ] nenhuma credencial real envolvida",
        "[ ] reversível em < 1 minuto",
    ]
    extras = {
        "n8n": [
            "[ ] camadas 1-13 presentes na spec (Manual Trigger → Error path)",
            "[ ] estado atual declarado (drafted / generated / JSON valid / imported inactive / …)",
            "[ ] workflow no nível ≤ `imported inactive` (active=false)",
            "[ ] sem webhook *Production* path",
            "[ ] sem credenciais reais no JSON (só placeholders `{{ $credentials.X }}`)",
            "[ ] Anti-loop + Dedupe explícitos na spec",
            "[ ] Send Mock substituível por Send Real só com OK do Theo",
            "[ ] `Continue On Fail = true` justificado em cada node onde aparece",
            "[ ] testado com Manual Trigger + payload mock antes de qualquer trigger automático",
        ],
        "app": [
            "[ ] repo plan validado",
            "[ ] branch rule respeitada",
            "[ ] sem deploy",
        ],
        "automation": [
            "[ ] trigger só em modo manual no início",
            "[ ] aprovação humana documentada nas etapas irreversíveis",
            "[ ] logs com rotação",
        ],
        "research": [
            "[ ] perguntas de pesquisa explícitas",
            "[ ] decision matrix preenchido",
            "[ ] decisão registrada",
        ],
    }[btype]
    return "# Validation checklist\n\n" + "\n".join(f"- {l}" for l in base + extras) + "\n"


def _status_real(btype, goal, ts):
    return (
        "# Status real\n\n"
        f"- Created: 5 arquivos de blueprint local (tipo={btype}) em {ts}\n"
        "- Modified: nada fora deste blueprint\n"
        "- Tested: nada\n"
        "- Not validated: spec ainda não revisada por humano\n"
        "- Production: nada alterado\n\n"
        f"## Goal\n{goal}\n"
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    btype, goal, dry_run = parse_args(sys.argv[1:])
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    slug = _slugify(goal)
    target = BLUEPRINTS_DIR / f"{ts}_{btype}_{slug}"
    rel = target.relative_to(ROOT)

    print("JARVIS — Blueprint")
    print(f"Status real: geração local para tipo={btype}. Nada em produção.")
    print("")
    print(f"Tipo: {btype}")
    print(f"Goal: {goal}")
    print(f"Pasta alvo: {rel}/")
    print("")
    print("Arquivos planejados:")
    for name in ("01_REQUEST.md", "02_SPEC.md", "03_CLAUDE_PROMPT.md", "04_VALIDATION_CHECKLIST.md", "05_STATUS_REAL.md"):
        print(f"  - {rel}/{name}")
    print("")

    if dry_run:
        print("Modo: --dry-run (nenhum arquivo gravado).")
        print("Produção: nada alterado.")
        return

    target.mkdir(parents=True, exist_ok=True)
    (target / "01_REQUEST.md").write_text(_request_md(btype, goal, ts), encoding="utf-8")
    (target / "02_SPEC.md").write_text(_spec_for(btype, goal), encoding="utf-8")
    (target / "03_CLAUDE_PROMPT.md").write_text(_claude_prompt(btype, goal, ts), encoding="utf-8")
    (target / "04_VALIDATION_CHECKLIST.md").write_text(_checklist(btype), encoding="utf-8")
    (target / "05_STATUS_REAL.md").write_text(_status_real(btype, goal, ts), encoding="utf-8")
    print(f"OK — blueprint criado em {rel}/")
    print("")
    print("Próximo passo seguro:")
    print(f"  cat {rel}/03_CLAUDE_PROMPT.md | pbcopy   # copiar prompt p/ Claude")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
