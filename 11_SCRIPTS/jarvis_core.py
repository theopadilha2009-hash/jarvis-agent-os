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

    py_compile = run(["python3", "-m", "py_compile", "11_SCRIPTS/jarvis_core.py"])
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

def report_policy_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/report_policy.py"], cwd=ROOT, check=False)

def storage_health_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/storage_health.py"], cwd=ROOT, check=False)

def secret_scan_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/secret_scan.py"], cwd=ROOT, check=False)

def safety_gate_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/safety_gate.py"], cwd=ROOT, check=False)

def mode_plan_command(text: str = ""):
    import subprocess
    if not text.strip():
        print('Uso: ./jarvis mode-plan "tarefa"')
        return
    subprocess.run(["python3", "11_SCRIPTS/mode_plan.py", text], cwd=ROOT, check=False)

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
  ./jarvis safety-gate            roda secret-scan, storage-health e quality-gate
  ./jarvis secret-scan            procura segredos em arquivos versionados
  ./jarvis storage-health         valida tracking/ignore de relatórios e segredos
  ./jarvis report-policy          mostra política de relatórios e snapshots
  ./jarvis cockpit                mostra painel operacional local
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
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/cli_smoke_test.py"], cwd=ROOT, check=False)

def release_check_command():
    import subprocess
    subprocess.run(["python3", "11_SCRIPTS/release_check.py"], cwd=ROOT, check=False)

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
