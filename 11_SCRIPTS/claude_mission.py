from pathlib import Path
from datetime import datetime
import json
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
VALID_TYPES = ("audit", "patch", "review", "docs")

USAGE = (
    "Uso:\n"
    "  ./jarvis claude-mission --jarvis-core --type audit \"tarefa\"\n"
    "  ./jarvis claude-mission --jarvis-core --type patch \"tarefa\"\n"
    "  ./jarvis claude-mission --jarvis-core --type review \"tarefa\"\n"
    "  ./jarvis claude-mission --jarvis-core --type docs \"tarefa\"\n"
    "  ./jarvis claude-mission --project ALIAS --type audit \"tarefa\"\n"
    "Tipos válidos: audit, patch, review, docs"
)

COMMON_RULES = [
    "Status real obrigatório: dizer claramente se algo foi alterado ou não.",
    "Nenhuma alegação de produção. Tudo aqui é local.",
    "Não tocar VPS, n8n, deploy, push, PR, main, .env ou secrets.",
    "Não imprimir tokens, API keys, cookies, senhas ou QR codes.",
    "Não gerar PDF. Não criar fontes randômicas.",
    "Não usar APIs externas neste pacote.",
    "Não fazer commit sem autorização explícita do usuário.",
]

PREFLIGHT_BLOCK = [
    "Antes de qualquer edição, rode e reporte:",
    "- git status --short",
    "- git branch --show-current",
    "- git log --oneline -5",
    "Se a árvore não estiver limpa, PARE e relate exatamente o que está sujo.",
]


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "claude-mission"


def parse_args(argv):
    scope = None
    project_alias = None
    mtype = None
    task_parts = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--jarvis-core":
            if scope is not None:
                print("FALHA: escopo já definido (não combine --jarvis-core com --project).")
                sys.exit(1)
            scope = "jarvis-core"
            i += 1
            continue
        if arg == "--project":
            if i + 1 >= len(argv):
                print("FALHA: --project exige alias.")
                sys.exit(1)
            if scope is not None:
                print("FALHA: escopo já definido (não combine --jarvis-core com --project).")
                sys.exit(1)
            scope = "project"
            project_alias = argv[i + 1].strip().lower()
            i += 2
            continue
        if arg.startswith("--project="):
            if scope is not None:
                print("FALHA: escopo já definido (não combine --jarvis-core com --project).")
                sys.exit(1)
            scope = "project"
            project_alias = arg.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if arg == "--type":
            if i + 1 >= len(argv):
                print("FALHA: --type exige valor (audit|patch|review|docs).")
                sys.exit(1)
            mtype = argv[i + 1].strip().lower()
            i += 2
            continue
        if arg.startswith("--type="):
            mtype = arg.split("=", 1)[1].strip().lower()
            i += 1
            continue
        task_parts.append(arg)
        i += 1
    return scope, project_alias, mtype, " ".join(task_parts).strip()


def load_project(alias):
    if not REGISTRY.exists():
        print("FALHA: PROJECT_REGISTRY.json não encontrado.")
        sys.exit(1)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    projects = {p["alias"]: p for p in registry.get("projects", [])}
    if alias not in projects:
        print(f"FALHA: project alias não registrado: {alias}")
        print("")
        print("Aliases disponíveis:")
        for key in sorted(projects):
            print(f"- {key}")
        sys.exit(1)
    project = projects[alias]
    if not project.get("allowed_for_local_exec", False):
        print(f"FALHA: projeto não permitido para LOCAL_EXEC: {alias}")
        sys.exit(1)
    return project


def mode_rules(mtype):
    if mtype == "audit":
        return [
            "Modo AUDIT: somente leitura. Nenhuma edição neste pacote.",
            "Retornar: diagnóstico, riscos, arquivos relevantes, próxima patch recomendada (sem aplicá-la).",
        ]
    if mtype == "patch":
        return [
            "Modo PATCH: leia primeiro, edite só o mínimo aprovado.",
            "Não refatorar fora do escopo. Não adicionar dependências.",
            "Não criar arquivos fora do necessário.",
            "Validar localmente. Não commitar sem autorização.",
            "Retornar: arquivos alterados, resumo de diff, validações executadas e safe-to-commit yes/no.",
        ]
    if mtype == "review":
        return [
            "Modo REVIEW: inspecione o resumo/output/diff fornecido.",
            "Classifique blockers (push/merge/deploy/produção/VPS/n8n/.env/secrets/rm -rf etc).",
            "Recomende ACEITAR / REJEITAR / REVISAR.",
            "Nenhuma edição salvo autorização explícita.",
        ]
    if mtype == "docs":
        return [
            "Modo DOCS: organizar ou melhorar docs/status locais.",
            "Sem alegações de produção. Sem PDFs. Sem fontes randômicas.",
            "Edições mínimas, preferir editar arquivo existente.",
        ]
    return []


def scope_rules(scope, project):
    if scope == "jarvis-core":
        return [
            "Escopo: repositório JARVIS local.",
            "Não quebrar command-audit, smoke-test, release-check, safety-gate, quality-gate.",
            "Manter JARVIS local-first. Sem produção. Sem PDFs. Sem fontes randômicas.",
            "Não refatorar jarvis_core.py além de registro de rota/help.",
        ]
    if scope == "project":
        return [
            f"Escopo: projeto {project['alias']} -> {project['path']}",
            f"Branch atual registrada: {project.get('branch', 'unknown')}",
            "Confirme pasta/projeto/branch antes de qualquer leitura ou edição.",
            "Não mexer em main sem autorização explícita.",
            "Não fazer deploy, push, PR ou merge.",
            "Respeitar project lock: somente este projeto.",
        ]
    return []


def validation_checklist(scope, mtype):
    if scope == "jarvis-core":
        return [
            "- git status --short",
            "- python3 -m py_compile para cada script alterado em 11_SCRIPTS/",
            "- ./jarvis command-audit",
            "- env JARVIS_NO_REPORT=1 ./jarvis smoke-test",
            "- ./jarvis quality-gate",
            "- env JARVIS_NO_REPORT=1 ./jarvis safety-gate",
        ]
    return [
        "- git status --short (no projeto)",
        "- git branch --show-current (no projeto)",
        "- se houver package.json: rodar build/test do package manager registrado",
        "- não rodar deploy, push, PR ou merge",
    ]


def return_format(mtype):
    if mtype == "audit":
        return [
            "1. STATUS REAL — nenhuma edição",
            "2. DIAGNÓSTICO",
            "3. RISCOS",
            "4. ARQUIVOS RELEVANTES",
            "5. PRÓXIMA PATCH RECOMENDADA (descritiva, não aplicada)",
            "6. SAFE TO PROCEED? yes/no",
        ]
    if mtype == "review":
        return [
            "1. STATUS REAL — nenhuma edição",
            "2. BLOCKERS DETECTADOS",
            "3. SINAIS POSITIVOS",
            "4. RECOMENDAÇÃO: ACEITAR / REJEITAR / REVISAR",
            "5. JUSTIFICATIVA CURTA",
        ]
    if mtype == "docs":
        return [
            "1. STATUS REAL",
            "2. ARQUIVOS EDITADOS (mínimo)",
            "3. RESUMO DAS MUDANÇAS",
            "4. VALIDAÇÕES",
            "5. SAFE TO COMMIT? yes/no",
        ]
    return [
        "1. STATUS REAL — o que foi ou não foi alterado",
        "2. FILES CHANGED",
        "3. WHAT CHANGED (curto)",
        "4. VALIDATION RESULTS — PASS/FAIL/PENDING por item",
        "5. GIT STATUS final",
        "6. RISKS / NOT VALIDATED",
        "7. SAFE TO COMMIT? yes/no",
    ]


def build_prompt(scope, project, mtype, task):
    scope_line = (
        "JARVIS local repository"
        if scope == "jarvis-core"
        else f"project {project['alias']} ({project['path']})"
    )
    lines = [
        "# Claude Mission Prompt",
        "",
        f"## Scope\n{scope_line}",
        "",
        f"## Type\n{mtype}",
        "",
        f"## Task\n{task}",
        "",
        "## Status real rules",
        *[f"- {r}" for r in COMMON_RULES],
        "",
        "## Git preflight",
        *PREFLIGHT_BLOCK,
        "",
        "## Scope rules",
        *[f"- {r}" for r in scope_rules(scope, project)],
        "",
        "## Mode rules",
        *[f"- {r}" for r in mode_rules(mtype)],
        "",
        "## Read-only first",
        ("Modo PATCH: leitura antes da edição mínima."
         if mtype == "patch"
         else "Este modo é read-only. Não editar arquivos."),
        "",
        "## Validation checklist",
        *validation_checklist(scope, mtype),
        "",
        "## Required return format",
        *return_format(mtype),
        "",
        "## Commit policy",
        "Não fazer commit sem autorização explícita. Retornar somente safe-to-commit yes/no.",
    ]
    return "\n".join(lines) + "\n"


def build_summary(scope, project, mtype, task, ts_iso):
    scope_line = (
        "jarvis-core"
        if scope == "jarvis-core"
        else f"project:{project['alias']} -> {project['path']}"
    )
    lines = [
        "# Claude Mission Summary",
        "",
        f"## Data\n{ts_iso}",
        "",
        f"## Scope\n{scope_line}",
        "",
        f"## Type\n{mtype}",
        "",
        f"## Task\n{task}",
        "",
        "## Status real",
        "Mission pack local. Nenhum projeto foi editado por este pacote.",
        "",
        "## Files in this mission",
        "- 00_MISSION_SUMMARY.md (este arquivo)",
        "- 01_CLAUDE_PROMPT.md",
        "- 02_VALIDATION_CHECKLIST.md",
        "- 03_RETURN_FORMAT.md",
        "",
        "## Como usar",
        "1. Abrir 01_CLAUDE_PROMPT.md.",
        "2. Colar inteiro no Claude Code.",
        "3. Pedir para Claude executar conforme o modo.",
        "4. Conferir contra 02_VALIDATION_CHECKLIST.md.",
        "5. Receber resposta no formato 03_RETURN_FORMAT.md.",
        "",
        "## Bloqueios mantidos",
        "- Sem push, merge, deploy.",
        "- Sem VPS, n8n, produção.",
        "- Sem leitura/exposição de .env, tokens, secrets.",
        "- Sem PDF, sem fontes randômicas, sem APIs externas.",
        "",
        "## Produção",
        "Nada alterado.",
    ]
    return "\n".join(lines) + "\n"


def build_checklist_file(scope, mtype):
    lines = [
        "# Claude Mission — Validation Checklist",
        "",
        "## Status real",
        "Checklist local. Rodar antes de aceitar qualquer patch ou commit.",
        "",
        "## Itens obrigatórios",
        *validation_checklist(scope, mtype),
        "",
        "## Bloqueios",
        "- Não rodar deploy, push, PR, merge.",
        "- Não tocar VPS, n8n, produção, .env, secrets.",
        "",
        "## Produção",
        "Nada alterado.",
    ]
    return "\n".join(lines) + "\n"


def build_return_format_file(mtype):
    lines = [
        "# Claude Mission — Required Return Format",
        "",
        "## Status real",
        "Formato obrigatório de resposta. Claude deve seguir.",
        "",
        "## Seções obrigatórias",
        *return_format(mtype),
        "",
        "## Produção",
        "Nada alterado.",
    ]
    return "\n".join(lines) + "\n"


def main():
    argv = sys.argv[1:]
    scope, project_alias, mtype, task = parse_args(argv)
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    print("JARVIS — Theo Padilha AI Worker Claude Mission")
    print("Status real: pacote de missão local. Nenhum projeto foi editado.")
    print("")

    if scope is None:
        print("FALHA: escopo obrigatório.")
        print("")
        print(USAGE)
        sys.exit(1)
    if mtype is None:
        print("FALHA: --type obrigatório.")
        print("")
        print(USAGE)
        sys.exit(1)
    if mtype not in VALID_TYPES:
        print(f"FALHA: --type inválido: {mtype}")
        print(f"Tipos válidos: {', '.join(VALID_TYPES)}")
        sys.exit(1)
    if not task:
        print("FALHA: tarefa obrigatória.")
        print("")
        print(USAGE)
        sys.exit(1)

    project = None
    if scope == "project":
        project = load_project(project_alias)

    scope_label = "--jarvis-core" if scope == "jarvis-core" else f"--project {project_alias}"
    print(f"Scope: {scope_label}")
    print(f"Type: {mtype}")
    print(f"Task: {task}")
    print("")

    ts_iso = datetime.now().isoformat(timespec="seconds")
    ts_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    slug = slugify(task)
    scope_slug = "jarvis-core" if scope == "jarvis-core" else f"project-{project_alias}"
    folder_name = f"{ts_dir}_{scope_slug}_{mtype}_{slug}"

    prompt = build_prompt(scope, project, mtype, task)
    summary_text = build_summary(scope, project, mtype, task, ts_iso)
    checklist_text = build_checklist_file(scope, mtype)
    return_text = build_return_format_file(mtype)

    if no_report:
        print("=== PREVIEW: 00_MISSION_SUMMARY.md ===")
        print(summary_text)
        print("=== PREVIEW: 01_CLAUDE_PROMPT.md ===")
        print(prompt)
        print("=== PREVIEW: 02_VALIDATION_CHECKLIST.md ===")
        print(checklist_text)
        print("=== PREVIEW: 03_RETURN_FORMAT.md ===")
        print(return_text)
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
        print("Produção: nada alterado.")
        return

    mission_dir = OUT_DIR / folder_name
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "00_MISSION_SUMMARY.md").write_text(summary_text, encoding="utf-8")
    (mission_dir / "01_CLAUDE_PROMPT.md").write_text(prompt, encoding="utf-8")
    (mission_dir / "02_VALIDATION_CHECKLIST.md").write_text(checklist_text, encoding="utf-8")
    (mission_dir / "03_RETURN_FORMAT.md").write_text(return_text, encoding="utf-8")

    print(f"Mission pack: {mission_dir.relative_to(ROOT)}")
    print(f"Prompt: {(mission_dir / '01_CLAUDE_PROMPT.md').relative_to(ROOT)}")
    print(f"Checklist: {(mission_dir / '02_VALIDATION_CHECKLIST.md').relative_to(ROOT)}")
    print(f"Return format: {(mission_dir / '03_RETURN_FORMAT.md').relative_to(ROOT)}")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
