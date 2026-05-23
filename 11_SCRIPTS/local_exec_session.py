from pathlib import Path
from datetime import datetime
import json
import os
import re
import subprocess
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "18_LOCAL_EXEC_SESSIONS"
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "local-exec-session"

def run(cmd):
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=90).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()
    except Exception as e:
        return f"ERRO: {e}"

def latest(folder, pattern):
    base = ROOT / folder
    if not base.exists():
        return "nenhum"
    items = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(items[0].relative_to(ROOT)) if items else "nenhum"

def parse_args(argv):
    if len(argv) == 1 and isinstance(argv[0], str):
        try:
            argv = shlex.split(argv[0])
        except Exception:
            pass

    project_alias = None
    task_parts = []
    i = 0

    while i < len(argv):
        arg = argv[i]

        if arg == "--project":
            if i + 1 >= len(argv):
                print("FALHA: --project exige alias.")
                sys.exit(1)
            project_alias = argv[i + 1].strip().lower()
            i += 2
            continue

        if arg.startswith("--project="):
            project_alias = arg.split("=", 1)[1].strip().lower()
            i += 1
            continue

        task_parts.append(arg)
        i += 1

    return project_alias, " ".join(task_parts).strip()

def load_project(alias):
    if not alias:
        return None

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

def main():
    project_alias, task = parse_args(sys.argv[1:])
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    if not task:
        print('Uso: ./jarvis local-exec-session --project oficina "tarefa"')
        print('Uso: ./jarvis local-exec-session "tarefa"')
        sys.exit(1)

    project = load_project(project_alias)
    execution_task = f"{project_alias} {task}" if project else task

    print("JARVIS — Theo Padilha AI Worker LOCAL_EXEC Session")
    print("")
    print("Status real: sessão de preparação local. Nenhum projeto foi editado.")
    print(f"Tarefa: {task}")

    if project:
        print(f"Project lock: {project_alias} -> {project['path']}")
    else:
        print("Project lock: não informado; seleção automática ainda permitida para compatibilidade.")

    print("")

    steps = [
        ("FLOW", ["./jarvis", "local-exec-flow", execution_task]),
        ("READONLY", ["./jarvis", "readonly-run", execution_task]),
        ("PLAN", ["./jarvis", "local-exec-plan", execution_task]),
        ("READY", ["./jarvis", "local-exec-ready", execution_task]),
        ("HANDOFF", ["./jarvis", "local-exec-handoff", execution_task]),
    ]

    for name, cmd in steps:
        print(f"=== {name} ===")
        out = run(cmd)
        print(out)
        print("")

    artifacts = {
        "flow": latest("05_EXECUCAO/17_LOCAL_EXEC_FLOWS", "*_local-exec-flow.md"),
        "readonly": latest("05_EXECUCAO/12_READONLY_RUNS", "*_readonly-run.md"),
        "plan": latest("05_EXECUCAO/13_LOCAL_EXEC_PLANS", "*_local-exec-plan.md"),
        "ready": latest("05_EXECUCAO/14_LOCAL_EXEC_READY", "*_local-exec-ready.md"),
        "handoff": latest("05_EXECUCAO/15_LOCAL_EXEC_HANDOFFS", "*"),
    }

    lines = [
        "# LOCAL_EXEC Session — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Tarefa\n{task}",
        "",
        f"## Project lock\n{project_alias or 'não informado'}",
        "",
        f"## Project path\n`{project['path'] if project else 'seleção automática'}`",
        "",
        "## Status real",
        "Sessão de preparação local. Nenhum projeto foi editado.",
        "",
        "## Artefatos gerados",
        f"- Flow: `{artifacts['flow']}`",
        f"- Readonly: `{artifacts['readonly']}`",
        f"- Plan: `{artifacts['plan']}`",
        f"- Ready: `{artifacts['ready']}`",
        f"- Handoff: `{artifacts['handoff']}`",
        "",
        "## Próximo passo seguro",
        "Abrir o handoff gerado. Se usar executor externo, salvar a resposta em arquivo e rodar `./jarvis local-exec-review arquivo.md`.",
        "",
        "## Bloqueios mantidos",
        "- Sem push.",
        "- Sem merge.",
        "- Sem deploy.",
        "- Sem VPS/n8n/produção.",
        "- Sem leitura/exposição de `.env` ou credenciais.",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    if no_report:
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        name = slugify((f"project-{project_alias}-" if project_alias else "") + task)
        out = OUT_DIR / f"{ts}_{name}_local-exec-session.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Relatório: {out.relative_to(ROOT)}")

    print("")
    print("Status real: sessão preparada. Projeto não editado.")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
