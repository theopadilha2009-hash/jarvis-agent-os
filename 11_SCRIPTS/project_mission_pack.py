"""
project_mission_pack.py — generates Claude mission packs for higher-level
project workflows: qa-sprint, goal-sprint, browser-qa, final-gate.

Reuses the 4-file pack layout from claude_mission.py and writes to
05_EXECUCAO/21_CLAUDE_MISSIONS/<TS>_<scope>_<mode>_<slug>/.

Usage:
  python3 11_SCRIPTS/project_mission_pack.py --mode <mode> --project <alias> [--goal "..."]

Modes: qa-sprint | goal-sprint | browser-qa | final-gate
"""
from pathlib import Path
from datetime import datetime
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
VALID_MODES = ("qa-sprint", "goal-sprint", "browser-qa", "final-gate", "self-evolve")

USAGE = (
    "Uso:\n"
    "  ./jarvis qa-sprint --project <alias>\n"
    '  ./jarvis goal-sprint --project <alias> --goal "objetivo"\n'
    "  ./jarvis browser-qa --project <alias>\n"
    "  ./jarvis final-gate --project <alias>\n"
    '  ./jarvis self-evolve --goal "objetivo" [--copy]   (alias jarvis-core)\n'
)

HARD_RULES = [
    "Não tocar VPS, n8n, deploy, push, PR, main, .env ou secrets.",
    "Não imprimir tokens, API keys, cookies, senhas ou QR codes.",
    "Não rodar migrations.",
    "Não editar Supabase ou banco de produção.",
    "Não gerar PDF. Não criar fontes randômicas.",
    "Não usar APIs externas neste pacote.",
    "Não fazer commit sem autorização explícita do usuário.",
    "Não fazer push, PR, merge ou deploy.",
]


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "mission"


def fail(msg, code=1):
    print(f"FALHA: {msg}")
    sys.exit(code)


def parse_args(argv):
    mode = None
    alias = None
    goal_parts = []
    copy_flag = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--mode":
            if i + 1 >= len(argv):
                fail("--mode exige valor.")
            mode = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--mode="):
            mode = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--project":
            if i + 1 >= len(argv):
                fail("--project exige alias.")
            alias = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--goal":
            if i + 1 >= len(argv):
                fail("--goal exige texto entre aspas.")
            goal_parts.append(argv[i + 1])
            i += 2
            continue
        if a.startswith("--goal="):
            goal_parts.append(a.split("=", 1)[1])
            i += 1
            continue
        if a == "--copy":
            copy_flag = True
            i += 1
            continue
        # leftover positional → join as goal text
        goal_parts.append(a)
        i += 1
    return mode, alias, " ".join(goal_parts).strip(), copy_flag


def load_project(alias):
    if not REGISTRY.exists():
        fail("PROJECT_REGISTRY.json não encontrado.")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    projects = {p["alias"]: p for p in registry.get("projects", [])}
    if alias not in projects:
        print(f"FALHA: project alias não registrado: {alias}")
        print("")
        print("Aliases disponíveis:")
        for key in sorted(projects):
            print(f"- {key}")
        sys.exit(1)
    p = projects[alias]
    if not p.get("allowed_for_local_exec", False):
        fail(f"projeto não permitido para LOCAL_EXEC: {alias}")
    return p


def detect_tooling(path: Path):
    pkg_file = path / "package.json"
    if not pkg_file.exists():
        return {"has_pkg": False}
    try:
        pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
    except Exception:
        return {"has_pkg": True, "parse_error": True}
    deps = {}
    deps.update(pkg.get("dependencies", {}) or {})
    deps.update(pkg.get("devDependencies", {}) or {})
    keys = set(deps.keys())
    scripts = pkg.get("scripts", {}) or {}
    pm = "npm"
    if (path / "bun.lockb").exists() or (path / "bun.lock").exists():
        pm = "bun"
    elif (path / "pnpm-lock.yaml").exists():
        pm = "pnpm"
    elif (path / "yarn.lock").exists():
        pm = "yarn"
    elif (path / "package-lock.json").exists():
        pm = "npm"
    return {
        "has_pkg": True,
        "pkg_manager": pm,
        "playwright": any(k.startswith("@playwright/") or k == "playwright" for k in keys),
        "cypress": "cypress" in keys,
        "vitest": "vitest" in keys,
        "jest": "jest" in keys,
        "rtl": "@testing-library/react" in keys,
        "tsc": "typescript" in keys or (path / "tsconfig.json").exists(),
        "scripts": scripts,
    }


# ── Prompt builders per mode ──────────────────────────────────────────


def _project_header(project, mode, task_or_goal):
    return [
        "# Claude Mission Prompt",
        "",
        f"## Scope\nproject {project['alias']} ({project['path']})",
        "",
        f"## Mode\n{mode}",
        "",
        f"## Goal\n{task_or_goal or '(não informado — Claude deve apurar com Theo se necessário)'}",
        "",
        "## Branch registrada",
        f"- {project.get('branch', 'unknown')}",
        "",
        "## Hard rules",
        *[f"- {r}" for r in HARD_RULES],
        "",
        "## Git preflight",
        "- pwd",
        "- git status --short",
        "- git branch --show-current",
        "- git log --oneline -8",
        "Se a árvore estiver suja antes da edição, PARE e reporte exatamente o que está sujo.",
        f"Se a branch for main/master, PARE — esta missão exige branch dedicada (registrada: {project.get('branch', 'unknown')}).",
        "",
    ]


def _tooling_block(tooling, project_path):
    lines = ["## Tooling do projeto (referência)"]
    if not tooling.get("has_pkg"):
        lines.append("- package.json: ausente")
        return lines
    if tooling.get("parse_error"):
        lines.append("- package.json: presente mas com erro de parse — checar manualmente")
        return lines
    pm = tooling.get("pkg_manager", "npm")
    lines.append(f"- package manager: {pm}")
    scripts = tooling.get("scripts", {}) or {}
    candidates = ("typecheck", "type-check", "tsc", "test", "test:run", "build", "lint")
    found = [s for s in candidates if s in scripts]
    if found:
        lines.append(f"- scripts úteis: {', '.join(found)}")
    if tooling.get("tsc"):
        lines.append("- typecheck: npx tsc --noEmit (ou script equivalente)")
    flags = []
    for k in ("playwright", "cypress", "vitest", "jest", "rtl"):
        if tooling.get(k):
            flags.append(k)
    lines.append(f"- bibliotecas de teste detectadas: {', '.join(flags) if flags else 'nenhuma óbvia'}")
    return lines


def build_qa_sprint(project, tooling, goal):
    lines = _project_header(project, "qa-sprint", goal or "QA sprint local sem editar produção")
    lines += [
        "## Missão QA-SPRINT",
        "Foco: aumentar a solidez local da branch via inspeção, validação e patches mínimos.",
        "",
        "### Inspeção (read-only primeiro)",
        "- git diff --stat origin/main..HEAD (se origin/main existir)",
        "- git diff --name-only origin/main..HEAD",
        "- listar arquivos alterados; mapear testes existentes para esses arquivos",
        "- identificar caminhos sem cobertura automatizada",
        "",
        "### Validação atual",
        "- rodar typecheck do projeto (se houver)",
        "- rodar a suíte de testes (se houver)",
        "- rodar build apenas se for rápido e seguro localmente",
        "- registrar ruído de stderr e classificar (pré-existente vs novo)",
        "",
        "### Patches permitidos (orçamento apertado)",
        "- adicionar 1–2 testes pequenos com alto valor (ex.: lock-in de bugfix da branch)",
        "- corrigir issues triviais de teste/lint que sejam comprovadamente isolados",
        "- NÃO refatorar nada além do mínimo",
        "- limite duro: até 2 arquivos modificados + até 1 arquivo novo de teste",
        "",
        "### Bloqueios duros",
        "- sem migrations",
        "- sem deploy/push/PR/merge",
        "- sem secrets/.env",
        "- sem mudança de comportamento de produção",
        "",
        *_tooling_block(tooling, project["path"]),
        "",
        "## Formato obrigatório de retorno",
        "1. STATUS REAL (Edited / Created / Tested / Production)",
        "2. INSPEÇÃO — o que mudou na branch e o que tem/não tem cobertura",
        "3. PATCH APPLIED? (yes/no — arquivos e linhas)",
        "4. VALIDATION RESULTS — typecheck/tests/lint PASS/FAIL com números",
        "5. RUÍDO DE TESTE — quem é intencional, quem é regressão",
        "6. RISKS / NOT VALIDATED",
        "7. NEXT BEST PATCH (uma sugestão concreta) OU STOP",
        "8. SAFE TO COMMIT? (yes/no; se yes, comando exato — não commitar)",
    ]
    return "\n".join(lines) + "\n"


def build_goal_sprint(project, tooling, goal):
    if not goal:
        goal = "(definir DoD com Theo antes de patchar)"
    lines = _project_header(project, "goal-sprint", goal)
    lines += [
        "## Missão GOAL-SPRINT",
        f'Objetivo declarado: "{goal}"',
        "",
        "### Definition of Done",
        "- Listar 3–6 critérios mensuráveis para considerar o objetivo cumprido.",
        "- Cada critério deve poder ser provado por código/tests/typecheck — sem 'parece OK'.",
        "- Se algum critério depende de browser/manual, marcar explicitamente como 'human-only'.",
        "",
        "### Loop iterativo",
        "1. Inspecionar estado atual da branch (changed files, testes, ruído).",
        "2. Escolher o próximo patch de maior valor e menor risco.",
        "3. Aplicar patch mínimo (até 2 arquivos por iteração).",
        "4. Validar (typecheck + tests + lint relevantes).",
        "5. Repetir enquanto houver patch seguro de alto valor.",
        "6. Parar quando o próximo patch for: arriscado, refator grande, ou ROI baixo.",
        "",
        "### Critérios de parada (não overengineer)",
        "- 'Posso provar com código?' Se não, é human-only — registrar e parar.",
        "- 'Custo > benefício?' Se sim, parar.",
        "- 'Arquitetura?' Se sim, propor sem aplicar.",
        "",
        "### Bloqueios duros",
        *[f"- {r}" for r in HARD_RULES],
        "",
        *_tooling_block(tooling, project["path"]),
        "",
        "## Formato obrigatório de retorno",
        "1. STATUS REAL",
        "2. DEFINITION OF DONE (lista mensurável)",
        "3. ITERAÇÕES APLICADAS (cada uma: patch, validação, decisão)",
        "4. CRITÉRIOS ATENDIDOS vs NÃO ATENDIDOS",
        "5. RESTANTE HUMAN-ONLY (lista mínima — só o que código não prova)",
        "6. EXACT NEXT ACTION (comando ou STOP)",
        "7. SAFE TO COMMIT? (yes/no; se yes, comando exato — não commitar)",
    ]
    return "\n".join(lines) + "\n"


def build_browser_qa(project, tooling, goal):
    has_pw = tooling.get("playwright")
    has_cy = tooling.get("cypress")
    has_vitest = tooling.get("vitest")
    has_rtl = tooling.get("rtl")
    lines = _project_header(project, "browser-qa", goal or "QA de UI/browser para a branch atual")
    lines += [
        "## Missão BROWSER-QA",
        "Foco: maximizar cobertura automatizada de UI sem instalar ferramentas novas.",
        "",
        "### Strategy detection",
    ]
    if has_pw or has_cy:
        tool = "Playwright" if has_pw else "Cypress"
        lines += [
            f"- O projeto JÁ TEM {tool} instalado — usar somente o que existe.",
            f"- Rodar a suíte {tool} existente (read-only).",
            "- Listar specs que cobrem os fluxos alterados na branch.",
            "- Para fluxos alterados sem cobertura, propor (sem aplicar) novos specs no estilo do repo.",
        ]
    elif has_vitest and has_rtl:
        lines += [
            "- Sem Playwright/Cypress. Vitest + RTL disponíveis.",
            "- Cobrir os caminhos de UI alterados via componentes puros (estados, branches, callbacks).",
            "- Mockar Supabase/contextos como já é feito em testes existentes.",
            "- NÃO instalar Playwright/Cypress automaticamente.",
        ]
    else:
        lines += [
            "- Nenhuma ferramenta de browser test detectada.",
            "- NÃO instalar nada por padrão.",
            "- Recomendar apenas verificação manual mínima dos fluxos alterados; deixar instalação para decisão humana.",
        ]
    lines += [
        "",
        "### Inventário de UI alterada",
        "- git diff --name-only origin/main..HEAD | grep -E '\\.(tsx|jsx|vue|svelte)$'",
        "- para cada arquivo, anotar: existe teste? quão crítico é o caminho? alterar comportamento ou só visual?",
        "",
        "### Patches permitidos",
        "- Adicionar 1–3 testes pequenos com alto valor (preferir Vitest/RTL se já existe).",
        "- NÃO criar harness pesado.",
        "- NÃO usar dados reais nem secrets.",
        "- Limite duro: até 2 arquivos novos de teste; sem alteração de produção.",
        "",
        "### Bloqueios duros",
        *[f"- {r}" for r in HARD_RULES],
        "",
        *_tooling_block(tooling, project["path"]),
        "",
        "## Formato obrigatório de retorno",
        "1. STATUS REAL",
        "2. TOOLING DETECTADO",
        "3. INVENTÁRIO DE UI ALTERADA (cobertura sim/não)",
        "4. PATCHES APLICADOS (arquivos)",
        "5. VALIDATION RESULTS",
        "6. STILL NEEDS HUMAN CHECK (lista enxuta — apenas o que automação não prova)",
        "7. SAFE TO COMMIT? (yes/no; se yes, comando exato — não commitar)",
    ]
    return "\n".join(lines) + "\n"


def build_final_gate(project, tooling, goal):
    lines = _project_header(project, "final-gate", goal or "Final validation antes de qualquer ação externa")
    lines += [
        "## Missão FINAL-GATE",
        "Foco: dar ou recusar luz verde para push/PR/merge/deploy de forma honesta.",
        "Esta missão NÃO autoriza push/PR/deploy. Apenas reporta safe/not-safe.",
        "",
        "### Checagens obrigatórias",
        "1. git status --short — exigir árvore limpa.",
        "2. git branch --show-current — exigir branch dedicada (não main/master).",
        "3. typecheck (se houver) — exigir PASS.",
        "4. Suíte de tests (se houver) — exigir PASS e relatar números (X/Y files, X/Y tests).",
        "5. Build (se houver e for seguro local) — opcional, marcar PASS/FAIL/SKIPPED.",
        "6. git diff --stat origin/main..HEAD — sumarizar mudanças (linhas, arquivos, áreas).",
        "7. Verificar se há .env, lockfiles novos, secrets em diff.",
        "8. Stderr/warnings introduzidos pela branch vs pré-existentes em origin/main.",
        "",
        "### Critérios de SAFE TO PROCEED",
        "- todos os itens 1–4 PASS",
        "- nenhum secret/.env em diff",
        "- nenhuma migration crítica não aplicada que o front exija",
        "- nenhuma alegação de produção sem prova",
        "",
        "### Bloqueios duros",
        *[f"- {r}" for r in HARD_RULES],
        "",
        *_tooling_block(tooling, project["path"]),
        "",
        "## Formato obrigatório de retorno",
        "1. STATUS REAL (apenas leitura — nada editado)",
        "2. CHECKLIST RESULT (cada item PASS/FAIL/SKIPPED com evidência)",
        "3. DIFF SUMMARY (arquivos por área + +X/-Y por commit)",
        "4. REMAINING UNVALIDATED (lista enxuta do que código não prova)",
        "5. SAFE TO PUSH? yes/no + razão curta",
        "6. SAFE TO OPEN PR? yes/no + razão curta",
        "7. SAFE TO DEPLOY? yes/no + razão curta (esperado: no, a menos que prova explícita)",
        "8. NEXT EXACT ACTION (comando ou STOP)",
    ]
    return "\n".join(lines) + "\n"


def build_self_evolve(project, tooling, goal):
    """Mission to evolve JARVIS itself (project=jarvis-core).
    Forces the doctrine, sections 1..12, and the local Claude Code workflow."""
    if not goal:
        goal = "(definir objetivo antes — Theo precisa declarar o que evoluir)"
    path = project.get("path", "")
    branch = project.get("branch", "unknown")
    lines = [
        "# Claude Mission Prompt — JARVIS SELF-EVOLVE",
        "",
        f"## Scope\nJARVIS local lab ({path})",
        "",
        "## Mode\nself-evolve",
        "",
        f"## Goal\n{goal}",
        "",
        "## Branch registrada",
        f"- {branch}",
        "",
        "## 1. MISSION",
        "Evoluir o próprio JARVIS — o repositório que gera missões Claude — para",
        "reduzir trabalho manual de Theo de forma segura e auditável.",
        "Trabalhar apenas dentro deste repo. Não tocar projetos-alvo.",
        "",
        "## 2. CURRENT STATE",
        "- Sprint 1: per-project doctor/qa-sprint/goal-sprint/browser-qa/final-gate.",
        "- Sprint 2: cockpit diário + mission-open-latest + gitignore de packs.",
        "- Sprint 3: project-memory + project-memory-update + parser regex de relatórios.",
        f"- Branch atual: {branch}",
        "- Gates esperados verdes: safety-gate, smoke-test, command-audit.",
        "- Tree esperada limpa antes da edição.",
        "",
        "## 3. TRUE NORTH",
        "JARVIS é a HARNESS de Claude Code: prepara, copia, organiza, lembra,",
        "valida, e sugere próximo passo. NÃO é executor de Claude. NÃO chama API.",
        "Reduz dependência de ChatGPT para escrever prompts.",
        "Status real sempre. Branch safe sempre. Production never.",
        "",
        "## 4. HARD RULES",
        *[f"- {r}" for r in HARD_RULES],
        "- Não usar APIs pagas (Anthropic/OpenAI). Stdlib only.",
        "- Não criar TUI/dashboard.",
        "- Não rodar Claude em background. Não fingir autonomia.",
        "- Não deletar comandos existentes.",
        "- Não usar `git add .` — sempre paths explícitos.",
        "- Não editar main/master. Se branch=main, PARE.",
        "",
        "## 5. WHAT TO INSPECT (read-only primeiro)",
        "- 11_SCRIPTS/jarvis_core.py — dispatcher + help",
        "- 11_SCRIPTS/project_mission_pack.py — gerador de missions",
        "- 11_SCRIPTS/project_memory*.py — loop de memória",
        "- 11_SCRIPTS/self_cockpit.py — entry point self-*",
        "- 11_SCRIPTS/claude_helpers.py — workflow Claude Code local",
        "- 11_SCRIPTS/command_audit.py — drift detector",
        "- 11_SCRIPTS/cli_smoke_test.py — CHECKS list",
        "- AGENTS.md — contrato com agentes",
        "- 01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md",
        "- 04_PROJETOS/JARVIS_CORE/PROJECT_STATUS.md — memória atual",
        "",
        "## 6. WHAT TO IMPROVE",
        "Foco no objetivo declarado em ## Goal. Iterar em patches pequenos:",
        "- inspecionar → escolher próximo patch mais alto valor / menor risco",
        "- aplicar (≤ 2 arquivos por iteração)",
        "- validar (bash -n + py_compile + command-audit + smoke + safety-gate)",
        "- decidir continuar ou parar",
        "Marcar critérios de Definition of Done mensuráveis.",
        "",
        "## 7. WHAT NOT TO BUILD",
        "- Web dashboard / TUI rich-textual.",
        "- Auto-execute Claude em background.",
        "- Integração com API paga.",
        "- Multi-agent orquestrador.",
        "- Refactor grande de scripts existentes (operator_workbench, run_safe).",
        "- Deduplicar 20+ pastas em 05_EXECUCAO/ (não é o gargalo).",
        "- Auto-detectar framework no doctor (Sprint 5+).",
        "Se cair na tentação de algo acima → PARE e proponha sem aplicar.",
        "",
        "## 8. IMPLEMENTATION PHASES",
        "1. Preflight (pwd, git status, branch, safety-gate, smoke).",
        "2. Inspect arquivos listados em ## 5.",
        "3. Decidir 1 patch + critérios de aceite.",
        "4. Aplicar patch (paths explícitos, sem git add .).",
        "5. Validar (typecheck/audit/smoke/safety).",
        "6. Commit local SE tudo verde — usar `git add <paths>`.",
        "7. Self-audit: reduziu trabalho manual? overengineering? gates verdes?",
        "8. Se houver outro patch de valor alto E baixo risco, repetir 3-7.",
        "9. Senão, parar e reportar.",
        "",
        "## 9. VALIDATION COMMANDS",
        "```",
        "bash -n ./jarvis",
        "python3 -m py_compile <arquivo alterado>",
        "./jarvis help",
        "./jarvis command-audit",
        "env JARVIS_NO_REPORT=1 ./jarvis smoke-test",
        "env JARVIS_NO_REPORT=1 ./jarvis safety-gate",
        "./jarvis self-cockpit",
        "git diff --stat",
        "git diff --check",
        "git status --short",
        "```",
        "",
        "## 10. COMMIT RULES",
        "- 1 commit por checkpoint validado.",
        "- `git add <paths explícitos>` (nunca `git add .`).",
        "- Mensagem padrão: `feat(jarvis): <verbo curto>` ou `fix(jarvis): ...`.",
        "- HEREDOC para multi-line.",
        "- Pre-commit hook deve passar (Python syntax + secret-block).",
        "- Sem push, PR, merge, deploy.",
        "",
        "## 11. SELF-AUDIT (perguntas obrigatórias antes de parar)",
        "- Reduziu trabalho manual real do Theo?",
        "- JARVIS está mais autônomo OU é autonomia fake?",
        "- Status real preservado em toda saída?",
        "- Comandos existentes ainda funcionam (command-audit OK)?",
        "- smoke-test e safety-gate verdes pós-commit?",
        "- Algum overengineering oculto introduzido?",
        "- Dependências adicionadas? (espera-se: NÃO).",
        "- Production touched? (espera-se: NÃO).",
        "",
        "## 12. RETURN FORMAT",
        "1. STATUS REAL (Created/Modified/Tested/Committed/Not validated/Production)",
        "2. WHAT IMPROVED",
        "3. COMMANDS ADDED/CHANGED",
        "4. NEW DAILY LOOP (se mudou)",
        "5. VALIDATION RESULTS (cada comando PASS/FAIL com números)",
        "6. COMMITS CREATED (hash + msg)",
        "7. FILES CHANGED (lista exata)",
        "8. RISKS / LIMITS (honesto)",
        "9. WHAT NOT TO BUILD NEXT",
        "10. NEXT BEST ACTION (1 comando exato)",
        "11. SAFE TO STOP? (yes/no)",
        "",
        *_tooling_block(tooling, project["path"]),
        "",
        "## Doctrine (não negociável)",
        "- Status real always · Branch safe always · Read before edit",
        "- No secrets in chat/Git/docs/logs · Production after controlled validation",
        "- IA decide subjetivo; harness controla regras/estado/logs/validação/memória",
        "- Tools radar ≠ permissão para instalar tudo",
        "- created ≠ imported ≠ configured ≠ tested ≠ validated ≠ production",
        "- Workflow pro = responde + loga + monitora + pausa + transfere + recupera + documenta",
    ]
    return "\n".join(lines) + "\n"


PROMPT_BUILDERS = {
    "qa-sprint": build_qa_sprint,
    "goal-sprint": build_goal_sprint,
    "browser-qa": build_browser_qa,
    "final-gate": build_final_gate,
    "self-evolve": build_self_evolve,
}


def build_summary(project, mode, goal, ts_iso):
    lines = [
        "# Claude Mission Summary",
        "",
        f"## Data\n{ts_iso}",
        "",
        f"## Scope\nproject:{project['alias']} -> {project['path']}",
        "",
        f"## Mode\n{mode}",
        "",
        f"## Goal\n{goal or '(não informado)'}",
        "",
        "## Status real",
        "Mission pack local. Nenhum projeto foi editado por este pacote.",
        "",
        "## Arquivos deste pacote",
        "- 00_MISSION_SUMMARY.md",
        "- 01_CLAUDE_PROMPT.md",
        "- 02_VALIDATION_CHECKLIST.md",
        "- 03_RETURN_FORMAT.md",
        "",
        "## Como usar",
        "1. Abrir 01_CLAUDE_PROMPT.md.",
        "2. Colar inteiro no Claude Code (Oficina, jarvis-core, etc).",
        "3. Pedir para Claude executar conforme o modo.",
        "4. Conferir contra 02_VALIDATION_CHECKLIST.md.",
        "5. Resposta no formato 03_RETURN_FORMAT.md.",
        "",
        "## Bloqueios mantidos",
        *[f"- {r}" for r in HARD_RULES],
        "",
        "## Produção",
        "Nada alterado por este pacote.",
    ]
    return "\n".join(lines) + "\n"


def build_checklist(mode):
    items_common = [
        "- pwd",
        "- git status --short (no projeto)",
        "- git branch --show-current (no projeto)",
        "- git log --oneline -8 (no projeto)",
    ]
    extra = {
        "qa-sprint": [
            "- npx tsc --noEmit (se TS)",
            "- script de test do package manager registrado",
            "- não rodar deploy/push/PR/merge",
        ],
        "goal-sprint": [
            "- validar typecheck e testes a cada iteração",
            "- parar quando o próximo patch tiver baixo ROI ou alto risco",
            "- não rodar deploy/push/PR/merge",
        ],
        "browser-qa": [
            "- usar somente ferramenta de browser já instalada",
            "- NÃO instalar Playwright/Cypress automaticamente",
            "- preferir Vitest+RTL para componentes puros",
        ],
        "final-gate": [
            "- exigir árvore limpa",
            "- exigir branch dedicada (não main)",
            "- exigir typecheck PASS",
            "- exigir test suite PASS com números",
            "- reportar safe/not-safe — JAMAIS executar push/PR/deploy",
        ],
        "self-evolve": [
            "- bash -n ./jarvis (sintaxe entrypoint)",
            "- python3 -m py_compile em cada script alterado",
            "- ./jarvis command-audit (drift core/help/catalog/smoke)",
            "- env JARVIS_NO_REPORT=1 ./jarvis smoke-test",
            "- env JARVIS_NO_REPORT=1 ./jarvis safety-gate",
            "- ./jarvis self-cockpit (verificar saída clara)",
            "- git diff --check (sem whitespace bugs)",
            "- git add <paths explícitos> antes do commit (NUNCA `git add .`)",
            "- sem push/PR/merge/deploy",
        ],
    }
    lines = [
        "# Claude Mission — Validation Checklist",
        "",
        "## Status real",
        "Checklist local. Rodar antes de aceitar qualquer patch ou commit.",
        "",
        "## Itens obrigatórios",
        *items_common,
        *extra.get(mode, []),
        "",
        "## Bloqueios",
        *[f"- {r}" for r in HARD_RULES],
        "",
        "## Produção",
        "Nada alterado.",
    ]
    return "\n".join(lines) + "\n"


def build_return_format(mode):
    # Each builder embeds the format inside the prompt; this file is a separate echo.
    base = [
        "# Claude Mission — Required Return Format",
        "",
        "## Status real",
        "Formato obrigatório de resposta. Claude deve seguir EXATAMENTE.",
        "",
        f"## Modo\n{mode}",
        "",
        "## Seções obrigatórias",
    ]
    sections = {
        "qa-sprint": [
            "1. STATUS REAL",
            "2. INSPEÇÃO",
            "3. PATCH APPLIED?",
            "4. VALIDATION RESULTS",
            "5. RUÍDO DE TESTE",
            "6. RISKS / NOT VALIDATED",
            "7. NEXT BEST PATCH ou STOP",
            "8. SAFE TO COMMIT? (comando exato se yes)",
        ],
        "goal-sprint": [
            "1. STATUS REAL",
            "2. DEFINITION OF DONE",
            "3. ITERAÇÕES APLICADAS",
            "4. ATENDIDOS vs NÃO ATENDIDOS",
            "5. HUMAN-ONLY RESTANTE",
            "6. EXACT NEXT ACTION",
            "7. SAFE TO COMMIT?",
        ],
        "browser-qa": [
            "1. STATUS REAL",
            "2. TOOLING DETECTADO",
            "3. INVENTÁRIO DE UI ALTERADA",
            "4. PATCHES APLICADOS",
            "5. VALIDATION RESULTS",
            "6. STILL NEEDS HUMAN CHECK",
            "7. SAFE TO COMMIT?",
        ],
        "final-gate": [
            "1. STATUS REAL (read-only)",
            "2. CHECKLIST RESULT",
            "3. DIFF SUMMARY",
            "4. REMAINING UNVALIDATED",
            "5. SAFE TO PUSH?",
            "6. SAFE TO OPEN PR?",
            "7. SAFE TO DEPLOY?",
            "8. NEXT EXACT ACTION",
        ],
        "self-evolve": [
            "1. STATUS REAL (Created/Modified/Tested/Committed/Not validated/Production)",
            "2. WHAT IMPROVED",
            "3. COMMANDS ADDED/CHANGED",
            "4. NEW DAILY LOOP (se mudou)",
            "5. VALIDATION RESULTS (PASS/FAIL com números)",
            "6. COMMITS CREATED (hash + msg)",
            "7. FILES CHANGED (lista exata)",
            "8. RISKS / LIMITS",
            "9. WHAT NOT TO BUILD NEXT",
            "10. NEXT BEST ACTION",
            "11. SAFE TO STOP?",
        ],
    }
    base += sections.get(mode, ["(modo desconhecido)"])
    base += ["", "## Produção", "Nada alterado."]
    return "\n".join(base) + "\n"


def main():
    argv = sys.argv[1:]
    mode, alias, goal, copy_flag = parse_args(argv)
    # self-evolve always targets jarvis-core regardless of --project.
    if mode == "self-evolve":
        alias = "jarvis-core"
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    print("JARVIS — Theo Padilha AI Worker Mission Pack")
    print("Status real: pacote de missão local. Nenhum projeto foi editado.")
    print("")

    if not mode:
        fail(USAGE)
    if mode not in VALID_MODES:
        fail(f"--mode inválido: {mode}. Válidos: {', '.join(VALID_MODES)}")
    if not alias:
        fail(USAGE)
    if mode == "goal-sprint" and not goal:
        fail('goal-sprint exige --goal "objetivo".')

    project = load_project(alias)
    path = Path(project["path"]).expanduser()
    tooling = detect_tooling(path) if path.exists() else {"has_pkg": False}

    print(f"Mode: {mode}")
    print(f"Project: {alias} -> {path}")
    if goal:
        print(f"Goal: {goal}")
    print("")

    ts_iso = datetime.now().isoformat(timespec="seconds")
    ts_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    slug = slugify(goal or mode)
    folder = f"{ts_dir}_project-{alias}_{mode}_{slug}"

    prompt = PROMPT_BUILDERS[mode](project, tooling, goal)
    summary = build_summary(project, mode, goal, ts_iso)
    checklist = build_checklist(mode)
    return_fmt = build_return_format(mode)

    if no_report:
        print("=== PREVIEW: 00_MISSION_SUMMARY.md ===")
        print(summary)
        print("=== PREVIEW: 01_CLAUDE_PROMPT.md ===")
        print(prompt)
        print("=== PREVIEW: 02_VALIDATION_CHECKLIST.md ===")
        print(checklist)
        print("=== PREVIEW: 03_RETURN_FORMAT.md ===")
        print(return_fmt)
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
        print("Produção: nada alterado.")
        return

    mission_dir = OUT_DIR / folder
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "00_MISSION_SUMMARY.md").write_text(summary, encoding="utf-8")
    (mission_dir / "01_CLAUDE_PROMPT.md").write_text(prompt, encoding="utf-8")
    (mission_dir / "02_VALIDATION_CHECKLIST.md").write_text(checklist, encoding="utf-8")
    (mission_dir / "03_RETURN_FORMAT.md").write_text(return_fmt, encoding="utf-8")

    print(f"Mission pack: {mission_dir.relative_to(ROOT)}")
    print(f"Prompt: {(mission_dir / '01_CLAUDE_PROMPT.md').relative_to(ROOT)}")
    print(f"Checklist: {(mission_dir / '02_VALIDATION_CHECKLIST.md').relative_to(ROOT)}")
    print(f"Return format: {(mission_dir / '03_RETURN_FORMAT.md').relative_to(ROOT)}")
    print("")
    if copy_flag:
        import shutil, subprocess  # local import — avoids hard dep at module load
        if shutil.which("pbcopy"):
            try:
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p.communicate(input=prompt.encode("utf-8"), timeout=10)
                if p.returncode == 0:
                    print("clipboard: prompt copiado via pbcopy ✓")
                else:
                    print("clipboard: pbcopy retornou erro — copie manualmente.")
            except Exception as exc:
                print(f"clipboard: falhou ({exc}). Copie manualmente.")
        else:
            print("clipboard: pbcopy indisponível. Fallback:")
            print(f"  cat \"{(mission_dir / '01_CLAUDE_PROMPT.md')}\" | pbcopy")
    print('Para ver depois: ./jarvis claude-mission-latest')
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
