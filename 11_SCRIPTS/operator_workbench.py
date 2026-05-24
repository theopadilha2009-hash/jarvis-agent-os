from pathlib import Path
from datetime import datetime
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "07_RELATORIOS" / "02_TECNICOS"
REPORT_FILE = REPORT_DIR / "ULTIMO_OPERATOR_WORKBENCH.md"
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"

USAGE = (
    "Uso:\n"
    "  ./jarvis operator-workbench                 painel geral do operador\n"
    "  ./jarvis operator-workbench --jarvis-core   modo repositório JARVIS\n"
    "  ./jarvis operator-workbench --project ALIAS modo projeto travado\n"
)

MUST_NOT = [
    "push, merge ou deploy",
    "tocar VPS, n8n ou produção",
    "abrir/ler .env ou imprimir secrets/tokens/API keys",
    "rodar rm -rf, git reset --hard, force-push, drop table, chmod 0777",
    "alterar projetos sem LOCAL_EXEC handoff aprovado",
    "criar PDFs, fontes randômicas, dependências externas ou APIs externas",
    "commitar artefatos sem revisão humana e sem secret-scan",
]

WHEN_USE_CLAUDE = [
    "tarefa precisa de auditoria estruturada de código (modo audit).",
    "patch curto e bem delimitado (modo patch) já planejado e aprovado.",
    "revisar saída de executor externo antes de aceitar (modo review).",
    "organizar/melhorar docs locais sem alegação de produção (modo docs).",
]

WHEN_NOT_USE_CLAUDE = [
    "tarefa trivial que você resolve sozinho mais rápido.",
    "ainda não entende o problema — primeiro readonly-run/project-resolve.",
    "Git sujo sem revisão — limpe antes de pedir patch.",
    "tarefa toca produção/VPS/n8n/deploy/push — JARVIS bloqueia, não delegue.",
    "precisa abrir .env ou secrets — Claude não deve ver isso.",
]


def run(cmd, cwd=None, timeout=10):
    try:
        out = subprocess.check_output(
            cmd,
            cwd=cwd or ROOT,
            text=True,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"ERRO: {e}"


def parse_args(argv):
    scope = "general"
    project_alias = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--jarvis-core":
            if scope != "general":
                print("FALHA: escopo já definido (não combine --jarvis-core com --project).")
                print("")
                print(USAGE)
                sys.exit(1)
            scope = "jarvis-core"
            i += 1
            continue
        if arg == "--project":
            if i + 1 >= len(argv):
                print("FALHA: --project exige alias.")
                print("")
                print(USAGE)
                sys.exit(1)
            if scope != "general":
                print("FALHA: escopo já definido (não combine --jarvis-core com --project).")
                print("")
                print(USAGE)
                sys.exit(1)
            scope = "project"
            project_alias = argv[i + 1].strip().lower()
            i += 2
            continue
        if arg.startswith("--project="):
            if scope != "general":
                print("FALHA: escopo já definido (não combine --jarvis-core com --project).")
                print("")
                print(USAGE)
                sys.exit(1)
            scope = "project"
            project_alias = arg.split("=", 1)[1].strip().lower()
            i += 1
            continue
        print(f"FALHA: opção desconhecida: {arg}")
        print("")
        print(USAGE)
        sys.exit(1)
    return scope, project_alias


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
        for k in sorted(projects):
            print(f"- {k}")
        sys.exit(1)
    return projects[alias]


def latest_file(folder, pattern="*.md"):
    p = ROOT / folder
    if not p.exists():
        return None
    files = [x for x in p.glob(pattern) if x.is_file()]
    return max(files, key=lambda x: x.stat().st_mtime) if files else None


def latest_dir(folder):
    p = ROOT / folder
    if not p.exists():
        return None
    dirs = [x for x in p.iterdir() if x.is_dir()]
    return max(dirs, key=lambda x: x.stat().st_mtime) if dirs else None


def rel(path):
    if not path:
        return "—"
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def age_str(path):
    if not path or not path.exists():
        return "—"
    secs = int((datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


def parse_gate_label(path):
    if not path or not path.exists():
        return "SEM RELATÓRIO"
    text = path.read_text(encoding="utf-8", errors="ignore")
    for label in ("PASSOU", "COM PENDÊNCIAS", "FALHOU"):
        if label in text:
            return label
    return "DESCONHECIDO"


def review_decision(path):
    if not path or not path.exists():
        return "—"
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"##\s+Decisão\s*\n([^\n]+)", text)
    return m.group(1).strip() if m else "—"


def project_lock_from(path):
    if not path:
        return "—"
    m = re.search(r"project-([a-z0-9]+(?:-[a-z0-9]+)*?)-", path.name)
    return m.group(1) if m else "—"


def git_info():
    _, commit = run(["git", "rev-parse", "--short", "HEAD"])
    _, branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    _, status = run(["git", "status", "--short"])
    return commit, branch, status


def project_git_state(project):
    path = Path(project["path"])
    if not path.exists():
        return {"exists": False, "is_git": False, "branch": "—", "clean": False, "status": "—"}
    is_git = (path / ".git").exists()
    if not is_git:
        return {"exists": True, "is_git": False, "branch": "—", "clean": False, "status": "—"}
    _, branch = run(["git", "branch", "--show-current"], cwd=path)
    _, status = run(["git", "status", "--short"], cwd=path)
    return {
        "exists": True,
        "is_git": True,
        "branch": branch or "unknown",
        "clean": not status,
        "status": status or "limpo",
    }


def action_menu(scope, dirty, gates_ok, review, project_alias):
    """Numbered action menu. Order changes by safety state."""
    items = []
    if dirty:
        items.append("Inspecionar status do Git e decidir o que commitar/limpar primeiro.")
        items.append("Rodar pending-artifacts e secret-scan antes de qualquer patch.")
    items.append("Apenas inspecionar status (sem editar nada).")
    if review.startswith("PARAR"):
        items.append("Revisar manualmente a última saída LOCAL_EXEC antes de aceitar patch.")
    if scope == "general" or scope == "jarvis-core":
        if not dirty and gates_ok:
            items.append("Criar Claude mission segura — modo audit (read-only).")
            items.append("Criar Claude mission segura — modo patch (escopo curto e aprovado).")
        items.append("Abrir a última Claude mission gerada.")
    if scope == "project":
        items.append(f"Validar alias do projeto: project-resolve {project_alias}.")
        items.append(f"Preparar run-safe travado em {project_alias} (sem deploy).")
        if not dirty:
            items.append(f"Criar Claude mission segura para {project_alias} — modo audit.")
        items.append("Revisar saída de executor externo antes de aceitar patch.")
    if scope == "general":
        items.append("Escolher projeto travado (project-menu) e sair do modo geral.")
    items.append("Fechar/snapshotar versão atual quando tudo estiver verde.")
    numbered = []
    for idx, txt in enumerate(items, start=1):
        numbered.append(f"{idx}. {txt}")
    return numbered


def exact_commands(scope, dirty, project_alias):
    """Exact safe shell commands to run next."""
    lines = []
    if dirty:
        lines += [
            "git status --short",
            "git diff --stat",
            "./jarvis pending-artifacts",
            "./jarvis secret-scan",
        ]
    lines += [
        "./jarvis visual-cockpit",
        "./jarvis claude-mission-latest",
        "./jarvis quality-gate",
    ]
    if scope == "general" or scope == "jarvis-core":
        lines += [
            './jarvis claude-mission --jarvis-core --type audit "descrever tarefa"',
            './jarvis claude-mission --jarvis-core --type patch "descrever patch aprovado"',
        ]
    if scope == "general":
        lines += [
            "./jarvis project-menu",
            "./jarvis next-step",
        ]
    if scope == "project":
        alias = project_alias or "ALIAS"
        lines += [
            f"./jarvis project-resolve {alias}",
            f'./jarvis run-safe --project {alias} "descrever tarefa sem deploy"',
            f'./jarvis claude-mission --project {alias} --type audit "descrever tarefa"',
            "./jarvis local-exec-review caminho/da/resposta.md",
        ]
    return lines


def blocked_list(dirty, smoke, release, safety, review, project_state):
    items = []
    if dirty:
        items.append("git status sujo no repositório JARVIS — pendências locais.")
    for name, label in (
        ("smoke-test", smoke),
        ("release-check", release),
        ("safety-gate", safety),
    ):
        if label != "PASSOU":
            items.append(f"{name}: {label}")
    if review.startswith("PARAR"):
        items.append(f"última review LOCAL_EXEC bloqueia patch: {review}")
    if project_state is not None:
        if not project_state["exists"]:
            items.append("caminho do projeto não existe localmente.")
        elif not project_state["is_git"]:
            items.append("projeto não é repositório Git — não rodar patch.")
        elif not project_state["clean"]:
            items.append("git status do projeto está sujo — limpar antes de patch.")
    return items


def build_text(scope, project_alias):
    commit, branch, status_text = git_info()
    dirty = bool(status_text)

    smoke_p = latest_file("10_TESTES/SMOKE_TESTS")
    release_p = latest_file("10_TESTES/RELEASE_CHECKS")
    safety_p = latest_file("10_TESTES/SAFETY_GATES")
    smoke = parse_gate_label(smoke_p)
    release = parse_gate_label(release_p)
    safety = parse_gate_label(safety_p)
    gates_ok = (smoke == release == safety == "PASSOU")

    session_p = latest_file("05_EXECUCAO/18_LOCAL_EXEC_SESSIONS")
    handoff_p = latest_dir("05_EXECUCAO/15_LOCAL_EXEC_HANDOFFS")
    review_p = latest_file("05_EXECUCAO/16_LOCAL_EXEC_REVIEWS")
    mission_p = latest_dir("05_EXECUCAO/21_CLAUDE_MISSIONS")
    project_lock_alias = project_lock_from(session_p)
    review = review_decision(review_p)

    project = None
    project_state = None
    if scope == "project":
        project = load_project(project_alias)
        project_state = project_git_state(project)

    scope_label = {
        "general": "geral",
        "jarvis-core": "jarvis-core",
        "project": f"project:{project_alias}",
    }[scope]

    header_lines = [
        "# Operator Workbench — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Escopo\n{scope_label}",
        "",
        "## Status real",
        "Painel local para operador. Nada aplicado em projeto real. Produção não alterada.",
    ]

    current_status_lines = [
        "## Current status",
        f"- Commit: {commit}",
        f"- Branch: {branch}",
        f"- Git JARVIS: {'sujo' if dirty else 'limpo'}",
    ]
    if scope == "project" and project is not None and project_state is not None:
        current_status_lines += [
            f"- Project alias: {project['alias']}",
            f"- Project path: {project['path']}",
            f"- Project Git: {'sujo' if (project_state['is_git'] and not project_state['clean']) else ('limpo' if project_state['is_git'] else 'não-git')}",
            f"- Project branch: {project_state['branch']}",
            f"- Package manager: {project.get('package_manager', 'unknown')}",
            f"- LOCAL_EXEC permitido: {project.get('allowed_for_local_exec', False)}",
        ]

    gate_lines = [
        "## Gate status",
        "| Gate          | Result          | Age  | Artifact |",
        "|---------------|-----------------|------|----------|",
        f"| smoke-test    | {smoke:<15} | {age_str(smoke_p):<4} | {rel(smoke_p)} |",
        f"| release-check | {release:<15} | {age_str(release_p):<4} | {rel(release_p)} |",
        f"| safety-gate   | {safety:<15} | {age_str(safety_p):<4} | {rel(safety_p)} |",
        "",
        "Nota: este workbench não executa gates. Use ./jarvis quality-gate ou ./jarvis safety-gate para validar agora.",
    ]

    mission_lines = [
        "## Latest Claude mission",
        f"- Pacote: {rel(mission_p)}",
        f"- Idade: {age_str(mission_p)}",
        "- Comando: `./jarvis claude-mission-latest` para abrir prompt.",
    ]

    lock_lines = [
        "## Latest project lock",
        f"- Projeto: {project_lock_alias}",
        f"- Sessão: {rel(session_p)}",
        f"- Idade: {age_str(session_p)}",
        f"- Handoff: {rel(handoff_p)}",
        f"- Última decisão de review: {review}",
    ]

    menu = action_menu(scope, dirty, gates_ok, review, project_alias)
    menu_lines = ["## Action menu", *menu]

    cmds = exact_commands(scope, dirty, project_alias)
    cmd_lines = ["## Exact commands", *[f"- `{c}`" for c in cmds]]

    use_claude_lines = ["## When to use Claude", *[f"- {x}" for x in WHEN_USE_CLAUDE]]
    not_use_claude_lines = ["## When NOT to use Claude", *[f"- {x}" for x in WHEN_NOT_USE_CLAUDE]]

    blocked = blocked_list(dirty, smoke, release, safety, review, project_state)
    blocked_lines = [
        "## Blocked / pending",
        *([f"- {x}" for x in blocked] if blocked else ["- nada bloqueando agora"]),
    ]

    must_not_lines = ["## Must NOT do", *[f"- {x}" for x in MUST_NOT]]

    production_lines = [
        "## Production status",
        "Nada alterado em produção, VPS, n8n, deploy, push ou PR.",
    ]

    sections = [
        header_lines,
        [""],
        current_status_lines,
        [""],
        gate_lines,
        [""],
        mission_lines,
        [""],
        lock_lines,
        [""],
        menu_lines,
        [""],
        cmd_lines,
        [""],
        use_claude_lines,
        [""],
        not_use_claude_lines,
        [""],
        blocked_lines,
        [""],
        must_not_lines,
        [""],
        production_lines,
    ]

    out = []
    for sec in sections:
        out.extend(sec)
    return "\n".join(out) + "\n"


def main():
    scope, project_alias = parse_args(sys.argv[1:])

    print("JARVIS — Theo Padilha AI Worker Operator Workbench")
    print("Status real: painel local. Nada aplicado em projeto real.")
    print("")

    text = build_text(scope, project_alias)
    print(text)

    if os.environ.get("JARVIS_NO_REPORT") == "1":
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
        print("Produção: nada alterado.")
        return

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(text, encoding="utf-8")
    print(f"Relatório: {REPORT_FILE.relative_to(ROOT)}")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
