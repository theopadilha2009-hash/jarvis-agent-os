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
        "## Status real\n"
        "Apenas plano. Nada criado em produção. Nenhum repositório remoto criado por JARVIS.\n"
        "JARVIS NÃO faz `npm init`, `bun create`, `git init` automaticamente.\n\n"
        f"## Objetivo\n{goal}\n\n"
        "## Branch rule\n"
        "- toda alteração em branch dedicada `feature/<topic>` ou `fix/<topic>`.\n"
        "- nunca editar `main`/`master` diretamente.\n"
        "- proteção: se branch atual = main, PARE.\n\n"
        "## Repo initialization checklist (manual)\n"
        "- [ ] nome sugerido: (preencher)\n"
        "- [ ] path local: ~/VAMOO_PROJETOS/<nome>\n"
        "- [ ] visibility: private por padrão\n"
        "- [ ] branch base: main local; remoto só com autorização\n"
        "- [ ] LICENSE definida (MIT/Apache-2.0/proprietário)\n"
        "- [ ] README inicial com seção 'Status real'\n"
        "- [ ] .gitignore antes do primeiro commit\n"
        "- [ ] .env.example presente (NUNCA .env)\n\n"
        "## Package manager choice\n"
        "- detectar/escolher entre: `bun` / `pnpm` / `yarn` / `npm` / `pip+venv` / `cargo`\n"
        "- commit do lockfile correspondente desde o primeiro commit\n"
        "- documentar versão exigida (engines / pyproject)\n\n"
        "## Testes / build / lint\n"
        "- adicionar `test` antes de qualquer integração\n"
        "- adicionar `lint` + `typecheck` cedo (não no fim)\n"
        "- adicionar `build` reprodutível antes de pensar em deploy\n"
        "- CI local (script `./scripts/check.sh`) replicando a sequência\n\n"
        "## Status real (níveis até deploy real)\n"
        "1. `drafted` — spec escrita; sem repo\n"
        "2. `repo created local` — pasta + git init, sem remoto\n"
        "3. `dependencies installed local` — install rodou; lockfile commitado\n"
        "4. `tests green local` — pelo menos 1 test passa\n"
        "5. `linted` — lint + typecheck verdes\n"
        "6. `build green local` — build reprodutível\n"
        "7. `remoto criado` — repo no GitHub (privado), sem deploy\n"
        "8. `deploy preview` — env staging com flags\n"
        "9. `production approved` — Theo dá OK por escrito\n\n"
        "## Não fazer (hard)\n"
        "- não publicar em registry público sem revisão\n"
        "- não fazer deploy sem nível ≥ 8\n"
        "- não criar workflow CI sem revisão humana do YAML\n"
        "- não armazenar secret no repo (nem em `.env.example`)\n"
    )


def _spec_automation(goal):
    return (
        "# Spec — Automation (LOCAL DRAFT)\n\n"
        "## Status real\n"
        "Apenas plano. Nada agendado em produção. JARVIS não dispara nada.\n\n"
        f"## Objetivo\n{goal}\n\n"
        "## Trigger\n"
        "- (escolher um) manual / cron / webhook / file watcher / event bus\n"
        "- início obrigatoriamente manual nos níveis 1-4 (ver status levels)\n\n"
        "## Input normalization\n"
        "- schema esperado (tipos + campos obrigatórios)\n"
        "- validação fail-fast antes de qualquer side-effect\n"
        "- rejeitar payload sem ack humano nos primeiros runs\n\n"
        "## Estado / memória\n"
        "- onde persistir (sqlite local / jsonl / markdown)\n"
        "- chave de correlation_id por evento\n"
        "- TTL claro para entradas antigas\n\n"
        "## Logs\n"
        "- caminho local (não /var/log de produção)\n"
        "- rotação simples (manual ou logrotate config)\n"
        "- sem PII em texto claro\n\n"
        "## Aprovação humana\n"
        "- toda ação irreversível exige confirmação explícita do Theo\n"
        "- ack registrado em arquivo + timestamp + assinatura textual\n\n"
        "## Idempotência / dedupe\n"
        "- chave única por job; reprocessamento não causa efeito duplicado\n"
        "- janela de dedupe documentada (ex: 24h)\n\n"
        "## Fallback / reversão\n"
        "- o que fazer se etapa N falhar?\n"
        "- como reverter parcialmente?\n"
        "- existe modo `--dry-run` que simula sem efeito real?\n\n"
        "## Error handling\n"
        "- estados de erro nomeados (não `except Exception: pass`)\n"
        "- error_trigger separado (alerta humano, não retry cego)\n"
        "- circuit breaker para evitar tempestade de falhas\n\n"
        "## Status real levels\n"
        "1. `drafted` — spec escrita\n"
        "2. `dry-run local` — código roda sem efeito real\n"
        "3. `manual trigger` — ack humano por execução\n"
        "4. `scheduled local` — cron/watcher em máquina do Theo\n"
        "5. `staging` — efeitos só em sandbox\n"
        "6. `prod read-only` — efeito de leitura em produção\n"
        "7. `prod write-with-ack` — escrita em produção com ack por execução\n"
        "8. `prod autônomo` — apenas após Theo dar OK por escrito\n"
        "- created ≠ imported ≠ configured ≠ tested ≠ validated ≠ production\n"
    )


def _spec_research(goal):
    return (
        "# Spec — Research plan (LOCAL DRAFT)\n\n"
        "## Status real\n"
        "Plano local de análise. Nada executado, sem Claude, sem API paga, sem produção.\n"
        "Este blueprint deve transformar fontes locais em decisão prática, não virar pesquisa infinita.\n\n"
        f"## Tema\n{goal}\n\n"
        "## Objetivo da pesquisa\n"
        "- Usar os deep research já adicionados no repositório como fonte principal.\n"
        "- Conectar os aprendizados com a evolução real do JARVIS.\n"
        "- Gerar uma recomendação prática em fases, com próximo comando seguro.\n\n"
        "## Fontes locais obrigatórias\n"
        "- `02_SOURCES/DEEP_RESEARCH/` — deep research adicionados.\n"
        "- `00_IDENTITY/JARVIS_EVOLUTION_PLAN.md` — plano atual de evolução, se existir.\n"
        "- `11_SCRIPTS/` — comandos e capacidades reais do JARVIS.\n"
        "- `05_EXECUCAO/40_BLUEPRINTS/` — blueprints já gerados, apenas para padrão/continuidade.\n\n"
        "## Perguntas que precisam ser respondidas\n"
        "1. O que dos deep research vira melhoria prática no JARVIS agora?\n"
        "2. O que deve ficar para depois para evitar overengineering?\n"
        "3. Quais comandos/capacidades faltam no JARVIS para reduzir retrabalho do Theo?\n"
        "4. O que pode ser feito local-first, sem API paga e sem produção?\n"
        "5. Qual é a próxima melhoria pequena, testável e commitável?\n\n"
        "## Critério de parada\n"
        "- Parar quando houver uma recomendação em fases v0/v1/v2.\n"
        "- Cada fase precisa ter: objetivo, arquivos prováveis, risco, teste e critério de pronto.\n"
        "- Não implementar código neste blueprint. Só plano/checklist/status.\n\n"
        "## Fases esperadas\n"
        "| Fase | Objetivo | Entrega local | Risco | Teste mínimo |\n"
        "|------|----------|---------------|-------|--------------|\n"
        "| v0 | Corrigir roteamento/templates fracos | patch pequeno em scripts | baixo | dry-run + py_compile |\n"
        "| v1 | Melhorar ingestão/uso de sources locais | comando ou digest local | médio | gerar artifact sem API |\n"
        "| v2 | Evoluir cockpit/ações assistidas | tools locais com aprovação | médio/alto | dry-run + human ack |\n\n"
        "## Regras de decisão\n"
        "- Priorizar o que reduz retrabalho diário do Theo.\n"
        "- Priorizar local-first e Git-safe.\n"
        "- Evitar depender de Claude/API paga como base obrigatória.\n"
        "- Não criar multi-agent, VPS, n8n real ou produção antes do core local estar sólido.\n"
        "- Toda ação real precisa ter dry-run, status real e validação.\n\n"
        "## O que NÃO fazer agora\n"
        "- Não criar deploy.\n"
        "- Não ativar workflow real.\n"
        "- Não adicionar API key.\n"
        "- Não transformar pesquisa em refactor gigante.\n"
        "- Não criar ferramenta nova sem teste mínimo e critério de pronto.\n\n"
        "## Resultado esperado\n"
        "Gerar uma recomendação de 1 página com:\n"
        "1. Contexto curto.\n"
        "2. O que os deep research indicam.\n"
        "3. Plano v0/v1/v2.\n"
        "4. Próximo comando seguro.\n"
        "5. Arquivos que podem ser commitados.\n"
        "6. O que fica bloqueado/adiado.\n"
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
            "[ ] branch rule explícita (nunca editar main)",
            "[ ] package manager escolhido + lockfile commitado",
            "[ ] LICENSE definida",
            "[ ] .gitignore antes do 1º commit",
            "[ ] .env.example (NUNCA .env real)",
            "[ ] test/lint/typecheck/build configurados antes de deploy",
            "[ ] status real declarado em README (nível 1-9)",
            "[ ] sem deploy até nível 8+",
        ],
        "automation": [
            "[ ] trigger inicial = manual",
            "[ ] input validado fail-fast",
            "[ ] idempotência/dedupe explícitos",
            "[ ] dry-run disponível",
            "[ ] aprovação humana em ações irreversíveis",
            "[ ] error_trigger separado do happy path",
            "[ ] logs sem PII em texto claro",
            "[ ] status real declarado (nível 1-8)",
        ],
        "research": [
            "[ ] perguntas de pesquisa explícitas",
            "[ ] assumptions escritas ANTES de pesquisar",
            "[ ] decision matrix preenchido (com 'não fazer' como opção)",
            "[ ] critério de parada definido",
            "[ ] recomendação final em 1 página seguindo o template",
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
