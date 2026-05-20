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
    high = ["produção", "prod", "deploy", "main", "banco real", "senha", "token", "api key", "vps", "dns", "cliente real", "paciente"]
    medium = ["github", "commit", "push", "webhook", "uazapi", "supabase", "n8n ativo"]
    if any(x in t for x in high):
        return "alto"
    if any(x in t for x in medium):
        return "médio"
    return "baixo"

def write_log(title: str, body: str):
    logs = ROOT / "09_LOGS"
    logs.mkdir(parents=True, exist_ok=True)
    file = logs / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{slugify(title)}.md"
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
    add_check("git inicializado", git_dir.is_dir())

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

def help_msg():
    print("""Comandos:
  ./jarvis doctor                 full health check
  ./jarvis scan-inbox             lista arquivos em 00_COLE_AQUI
  ./jarvis intake "pedido"        cria task a partir de um pedido
  ./jarvis process-inbox          cria tasks de arquivos .txt/.md do inbox
  ./jarvis report                 mostra projetos, tasks e logs
  ./jarvis status                 alias de report
  ./jarvis next                   mostra a próxima task ativa
  ./jarvis close-task             fecha a próxima task ativa
  ./jarvis close-task "texto"     fecha task que contenha o texto
  ./jarvis check                  alias de doctor
  ./jarvis help                   ajuda
""")

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd in ["doctor", "check"]:
        doctor()
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
    else:
        help_msg()

if __name__ == "__main__":
    main()
