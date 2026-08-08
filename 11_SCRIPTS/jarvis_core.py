#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import sys
import subprocess
import re
import textwrap

ROOT = Path.cwd()

REQUIRED_DIRS = [
    "00_COLE_AQUI",
    "01_SISTEMA",
    "02_TAREFAS",
    "03_MEMORIA",
    "04_PROJETOS",
    "05_EXECUCAO",
    "06_PROMPTS",
    "07_RELATORIOS",
    "08_REFERENCIAS",
    "09_LOGS",
    "10_TESTES",
    "99_ARQUIVO_MORTO",
]

INBOX_DIRS = [
    "00_COLE_AQUI/01_PEDIDOS_BRUTOS",
    "00_COLE_AQUI/02_PDFS_TXTS_DOCS",
    "00_COLE_AQUI/03_OUTPUTS_CLAUDE_CHATGPT",
    "00_COLE_AQUI/04_PRINTS_SANITIZADOS",
    "00_COLE_AQUI/05_N8N_JSON_SANITIZADO",
    "00_COLE_AQUI/06_CODIGO_OU_REPO_INFO",
]

def extract_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == heading:
            content = []
            for next_line in lines[i+1:]:
                if next_line.startswith("## "):
                    break
                if next_line.strip():
                    content.append(next_line)
            return "\n".join(content).strip()
    return ""

def project_slug(name: str) -> str:
    name = name.strip().upper()
    replacements = {
        "Á": "A", "À": "A", "Ã": "A", "Â": "A",
        "É": "E", "Ê": "E",
        "Í": "I",
        "Ó": "O", "Õ": "O", "Ô": "O",
        "Ú": "U",
        "Ç": "C",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = re.sub(r"[^A-Z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:60] or "NOVO_PROJETO"

def now_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9áàãâéêíóôõúçñ\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = text.replace("ç", "c")
    return text[:60] or "task"

def ensure_dirs():
    for d in REQUIRED_DIRS + INBOX_DIRS:
        (ROOT / d).mkdir(parents=True, exist_ok=True)

def detect_type(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["n8n", "workflow", "webhook", "uazapi", "chatwoot"]):
        return "n8n/workflow"
    if any(x in t for x in ["vps", "docker", "traefik", "portainer", "ssh", "servidor"]):
        return "VPS/infra"
    if any(x in t for x in ["bug", "erro", "build", "repo", "github", "branch", "commit"]):
        return "bug/código"
    if any(x in t for x in ["roblox", "jogo", "factory"]):
        return "Factory Roblox"
    if any(x in t for x in ["portfolio", "portfólio", "site", "landing"]):
        return "portfólio/site"
    if any(x in t for x in ["relatorio", "relatório", "resumo", "pdf", "documento"]):
        return "documentação"
    return "geral"

def detect_risk(text: str) -> str:
    t = text.lower()

    safe_negations = [
        "sem produção",
        "sem producao",
        "não mexer em produção",
        "nao mexer em producao",
        "não usar produção",
        "nao usar producao",
        "sem deploy",
        "não deployar",
        "nao deployar",
        "sem credenciais",
        "sem senha",
        "sem token",
        "sem api key",
        "sem banco real",
        "sem envio real",
        "read-only",
        "somente leitura",
    ]

    for phrase in safe_negations:
        t = t.replace(phrase, " ")

    high = [
        "produção", "producao", "prod", "deploy", "main",
        "banco real", "senha", "token", "api key", "vps real",
        "dns", "cliente real", "paciente", "credenciais"
    ]

    medium = [
        "github", "commit", "push", "webhook", "uazapi",
        "supabase", "n8n ativo", "empresa", "chefe", "ruan",
        "claude", "vs code", "repo"
    ]

    if any(x in t for x in high):
        return "alto"
    if any(x in t for x in medium):
        return "médio"
    return "baixo"
def write_log(title: str, body: str):
    logs = ROOT / "09_LOGS"
    logs.mkdir(parents=True, exist_ok=True)

    base = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')}_{slugify(title)}.md"
    file = logs / base

    counter = 1
    while file.exists():
        file = logs / base.replace(".md", f"-{counter}.md")
        counter += 1

    file.write_text(body.strip() + "\n", encoding="utf-8")
    return file

def create_task(text: str, source: str = "manual"):
    ensure_dirs()
    task_type = detect_type(text)
    risk = detect_risk(text)
    task_id = f"TASK-{now_id()}"
    file = ROOT / "02_TAREFAS/00_NOVAS" / f"{task_id}-{slugify(text)}.md"
    file.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Task

## ID
{task_id}

## Projeto
A definir

## Fonte
{source}

## Pedido original
{text}

## Objetivo final
Transformar o pedido em plano seguro, memória organizada e próximo passo executável.

## Tipo detectado
{task_type}

## Status real
Criado localmente.

## Risco detectado
{risk}

## Ferramenta sugerida
A definir pelo Jarvis cockpit.

## Contexto usado
Ainda não carregado.

## Plano seguro inicial
1. Confirmar projeto e ambiente.
2. Separar leitura, alteração, teste e produção.
3. Verificar se há risco de segredo, cliente real ou custo.
4. Criar plano mínimo.
5. Pedir aprovação humana se houver risco médio/alto.

## Aprovação humana necessária antes de
- deploy
- push/main
- produção
- VPS real
- banco real
- envio real para cliente/paciente/lead
- credenciais
- API paga relevante

## Resultado esperado
Task pronta para análise.

## Resultado obtido
Task criada automaticamente pelo Jarvis local.

## Próximo passo
Rodar cockpit/revisão: decidir projeto, ferramenta e primeira ação segura.
"""
    file.write_text(content, encoding="utf-8")

    log = write_log(
        "task-created",
        f"""# Log — Task criada

## Task
{task_id}

## Arquivo
{file}

## Tipo
{task_type}

## Risco
{risk}

## Status real
Criado localmente. Não executado.

## Fonte
{source}
"""
    )
    print(f"Task criada: {file}")
    print(f"Log criado: {log}")

def scan_inbox():
    ensure_dirs()
    print("Scan do 00_COLE_AQUI")
    total = 0
    for d in INBOX_DIRS:
        path = ROOT / d
        files = [p for p in path.rglob("*") if p.is_file() and not p.name.startswith(".")]
        print(f"- {d}: {len(files)} arquivo(s)")
        for p in files[:10]:
            print(f"  • {p.relative_to(ROOT)}")
        if len(files) > 10:
            print(f"  ... +{len(files)-10}")
        total += len(files)
    print(f"Total: {total} arquivo(s)")

def process_inbox():
    ensure_dirs()
    created = 0
    archived = 0
    supported = {".txt", ".md"}
    archive_root = ROOT / "99_ARQUIVO_MORTO" / "INBOX_PROCESSADOS" / datetime.now().strftime("%Y-%m-%d")
    archive_root.mkdir(parents=True, exist_ok=True)

    for d in INBOX_DIRS:
        inbox_path = ROOT / d
        for p in list(inbox_path.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            if p.suffix.lower() not in supported:
                continue

            try:
                text = p.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                continue

            if not text:
                continue

            rel = p.relative_to(ROOT)
            sample = text[:1000]

            create_task(
                f"Processar arquivo de inbox: {rel}\n\nResumo bruto:\n{sample}",
                source=str(rel)
            )
            created += 1

            target = archive_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.exists():
                target = target.with_name(target.stem + "-" + datetime.now().strftime("%H%M%S") + target.suffix)

            p.rename(target)
            archived += 1

    print(f"Processamento concluído. Tasks criadas: {created}. Arquivos arquivados: {archived}.")
    if created == 0:
        print("Nenhum .txt ou .md novo encontrado para processar. PDFs/DOCX ficam para etapa futura.")

def doctor():
    ensure_dirs()
    print("JARVIS — Theo Padilha AI Worker Doctor")
    print("Status real: laboratório local")
    print("")
    ok = True
    for d in REQUIRED_DIRS:
        exists = (ROOT / d).is_dir()
        print(("OK     " if exists else "FALTA  ") + d)
        ok = ok and exists

    print("")
    projects = list((ROOT / "04_PROJETOS").glob("*"))
    tasks = list((ROOT / "02_TAREFAS").rglob("*.md"))
    logs = list((ROOT / "09_LOGS").glob("*.md"))
    print(f"Projetos detectados: {len(projects)}")
    print(f"Tasks detectadas: {len(tasks)}")
    print(f"Logs detectados: {len(logs)}")
    print("")
    print("Resultado:", "estrutura saudável" if ok else "estrutura incompleta")

def report():
    print("JARVIS — Theo Padilha AI Worker Report")
    print("")
    print("Projetos:")
    for p in sorted((ROOT / "04_PROJETOS").glob("*")):
        if p.is_dir():
            print(f"- {p.name}")
    print("")
    print("Tasks novas:")
    new_tasks = sorted((ROOT / "02_TAREFAS/00_NOVAS").glob("*.md"))
    for t in new_tasks[-10:]:
        print(f"- {t.name}")
    if not new_tasks:
        print("- nenhuma")
    print("")
    print("Últimos logs:")
    logs = sorted((ROOT / "09_LOGS").glob("*.md"))
    for l in logs[-10:]:
        print(f"- {l.name}")
    if not logs:
        print("- nenhum")

def next_task():
    open_dir = ROOT / "02_TAREFAS/00_NOVAS"
    tasks = sorted(open_dir.glob("*.md"))

    if not tasks:
        print("JARVIS — Theo Padilha AI Worker")
        print("Nenhuma task nova encontrada.")
        print("")
        print("Próximo passo seguro:")
        print('- coloque algo em 00_COLE_AQUI e rode ./jarvis process-inbox')
        print('- ou rode ./jarvis intake "seu pedido"')
        return

    task = tasks[0]
    text = task.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    print("JARVIS — Theo Padilha AI Worker")
    print("Próxima task ativa")
    print("")
    print(f"Arquivo: {task.relative_to(ROOT)}")
    print("")

    wanted_sections = [
        "## ID",
        "## Projeto",
        "## Pedido original",
        "## Objetivo final",
        "## Tipo detectado",
        "## Status real",
        "## Risco detectado",
        "## Próximo passo",
    ]

    for section in wanted_sections:
        for i, line in enumerate(lines):
            if line.strip() == section:
                print(section)
                content = []
                for next_line in lines[i+1:]:
                    if next_line.startswith("## "):
                        break
                    if next_line.strip():
                        content.append(next_line)
                if content:
                    print("\n".join(content[:8]))
                else:
                    print("-")
                print("")
                break

    print("Ação segura sugerida:")
    print("1. Ler a task acima.")
    print("2. Decidir se ela vira memória, execução, pesquisa ou relatório.")
    print("3. Não executar produção, VPS, deploy, credenciais ou envio real sem aprovação.")

def close_task(query: str = ""):
    open_dir = ROOT / "02_TAREFAS/00_NOVAS"
    closed_dir = ROOT / "02_TAREFAS/03_FINALIZADAS/JARVIS_CLOSED"
    closed_dir.mkdir(parents=True, exist_ok=True)

    tasks = sorted(open_dir.glob("*.md"))
    if not tasks:
        print("Nenhuma task nova para fechar.")
        return

    selected = None
    if query:
        q = query.lower()
        for task in tasks:
            if q in task.name.lower() or q in task.read_text(encoding="utf-8", errors="ignore").lower():
                selected = task
                break
        if selected is None:
            print(f"Nenhuma task encontrada para: {query}")
            return
    else:
        selected = tasks[0]

    text = selected.read_text(encoding="utf-8", errors="ignore")
    closing_note = f"""

## Fechamento pelo JARVIS
Status real: finalizada localmente.
Fechada em: {datetime.now().isoformat(timespec='seconds')}
Produção: nada alterado.
"""
    selected.write_text(text.rstrip() + closing_note + "\n", encoding="utf-8")

    target = closed_dir / selected.name
    if target.exists():
        target = target.with_name(target.stem + "-" + datetime.now().strftime("%H%M%S") + target.suffix)

    selected.rename(target)

    log = write_log(
        "task-closed",
        f"""# Log — Task fechada

## Task
{target.name}

## Local final
{target.relative_to(ROOT)}

## Status real
Finalizada localmente.

## Produção
Nada alterado.
"""
    )

    print(f"Task fechada: {target.relative_to(ROOT)}")
    print(f"Log criado: {log.relative_to(ROOT)}")

def create_project(name: str):
    if not name.strip():
        print('Uso: ./jarvis create-project "Nome do Projeto"')
        return

    slug = project_slug(name)
    project_dir = ROOT / "04_PROJETOS" / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    status_file = project_dir / "PROJECT_STATUS.md"
    next_file = project_dir / "NEXT_ACTIONS.md"

    if not status_file.exists():
        status_file.write_text(f"""# Project Status — {name}

## Projeto
{name}

## Slug
{slug}

## Criador / dono do sistema
Theo Padilha

## Status real atual
Criado localmente.

## O que já existe
- Pasta do projeto criada dentro do JARVIS.

## O que foi criado
- PROJECT_STATUS.md
- NEXT_ACTIONS.md

## O que foi configurado
Nada ainda.

## O que foi testado
Criação local da estrutura.

## O que foi validado
Apenas existência local dos arquivos.

## O que NÃO é produção
Tudo. Este projeto ainda é apenas memória/estrutura local.

## Riscos
- Ainda não há contexto real.
- Ainda não há execução.
- Ainda não há automação conectada.

## Próximo passo seguro
Adicionar contexto inicial do projeto ou criar task relacionada.
""", encoding="utf-8")

    if not next_file.exists():
        next_file.write_text(f"""# Next Actions — {name}

## Agora
- Adicionar contexto inicial do projeto.
- Criar primeira task com `./jarvis intake`.

## Depois
- Classificar risco.
- Criar plano seguro.
- Decidir ferramenta: ChatGPT, Claude Code, Gemini, n8n ou manual.

## Bloqueado por
- Contexto ainda não informado.

## Não fazer ainda
- Produção.
- Deploy.
- VPS.
- Credenciais.
- API paga.
""", encoding="utf-8")

    log = write_log(
        "project-created",
        f"""# Log — Projeto criado

## Projeto
{name}

## Slug
{slug}

## Local
{project_dir.relative_to(ROOT)}

## Status real
Criado localmente.

## Produção
Nada alterado.

## Próximo passo
Adicionar contexto inicial e criar task.
"""
    )

    print(f"Projeto criado/confirmado: {project_dir.relative_to(ROOT)}")
    print(f"Status: {status_file.relative_to(ROOT)}")
    print(f"Next actions: {next_file.relative_to(ROOT)}")
    print(f"Log criado: {log.relative_to(ROOT)}")


def memory_from_task(query: str = ""):
    open_dir = ROOT / "02_TAREFAS/00_NOVAS"

    if query:
        search_dirs = [
            ROOT / "02_TAREFAS/00_NOVAS",
            ROOT / "02_TAREFAS/01_EM_ANDAMENTO",
            ROOT / "02_TAREFAS/02_BLOQUEADAS",
            ROOT / "02_TAREFAS/03_FINALIZADAS",
        ]
        tasks = []
        for folder in search_dirs:
            if folder.exists():
                tasks.extend(sorted(folder.rglob("*.md")))
    else:
        tasks = sorted(open_dir.glob("*.md"))

    if not tasks:
        print("Nenhuma task encontrada para transformar em memória.")
        return

    selected = None

    if query:
        q = query.lower()
        for task in tasks:
            task_text = task.read_text(encoding="utf-8", errors="ignore")
            if q in task.name.lower() or q in task_text.lower():
                selected = task
                break
        if selected is None:
            print(f"Nenhuma task encontrada para: {query}")
            return
    else:
        selected = tasks[0]

    text = selected.read_text(encoding="utf-8", errors="ignore")

    task_id = extract_section(text, "## ID") or selected.stem
    projeto = extract_section(text, "## Projeto") or "A definir"
    pedido = extract_section(text, "## Pedido original") or "-"
    objetivo = extract_section(text, "## Objetivo final") or "-"
    tipo = extract_section(text, "## Tipo detectado") or extract_section(text, "## Tipo") or "-"
    risco = extract_section(text, "## Risco detectado") or extract_section(text, "## Risco") or "-"
    status = extract_section(text, "## Status real") or "-"
    proximo = extract_section(text, "## Próximo passo") or "-"

    title_slug = slugify(f"{task_id} {pedido}")
    date = datetime.now().strftime("%Y-%m-%d")

    if "jarvis" in pedido.lower() or "jarvis" in projeto.lower():
        memory_dir = ROOT / "03_MEMORIA/02_DECISOES"
        memory_kind = "Decisão / evolução do JARVIS"
    else:
        memory_dir = ROOT / "03_MEMORIA/01_APRENDIZADOS"
        memory_kind = "Aprendizado"

    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_file = memory_dir / f"{date}_{title_slug}.md"

    if memory_file.exists():
        memory_file = memory_file.with_name(
            memory_file.stem + "-" + datetime.now().strftime("%H%M%S") + memory_file.suffix
        )

    memory_file.write_text(f"""# {memory_kind} — {task_id}

## Origem
Task: `{selected.relative_to(ROOT)}`

## Projeto
{projeto}

## Pedido original
{pedido}

## Objetivo
{objetivo}

## Tipo
{tipo}

## Risco
{risco}

## Status real no momento da memória
{status}

## Decisão / aprendizado registrado
Esta task foi transformada em memória operacional pelo comando `./jarvis memory-from-task`.

## Interpretação operacional
JARVIS deve preservar tarefas importantes como memória reutilizável para reduzir retrabalho, manter histórico de decisões e facilitar evolução segura do sistema.

## Próximo passo seguro
{proximo}

## Produção
Nada alterado.

## Criador / dono
Theo Padilha.
""", encoding="utf-8")

    log = write_log(
        "memory-from-task",
        f"""# Log — Memória criada a partir de task

## Task
{selected.name}

## Memória criada
{memory_file.relative_to(ROOT)}

## Tipo
{memory_kind}

## Status real
Memória criada localmente.

## Produção
Nada alterado.
"""
    )

    print(f"Memória criada: {memory_file.relative_to(ROOT)}")
    print(f"Log criado: {log.relative_to(ROOT)}")

    try:
        selected.relative_to(open_dir)
        print("")
        print("Próximo passo sugerido:")
        print(f'./jarvis close-task "{task_id}"')
    except ValueError:
        print("")
        print("Task já não está em 00_NOVAS; não precisa fechar novamente.")

def self_test():
    print("JARVIS — Theo Padilha AI Worker Self-Test")
    print("")

    checks = []

    def add_check(name, ok, detail=""):
        checks.append((name, ok, detail))
        status = "OK" if ok else "FALHA"
        print(f"{status}  {name}" + (f" — {detail}" if detail else ""))

    # Required folders
    for d in REQUIRED_DIRS:
        add_check(f"diretório {d}", (ROOT / d).is_dir())

    # Core files
    add_check("arquivo README.md", (ROOT / "README.md").is_file())
    add_check("arquivo jarvis", (ROOT / "jarvis").is_file())
    add_check("script jarvis_core.py", (ROOT / "11_SCRIPTS/jarvis_core.py").is_file())

    # Project and memory
    add_check("projeto JARVIS_CORE", (ROOT / "04_PROJETOS/JARVIS_CORE").is_dir())
    add_check("identidade Theo Padilha", (ROOT / "01_SISTEMA/00_REGRAS/IDENTIDADE_JARVIS_THEO_PADILHA.md").is_file())

    # Logs and tasks
    logs = list((ROOT / "09_LOGS").glob("*.md"))
    add_check("logs existentes", len(logs) > 0, f"{len(logs)} log(s)")

    new_tasks = list((ROOT / "02_TAREFAS/00_NOVAS").glob("*.md"))
    add_check("task inbox acessível", (ROOT / "02_TAREFAS/00_NOVAS").is_dir(), f"{len(new_tasks)} task(s) nova(s)")

    # Git
    git_dir = ROOT / ".git"
    # A linked worktree stores .git as a pointer file, not a directory.
    add_check("git inicializado", git_dir.exists())

    ok_all = all(ok for _, ok, _ in checks)

    print("")
    print("Resultado:", "SELF-TEST PASSOU" if ok_all else "SELF-TEST FALHOU")
    print("Status real: teste local, sem produção, sem credenciais.")

def show_tools():
    registry = ROOT / "01_SISTEMA/02_DECISORES/TOOL_REGISTRY.md"
    print("JARVIS — Theo Padilha AI Worker Tools")
    print("")

    if not registry.exists():
        print("Tool Registry não encontrado.")
        print("Esperado: 01_SISTEMA/02_DECISORES/TOOL_REGISTRY.md")
        return

    text = registry.read_text(encoding="utf-8", errors="ignore")
    current = None
    status = None
    uso = None
    risco = None

    tools = []

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("### "):
            if current:
                tools.append((current, status, uso, risco))
            current = line.replace("### ", "").strip()
            status = uso = risco = "-"
        elif line.startswith("Status:"):
            status = line.replace("Status:", "").strip()
        elif line.startswith("Uso:"):
            uso = line.replace("Uso:", "").strip()
        elif line.startswith("Risco:"):
            risco = line.replace("Risco:", "").strip()

    if current:
        tools.append((current, status, uso, risco))

    for name, status, uso, risco in tools:
        print(f"- {name}")
        print(f"  Status: {status}")
        print(f"  Uso: {uso}")
        print(f"  Risco: {risco}")
        print("")

    print("Regra: registrado não significa conectado. Conectar só depois de teste em laboratório.")


def checkpoint():
    checkpoint_dir = ROOT / "10_TESTES" / "CHECKPOINTS"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file = checkpoint_dir / f"{ts}_checkpoint.md"

    def run(cmd):
        try:
            return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
        except Exception as e:
            return f"indisponivel: {e}"

    git_commit = run(["git", "rev-parse", "--short", "HEAD"])
    git_status = run(["git", "status", "--short"]) or "limpo"

    projects = sorted([p.name for p in (ROOT / "04_PROJETOS").glob("*") if p.is_dir()])
    new_tasks = sorted([p.name for p in (ROOT / "02_TAREFAS/00_NOVAS").glob("*.md")])
    logs = sorted([p.name for p in (ROOT / "09_LOGS").glob("*.md")])

    commands = [
        "./jarvis doctor",
        "./jarvis report",
        "./jarvis intake",
        "./jarvis scan-inbox",
        "./jarvis process-inbox",
        "./jarvis next",
        "./jarvis close-task",
        "./jarvis create-project",
        "./jarvis memory-from-task",
        "./jarvis self-test",
        "./jarvis tools",
        "./jarvis checkpoint",
    ]

    content = "# Checkpoint — JARVIS Theo Padilha AI Worker\n\n"
    content += f"## Data\n{datetime.now().isoformat(timespec='seconds')}\n\n"
    content += "## Criador / dono\nTheo Padilha\n\n"
    content += "## Status real\nLaboratório local em evolução. Não é produção.\n\n"
    content += f"## Git\nCommit atual: `{git_commit}`\n\n"
    content += f"Git status:\n```text\n{git_status}\n```\n\n"
    content += "## Comandos disponíveis\n" + "\n".join([f"- `{cmd}`" for cmd in commands]) + "\n\n"
    content += "## Projetos detectados\n" + "\n".join([f"- {p}" for p in projects]) + "\n\n"
    content += "## Tasks novas\n" + ("\n".join([f"- {t}" for t in new_tasks]) if new_tasks else "- nenhuma") + "\n\n"
    content += "## Logs recentes\n" + "\n".join([f"- {l}" for l in logs[-12:]]) + "\n\n"
    content += "## Produção\nNada alterado.\n\n"
    content += "## Credenciais\nNenhuma credencial deve estar salva neste laboratório.\n\n"
    content += "## Próximo passo seguro\nContinuar evolução local antes de conectar Claude, Gemini, n8n, VPS ou APIs.\n"

    file.write_text(content, encoding="utf-8")

    log = write_log(
        "checkpoint-created",
        f"""# Log — Checkpoint criado

## Checkpoint
{file.relative_to(ROOT)}

## Git commit
{git_commit}

## Status real
Checkpoint local criado.

## Produção
Nada alterado.
"""
    )

    print(f"Checkpoint criado: {file.relative_to(ROOT)}")
    print(f"Log criado: {log.relative_to(ROOT)}")


def summary():
    print("JARVIS — Theo Padilha AI Worker Summary")
    print("")

    def run(cmd):
        try:
            return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
        except Exception as e:
            return f"indisponivel: {e}"

    git_commit = run(["git", "rev-parse", "--short", "HEAD"])
    git_status = run(["git", "status", "--short"]) or "limpo"

    projects = sorted([p.name for p in (ROOT / "04_PROJETOS").glob("*") if p.is_dir()])
    new_tasks = sorted([p.name for p in (ROOT / "02_TAREFAS/00_NOVAS").glob("*.md")])
    logs = sorted([p.name for p in (ROOT / "09_LOGS").glob("*.md")])
    checkpoints = sorted([p.name for p in (ROOT / "10_TESTES/CHECKPOINTS").glob("*.md")]) if (ROOT / "10_TESTES/CHECKPOINTS").exists() else []

    commands = [
        "./jarvis doctor",
        "./jarvis report",
        "./jarvis intake",
        "./jarvis scan-inbox",
        "./jarvis process-inbox",
        "./jarvis next",
        "./jarvis close-task",
        "./jarvis create-project",
        "./jarvis memory-from-task",
        "./jarvis self-test",
        "./jarvis tools",
        "./jarvis checkpoint",
        "./jarvis summary",
    ]

    content = []
    content.append("# JARVIS — Theo Padilha AI Worker")
    content.append("")
    content.append("## Criador / dono")
    content.append("Theo Padilha")
    content.append("")
    content.append("## Status real")
    content.append("Laboratório local funcionando. Não é produção. Não executa ações perigosas sem aprovação humana.")
    content.append("")
    content.append("## Git")
    content.append(f"Commit atual: {git_commit}")
    content.append(f"Status: {git_status}")
    content.append("")
    content.append("## O que já existe")
    content.append("- CLI local `./jarvis`")
    content.append("- sistema de tasks")
    content.append("- processamento de inbox")
    content.append("- arquivamento de entradas processadas")
    content.append("- criação de projetos")
    content.append("- fechamento de tasks")
    content.append("- memória a partir de task")
    content.append("- self-test")
    content.append("- tool registry")
    content.append("- checkpoint")
    content.append("- Git versionado localmente")
    content.append("")
    content.append("## Projetos registrados")
    for p in projects:
        content.append(f"- {p}")
    content.append("")
    content.append("## Tasks novas")
    if new_tasks:
        for t in new_tasks:
            content.append(f"- {t}")
    else:
        content.append("- nenhuma")
    content.append("")
    content.append("## Último checkpoint")
    content.append(f"- {checkpoints[-1] if checkpoints else 'nenhum'}")
    content.append("")
    content.append("## Logs registrados")
    content.append(f"{len(logs)} log(s)")
    content.append("")
    content.append("## Comandos disponíveis")
    for cmd in commands:
        content.append(f"- `{cmd}`")
    content.append("")
    content.append("## Ferramentas mapeadas")
    content.append("ChatGPT, Claude manual/futuro, Gemini manual/futuro, Ollama, Groq, DeepSeek, Flow, n8n, Playwright e Ruflo estão registrados como ferramentas possíveis, mas nem todas estão conectadas.")
    content.append("")
    content.append("## Próximo passo seguro")
    content.append("Continuar evoluindo localmente antes de conectar Claude, Gemini, n8n, VPS, APIs ou qualquer produção.")
    content.append("")
    content.append("## Frase simples")
    content.append("JARVIS é um worker local criado por Theo Padilha para organizar projetos, tarefas, memória, logs, ferramentas e próximos passos com segurança.")

    summary_text = "\n".join(content)

    out = ROOT / "07_RELATORIOS/02_TECNICOS/ULTIMO_RESUMO_EXECUTIVO_JARVIS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(summary_text + "\n", encoding="utf-8")

    print(summary_text)
    print("")
    print(f"Resumo salvo em: {out.relative_to(ROOT)}")


def show_profiles():
    profiles = ROOT / "01_SISTEMA/02_DECISORES/EXECUTOR_PROFILES.md"
    print("JARVIS — Theo Padilha AI Worker Profiles")
    print("")

    if not profiles.exists():
        print("Executor Profiles não encontrado.")
        print("Esperado: 01_SISTEMA/02_DECISORES/EXECUTOR_PROFILES.md")
        return

    text = profiles.read_text(encoding="utf-8", errors="ignore")

    current = None
    fields = {}
    parsed = []

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("### "):
            if current:
                parsed.append((current, fields))
            current = line.replace("### ", "").strip()
            fields = {}
        elif ":" in line and current:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()

    if current:
        parsed.append((current, fields))

    for name, data in parsed:
        print(f"- {name}")
        for key in ["Dono", "Uso", "Ferramentas atuais", "Ferramentas futuras", "Permissão", "Bloqueios", "Status"]:
            if key in data:
                print(f"  {key}: {data[key]}")
        print("")

    print("Regra: perfil define permissão. Não libera produção, credenciais, VPS, deploy ou API paga sozinho.")


def route_request(text: str):
    if not text.strip():
        print('Uso: ./jarvis route "pedido"')
        return

    task_type = detect_type(text)
    risk = detect_risk(text)
    lower = text.lower()

    profile = "THEO_OWNER"
    tool = "CHATGPT_COCKPIT"
    reason = "Pedido geral: começar pelo cockpit, plano seguro e memória."

    blocked = [
        "produção",
        "VPS real",
        "deploy",
        "main/push/merge",
        "credenciais",
        "banco real",
        "envio real",
        "API paga relevante",
    ]

    if risk == "alto":
        profile = "PRODUCTION_LOCKED"
        tool = "CHATGPT_COCKPIT + checklist read-only"
        reason = "Pedido contém risco alto. Só diagnóstico/plano até aprovação humana."

    elif task_type == "VPS/infra":
        profile = "PRODUCTION_LOCKED"
        tool = "CHATGPT_COCKPIT + terminal read-only futuro"
        reason = "Infra/VPS exige modo seguro, backup e aprovação antes de qualquer comando real."

    elif task_type == "n8n/workflow":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT + N8N_FUTURO"
        reason = "Workflow n8n deve começar com análise, mock/dry-run, active=false e logs."

    elif task_type == "bug/código":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT agora; CLAUDE_CODE_FUTURO quando disponível"
        reason = "Código precisa de branch, git status, patch mínimo, build/teste e sem deploy."

    elif task_type == "Factory Roblox":
        profile = "THEO_OWNER"
        tool = "FLOW_SPEC + CHATGPT_COCKPIT; depois CLAUDE/GEMINI"
        reason = "Factory Roblox é projeto grande: começar com spec, estágios, judges e sandbox."

    elif task_type == "portfólio/site":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT + CLAUDE/GEMINI manual futuro"
        reason = "Site/portfólio pode ser editado em branch/local e publicado só com aprovação."

    elif any(x in lower for x in ["empresa", "vamoo", "chefe", "ruan", "cliente da empresa", "projeto da empresa"]):
        profile = "COMPANY_WORKSPACE"
        tool = "CHATGPT_COCKPIT + CLAUDE_MANUAL/CLAUDE_CODE_FUTURO se autorizado"
        reason = "Pedido menciona contexto de empresa; separar do modo pessoal e usar regras de autorização."

    elif "claude" in lower or "chefe" in lower:
        profile = "CHEFE_CLAUDE"
        tool = "CLAUDE_MANUAL / CLAUDE_CODE_FUTURO"
        reason = "Pedido menciona Claude/chefe; usar perfil separado, sem misturar projeto pessoal sensível."

    elif "free" in lower or "grátis" in lower or "gratis" in lower or "ollama" in lower or "groq" in lower:
        profile = "LAB_FREE"
        tool = "OLLAMA_LOCAL_FUTURO / GROQ_API_FUTURO / GEMINI_MANUAL"
        reason = "Pedido pede baixo custo/free-first; usar laboratório e evitar dados sensíveis."

    print("JARVIS — Theo Padilha AI Worker Route")
    print("")
    print(f"Pedido: {text}")
    print(f"Tipo detectado: {task_type}")
    print(f"Risco detectado: {risk}")
    print(f"Perfil sugerido: {profile}")
    print(f"Ferramenta sugerida: {tool}")
    print(f"Motivo: {reason}")
    print("")
    print("Bloqueios permanentes sem aprovação humana:")
    for item in blocked:
        print(f"- {item}")
    print("")
    print("Próximo passo seguro:")
    if risk == "alto":
        print("Criar task read-only e plano de diagnóstico. Não executar ação real.")
    else:
        print("Criar task com ./jarvis intake ou adicionar contexto em 00_COLE_AQUI.")


def create_plan(text: str):
    if not text.strip():
        print('Uso: ./jarvis plan "pedido"')
        return

    task_type = detect_type(text)
    risk = detect_risk(text)
    lower = text.lower()

    profile = "THEO_OWNER"
    tool = "CHATGPT_COCKPIT"
    mode = "laboratório local"
    first_action = "Criar task e reunir contexto."

    if risk == "alto":
        profile = "PRODUCTION_LOCKED"
        tool = "CHATGPT_COCKPIT + checklist read-only"
        mode = "diagnóstico read-only"
        first_action = "Criar plano de diagnóstico. Não executar ação real."

    elif task_type == "VPS/infra":
        profile = "PRODUCTION_LOCKED"
        tool = "CHATGPT_COCKPIT + checklist read-only"
        mode = "infra read-only"
        first_action = "Mapear ambiente, risco e backup antes de qualquer comando."

    elif task_type == "n8n/workflow":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT + N8N_FUTURO"
        mode = "mock/dry-run, active=false"
        first_action = "Analisar JSON/workflow sanitizado e criar plano de teste controlado."

    elif task_type == "bug/código":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT agora; CLAUDE_CODE_FUTURO depois"
        mode = "branch/sandbox"
        first_action = "Confirmar git status, branch e escopo antes de editar."

    elif task_type == "Factory Roblox":
        profile = "THEO_OWNER"
        tool = "FLOW_SPEC + CHATGPT_COCKPIT"
        mode = "spec/laboratório"
        first_action = "Criar spec por estágios, judges, critérios e sandbox."

    elif task_type == "portfólio/site":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT + CLAUDE/GEMINI manual futuro"
        mode = "branch/local"
        first_action = "Localizar projeto, criar branch e planejar alteração."

    elif "claude" in lower or "chefe" in lower:
        profile = "CHEFE_CLAUDE"
        tool = "CLAUDE_MANUAL / CLAUDE_CODE_FUTURO"
        mode = "perfil separado"
        first_action = "Separar contexto autorizado e não misturar projeto pessoal sensível."

    elif "free" in lower or "grátis" in lower or "gratis" in lower or "ollama" in lower or "groq" in lower:
        profile = "LAB_FREE"
        tool = "OLLAMA_LOCAL_FUTURO / GROQ_API_FUTURO / GEMINI_MANUAL"
        mode = "sandbox/free-first"
        first_action = "Usar dados não sensíveis e limitar custo."

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    plan_dir = ROOT / "05_EXECUCAO" / "00_PLANOS_SEGUROS"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / f"{ts}_{slugify(text)}.md"

    content = f"""# Plano Seguro — JARVIS Theo Padilha AI Worker

## Pedido
{text}

## Tipo detectado
{task_type}

## Risco detectado
{risk}

## Perfil sugerido
{profile}

## Ferramenta sugerida
{tool}

## Modo de execução
{mode}

## Status real
Plano criado localmente. Nada executado.

## Primeira ação segura
{first_action}

## Etapas recomendadas
1. Criar ou vincular task.
2. Reunir contexto em `00_COLE_AQUI` ou projeto correspondente.
3. Confirmar risco e ambiente.
4. Separar leitura, plano, execução e validação.
5. Executar apenas em laboratório/branch/sandbox quando permitido.
6. Rodar validação possível.
7. Salvar memória, logs e relatório.
8. Pedir aprovação humana antes de qualquer ação sensível.

## Bloqueios sem aprovação humana
- produção
- VPS real
- deploy
- main/push/merge
- credenciais
- banco real
- envio real para cliente/paciente/lead
- API paga relevante
- instalação de ferramenta nova
- autoalteração de arquitetura

## Próximo passo
{first_action}

## Criador / dono
Theo Padilha.
"""

    plan_file.write_text(content, encoding="utf-8")

    log = write_log(
        "safe-plan-created",
        f"""# Log — Plano seguro criado

## Plano
{plan_file.relative_to(ROOT)}

## Pedido
{text}

## Perfil
{profile}

## Ferramenta
{tool}

## Risco
{risk}

## Status real
Plano criado. Nada executado.

## Produção
Nada alterado.
"""
    )

    print(f"Plano criado: {plan_file.relative_to(ROOT)}")
    print(f"Log criado: {log.relative_to(ROOT)}")
    print("")
    print("Resumo:")
    print(f"- Tipo: {task_type}")
    print(f"- Risco: {risk}")
    print(f"- Perfil: {profile}")
    print(f"- Ferramenta: {tool}")
    print(f"- Próximo passo: {first_action}")


def route_metadata(text: str):
    task_type = detect_type(text)
    risk = detect_risk(text)
    lower = text.lower()

    profile = "THEO_OWNER"
    tool = "CHATGPT_COCKPIT"
    mode = "laboratório local"
    reason = "Pedido geral: começar pelo cockpit, plano seguro e memória."
    first_action = "Criar task e reunir contexto."

    if risk == "alto":
        profile = "PRODUCTION_LOCKED"
        tool = "CHATGPT_COCKPIT + checklist read-only"
        mode = "diagnóstico read-only"
        reason = "Pedido contém risco alto. Só diagnóstico/plano até aprovação humana."
        first_action = "Criar plano de diagnóstico. Não executar ação real."

    elif task_type == "VPS/infra":
        profile = "PRODUCTION_LOCKED"
        tool = "CHATGPT_COCKPIT + checklist read-only"
        mode = "infra read-only"
        reason = "Infra/VPS exige modo seguro, backup e aprovação antes de qualquer comando real."
        first_action = "Mapear ambiente, risco e backup antes de qualquer comando."

    elif task_type == "n8n/workflow":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT + N8N_FUTURO"
        mode = "mock/dry-run, active=false"
        reason = "Workflow n8n deve começar com análise, mock/dry-run, active=false e logs."
        first_action = "Analisar JSON/workflow sanitizado e criar plano de teste controlado."

    elif task_type == "bug/código":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT agora; CLAUDE_CODE_FUTURO depois"
        mode = "branch/sandbox"
        reason = "Código precisa de branch, git status, patch mínimo, build/teste e sem deploy."
        first_action = "Confirmar git status, branch e escopo antes de editar."

    elif task_type == "Factory Roblox":
        profile = "THEO_OWNER"
        tool = "FLOW_SPEC + CHATGPT_COCKPIT"
        mode = "spec/laboratório"
        reason = "Factory Roblox é projeto grande: começar com spec, estágios, judges e sandbox."
        first_action = "Criar spec por estágios, judges, critérios e sandbox."

    elif task_type == "portfólio/site":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT + CLAUDE/GEMINI manual futuro"
        mode = "branch/local"
        reason = "Site/portfólio pode ser editado em branch/local e publicado só com aprovação."
        first_action = "Localizar projeto, criar branch e planejar alteração."

    elif any(x in lower for x in ["empresa", "vamoo", "chefe", "ruan", "cliente da empresa", "projeto da empresa"]):
        profile = "COMPANY_WORKSPACE"
        tool = "CHATGPT_COCKPIT + CLAUDE_MANUAL/CLAUDE_CODE_FUTURO se autorizado"
        mode = "workspace empresa / branch / read-only primeiro"
        reason = "Pedido menciona contexto de empresa; separar do modo pessoal e usar regras de autorização."
        first_action = "Confirmar pasta, git status, branch, escopo e autorização antes de executar."

    elif "claude" in lower or "chefe" in lower:
        profile = "CHEFE_CLAUDE"
        tool = "CLAUDE_MANUAL / CLAUDE_CODE_FUTURO"
        mode = "perfil separado"
        reason = "Pedido menciona Claude/chefe; usar perfil separado, sem misturar projeto pessoal sensível."
        first_action = "Separar contexto autorizado e não misturar projeto pessoal sensível."

    elif "free" in lower or "grátis" in lower or "gratis" in lower or "ollama" in lower or "groq" in lower:
        profile = "LAB_FREE"
        tool = "OLLAMA_LOCAL_FUTURO / GROQ_API_FUTURO / GEMINI_MANUAL"
        mode = "sandbox/free-first"
        reason = "Pedido pede baixo custo/free-first; usar laboratório e evitar dados sensíveis."
        first_action = "Usar dados não sensíveis e limitar custo."

    return {
        "task_type": task_type,
        "risk": risk,
        "profile": profile,
        "tool": tool,
        "mode": mode,
        "reason": reason,
        "first_action": first_action,
    }


def launch_mission(text: str):
    if not text.strip():
        print('Uso: ./jarvis launch "pedido"')
        return

    meta = route_metadata(text)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    mission_id = "MISSION-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    slug = slugify(text)

    mission_dir = ROOT / "05_EXECUCAO" / "01_MISSOES"
    plan_dir = ROOT / "05_EXECUCAO" / "00_PLANOS_SEGUROS"
    task_dir = ROOT / "02_TAREFAS" / "00_NOVAS"
    mission_dir.mkdir(parents=True, exist_ok=True)
    plan_dir.mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)

    task_file = task_dir / f"{mission_id}_{slug}.md"
    plan_file = plan_dir / f"{ts}_{slug}.md"
    brief_file = mission_dir / f"{ts}_{slug}_mission-brief.md"

    blockers = [
        "produção",
        "VPS real",
        "deploy",
        "main/push/merge",
        "credenciais",
        "banco real",
        "envio real para cliente/paciente/lead",
        "API paga relevante",
        "instalação de ferramenta nova",
        "autoalteração de arquitetura",
    ]

    task_content = f"""# Mission Task — {mission_id}

## ID
{mission_id}

## Projeto
A definir

## Pedido original
{text}

## Objetivo final
Transformar o pedido em execução segura, rastreável e validável.

## Tipo detectado
{meta['task_type']}

## Status real
Criado localmente. Nada executado.

## Risco detectado
{meta['risk']}

## Perfil sugerido
{meta['profile']}

## Ferramenta sugerida
{meta['tool']}

## Modo de execução
{meta['mode']}

## Motivo do roteamento
{meta['reason']}

## Plano seguro inicial
1. Reunir contexto.
2. Confirmar ambiente.
3. Validar risco.
4. Separar leitura, plano, execução e validação.
5. Executar apenas em laboratório/branch/sandbox quando permitido.
6. Gerar evidência.
7. Atualizar memória e relatório.

## Aprovação humana necessária antes de
""" + "\n".join([f"- {b}" for b in blockers]) + f"""

## Resultado esperado
Missão preparada para próxima etapa segura.

## Resultado obtido
Task criada automaticamente por `./jarvis launch`.

## Próximo passo
{meta['first_action']}
"""

    plan_content = f"""# Plano Seguro — {mission_id}

## Pedido
{text}

## Tipo detectado
{meta['task_type']}

## Risco detectado
{meta['risk']}

## Perfil sugerido
{meta['profile']}

## Ferramenta sugerida
{meta['tool']}

## Modo
{meta['mode']}

## Status real
Plano criado localmente. Nada executado.

## Primeira ação segura
{meta['first_action']}

## Fases
### Fase 1 — Contexto
Reunir arquivos, prints, logs, descrição, projeto e objetivo.

### Fase 2 — Diagnóstico
Entender ambiente, risco, ferramenta e limite.

### Fase 3 — Execução segura
Executar somente em laboratório/local/branch/sandbox, se permitido.

### Fase 4 — Validação
Rodar self-test, build, diff, review ou checklist aplicável.

### Fase 5 — Memória
Criar aprendizado, decisão, log e relatório.

## Bloqueios sem aprovação
""" + "\n".join([f"- {b}" for b in blockers]) + """

## Produção
Nada alterado.

## Criador / dono
Theo Padilha.
"""

    brief_content = f"""# Mission Brief — {mission_id}

## Pedido
{text}

## Resumo executivo
JARVIS recebeu o pedido, classificou o tipo, estimou risco, escolheu perfil/ferramenta sugerida e criou task + plano seguro. Nenhuma ação perigosa foi executada.

## Tipo
{meta['task_type']}

## Risco
{meta['risk']}

## Perfil
{meta['profile']}

## Ferramenta
{meta['tool']}

## Modo
{meta['mode']}

## Motivo
{meta['reason']}

## Arquivos criados
- `{task_file.relative_to(ROOT)}`
- `{plan_file.relative_to(ROOT)}`
- `{brief_file.relative_to(ROOT)}`

## Próximo passo seguro
{meta['first_action']}

## Status real
Missão preparada localmente. Não é produção.
"""

    task_file.write_text(task_content, encoding="utf-8")
    plan_file.write_text(plan_content, encoding="utf-8")
    brief_file.write_text(brief_content, encoding="utf-8")

    log = write_log(
        "mission-launched",
        f"""# Log — Mission launched

## Mission
{mission_id}

## Pedido
{text}

## Task
{task_file.relative_to(ROOT)}

## Plano
{plan_file.relative_to(ROOT)}

## Brief
{brief_file.relative_to(ROOT)}

## Perfil
{meta['profile']}

## Ferramenta
{meta['tool']}

## Risco
{meta['risk']}

## Status real
Missão criada localmente. Nada executado.

## Produção
Nada alterado.
"""
    )

    print("JARVIS — Theo Padilha AI Worker Mission Launch")
    print("")
    print(f"Mission: {mission_id}")
    print(f"Tipo: {meta['task_type']}")
    print(f"Risco: {meta['risk']}")
    print(f"Perfil: {meta['profile']}")
    print(f"Ferramenta: {meta['tool']}")
    print(f"Task: {task_file.relative_to(ROOT)}")
    print(f"Plano: {plan_file.relative_to(ROOT)}")
    print(f"Brief: {brief_file.relative_to(ROOT)}")
    print(f"Log: {log.relative_to(ROOT)}")
    print("")
    print(f"Próximo passo seguro: {meta['first_action']}")


def show_missions():
    mission_dir = ROOT / "05_EXECUCAO" / "01_MISSOES"
    task_dir = ROOT / "02_TAREFAS" / "00_NOVAS"

    print("JARVIS — Theo Padilha AI Worker Missions")
    print("")

    if not mission_dir.exists():
        print("Nenhuma pasta de missões encontrada.")
        return

    briefs = sorted(mission_dir.glob("*.md"))
    if not briefs:
        print("Nenhuma missão encontrada.")
        return

    open_tasks = {p.name for p in task_dir.glob("*.md")} if task_dir.exists() else set()

    for brief in briefs[-20:]:
        text = brief.read_text(encoding="utf-8", errors="ignore")
        mission = extract_section(text, "## Pedido") or brief.stem
        tipo = extract_section(text, "## Tipo") or "-"
        risco = extract_section(text, "## Risco") or "-"
        perfil = extract_section(text, "## Perfil") or "-"
        ferramenta = extract_section(text, "## Ferramenta") or "-"
        proximo = extract_section(text, "## Próximo passo seguro") or "-"

        # detect related task names by same slug pieces
        status = "brief criado"
        for task_name in open_tasks:
            if any(part and part in task_name for part in brief.stem.split("_")[:2]):
                status = "task aberta"
                break

        print(f"- {brief.name}")
        print(f"  Pedido: {mission[:120]}")
        print(f"  Tipo: {tipo}")
        print(f"  Risco: {risco}")
        print(f"  Perfil: {perfil}")
        print(f"  Ferramenta: {ferramenta}")
        print(f"  Status: {status}")
        print(f"  Próximo: {proximo[:120]}")
        print("")

    print("Regra: missão criada não significa execução feita. É preparação segura.")


def quality_gate():
    print("JARVIS — Theo Padilha AI Worker Quality Gate")
    print("")

    def run(cmd):
        try:
            return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
        except subprocess.CalledProcessError as e:
            return "ERRO: " + e.output.strip()
        except Exception as e:
            return "ERRO: " + str(e)

    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        status = "OK" if ok else "FALHA"
        print(f"{status}  {name}" + (f" — {detail}" if detail else ""))

    py_compile = run(["python3", "11_SCRIPTS/python_syntax_gate.py"])
    check("Python compile", not py_compile.startswith("ERRO"), py_compile if py_compile else "sem erro")

    smoke_py = ROOT / "11_SCRIPTS" / "cli_smoke_test.py"
    if smoke_py.exists():
        smoke_compile = run(["python3", "-m", "py_compile", "11_SCRIPTS/cli_smoke_test.py"])
        check("Smoke script compile", not smoke_compile.startswith("ERRO"), smoke_compile if smoke_compile else "sem erro")
    else:
        check("Smoke script compile", False, "cli_smoke_test.py ausente")

    git_status = run(["git", "status", "--short"])
    check("Git status", git_status == "", "limpo" if git_status == "" else git_status.replace("\n", " | "))

    required_ok = all((ROOT / d).is_dir() for d in REQUIRED_DIRS)
    check("Estrutura principal", required_ok)

    identity_ok = (ROOT / "01_SISTEMA/00_REGRAS/IDENTIDADE_JARVIS_THEO_PADILHA.md").is_file()
    check("Identidade Theo Padilha", identity_ok)

    scripts_ok = (ROOT / "jarvis").is_file() and (ROOT / "11_SCRIPTS/jarvis_core.py").is_file()
    check("CLI presente", scripts_ok)

    new_tasks = list((ROOT / "02_TAREFAS/00_NOVAS").glob("*.md"))
    check("Tasks abertas", len(new_tasks) == 0, f"{len(new_tasks)} aberta(s)")

    missions = list((ROOT / "05_EXECUCAO/01_MISSOES").glob("*.md")) if (ROOT / "05_EXECUCAO/01_MISSOES").exists() else []
    check("Missões registradas", True, f"{len(missions)} brief(s)")

    logs = list((ROOT / "09_LOGS").glob("*.md"))
    check("Logs", len(logs) > 0, f"{len(logs)} log(s)")

    ok_all = all(checks)

    print("")
    print("Resultado:", "QUALITY GATE PASSOU" if ok_all else "QUALITY GATE COM PENDÊNCIAS")
    print("Status real: validação local. Produção não alterada.")

    if not ok_all:
        print("")
        print("Ação segura:")
        print("- Resolver pendências antes de conectar IA externa, n8n, VPS ou APIs.")

        # QUALITY_GATE_EXIT_NONZERO_V1
        import sys
        sys.exit(1)


def defer_task(query: str = ""):
    open_dir = ROOT / "02_TAREFAS/00_NOVAS"
    backlog_dir = ROOT / "02_TAREFAS/04_BACKLOG"
    backlog_dir.mkdir(parents=True, exist_ok=True)

    tasks = sorted(open_dir.glob("*.md"))
    if not tasks:
        print("Nenhuma task nova para mover ao backlog.")
        return

    selected = None
    if query:
        q = query.lower()
        for task in tasks:
            txt = task.read_text(encoding="utf-8", errors="ignore")
            if q in task.name.lower() or q in txt.lower():
                selected = task
                break
        if selected is None:
            print(f"Nenhuma task encontrada para: {query}")
            return
    else:
        selected = tasks[0]

    text = selected.read_text(encoding="utf-8", errors="ignore")
    text += f"""

## Backlog pelo JARVIS
Status real: movida para backlog local.
Movida em: {datetime.now().isoformat(timespec='seconds')}
Produção: nada alterado.
"""
    selected.write_text(text, encoding="utf-8")

    target = backlog_dir / selected.name
    if target.exists():
        target = target.with_name(target.stem + "-" + datetime.now().strftime("%H%M%S-%f") + target.suffix)

    selected.rename(target)

    log = write_log(
        "task-deferred",
        f"""# Log — Task movida para backlog

## Task
{target.name}

## Local
{target.relative_to(ROOT)}

## Status real
Movida para backlog local.

## Produção
Nada alterado.
"""
    )

    print(f"Task movida para backlog: {target.relative_to(ROOT)}")
    print(f"Log criado: {log.relative_to(ROOT)}")


def show_backlog():
    backlog_dir = ROOT / "02_TAREFAS/04_BACKLOG"
    print("JARVIS — Theo Padilha AI Worker Backlog")
    print("")

    if not backlog_dir.exists():
        print("Backlog ainda não existe.")
        return

    tasks = sorted(backlog_dir.glob("*.md"))
    if not tasks:
        print("Backlog vazio.")
        return

    for task in tasks[-30:]:
        txt = task.read_text(encoding="utf-8", errors="ignore")
        pedido = extract_section(txt, "## Pedido original") or task.stem
        risco = extract_section(txt, "## Risco detectado") or "-"
        tipo = extract_section(txt, "## Tipo detectado") or "-"
        print(f"- {task.name}")
        print(f"  Pedido: {pedido[:120]}")
        print(f"  Tipo: {tipo}")
        print(f"  Risco: {risco}")
        print("")


def security_audit():
    print("JARVIS — Theo Padilha AI Worker Security Audit")
    print("")

    audit_dir = ROOT / "10_TESTES" / "AUDITS"
    audit_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    audit_file = audit_dir / f"{ts}_security-audit.md"

    ignore_parts = {
        ".git", "__pycache__", ".cache", ".runtime", "99_ARQUIVO_MORTO"
    }

    scan_ext = {
        ".md", ".txt", ".py", ".json", ".yml", ".yaml", ".env", ".sh", ".toml"
    }

    risky_name_terms = [
        ".env", "secret", "token", "credential", "credentials",
        "senha", "password", "apikey", "api_key", "service_role",
        "private_key", "uazapi", "instance_token"
    ]

    risky_content_terms = [
        "api_key", "apikey", "secret_key", "service_role", "bearer ",
        "authorization:", "password=", "senha=", "token=", "instance token",
        "private_key", "BEGIN PRIVATE KEY", "sk-", "xoxb-", "ghp_"
    ]

    files_scanned = 0
    risky_names = []
    risky_contents = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        parts = set(rel.parts)

        if parts & ignore_parts:
            continue

        if path.suffix.lower() not in scan_ext and path.name != "jarvis":
            continue

        files_scanned += 1
        name_lower = path.name.lower()
        rel_str = str(rel)

        if any(term in name_lower for term in risky_name_terms):
            risky_names.append(rel_str)

        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue

        hits = []
        for term in risky_content_terms:
            if term.lower() in text:
                hits.append(term)

        if hits:
            risky_contents.append((rel_str, sorted(set(hits))))

    status = "PASSOU" if not risky_names and not risky_contents else "PENDÊNCIAS"

    lines = []
    lines.append("# Security Audit — JARVIS Theo Padilha AI Worker")
    lines.append("")
    lines.append(f"## Data\n{datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Status real\nAuditoria local. Nada foi alterado em produção.")
    lines.append("")
    lines.append(f"## Resultado\n{status}")
    lines.append("")
    lines.append(f"## Arquivos analisados\n{files_scanned}")
    lines.append("")
    lines.append("## Arquivos com nome sensível")
    if risky_names:
        for item in risky_names:
            lines.append(f"- {item}")
    else:
        lines.append("- nenhum")
    lines.append("")
    lines.append("## Arquivos com termos sensíveis no conteúdo")
    if risky_contents:
        for file, hits in risky_contents:
            lines.append(f"- {file}: {', '.join(hits)}")
    else:
        lines.append("- nenhum")
    lines.append("")
    lines.append("## Observação")
    lines.append("Este audit não imprime segredos. Ele só lista arquivos/termos suspeitos para revisão.")
    lines.append("")
    lines.append("## Próximo passo seguro")
    if status == "PASSOU":
        lines.append("Pode continuar evolução local.")
    else:
        lines.append("Revisar os arquivos apontados antes de conectar IA externa, n8n, VPS ou APIs.")

    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    log = write_log(
        "security-audit",
        f"""# Log — Security audit

## Audit
{audit_file.relative_to(ROOT)}

## Resultado
{status}

## Arquivos analisados
{files_scanned}

## Produção
Nada alterado.
"""
    )

    print(f"Resultado: SECURITY AUDIT {status}")
    print(f"Arquivos analisados: {files_scanned}")
    print(f"Audit salvo: {audit_file.relative_to(ROOT)}")
    print(f"Log criado: {log.relative_to(ROOT)}")

    if risky_names or risky_contents:
        print("")
        print("Pendências detectadas:")
        for item in risky_names[:20]:
            print(f"- nome sensível: {item}")
        for file, hits in risky_contents[:20]:
            print(f"- conteúdo sensível: {file} -> {', '.join(hits)}")
        print("")
        print("Ação segura: revisar antes de conectar qualquer executor externo.")


def prompt_pack(text: str):
    if not text.strip():
        print('Uso: ./jarvis prompt-pack "pedido"')
        return

    meta = route_metadata(text) if "route_metadata" in globals() else {
        "task_type": detect_type(text),
        "risk": detect_risk(text),
        "profile": "THEO_OWNER",
        "tool": "CHATGPT_COCKPIT",
        "mode": "laboratório local",
        "reason": "Fallback routing.",
        "first_action": "Criar task e reunir contexto.",
    }

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out_dir = ROOT / "06_PROMPTS" / "99_GENERATED" / f"{ts}_{slugify(text)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    shared_context = f"""# Contexto JARVIS

Sistema: JARVIS — Theo Padilha AI Worker
Creator / Owner: Theo Padilha
Status real: laboratório local. Não é produção.

Pedido:
{text}

Tipo detectado:
{meta['task_type']}

Risco detectado:
{meta['risk']}

Perfil sugerido:
{meta['profile']}

Ferramenta sugerida:
{meta['tool']}

Modo:
{meta['mode']}

Motivo:
{meta['reason']}

Primeira ação segura:
{meta['first_action']}

Bloqueios:
- não pedir ou expor credenciais
- não usar produção
- não fazer deploy
- não mexer em main/push/merge
- não usar banco real
- não enviar mensagem real
- não usar API paga sem aprovação
"""

    chatgpt_prompt = shared_context + """

# Tarefa para ChatGPT Cockpit

Atue como cockpit técnico.
Entregue:
1. diagnóstico
2. plano seguro
3. próximos passos
4. riscos/não validado
5. prompt curto para executor, se útil

Não invente validação.
Não diga que algo foi testado se não há evidência.
"""

    claude_prompt = shared_context + """

# Tarefa para Claude / Claude Code

Modo inicial: read-only.
Antes de editar:
- confirmar pasta/projeto
- rodar git status
- identificar branch
- localizar arquivos relevantes
- propor patch mínimo

Se for autorizado editar:
- não mexer na main
- não refatorar fora do escopo
- não commitar/push/deployar
- rodar build/teste possível
- resumir arquivos alterados

Saída obrigatória:
- arquivos lidos
- diagnóstico
- plano
- alterações sugeridas ou feitas
- testes rodados
- riscos restantes
"""

    gemini_prompt = shared_context + """

# Tarefa para Gemini

Use como segundo cérebro de baixo custo/manual.
Entregue:
- análise alternativa
- riscos que podem ter passado batido
- opções free/baixo custo
- plano simplificado
- pontos para validar antes de executar

Não assumir acesso a arquivos locais.
Não usar dados sensíveis.
"""

    output_instructions = f"""# Output Intake Instructions

Depois de usar qualquer executor manual:

1. Salvar a resposta em:
`00_COLE_AQUI/03_OUTPUTS_CLAUDE_CHATGPT/`

2. Rodar:
`./jarvis process-inbox`

3. Depois:
`./jarvis next`

4. Se virar aprendizado:
`./jarvis memory-from-task "trecho"`

5. Validar:
`./jarvis quality-gate`

Status real:
Prompt pack criado. Executor externo ainda não conectado.
"""

    files = {
        "00_CONTEXT.md": shared_context,
        "01_CHATGPT_COCKPIT_PROMPT.md": chatgpt_prompt,
        "02_CLAUDE_MANUAL_PROMPT.md": claude_prompt,
        "03_GEMINI_MANUAL_PROMPT.md": gemini_prompt,
        "04_OUTPUT_INTAKE_INSTRUCTIONS.md": output_instructions,
    }

    for name, content in files.items():
        (out_dir / name).write_text(content.strip() + "\n", encoding="utf-8")

    log = write_log(
        "prompt-pack-created",
        f"""# Log — Prompt pack criado

## Pedido
{text}

## Pasta
{out_dir.relative_to(ROOT)}

## Perfil
{meta['profile']}

## Ferramenta sugerida
{meta['tool']}

## Risco
{meta['risk']}

## Status real
Prompt pack criado localmente. Nenhum executor externo conectado.

## Produção
Nada alterado.
"""
    )

    print("JARVIS — Theo Padilha AI Worker Prompt Pack")
    print(f"Pasta: {out_dir.relative_to(ROOT)}")
    print(f"Log: {log.relative_to(ROOT)}")
    print(f"Perfil: {meta['profile']}")
    print(f"Ferramenta: {meta['tool']}")
    print(f"Risco: {meta['risk']}")
    print("Status real: prompts criados, nada conectado.")


def review_outputs():
    inbox = ROOT / "00_COLE_AQUI/03_OUTPUTS_CLAUDE_CHATGPT"
    reviewed = ROOT / "05_EXECUCAO/03_EXECUTOR_OUTPUTS_REVIEWED"
    archive = ROOT / "99_ARQUIVO_MORTO/EXECUTOR_OUTPUTS_PROCESSADOS" / datetime.now().strftime("%Y-%m-%d")
    reviewed.mkdir(parents=True, exist_ok=True)
    archive.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in inbox.glob("*.md") if p.is_file()])
    if not files:
        print("Nenhum output .md encontrado em 00_COLE_AQUI/03_OUTPUTS_CLAUDE_CHATGPT")
        return

    count = 0
    for src in files:
        raw = src.read_text(encoding="utf-8", errors="ignore").strip()
        if not raw:
            continue

        risk = detect_risk(raw)
        task_type = detect_type(raw)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        slug = slugify(src.stem)
        review_file = reviewed / f"{ts}_{slug}_review.md"

        review = f"""# Executor Output Review — JARVIS

## Fonte
`{src.relative_to(ROOT)}`

## Status real
Output externo processado localmente. Nada executado.

## Tipo detectado
{task_type}

## Risco detectado
{risk}

## Resumo bruto
{raw[:1800]}

## Decisão JARVIS
Este output deve ser tratado como sugestão de executor externo, não como verdade validada.

## Próximo passo seguro
- Se for código: revisar diff, branch, build/teste antes de aplicar.
- Se for n8n: importar inactive/dry-run antes de qualquer ativação.
- Se for VPS/produção: read-only e aprovação humana.
- Se for documentação: transformar em memória ou relatório.

## Produção
Nada alterado.

## Criador / dono
Theo Padilha.
"""
        review_file.write_text(review, encoding="utf-8")

        create_task(
            f"Revisar output externo processado: {review_file.relative_to(ROOT)}",
            source=str(src.relative_to(ROOT))
        )

        target = archive / src.name
        if target.exists():
            target = target.with_name(target.stem + "-" + datetime.now().strftime("%H%M%S-%f") + target.suffix)
        src.rename(target)
        count += 1

    log = write_log(
        "executor-outputs-reviewed",
        f"""# Log — Executor outputs reviewed

## Quantidade
{count}

## Status real
Outputs externos revisados localmente.

## Produção
Nada alterado.
"""
    )

    print(f"Outputs revisados: {count}")
    print(f"Log criado: {log.relative_to(ROOT)}")

# Override v2 — company routing priority
def is_company_context(text: str) -> bool:
    lower = text.lower()
    return any(x in lower for x in [
        "empresa",
        "vamoo",
        "chefe",
        "ruan",
        "cliente da empresa",
        "projeto da empresa",
        "vs code com claude",
        "claude do chefe"
    ])


def route_metadata(text: str):
    task_type = detect_type(text)
    risk = detect_risk(text)
    lower = text.lower()

    profile = "THEO_OWNER"
    tool = "CHATGPT_COCKPIT"
    mode = "laboratório local"
    reason = "Pedido geral: começar pelo cockpit, plano seguro e memória."
    first_action = "Criar task e reunir contexto."

    if is_company_context(text) and risk != "alto":
        profile = "COMPANY_WORKSPACE"
        tool = "CHATGPT_COCKPIT + CLAUDE_MANUAL/CLAUDE_CODE_FUTURO se autorizado"
        mode = "workspace empresa / branch / read-only primeiro"
        reason = "Pedido menciona contexto de empresa; usar workspace separado, VS Code/Git seguro e Claude apenas como executor autorizado."
        first_action = "Confirmar pasta, git status, branch, escopo e autorização antes de executar."

    elif risk == "alto":
        profile = "PRODUCTION_LOCKED"
        tool = "CHATGPT_COCKPIT + checklist read-only"
        mode = "diagnóstico read-only"
        reason = "Pedido contém risco alto. Só diagnóstico/plano até aprovação humana."
        first_action = "Criar plano de diagnóstico. Não executar ação real."

    elif task_type == "VPS/infra":
        profile = "PRODUCTION_LOCKED"
        tool = "CHATGPT_COCKPIT + checklist read-only"
        mode = "infra read-only"
        reason = "Infra/VPS exige modo seguro, backup e aprovação antes de qualquer comando real."
        first_action = "Mapear ambiente, risco e backup antes de qualquer comando."

    elif task_type == "n8n/workflow":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT + N8N_FUTURO"
        mode = "mock/dry-run, active=false"
        reason = "Workflow n8n deve começar com análise, mock/dry-run, active=false e logs."
        first_action = "Analisar JSON/workflow sanitizado e criar plano de teste controlado."

    elif task_type == "bug/código":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT agora; CLAUDE_CODE_FUTURO depois"
        mode = "branch/sandbox"
        reason = "Código precisa de branch, git status, patch mínimo, build/teste e sem deploy."
        first_action = "Confirmar git status, branch e escopo antes de editar."

    elif task_type == "Factory Roblox":
        profile = "THEO_OWNER"
        tool = "FLOW_SPEC + CHATGPT_COCKPIT"
        mode = "spec/laboratório"
        reason = "Factory Roblox é projeto grande: começar com spec, estágios, judges e sandbox."
        first_action = "Criar spec por estágios, judges, critérios e sandbox."

    elif task_type == "portfólio/site":
        profile = "THEO_OWNER"
        tool = "CHATGPT_COCKPIT + CLAUDE/GEMINI manual futuro"
        mode = "branch/local"
        reason = "Site/portfólio pode ser editado em branch/local e publicado só com aprovação."
        first_action = "Localizar projeto, criar branch e planejar alteração."

    elif "claude" in lower:
        profile = "CHEFE_CLAUDE"
        tool = "CLAUDE_MANUAL / CLAUDE_CODE_FUTURO"
        mode = "perfil separado"
        reason = "Pedido menciona Claude; usar perfil separado e sem misturar projeto pessoal sensível."
        first_action = "Separar contexto autorizado e não misturar projeto pessoal sensível."

    elif "free" in lower or "grátis" in lower or "gratis" in lower or "ollama" in lower or "groq" in lower:
        profile = "LAB_FREE"
        tool = "OLLAMA_LOCAL_FUTURO / GROQ_API_FUTURO / GEMINI_MANUAL"
        mode = "sandbox/free-first"
        reason = "Pedido pede baixo custo/free-first; usar laboratório e evitar dados sensíveis."
        first_action = "Usar dados não sensíveis e limitar custo."

    return {
        "task_type": task_type,
        "risk": risk,
        "profile": profile,
        "tool": tool,
        "mode": mode,
        "reason": reason,
        "first_action": first_action,
    }


def route_request(text: str):
    if not text.strip():
        print('Uso: ./jarvis route "pedido"')
        return

    meta = route_metadata(text)

    print("JARVIS — Theo Padilha AI Worker Route")
    print("")
    print(f"Pedido: {text}")
    print(f"Tipo detectado: {meta['task_type']}")
    print(f"Risco detectado: {meta['risk']}")
    print(f"Perfil sugerido: {meta['profile']}")
    print(f"Ferramenta sugerida: {meta['tool']}")
    print(f"Motivo: {meta['reason']}")
    print("")
    print("Bloqueios permanentes sem aprovação humana:")
    for item in [
        "produção",
        "VPS real",
        "deploy",
        "main/push/merge",
        "credenciais",
        "banco real",
        "envio real",
        "API paga relevante",
    ]:
        print(f"- {item}")
    print("")
    print("Próximo passo seguro:")
    print(meta["first_action"])

# Override v3 — plan uses route_metadata
def create_plan(text: str):
    if not text.strip():
        print('Uso: ./jarvis plan "pedido"')
        return

    meta = route_metadata(text)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    plan_dir = ROOT / "05_EXECUCAO" / "00_PLANOS_SEGUROS"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / f"{ts}_{slugify(text)}.md"

    blockers = [
        "produção",
        "VPS real",
        "deploy",
        "main/push/merge",
        "credenciais",
        "banco real",
        "envio real para cliente/paciente/lead",
        "API paga relevante",
        "instalação de ferramenta nova",
        "autoalteração de arquitetura",
    ]

    content = f"""# Plano Seguro — JARVIS Theo Padilha AI Worker

## Pedido
{text}

## Tipo detectado
{meta['task_type']}

## Risco detectado
{meta['risk']}

## Perfil sugerido
{meta['profile']}

## Ferramenta sugerida
{meta['tool']}

## Modo de execução
{meta['mode']}

## Motivo do roteamento
{meta['reason']}

## Status real
Plano criado localmente. Nada executado.

## Primeira ação segura
{meta['first_action']}

## Etapas recomendadas
1. Confirmar projeto, pasta e contexto.
2. Rodar `git status` quando houver repo.
3. Confirmar branch e escopo.
4. Separar leitura, plano, execução e validação.
5. Executar só em laboratório/branch/sandbox quando permitido.
6. Rodar validação possível.
7. Salvar logs, memória e relatório.
8. Pedir aprovação humana antes de qualquer ação sensível.

## Bloqueios sem aprovação humana
""" + "\n".join([f"- {b}" for b in blockers]) + """

## Produção
Nada alterado.

## Criador / dono
Theo Padilha.
"""

    plan_file.write_text(content, encoding="utf-8")

    log = write_log(
        "safe-plan-created",
        f"""# Log — Plano seguro criado

## Plano
{plan_file.relative_to(ROOT)}

## Pedido
{text}

## Perfil
{meta['profile']}

## Ferramenta
{meta['tool']}

## Risco
{meta['risk']}

## Status real
Plano criado. Nada executado.

## Produção
Nada alterado.
"""
    )

    print(f"Plano criado: {plan_file.relative_to(ROOT)}")
    print(f"Log criado: {log.relative_to(ROOT)}")
    print("")
    print("Resumo:")
    print(f"- Tipo: {meta['task_type']}")
    print(f"- Risco: {meta['risk']}")
    print(f"- Perfil: {meta['profile']}")
    print(f"- Ferramenta: {meta['tool']}")
    print(f"- Próximo passo: {meta['first_action']}")

def execution_modes_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/execution_modes.py"], cwd=ROOT, check=False)

def review_output_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/review_output_latest.py"], cwd=ROOT, check=False)

def review_output_index_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/review_output_index.py"], cwd=ROOT, check=False)

def cockpit_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/cockpit.py"], cwd=ROOT, check=False)

def visual_cockpit_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/visual_cockpit.py"], cwd=ROOT, check=False)

def claude_mission_command(args=None):
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/claude_mission.py", *args], cwd=ROOT, check=False)

def claude_mission_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/claude_mission_latest.py"], cwd=ROOT, check=False)

def operator_workbench_command(args=None):
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/operator_workbench.py", *args], cwd=ROOT, check=False)

def project_doctor_command(args=None):
    """./jarvis doctor --project <alias> — read-only project health."""
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/project_doctor.py", *args], cwd=ROOT, check=False)

def project_mission_pack_command(mode: str, args=None):
    """qa-sprint | goal-sprint | browser-qa | final-gate — gera mission pack para Claude."""
    import subprocess
    args = args or []
    subprocess.run(
        ["python3", "11_SCRIPTS/project_mission_pack.py", "--mode", mode, *args],
        cwd=ROOT,
        check=False,
    )

def project_status_command(args=None, full: bool = False):
    """./jarvis project-status --project ALIAS  (compacto)
       ./jarvis project-cockpit --project ALIAS (cockpit; status + última missão + next)"""
    import subprocess
    args = list(args or [])
    if full and "--full" not in args:
        args.append("--full")
    subprocess.run(["python3", "11_SCRIPTS/project_status.py", *args], cwd=ROOT, check=False)

def mission_open_latest_command(args=None):
    """./jarvis mission-open-latest [--project ALIAS] [--print]
       Imprime o path absoluto do prompt da última missão em uma linha.
       Útil: cat "$(./jarvis mission-open-latest)" | pbcopy"""
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/mission_open_latest.py", *args], cwd=ROOT, check=False)

def project_memory_command(args=None):
    """./jarvis project-memory --project ALIAS — read-only memory display."""
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/project_memory.py", *args], cwd=ROOT, check=False)

def project_memory_update_command(args=None):
    """./jarvis project-memory-update --project ALIAS --from-git|--from-file PATH [--dry-run|--apply]

    Propaga exit code para que a recusa de relatório fraco (--apply sem
    --force-weak-report) realmente falhe `./jarvis`."""
    import subprocess
    args = list(args or [])
    result = subprocess.run(["python3", "11_SCRIPTS/project_memory_update.py", *args], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)

def self_cockpit_command(args=None, mode_default="cockpit"):
    """./jarvis self-status | self-cockpit | self-next — reads about JARVIS itself."""
    import subprocess
    args = list(args or [])
    if "--mode" not in args and not any(a.startswith("--mode=") for a in args):
        args = ["--mode", mode_default, *args]
    subprocess.run(["python3", "11_SCRIPTS/self_cockpit.py", *args], cwd=ROOT, check=False)

def self_evolve_command(args=None):
    """./jarvis self-evolve --goal "..." [--copy] — generates JARVIS self-evolution mission pack."""
    import subprocess
    args = list(args or [])
    # Force project=jarvis-core (project_mission_pack also enforces, but be explicit here for clarity).
    subprocess.run(
        ["python3", "11_SCRIPTS/project_mission_pack.py",
         "--mode", "self-evolve", "--project", "jarvis-core", *args],
        cwd=ROOT, check=False,
    )

def self_debrief_command(args=None):
    """./jarvis self-debrief --from-git|--from-file PATH [--dry-run|--apply]
       Thin wrapper around project-memory-update locked to alias jarvis-core.
       Propaga exit code (recusa de relatório fraco → falha do ./jarvis)."""
    import subprocess
    args = list(args or [])
    if "--project" not in args and not any(a.startswith("--project=") for a in args):
        args = ["--project", "jarvis-core", *args]
    result = subprocess.run(["python3", "11_SCRIPTS/project_memory_update.py", *args], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)

def claude_helper_command(sub, args=None):
    """Dispatcher for claude-copy-latest / claude-launch / claude-save-report-template."""
    import subprocess
    args = list(args or [])
    subprocess.run(["python3", "11_SCRIPTS/claude_helpers.py", sub, *args], cwd=ROOT, check=False)

def doctrine_check_command():
    """./jarvis doctrine-check — verifies AGENTS/CATALOG/help/registry/mission templates sync."""
    _run_py_propagate("11_SCRIPTS/doctrine_check.py", [])

def _run_py_propagate(script, args):
    """Run a Python script and propagate its returncode through sys.exit.

    Used only by NEW Agent OS wrappers (ask, go, capture, inbox, agenda,
    blueprint, project-open, plan, limits, ask-log) and by guarded debrief
    paths (self-debrief, project-memory-update) so a non-zero refusal in
    Python actually fails `./jarvis`. Legacy commands keep their
    subprocess.run(check=False) pattern to avoid regression risk."""
    import subprocess
    args = list(args or [])
    result = subprocess.run(["python3", script, *args], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)

def ask_command(args=None):
    """./jarvis ask "pedido em linguagem natural" — router local (regex; sem LLM)."""
    _run_py_propagate("11_SCRIPTS/ask_router.py", args)

def go_command(args=None):
    """./jarvis go "pedido" — power-wrapper sobre ask: classify + delegate +
    run package + Claude launch banner + project-aware debrief block + gates.

    Adicionalmente:
      - Cria run package em 05_EXECUCAO/35_RUNS/<ts>_<slug>/ (gitignored)
        a não ser que --dry-run, JARVIS_NO_REPORT=1 ou --no-run-log.
      - Imprime project-intel sugerido se um alias foi detectado.
      - Emite o bloco de debrief CORRETO (self-debrief vs project-memory-update).
      - Imprime o que JARVIS fez/não fez. Nunca executa Claude. Nunca toca produção."""
    import os
    import subprocess
    args = list(args or [])
    has_copy = "--copy" in args
    has_nocopy = "--no-copy" in args
    if not has_copy and not has_nocopy:
        args = ["--copy", *args]
    is_dry = "--dry-run" in args
    no_run = "--no-run-log" in args
    if no_run:
        args = [a for a in args if a != "--no-run-log"]
    suppress_run = is_dry or no_run or os.environ.get("JARVIS_NO_REPORT") == "1"

    # Extract the free-text request and optional project (mirrors ask_router parsing).
    text_parts = []
    alias_override = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--project" and i + 1 < len(args):
            alias_override = args[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--project="):
            alias_override = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a in ("--dry-run", "--copy", "--no-copy", "--explain", "--force", "--log", "--no-log"):
            i += 1
            continue
        text_parts.append(a)
        i += 1
    request_text = " ".join(text_parts).strip()

    print("JARVIS — Go (power-wrapper de ask)")
    print("Status real: roteia pedido → ask_router → delegate; sem executar Claude.")
    print("")
    rc = subprocess.call(["python3", "11_SCRIPTS/ask_router.py", *args], cwd=ROOT)

    # Best-effort detection of intent/project/safety/next-command for the run
    # log: reuse ask_router functions directly (no second subprocess).
    intent = "?"
    project = ""
    safety = "?"
    next_cmd = "?"
    try:
        sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
        from ask_router import (
            detect_intent as _di,
            detect_project_alias as _dp,
            _next_command_for as _ncf,
        )
        intent = _di(request_text) if request_text else "?"
        project = _dp(request_text, alias_override) or ""
        _cl, next_cmd, safety, _safe = _ncf(intent, project, request_text, None) if request_text else ([], "?", "?", True)
    except Exception:
        pass

    run_path = ""
    if request_text and not suppress_run:
        try:
            out = subprocess.check_output(
                ["python3", "11_SCRIPTS/run_log.py", "create",
                 "--request", request_text,
                 "--project", project or "",
                 "--intent", intent or "",
                 "--safety", safety or "",
                 "--next-command", next_cmd or "",
                 "--print-path"],
                cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=10,
            ).strip()
            run_path = out.splitlines()[-1] if out else ""
        except Exception as e:
            print(f"AVISO: não consegui criar run package: {e}")

    print("")
    print("── Run package ─────────────────────────────────────────────")
    if suppress_run:
        print("(suprimido: --dry-run / --no-run-log / JARVIS_NO_REPORT=1)")
    elif run_path:
        print(f"Run log: {run_path}")
        print(f"Ver:     ./jarvis run-show latest")
    else:
        print("(não criado — pedido vazio ou erro acima)")

    # Project-intel hint for project-scoped intents
    if project and project != "jarvis-core":
        print("")
        print("── Project intel sugerido ──────────────────────────────────")
        print(f"  ./jarvis project-intel --project {project}")
        print(f"  ./jarvis project-open  --project {project} --print-only")

    # Debrief block — pick the right command depending on the project
    if project == "jarvis-core" or not project:
        debrief = (
            "./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --dry-run\n"
            "./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --apply"
        )
    else:
        debrief = (
            f"./jarvis project-memory-update --project {project} --from-file /tmp/claude-out.md --dry-run\n"
            f"./jarvis project-memory-update --project {project} --from-file /tmp/claude-out.md --apply"
        )

    print("")
    print("── Próximo passo manual (Theo executa) ─────────────────────")
    print(f"cd {ROOT}")
    print("claude                          # abrir Claude Code manualmente")
    print("# (cole a missão se foi gerada)")
    print("cat > /tmp/jarvis-claude-out.md  # salvar RELATÓRIO FINAL aqui")
    print("# (cole o relatório final; Ctrl+D para fechar)")
    for line in debrief.splitlines():
        print(line)
    print("./jarvis self-cockpit")
    print("")
    print("── Gates de saúde ──────────────────────────────────────────")
    print("env JARVIS_NO_REPORT=1 ./jarvis safety-gate")
    print("env JARVIS_NO_REPORT=1 ./jarvis smoke-test")
    print("./jarvis doctrine-check")

    print("")
    print("── O que JARVIS fez ────────────────────────────────────────")
    print("- interpretou o pedido localmente (regex + registry)")
    print("- delegou para o sub-comando seguro acima")
    if not suppress_run and run_path:
        print(f"- gravou run package em {run_path}")
    print("")
    print("── O que JARVIS NÃO fez ────────────────────────────────────")
    print("- não executou Claude")
    print("- não tocou produção / VPS / n8n real")
    print("- não fez push / PR / merge / deploy")
    print("- não leu .env nem imprimiu segredos")
    print("- não editou arquivos de projeto-alvo")
    print("")
    print("Produção: nada alterado por JARVIS.")
    if rc != 0:
        sys.exit(rc)

def capture_command(args=None):
    """./jarvis capture "texto" — inbox local append-only."""
    _run_py_propagate("11_SCRIPTS/local_capture.py", ["capture", *(args or [])])

def inbox_command(args=None):
    """./jarvis inbox — exibe inbox local."""
    _run_py_propagate("11_SCRIPTS/local_capture.py", ["inbox", *(args or [])])

def agenda_add_command(args=None):
    """./jarvis agenda-add "texto" [--date YYYY-MM-DD] — agenda local."""
    _run_py_propagate("11_SCRIPTS/local_capture.py", ["agenda-add", *(args or [])])

def agenda_command(args=None):
    """./jarvis agenda — exibe agenda local."""
    _run_py_propagate("11_SCRIPTS/local_capture.py", ["agenda", *(args or [])])

def blueprint_command(args=None):
    """./jarvis blueprint --type <n8n|app|automation|research> --goal "..." [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/blueprint.py", args)


def research_digest_command(args=None):
    """./jarvis research-digest [--goal "..."] [--dry-run] — digest local dos deep research."""
    _run_py_propagate("11_SCRIPTS/research_digest.py", args)

def research_digest_latest_command(args=None):
    """./jarvis research-digest-latest [--file plan|backlog|n8n|digest|status|index]""" 
    _run_py_propagate("11_SCRIPTS/research_digest_latest.py", args)

def research_digest_validate_command(args=None):
    """./jarvis research-digest-validate [--path PATH] — valida último digest."""
    _run_py_propagate("11_SCRIPTS/research_digest_validate.py", args)

def api_command(args=None):
    """./jarvis api [--host 127.0.0.1] [--port 8787] — API local segura do JARVIS."""
    _run_py_propagate("11_SCRIPTS/jarvis_api.py", args)

def project_open_command(args=None):
    """./jarvis project-open --project ALIAS [--print-only|--copy-cd|--code]"""
    _run_py_propagate("11_SCRIPTS/project_open.py", args)

def plan_request_command(args=None):
    """./jarvis plan "pedido" [--save] — gera plano de execução local."""
    _run_py_propagate("11_SCRIPTS/plan_request.py", args)

def limits_command(args=None):
    """./jarvis limits — explica fronteira do robô (o que pode/não pode/precisa Claude)."""
    _run_py_propagate("11_SCRIPTS/limits.py", args)

def ask_log_command(args=None):
    """./jarvis ask-log — exibe pedidos cujo intent ficou unclear (para pattern tuning)."""
    _run_py_propagate("11_SCRIPTS/ask_router.py", ["--log", *(args or [])])

def task_add_command(args=None):
    """./jarvis task-add "texto" [--dry-run] [--source X] [--project A] [--intent I]"""
    _run_py_propagate("11_SCRIPTS/task_queue.py", ["add", *(args or [])])

def task_list_command(args=None):
    """./jarvis task-list — lista tarefas locais (pending/blocked/done)."""
    _run_py_propagate("11_SCRIPTS/task_queue.py", ["list", *(args or [])])

def task_next_command(args=None):
    """./jarvis task-next — top pending + comando seguro sugerido."""
    _run_py_propagate("11_SCRIPTS/task_queue.py", ["next", *(args or [])])

def task_show_command(args=None):
    """./jarvis task-show ID — events da task."""
    _run_py_propagate("11_SCRIPTS/task_queue.py", ["show", *(args or [])])

def task_done_command(args=None):
    """./jarvis task-done ID [--note '...'] — marca task como done (append-only)."""
    _run_py_propagate("11_SCRIPTS/task_queue.py", ["done", *(args or [])])

def task_block_command(args=None):
    """./jarvis task-block ID --reason '...' — marca task como blocked."""
    _run_py_propagate("11_SCRIPTS/task_queue.py", ["block", *(args or [])])

def decision_add_command(args=None):
    """./jarvis decision-add "escolha" [--project A] [--context X] [--reason Y]"""
    _run_py_propagate("11_SCRIPTS/decision_log.py", ["add", *(args or [])])

def decision_list_command(args=None):
    """./jarvis decision-list [--project A] [--limit N]"""
    _run_py_propagate("11_SCRIPTS/decision_log.py", ["list", *(args or [])])

def decision_show_command(args=None):
    """./jarvis decision-show latest|ID"""
    _run_py_propagate("11_SCRIPTS/decision_log.py", ["show", *(args or [])])

def assistant_doctor_command(args=None):
    """./jarvis assistant-doctor — verifica utilidades pessoais locais."""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["doctor", *(args or [])])

def web_command(args=None):
    """./jarvis web [--host IP] [--port N] [--no-open|--check]"""
    try:
        _run_py_propagate("api/index.py", list(args or []))
    except KeyboardInterrupt:
        print("JARVIS web encerrado.")

def screen_capture_command(args=None):
    """./jarvis screen-capture [--interactive] [--output P] [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["screen-capture", *(args or [])])

def screen_record_command(args=None):
    """./jarvis screen-record [--dry-run] — abre o gravador nativo do macOS."""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["screen-record", *(args or [])])

def github_overview_command(args=None):
    """./jarvis github-overview [--limit N] [--dry-run] — resumo GitHub read-only."""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["github-overview", *(args or [])])

def image_to_pdf_command(args=None):
    """./jarvis image-to-pdf IMAGEM --dry-run — planejamento; PDF bloqueado."""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["image-to-pdf", *(args or [])])

def image_convert_command(args=None):
    """./jarvis image-convert IMAGEM --to png|jpg|tiff [--output P] [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["image-convert", *(args or [])])

def speak_command(args=None):
    """./jarvis speak texto [--voice VOZ] [--output audio.aiff] [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["speak", *(args or [])])

def message_draft_command(args=None):
    """./jarvis message-draft --phone NUMERO texto [--open|--copy|--dry-run]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["message-draft", *(args or [])])

def message_send_command(args=None):
    """./jarvis message-send --phone NUMERO texto [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["message-send", *(args or [])])

def memory_save_command(args=None):
    """./jarvis memory-save texto [--kind learning|decision|preference] [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["memory-save", *(args or [])])

def storage_scan_command(args=None):
    """./jarvis storage-scan [PASTA] [--top N] [--min-mb N]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["storage-scan", *(args or [])])

def system_memory_command(args=None):
    """./jarvis system-memory [--cleanup-jarvis] [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["system-memory", *(args or [])])

def computer_command(args=None):
    """./jarvis computer list|inspect|open|close [APP] [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["computer", *(args or [])])

def computer_worker_command(args=None):
    """./jarvis computer-worker [--once|--watch|--install|--status|--uninstall] [--dry-run]"""
    _run_py_propagate("11_SCRIPTS/device_worker.py", args or [])

def self_edit_command(args=None):
    """./jarvis self-edit "melhoria" [--dry-run] [--publish] — Codex isolado, publicação explícita."""
    _run_py_propagate("11_SCRIPTS/self_edit.py", args or [])

def files_triage_command(args=None):
    """./jarvis files-triage [PASTA] [--limit N] — plano read-only."""
    _run_py_propagate("11_SCRIPTS/personal_tools.py", ["files-triage", *(args or [])])

def run_list_command(args=None):
    """./jarvis run-list — lista run packages gerados por `go`."""
    _run_py_propagate("11_SCRIPTS/run_log.py", ["list", *(args or [])])

def run_show_command(args=None):
    """./jarvis run-show latest|ID — imprime arquivos de um run package."""
    _run_py_propagate("11_SCRIPTS/run_log.py", ["show", *(args or [])])

def run_latest_command(args=None):
    """./jarvis run-latest — alias de run-show latest."""
    _run_py_propagate("11_SCRIPTS/run_log.py", ["latest", *(args or [])])

def capabilities_command(args=None):
    """./jarvis capabilities — lista capability registry por grupo."""
    _run_py_propagate("11_SCRIPTS/capabilities.py", ["list", *(args or [])])

def capability_check_command(args=None):
    """./jarvis capability-check NAME — detalhe + safe behavior."""
    _run_py_propagate("11_SCRIPTS/capabilities.py", ["check", *(args or [])])

def capability_plan_command(args=None):
    """./jarvis capability-plan NAME — plano local para future_adapter."""
    _run_py_propagate("11_SCRIPTS/capabilities.py", ["plan", *(args or [])])

def project_intel_command(args=None):
    """./jarvis project-intel --project ALIAS — inspeção read-only do projeto."""
    _run_py_propagate("11_SCRIPTS/project_intel.py", args)

def work_start_command(args=None):
    """./jarvis work-start "pedido" [--dry-run] [--project A] [--no-task]"""
    _run_py_propagate("11_SCRIPTS/work_session.py", ["start", *(args or [])])

def work_status_command(args=None):
    """./jarvis work-status — status da sessão de trabalho atual."""
    _run_py_propagate("11_SCRIPTS/work_session.py", ["status", *(args or [])])

def work_next_command(args=None):
    """./jarvis work-next — próximo comando seguro do lifecycle."""
    _run_py_propagate("11_SCRIPTS/work_session.py", ["next", *(args or [])])

def work_block_command(args=None):
    """./jarvis work-block --reason "..." — marca sessão como blocked."""
    _run_py_propagate("11_SCRIPTS/work_session.py", ["block", *(args or [])])

def work_close_command(args=None):
    """./jarvis work-close [--dry-run] [--force]"""
    _run_py_propagate("11_SCRIPTS/work_session.py", ["close", *(args or [])])

def resume_command(args=None):
    """./jarvis resume — pickup point: work-status + work-next + último run + top task."""
    _run_py_propagate("11_SCRIPTS/work_session.py", ["resume", *(args or [])])

def report_template_command(args=None):
    """./jarvis report-template — imprime o `cat > PATH` exato do projeto atual."""
    _run_py_propagate("11_SCRIPTS/report_intake.py", ["template", *(args or [])])

def report_status_command(args=None):
    """./jarvis report-status — presença / qualidade do relatório esperado."""
    _run_py_propagate("11_SCRIPTS/report_intake.py", ["status", *(args or [])])

def report_check_command(args=None):
    """./jarvis report-check --file PATH — valida headings/quality (sem gravar)."""
    _run_py_propagate("11_SCRIPTS/report_intake.py", ["check", *(args or [])])

def report_apply_command(args=None):
    """./jarvis report-apply --file PATH [--force-weak] [--project ALIAS]"""
    _run_py_propagate("11_SCRIPTS/report_intake.py", ["apply", *(args or [])])

def gate_run_command(args=None):
    """./jarvis gate-run — roda safety+smoke+doctrine, atualiza work session."""
    _run_py_propagate("11_SCRIPTS/gate_runner.py", ["run", *(args or [])])

def gate_status_command(args=None):
    """./jarvis gate-status — último gate-run + work session ativa."""
    _run_py_propagate("11_SCRIPTS/gate_runner.py", ["status", *(args or [])])

def run_prune_command(args=None):
    """./jarvis run-prune --keep N [--dry-run|--apply]"""
    _run_py_propagate("11_SCRIPTS/run_log.py", ["prune", *(args or [])])

def doctor_agent_command(args=None):
    """./jarvis doctor-agent [--full] — diagnóstico do próprio JARVIS."""
    _run_py_propagate("11_SCRIPTS/agent_doctor.py", args)

def state_status_command(args=None):
    """./jarvis state-status — leitura runtime do JARVIS (sessões, tasks, gates)."""
    _run_py_propagate("11_SCRIPTS/state_tools.py", ["status", *(args or [])])

def state_reset_command(args=None):
    """./jarvis state-reset --dry-run|--apply — remove current.json travada."""
    _run_py_propagate("11_SCRIPTS/state_tools.py", ["reset", *(args or [])])

def state_archive_command(args=None):
    """./jarvis state-archive --dry-run|--apply — copia current.json para archive/."""
    _run_py_propagate("11_SCRIPTS/state_tools.py", ["archive", *(args or [])])

def no_claude_command(args=None):
    """./jarvis no-claude "pedido" [--project A] [--dry-run] [--no-task] — modo offline."""
    _run_py_propagate("11_SCRIPTS/no_claude.py", args)

def cheatsheet_command(args=None):
    """./jarvis cheatsheet — uma tela com os comandos essenciais."""
    _run_py_propagate("11_SCRIPTS/cheatsheet.py", args)

def handoff_self_command(args=None):
    """./jarvis handoff-self [--save] — snapshot textual do JARVIS para handoff."""
    _run_py_propagate("11_SCRIPTS/handoff_self.py", args)

def daily_command(args=None):
    """./jarvis daily — dashboard de uma tela (health/work/gates/next)."""
    _run_py_propagate("11_SCRIPTS/daily_dashboard.py", args)

def first_run_check_command(args=None):
    """./jarvis first-run-check [--full] — verifica ambiente local."""
    _run_py_propagate("11_SCRIPTS/first_run_check.py", args)

def recipe_list_command(args=None):
    """./jarvis recipe-list — lista golden paths."""
    _run_py_propagate("11_SCRIPTS/recipes.py", ["list", *(args or [])])

def recipe_show_command(args=None):
    """./jarvis recipe-show NAME — imprime passos da receita."""
    _run_py_propagate("11_SCRIPTS/recipes.py", ["show", *(args or [])])

def recipe_run_command(args=None):
    """./jarvis recipe-run NAME [--project A] [--goal "..."] [--dry-run|--live]"""
    _run_py_propagate("11_SCRIPTS/recipes.py", ["run", *(args or [])])

def rc_status_command(args=None):
    """./jarvis rc-status — readiness do release candidate."""
    _run_py_propagate("11_SCRIPTS/release_candidate.py", ["status", *(args or [])])

def rc_freeze_command(args=None):
    """./jarvis rc-freeze --dry-run|--apply [--skip-gates] — snapshot RC."""
    _run_py_propagate("11_SCRIPTS/release_candidate.py", ["freeze", *(args or [])])

def acceptance_command(args=None):
    """./jarvis acceptance --dry-run|--full — cenários locais sem Claude."""
    _run_py_propagate("11_SCRIPTS/acceptance.py", args)

def do_command(args=None):
    args = list(args or [])
    raw = " ".join(args).strip()
    lowered = raw.lower()

    is_report_flow = "--report" in args or any(a.startswith("--report=") for a in args)

    digest_triggers = [
        "deep research",
        "research digest",
        "research-digest",
        "sources",
        "source",
        "fontes",
        "referências",
        "referencias",
        "plano de evolução",
        "plano de evolucao",
        "evolução do jarvis",
        "evolucao do jarvis",
    ]

    if raw and not is_report_flow and any(t in lowered for t in digest_triggers):
        cleaned = []
        skip_next = False

        for a in args:
            if skip_next:
                skip_next = False
                continue

            if a in ["--project", "--mode"]:
                skip_next = True
                continue

            if a.startswith("--project=") or a.startswith("--mode="):
                continue

            if a in ["--copy", "--reuse-last", "--dry-run"]:
                continue

            cleaned.append(a)

        goal = " ".join(cleaned).strip() or "evolução do JARVIS usando deep research locais"
        digest_args = ["--goal", goal]

        if "--dry-run" in args:
            digest_args.append("--dry-run")

        return research_digest_command(digest_args)

    return _run_py_propagate("11_SCRIPTS/worker_engine.py", args)

def do_history_command(args=None):
    """./jarvis do-history [--limit N] [--route NAME] [--project ALIAS]"""
    _run_py_propagate("11_SCRIPTS/do_history.py", ["history", *(args or [])])

def do_show_command(args=None):
    """./jarvis do-show {latest|ID}"""
    _run_py_propagate("11_SCRIPTS/do_history.py", ["show", *(args or [])])

def do_learn_command(args=None):
    """./jarvis do-learn [--dry-run|--apply]"""
    _run_py_propagate("11_SCRIPTS/do_history.py", ["learn", *(args or [])])

def report_policy_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/report_policy.py"], cwd=ROOT, check=False)

def storage_health_command():
    _run_py_propagate("11_SCRIPTS/storage_health.py", [])

def secret_scan_command():
    _run_py_propagate("11_SCRIPTS/secret_scan.py", [])

def safety_gate_command():
    _run_py_propagate("11_SCRIPTS/safety_gate.py", [])

def mode_plan_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis mode-plan "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/mode_plan.py", text], cwd=ROOT, check=False)

def pending_artifacts_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/pending_artifacts.py"], cwd=ROOT, check=False)

def snapshot_prep_core_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/snapshot_preparation_core.py"], cwd=ROOT, check=False)

def readonly_run_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis readonly-run "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/readonly_run.py", text], cwd=ROOT, check=False)

def readonly_run_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/readonly_run_latest.py"], cwd=ROOT, check=False)

def command_audit_command():
    _run_py_propagate("11_SCRIPTS/command_audit.py", [])

def local_exec_plan_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis local-exec-plan "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/local_exec_plan.py", text], cwd=ROOT, check=False)

def local_exec_plan_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/local_exec_plan_latest.py"], cwd=ROOT, check=False)

def local_exec_ready_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis local-exec-ready "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/local_exec_ready.py", text], cwd=ROOT, check=False)

def local_exec_ready_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/local_exec_ready_latest.py"], cwd=ROOT, check=False)

def local_exec_handoff_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis local-exec-handoff "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/local_exec_handoff.py", text], cwd=ROOT, check=False)

def local_exec_handoff_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/local_exec_handoff_latest.py"], cwd=ROOT, check=False)

def local_exec_review_command(args=None):
    import subprocess
    args = args or []
    if not args:
        print('Uso: ./jarvis local-exec-review arquivo.md')
        return
    subprocess.run(["python3", "11_SCRIPTS/local_exec_review.py", *args], cwd=ROOT, check=False)

def local_exec_review_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/local_exec_review_latest.py"], cwd=ROOT, check=False)

def local_exec_flow_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis local-exec-flow "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/local_exec_flow.py", text], cwd=ROOT, check=False)

def local_exec_flow_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/local_exec_flow_latest.py"], cwd=ROOT, check=False)

def local_exec_session_command(args=None):
    import subprocess
    args = args or []
    if not args:
        print('Uso: ./jarvis local-exec-session --project oficina "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/local_exec_session.py", *args], cwd=ROOT, check=False)

def local_exec_session_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/local_exec_session_latest.py"], cwd=ROOT, check=False)

def project_resolve_command(args=None):
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/project_resolve.py", *args], cwd=ROOT, check=False)

def project_menu_command(args=None):
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/project_menu.py", *args], cwd=ROOT, check=False)

def next_step_command(args=None):
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/next_step.py", *args], cwd=ROOT, check=False)

def future_tools_radar_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/future_tools_radar.py"], cwd=ROOT, check=False)

def run_safe_command(args=None):
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/run_safe.py", *args], cwd=ROOT, check=False)

_HELP_TOP = """JARVIS — interface principal (use `./jarvis help --all` para ver tudo)

## Interface única
  ./jarvis do                                smart resume (sem argumento)
  ./jarvis do "pedido"                       worker engine: rota + executa + grava
  ./jarvis do "pedido" --copy                + joga mission no clipboard
  ./jarvis do "pedido" --project ALIAS       força projeto
  ./jarvis do "pedido" --mode no-claude      rota offline (pacote real)
  ./jarvis do "pedido" --dry-run             preview, sem executar
  ./jarvis do "melhor a última missão"       regenera baseado no último run
  ./jarvis do --reuse-last "novo ajuste"     idem, explícito
  ./jarvis do --report /tmp/x.md             fecha o loop: check + apply + gates
  ./jarvis do --report /tmp/x.md --auto-finish  + fecha a sessão

## Memória de worker runs
  ./jarvis do-history [--limit N] [--route X] [--project A]
  ./jarvis do-show {latest|ID}
  ./jarvis do-learn [--dry-run|--apply]      sugere INTENT_PATTERNS

## Diário / saúde
  ./jarvis daily                             dashboard de uma tela
  ./jarvis decision-list                     decisões operacionais recentes
  ./jarvis decision-add "escolha" --dry-run  preview append-only
  ./jarvis cheatsheet                        atalhos essenciais
  ./jarvis health                            doctor-agent
  ./jarvis first-run-check                   ambiente local OK?

## Ações pessoais locais
  ./jarvis assistant-doctor                  verifica captura/imagem/voz/mensagem
  ./jarvis screen-capture --dry-run          prepara captura de tela
  ./jarvis screen-record --dry-run           prepara gravador nativo de tela
  ./jarvis github-overview --dry-run         inspeciona GitHub autenticado
  ./jarvis image-to-pdf IMAGEM --dry-run     planeja; PDF bloqueado pela doutrina
  ./jarvis image-convert IMAGEM --to jpg     converte preservando original
  ./jarvis speak "bom dia" --dry-run         fala local com a voz do macOS
  ./jarvis message-draft --phone NUM "oi"    abre/copia rascunho de WhatsApp
  ./jarvis message-send --phone NUM "oi"     envia pelo app Mensagens do Mac
  ./jarvis memory-save "texto"               grava na memória local versionável
  ./jarvis web                                abre o JARVIS visual ligado ao worker local
  ./jarvis storage-scan PASTA                mostra arquivos grandes, sem apagar
  ./jarvis system-memory                     diagnostica RAM; limpa só temporários JARVIS sob pedido
  ./jarvis computer open|close "APP"         controla apps locais com evidência via Orca
  ./jarvis computer-worker --status          ponte Vercel → Supabase → Mac
  ./jarvis files-triage PASTA                plano de organização, sem mover

## Lifecycle longo (quando `do` não basta)
  ./jarvis start "pedido"                    inicia sessão
  ./jarvis next                              próximo passo seguro
  ./jarvis report-template                   cat > /tmp/... para colar
  ./jarvis report-check --file PATH          valida relatório
  ./jarvis report-apply --file PATH          aplica debrief
  ./jarvis gates                             safety + smoke + doctrine
  ./jarvis finish                            fecha sessão

## Recuperação
  ./jarvis state-status                      ver runtime travado
  ./jarvis state-reset --dry-run             remove current.json (preview)
  ./jarvis no-claude "pedido"                pacote offline manual
  ./jarvis research-digest                   digest local dos deep research + plano JARVIS

## Catálogo completo
  ./jarvis help --all                        lista TODOS os comandos
  ./jarvis commands                          catálogo profissional
  ./jarvis limits                            fronteira do robô
  ./jarvis doctrine-check                    drift de docs/help/catalog
  ./jarvis command-audit                     auditoria de comandos

Produção: nada alterado por este help.
"""


def help_msg():
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    if any(a == "--all" for a in args):
        _help_full()
        return
    print(_HELP_TOP, end="")


def _help_full():
    print("""Comandos (full):
  ./jarvis doctor                 full health check
  ./jarvis scan-inbox             lista arquivos em 00_COLE_AQUI
  ./jarvis intake "pedido"        cria task a partir de um pedido
  ./jarvis process-inbox          cria tasks de arquivos .txt/.md do inbox
  ./jarvis report                 mostra projetos, tasks e logs
  ./jarvis status                 alias de report
  ./jarvis next-legacy            mostra a próxima task ativa (legado 02_TAREFAS)
  ./jarvis close-task             fecha a próxima task ativa
  ./jarvis close-task "texto"     fecha task que contenha o texto
  ./jarvis check                  alias de doctor
  ./jarvis help                   ajuda
  ./jarvis run-safe --project ALIAS "tarefa" orquestra preparação segura
  ./jarvis future-tools-radar mostra radar futuro de ferramentas
  ./jarvis next-step [alias] mostra opções humanas do próximo passo
  ./jarvis project-menu [alias] menu humano de projeto
  ./jarvis project-resolve [alias] valida alias de projeto
  ./jarvis local-exec-session-latest imprime última sessão LOCAL_EXEC
  ./jarvis local-exec-session "task" prepara sessão LOCAL_EXEC completa
  ./jarvis local-exec-flow-latest imprime último guia LOCAL_EXEC
  ./jarvis local-exec-flow "task" guia fluxo LOCAL_EXEC completo
  ./jarvis local-exec-review-latest imprime última revisão LOCAL_EXEC
  ./jarvis local-exec-review arquivo.md revisa saída LOCAL_EXEC
  ./jarvis local-exec-handoff-latest imprime último pacote LOCAL_EXEC
  ./jarvis local-exec-handoff "task" gera pacote LOCAL_EXEC para executor
  ./jarvis local-exec-ready-latest imprime último LOCAL_EXEC ready check
  ./jarvis local-exec-ready "task" checa se LOCAL_EXEC pode iniciar
  ./jarvis local-exec-plan-latest imprime último plano LOCAL_EXEC
  ./jarvis local-exec-plan "task" prepara plano LOCAL_EXEC sem editar
  ./jarvis executor-handoff "task" gera pacote manual para Claude/VS Code
  ./jarvis mode-plan "task"      classifica tarefa por modo de execução
  ./jarvis command-audit          audita core/help/catalog/smoke
  ./jarvis readonly-run-latest    imprime última inspeção read-only
  ./jarvis snapshot-prep-core     cria snapshot limpo do preparation core
  ./jarvis pending-artifacts      lista artefatos gerados pendentes no Git
  ./jarvis safety-gate            roda secret-scan, storage-health e quality-gate
  ./jarvis secret-scan            procura segredos em arquivos versionados
  ./jarvis storage-health         valida tracking/ignore de relatórios e segredos
  ./jarvis report-policy          mostra política de relatórios e snapshots
  ./jarvis cockpit                mostra painel operacional local
  ./jarvis visual-cockpit         mostra dashboard visual de gates, lock e próximas ações
  ./jarvis claude-mission         gera mission pack pronto para Claude Code
  ./jarvis claude-mission-latest  imprime a missão Claude mais recente
  ./jarvis operator-workbench     mostra workbench humano do operador (geral/--jarvis-core/--project)
  ./jarvis workbench              alias de operator-workbench
  ./jarvis doctor --project A     diagnóstico read-only do projeto registrado A
  ./jarvis qa-sprint --project A  gera mission Claude para QA sprint do projeto A
  ./jarvis goal-sprint --project A --goal "..."  gera mission Claude orientada a objetivo
  ./jarvis browser-qa --project A gera mission Claude para QA de UI/browser
  ./jarvis final-gate --project A gera mission Claude para validação final (push/PR/deploy)
  ./jarvis project-status --project A   status compacto do projeto (1 tela)
  ./jarvis project-cockpit --project A  cockpit (status + última missão + próximo passo)
  ./jarvis mission-open-latest    imprime path absoluto do prompt mais recente
  ./jarvis project-memory --project A   exibe memória do projeto (STATUS+NEXT+missão+commits)
  ./jarvis project-memory-update --project A --from-git [--apply]  gera/registra entrada de debrief
  ./jarvis self-status            status compacto do próprio JARVIS
  ./jarvis self-cockpit           cockpit do JARVIS (status + memória + próximo passo)
  ./jarvis self-next              imprime apenas o próximo comando seguro
  ./jarvis self-evolve --goal "…" [--copy]   gera missão Claude para evoluir JARVIS
  ./jarvis self-debrief --from-git|--from-file PATH [--apply]   wrapper de project-memory-update p/ jarvis-core
  ./jarvis claude-copy-latest [--project A]   copia o último prompt para o clipboard (pbcopy)
  ./jarvis claude-launch --project A [--copy] [--print-only]   imprime bloco "cd PATH; claude" (não executa)
  ./jarvis claude-save-report-template [--project A]   imprime template bash para capturar resposta do Claude
  ./jarvis doctrine-check         verifica drift entre AGENTS/CATALOG/help/registry/mission templates
  ./jarvis ask "pedido"           router local: classifica intent + sugere comando seguro
  ./jarvis go  "pedido"           power-wrapper: ask --copy + banner de launch/debrief
  ./jarvis capture "ideia"        anexa ideia ao inbox local (05_EXECUCAO/30_INBOX)
  ./jarvis inbox                  exibe inbox local
  ./jarvis agenda-add "tarefa"    anexa item à agenda local (05_EXECUCAO/31_AGENDA)
  ./jarvis agenda                 exibe agenda local
  ./jarvis assistant-doctor       verifica comandos nativos para utilidades pessoais
  ./jarvis screen-capture [--interactive] [--output P] [--dry-run]  captura local sob comando
  ./jarvis screen-record [--dry-run]  abre o gravador nativo do macOS
  ./jarvis github-overview [--limit N] [--dry-run]  GitHub read-only
  ./jarvis image-to-pdf IMAGEM --dry-run  planeja; PDF permanece bloqueado pelo AGENTS.md
  ./jarvis image-convert IMAGEM --to png|jpg|tiff [--output P] [--dry-run]  conversão permitida
  ./jarvis speak "texto" [--voice VOZ] [--output audio.aiff] [--dry-run]  voz local
  ./jarvis message-draft --phone NUM "texto" [--open|--copy|--dry-run]  WhatsApp sem autoenvio
  ./jarvis message-send --phone NUM "texto" [--dry-run]  envio explícito pelo app Mensagens
  ./jarvis memory-save "texto" [--kind learning|decision|preference] [--dry-run]  memória local
  ./jarvis web [--no-open|--check]  cockpit visual + OpenRouter + worker local
  ./jarvis storage-scan [PASTA] [--top N] [--min-mb N]  inventário read-only de arquivos grandes
  ./jarvis system-memory [--cleanup-jarvis] [--dry-run]  RAM + limpeza restrita a temporários JARVIS
  ./jarvis computer list|inspect|open|close [APP] [--dry-run]  Computer Use local via Orca
  ./jarvis computer-worker [--once|--watch|--install|--status|--uninstall] [--dry-run]  fila allowlisted Vercel → Mac
  ./jarvis self-edit "melhoria" [--dry-run] [--publish]  altera/testa; --publish faz PR+merge+deploy apenas no JARVIS autorizado
  ./jarvis files-triage [PASTA] [--limit N]  plano de organização por tipo; não move nada
  ./jarvis blueprint --type T --goal "..."  blueprint local (n8n|app|automation|research)
  ./jarvis research-digest [--goal "..."]  digest local dos deep research + plano de evolução
  ./jarvis project-open --project A [--print-only|--copy-cd|--code]  abre projeto local com segurança
  ./jarvis plan "pedido" [--save]  gera plano de execução local (intent+safety+next+missão+validation)
  ./jarvis limits                 imprime fronteira do robô (pode/não pode/precisa Claude)
  ./jarvis ask-log                exibe pedidos cujo intent ficou unclear (pattern tuning)
  ./jarvis task-add "texto" [--dry-run]  adiciona tarefa à fila local (JSONL append-only)
  ./jarvis task-list              lista tarefas locais (pending/blocked/done)
  ./jarvis task-next              top pending + comando seguro sugerido
  ./jarvis task-show ID           events da task
  ./jarvis task-done ID           marca task done (append-only)
  ./jarvis task-block ID --reason "..."  marca task blocked
  ./jarvis decision-add "escolha" [--project A] [--context X] [--reason Y] [--dry-run]  registra decisão local
  ./jarvis decision-list [--project A] [--limit N]  lista decisões recentes
  ./jarvis decision-show latest|ID  exibe uma decisão
  ./jarvis run-list               lista run packages (gerados por go)
  ./jarvis run-show latest|ID     imprime arquivos de um run package
  ./jarvis run-latest             alias de run-show latest
  ./jarvis capabilities           lista CAPABILITY_REGISTRY por grupo
  ./jarvis capability-check NAME  detalhe + safe behavior + setup
  ./jarvis capability-plan NAME   plano local para future_adapter
  ./jarvis project-intel --project A  inspeção read-only (package mgr, tests, migrations, .env presence)
  ./jarvis resume                 pickup point: status + next + último run + top task
  ./jarvis work-start "pedido"    inicia ciclo: task+run+session+missão (gitignored runtime)
  ./jarvis work-status            status da sessão atual (intent/project/status/next/report)
  ./jarvis work-next              próximo comando seguro do lifecycle
  ./jarvis work-block --reason "..."  marca sessão como blocked
  ./jarvis work-close [--force]   fecha sessão (espera gates_passed/blocked)
  ./jarvis report-template        imprime o `cat > PATH` exato (project-aware)
  ./jarvis report-status          presença + qualidade do relatório esperado
  ./jarvis report-check --file P  valida headings/quality (sem gravar)
  ./jarvis report-apply --file P [--project A] [--force-weak]  delega para writer seguro
  ./jarvis gate-run               roda safety+smoke+doctrine; atualiza work session
  ./jarvis gate-status            último gate-run registrado
  ./jarvis run-prune --keep N [--apply]  remove run packages antigos (default --dry-run)
  ./jarvis now                    alias de resume (primeiro comando do dia)
  ./jarvis start "pedido"         alias de work-start (inicia lifecycle)
  ./jarvis next                   alias de work-next (próximo passo seguro)
  ./jarvis finish                 alias de work-close (fecha sessão)
  ./jarvis gates                  alias de gate-run (safety+smoke+doctrine)
  ./jarvis health                 alias de doctor-agent (diagnóstico local)
  ./jarvis doctor-agent [--full]  diagnóstico do próprio JARVIS (read-only)
  ./jarvis state-status           leitura runtime (sessões, tasks, gates)
  ./jarvis state-reset --dry-run  remove current.json travada (events.jsonl preservado)
  ./jarvis state-archive --dry-run  copia current.json para archive/<ts>_current.json
  ./jarvis no-claude "pedido"     modo offline: plano manual + comandos seguros
  ./jarvis cheatsheet             uma tela com atalhos essenciais
  ./jarvis handoff-self [--save]  snapshot textual do JARVIS (para ChatGPT/handoff)
  ./jarvis daily                  dashboard de uma tela (health/work/gates/next)
  ./jarvis first-run-check [--full]  verifica ambiente local (python/git/claude/code/gitignore)
  ./jarvis recipe-list            lista golden paths (n8n-workflow/project-fix/self-evolve/...)
  ./jarvis recipe-show NAME       imprime passos da receita
  ./jarvis recipe-run NAME [--project A] [--goal "..."] [--dry-run|--live]   roda golden path
  ./jarvis rc-status              readiness do release candidate
  ./jarvis rc-freeze --dry-run    snapshot RC em 41_RELEASE_CANDIDATES/ (default dry-run)
  ./jarvis acceptance --dry-run   cenários locais sem Claude (--full inclui gate-run)
  ./jarvis do "pedido" [--project A] [--mode safe|no-claude] [--dry-run] [--copy] [--reuse-last]   worker engine (observe-act loop)
  ./jarvis do --report PATH [--project A] [--auto-finish] [--dry-run]   fecha loop pós-Claude (check+apply+gates)
  ./jarvis do-history [--limit N] [--route NAME] [--project ALIAS]   lista worker runs recentes
  ./jarvis do-show {latest|ID}    abre um worker run em detalhe
  ./jarvis do-learn [--dry-run|--apply]   sugere INTENT_PATTERNS a partir de unclear runs
  ./jarvis review-output-index    indexa revisões de outputs externos
  ./jarvis review-output-latest   imprime última revisão de output externo
  ./jarvis execution-modes        mostra modos de execução forte
  ./jarvis review-output-v2       revisa output de executor externo
  ./jarvis auto-task-latest       imprime último auto-task
  ./jarvis task-brief-latest      imprime último briefing de tarefa
  ./jarvis overview               mostra visão atual completa do sistema
  ./jarvis task-status            mostra último status operacional
  ./jarvis commands               mostra catálogo profissional de comandos
  ./jarvis handoff-print          imprime último prompt Claude no terminal
  ./jarvis release-check          roda validação completa local
  ./jarvis smoke-test             testa comandos principais do JARVIS
  ./jarvis handoff-open           abre último handoff no Finder
  ./jarvis handoff-latest         mostra último pacote para Claude/VS Code
""")

def workspace_check_command(path_text: str = ""):
    import subprocess
    target = path_text.strip() or "."
    subprocess.run(["python3", "11_SCRIPTS/workspace_check.py", target], cwd=ROOT, check=False)

def workspace_scan_command(path_text: str = ""):
    import subprocess
    target = path_text.strip() or "."
    subprocess.run(["python3", "11_SCRIPTS/workspace_scan.py", target], cwd=ROOT, check=False)

def project_index_command(path_text: str = ""):
    import subprocess
    target = path_text.strip() or "~/VAMOO_PROJETOS"
    subprocess.run(["python3", "11_SCRIPTS/project_index.py", target], cwd=ROOT, check=False)

def project_select_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis project-select "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/project_select.py", text], cwd=ROOT, check=False)

def task_start_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis task-start "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/task_start.py", text], cwd=ROOT, check=False)

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd in ["doctor", "check"]:
        # ./jarvis doctor --project ALIAS → project_doctor.py (read-only health)
        # ./jarvis doctor (sem --project)  → doctor() do lab JARVIS local
        if "--project" in sys.argv[2:] or any(a.startswith("--project=") for a in sys.argv[2:]):
            project_doctor_command(sys.argv[2:])
        else:
            doctor()
    elif cmd == "qa-sprint":
        project_mission_pack_command("qa-sprint", sys.argv[2:])
    elif cmd == "goal-sprint":
        project_mission_pack_command("goal-sprint", sys.argv[2:])
    elif cmd == "browser-qa":
        project_mission_pack_command("browser-qa", sys.argv[2:])
    elif cmd == "final-gate":
        project_mission_pack_command("final-gate", sys.argv[2:])
    elif cmd == "project-status":
        project_status_command(sys.argv[2:], full=False)
    elif cmd == "project-cockpit":
        project_status_command(sys.argv[2:], full=True)
    elif cmd == "mission-open-latest":
        mission_open_latest_command(sys.argv[2:])
    elif cmd == "project-memory":
        project_memory_command(sys.argv[2:])
    elif cmd == "project-memory-update":
        project_memory_update_command(sys.argv[2:])
    elif cmd == "self-status":
        self_cockpit_command(sys.argv[2:], mode_default="status")
    elif cmd == "self-cockpit":
        self_cockpit_command(sys.argv[2:], mode_default="cockpit")
    elif cmd == "self-next":
        self_cockpit_command(sys.argv[2:], mode_default="next")
    elif cmd == "self-evolve":
        self_evolve_command(sys.argv[2:])
    elif cmd == "self-debrief":
        self_debrief_command(sys.argv[2:])
    elif cmd == "claude-copy-latest":
        claude_helper_command("copy-latest", sys.argv[2:])
    elif cmd == "claude-launch":
        claude_helper_command("launch", sys.argv[2:])
    elif cmd == "claude-save-report-template":
        claude_helper_command("save-report-template", sys.argv[2:])
    elif cmd == "doctrine-check":
        doctrine_check_command()
    elif cmd == "ask":
        ask_command(sys.argv[2:])
    elif cmd == "go":
        go_command(sys.argv[2:])
    elif cmd == "capture":
        capture_command(sys.argv[2:])
    elif cmd == "inbox":
        inbox_command(sys.argv[2:])
    elif cmd == "agenda-add":
        agenda_add_command(sys.argv[2:])
    elif cmd == "agenda":
        agenda_command(sys.argv[2:])
    elif cmd == "blueprint":
        blueprint_command(sys.argv[2:])
    elif cmd == "research-digest":
        research_digest_command(sys.argv[2:])
    elif cmd == "research-digest-latest":
        research_digest_latest_command(sys.argv[2:])
    elif cmd == "research-digest-validate":
        research_digest_validate_command(sys.argv[2:])
    elif cmd == "api":
        api_command(sys.argv[2:])
    elif cmd == "project-open":
        project_open_command(sys.argv[2:])
    elif cmd == "plan":
        plan_request_command(sys.argv[2:])
    elif cmd == "limits":
        limits_command(sys.argv[2:])
    elif cmd == "ask-log":
        ask_log_command(sys.argv[2:])
    elif cmd == "task-add":
        task_add_command(sys.argv[2:])
    elif cmd == "task-list":
        task_list_command(sys.argv[2:])
    elif cmd == "task-next":
        task_next_command(sys.argv[2:])
    elif cmd == "task-show":
        task_show_command(sys.argv[2:])
    elif cmd == "task-done":
        task_done_command(sys.argv[2:])
    elif cmd == "task-block":
        task_block_command(sys.argv[2:])
    elif cmd == "decision-add":
        decision_add_command(sys.argv[2:])
    elif cmd == "decision-list":
        decision_list_command(sys.argv[2:])
    elif cmd == "decision-show":
        decision_show_command(sys.argv[2:])
    elif cmd == "assistant-doctor":
        assistant_doctor_command(sys.argv[2:])
    elif cmd == "web":
        web_command(sys.argv[2:])
    elif cmd == "screen-capture":
        screen_capture_command(sys.argv[2:])
    elif cmd == "screen-record":
        screen_record_command(sys.argv[2:])
    elif cmd == "github-overview":
        github_overview_command(sys.argv[2:])
    elif cmd == "image-to-pdf":
        image_to_pdf_command(sys.argv[2:])
    elif cmd == "image-convert":
        image_convert_command(sys.argv[2:])
    elif cmd == "speak":
        speak_command(sys.argv[2:])
    elif cmd == "message-draft":
        message_draft_command(sys.argv[2:])
    elif cmd == "message-send":
        message_send_command(sys.argv[2:])
    elif cmd == "memory-save":
        memory_save_command(sys.argv[2:])
    elif cmd == "storage-scan":
        storage_scan_command(sys.argv[2:])
    elif cmd == "system-memory":
        system_memory_command(sys.argv[2:])
    elif cmd == "computer":
        computer_command(sys.argv[2:])
    elif cmd == "computer-worker":
        computer_worker_command(sys.argv[2:])
    elif cmd == "self-edit":
        self_edit_command(sys.argv[2:])
    elif cmd == "files-triage":
        files_triage_command(sys.argv[2:])
    elif cmd == "run-list":
        run_list_command(sys.argv[2:])
    elif cmd == "run-show":
        run_show_command(sys.argv[2:])
    elif cmd == "run-latest":
        run_latest_command(sys.argv[2:])
    elif cmd == "capabilities":
        capabilities_command(sys.argv[2:])
    elif cmd == "capability-check":
        capability_check_command(sys.argv[2:])
    elif cmd == "capability-plan":
        capability_plan_command(sys.argv[2:])
    elif cmd == "project-intel":
        project_intel_command(sys.argv[2:])
    elif cmd == "work-start":
        work_start_command(sys.argv[2:])
    elif cmd == "work-status":
        work_status_command(sys.argv[2:])
    elif cmd == "work-next":
        work_next_command(sys.argv[2:])
    elif cmd == "work-block":
        work_block_command(sys.argv[2:])
    elif cmd == "work-close":
        work_close_command(sys.argv[2:])
    elif cmd == "resume":
        resume_command(sys.argv[2:])
    elif cmd == "report-template":
        report_template_command(sys.argv[2:])
    elif cmd == "report-status":
        report_status_command(sys.argv[2:])
    elif cmd == "report-check":
        report_check_command(sys.argv[2:])
    elif cmd == "report-apply":
        report_apply_command(sys.argv[2:])
    elif cmd == "gate-run":
        gate_run_command(sys.argv[2:])
    elif cmd == "gate-status":
        gate_status_command(sys.argv[2:])
    elif cmd == "run-prune":
        run_prune_command(sys.argv[2:])
    elif cmd == "doctor-agent":
        doctor_agent_command(sys.argv[2:])
    elif cmd == "state-status":
        state_status_command(sys.argv[2:])
    elif cmd == "state-reset":
        state_reset_command(sys.argv[2:])
    elif cmd == "state-archive":
        state_archive_command(sys.argv[2:])
    elif cmd == "no-claude":
        no_claude_command(sys.argv[2:])
    elif cmd == "cheatsheet":
        cheatsheet_command(sys.argv[2:])
    elif cmd == "handoff-self":
        handoff_self_command(sys.argv[2:])
    elif cmd == "daily":
        daily_command(sys.argv[2:])
    elif cmd == "first-run-check":
        first_run_check_command(sys.argv[2:])
    elif cmd == "recipe-list":
        recipe_list_command(sys.argv[2:])
    elif cmd == "recipe-show":
        recipe_show_command(sys.argv[2:])
    elif cmd == "recipe-run":
        recipe_run_command(sys.argv[2:])
    elif cmd == "rc-status":
        rc_status_command(sys.argv[2:])
    elif cmd == "rc-freeze":
        rc_freeze_command(sys.argv[2:])
    elif cmd == "acceptance":
        acceptance_command(sys.argv[2:])
    elif cmd == "do":
        do_command(sys.argv[2:])
    elif cmd == "do-history":
        do_history_command(sys.argv[2:])
    elif cmd == "do-show":
        do_show_command(sys.argv[2:])
    elif cmd == "do-learn":
        do_learn_command(sys.argv[2:])
    elif cmd == "now":
        resume_command(sys.argv[2:])
    elif cmd == "start":
        work_start_command(sys.argv[2:])
    elif cmd == "finish":
        work_close_command(sys.argv[2:])
    elif cmd == "gates":
        gate_run_command(sys.argv[2:])
    elif cmd == "health":
        doctor_agent_command(sys.argv[2:])
    elif cmd == "scan-inbox":
        scan_inbox()
    elif cmd == "intake":
        text = " ".join(sys.argv[2:]).strip()
        if not text:
            print('Uso: ./jarvis intake "seu pedido aqui"')
            sys.exit(1)
        create_task(text)
    elif cmd == "process-inbox":
        process_inbox()
    elif cmd in ["report", "status"]:
        report()
    elif cmd == "next":
        # Alias Sprint 6: ./jarvis next → ./jarvis work-next
        # Legado: next_task() (02_TAREFAS/00_NOVAS) movido para `next-legacy`.
        work_next_command(sys.argv[2:])
    elif cmd == "next-legacy":
        next_task()
    elif cmd == "close-task":
        query = " ".join(sys.argv[2:]).strip()
        close_task(query)
    elif cmd == "create-project":
        name = " ".join(sys.argv[2:]).strip()
        create_project(name)
    elif cmd == "memory-from-task":
        query = " ".join(sys.argv[2:]).strip()
        memory_from_task(query)
    elif cmd == "self-test":
        self_test()
    elif cmd == "tools":
        show_tools()
    elif cmd == "checkpoint":
        checkpoint()
    elif cmd == "summary":
        summary()
    elif cmd == "profiles":
        show_profiles()
    elif cmd == "route":
        text = " ".join(sys.argv[2:]).strip()
        route_request(text)
    elif cmd == "plan":
        text = " ".join(sys.argv[2:]).strip()
        create_plan(text)
    elif cmd == "launch":
        text = " ".join(sys.argv[2:]).strip()
        launch_mission(text)
    elif cmd == "missions":
        show_missions()
    elif cmd == "quality-gate":
        quality_gate()
    elif cmd == "security-audit":
        security_audit()
    elif cmd == "defer-task":
        query = " ".join(sys.argv[2:]).strip()
        defer_task(query)
    elif cmd == "backlog":
        show_backlog()
    elif cmd == "prompt-pack":
        text = " ".join(sys.argv[2:]).strip()
        prompt_pack(text)
    elif cmd == "review-outputs":
        review_outputs()
    elif cmd == "workspace-check":
        path_text = " ".join(sys.argv[2:]).strip()
        workspace_check_command(path_text)
    elif cmd == "workspace-scan":
        path_text = " ".join(sys.argv[2:]).strip()
        workspace_scan_command(path_text)
    elif cmd == "project-index":
        path_text = " ".join(sys.argv[2:]).strip()
        project_index_command(path_text)
    elif cmd == "project-select":
        text = " ".join(sys.argv[2:]).strip()
        project_select_command(text)
    elif cmd == "task-start":
        text = " ".join(sys.argv[2:]).strip()
        task_start_command(text)
    elif cmd == "executor-handoff":
        text = " ".join(sys.argv[2:]).strip()
        executor_handoff_command(text)
    elif cmd == "handoff-latest":
        handoff_latest_command()
    elif cmd == "handoff-open":
        handoff_open_command()
    elif cmd == "smoke-test":
        smoke_test_command()
    elif cmd == "release-check":
        release_check_command()
    elif cmd == "handoff-print":
        handoff_print_command()
    elif cmd == "commands":
        commands_command()
    elif cmd == "task-status":
        task_status_command()
    elif cmd == "overview":
        overview_command()
    elif cmd == "task-brief":
        text = " ".join(sys.argv[2:]).strip()
        task_brief_command(text)
    elif cmd == "task-brief-latest":
        task_brief_latest_command()
    elif cmd == "auto-task":
        text = " ".join(sys.argv[2:]).strip()
        auto_task_command(text)
    elif cmd == "auto-task-latest":
        auto_task_latest_command()
    elif cmd == "review-output-v2":
        review_output_v2_command(sys.argv[2:])
    elif cmd == "execution-modes":
        execution_modes_command()
    elif cmd == "review-output-latest":
        review_output_latest_command()
    elif cmd == "review-output-index":
        review_output_index_command()
    elif cmd == "cockpit":
        cockpit_command()
    elif cmd == "visual-cockpit":
        visual_cockpit_command()
    elif cmd == "claude-mission":
        claude_mission_command(sys.argv[2:])
    elif cmd == "claude-mission-latest":
        claude_mission_latest_command()
    elif cmd == "operator-workbench":
        operator_workbench_command(sys.argv[2:])
    elif cmd == "workbench":
        operator_workbench_command(sys.argv[2:])
    elif cmd == "report-policy":
        report_policy_command()
    elif cmd == "storage-health":
        storage_health_command()
    elif cmd == "secret-scan":
        secret_scan_command()
    elif cmd == "safety-gate":
        safety_gate_command()
    elif cmd == "mode-plan":
        text = " ".join(sys.argv[2:]).strip()
        mode_plan_command(text)
    elif cmd == "pending-artifacts":
        pending_artifacts_command()
    elif cmd == "snapshot-prep-core":
        snapshot_prep_core_command()
    elif cmd == "readonly-run":
        text = " ".join(sys.argv[2:]).strip()
        readonly_run_command(text)
    elif cmd == "readonly-run-latest":
        readonly_run_latest_command()
    elif cmd == "command-audit":
        command_audit_command()
    elif cmd == "local-exec-plan":
        text = " ".join(sys.argv[2:]).strip()
        local_exec_plan_command(text)
    elif cmd == "local-exec-plan-latest":
        local_exec_plan_latest_command()
    elif cmd == "local-exec-ready":
        text = " ".join(sys.argv[2:]).strip()
        local_exec_ready_command(text)
    elif cmd == "local-exec-ready-latest":
        local_exec_ready_latest_command()
    elif cmd == "local-exec-handoff":
        text = " ".join(sys.argv[2:]).strip()
        local_exec_handoff_command(text)
    elif cmd == "local-exec-handoff-latest":
        local_exec_handoff_latest_command()
    elif cmd == "local-exec-review":
        local_exec_review_command(sys.argv[2:])
    elif cmd == "local-exec-review-latest":
        local_exec_review_latest_command()
    elif cmd == "local-exec-flow":
        text = " ".join(sys.argv[2:]).strip()
        local_exec_flow_command(text)
    elif cmd == "local-exec-flow-latest":
        local_exec_flow_latest_command()
    elif cmd == "local-exec-session":
        local_exec_session_command(sys.argv[2:])
    elif cmd == "local-exec-session-latest":
        local_exec_session_latest_command()
    elif cmd == "project-resolve":
        project_resolve_command(sys.argv[2:])
    elif cmd == "project-menu":
        project_menu_command(sys.argv[2:])
    elif cmd == "next-step":
        next_step_command(sys.argv[2:])
    elif cmd == "future-tools-radar":
        future_tools_radar_command()
    elif cmd == "run-safe":
        run_safe_command(sys.argv[2:])
    else:
        help_msg()

def executor_handoff_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis executor-handoff "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/executor_handoff.py", text], cwd=ROOT, check=False)

def handoff_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/handoff_latest.py"], cwd=ROOT, check=False)

def handoff_open_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/handoff_open.py"], cwd=ROOT, check=False)

def smoke_test_command():
    """Run the CLI smoke suite and make a failed gate fail `./jarvis`."""
    _run_py_propagate("11_SCRIPTS/cli_smoke_test.py", [])

def release_check_command():
    """Run the release suite and propagate its status to callers and CI."""
    _run_py_propagate("11_SCRIPTS/release_check.py", [])

def handoff_print_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/handoff_print.py"], cwd=ROOT, check=False)

def commands_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/command_catalog.py"], cwd=ROOT, check=False)

def task_status_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/task_status.py"], cwd=ROOT, check=False)

def overview_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/system_overview.py"], cwd=ROOT, check=False)

def task_brief_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis task-brief "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/task_brief.py", text], cwd=ROOT, check=False)

def task_brief_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/task_brief_latest.py"], cwd=ROOT, check=False)

def auto_task_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis auto-task "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/auto_task.py", text], cwd=ROOT, check=False)

def auto_task_latest_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/auto_task_latest.py"], cwd=ROOT, check=False)

def review_output_v2_command(args=None):
    import subprocess
    args = args or []
    subprocess.run(["python3", "11_SCRIPTS/review_outputs_v2.py", *args], cwd=ROOT, check=False)

if __name__ == "__main__":
    main()
