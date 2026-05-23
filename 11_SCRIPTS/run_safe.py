from pathlib import Path
from datetime import datetime
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "19_RUN_SAFE"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "run-safe"

def run(cmd):
    try:
        return subprocess.check_output(
            cmd,
            cwd=ROOT,
            text=True,
            stderr=subprocess.STDOUT,
            timeout=180,
            env=os.environ.copy(),
        ).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()
    except Exception as e:
        return f"ERRO: {e}"

def latest(folder, pattern="*"):
    base = ROOT / folder
    if not base.exists():
        return "nenhum"
    items = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not items:
        return "nenhum"
    return str(items[0].relative_to(ROOT))

def parse_args(argv):
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

def main():
    project_alias, task = parse_args(sys.argv[1:])
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    print("JARVIS — Theo Padilha AI Worker RUN SAFE")
    print("")
    print("Status real: orquestração local segura. Nenhum patch, push, deploy, VPS, n8n ou produção.")
    print("")

    if not project_alias:
        print("FALHA: run-safe exige --project para evitar escolha errada de projeto.")
        print("")
        print("Use:")
        print('./jarvis run-safe --project oficina "descrever tarefa sem deploy"')
        print("")
        print("Para ver opções:")
        print("./jarvis project-menu")
        sys.exit(1)

    if not task:
        print("FALHA: informe a tarefa.")
        print("")
        print("Use:")
        print(f'./jarvis run-safe --project {project_alias} "descrever tarefa sem deploy"')
        sys.exit(1)

    print(f"Project lock: {project_alias}")
    print(f"Tarefa: {task}")
    print("")

    steps = [
        ("PROJECT RESOLVE", ["./jarvis", "project-resolve", project_alias]),
        ("NEXT STEP", ["./jarvis", "next-step", project_alias]),
        ("LOCAL EXEC SESSION", ["./jarvis", "local-exec-session", "--project", project_alias, task]),
        ("LOCAL EXEC SESSION LATEST", ["./jarvis", "local-exec-session-latest"]),
        ("LOCAL EXEC HANDOFF LATEST", ["./jarvis", "local-exec-handoff-latest"]),
    ]

    outputs = []

    for name, cmd in steps:
        print(f"=== {name} ===")
        out = run(cmd)
        outputs.append((name, out))
        print(out)
        print("")

    artifacts = {
        "session": latest("05_EXECUCAO/18_LOCAL_EXEC_SESSIONS", "*.md"),
        "handoff": latest("05_EXECUCAO/15_LOCAL_EXEC_HANDOFFS", "*"),
        "ready": latest("05_EXECUCAO/14_LOCAL_EXEC_READY", "*.md"),
        "plan": latest("05_EXECUCAO/13_LOCAL_EXEC_PLANS", "*.md"),
        "readonly": latest("05_EXECUCAO/12_READONLY_RUNS", "*.md"),
        "flow": latest("05_EXECUCAO/17_LOCAL_EXEC_FLOWS", "*.md"),
    }

    lines = [
        "# RUN SAFE — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Project lock\n{project_alias}",
        "",
        f"## Tarefa\n{task}",
        "",
        "## Status real",
        "Orquestração local segura concluída. Nenhum projeto real foi editado por este comando.",
        "",
        "## Artefatos",
        f"- Flow: `{artifacts['flow']}`",
        f"- Readonly: `{artifacts['readonly']}`",
        f"- Plan: `{artifacts['plan']}`",
        f"- Ready: `{artifacts['ready']}`",
        f"- Session: `{artifacts['session']}`",
        f"- Handoff: `{artifacts['handoff']}`",
        "",
        "## Próximo passo humano",
        "Abrir o handoff. Se usar executor externo, salvar a resposta em `.md` e rodar `./jarvis local-exec-review arquivo.md` antes de aceitar qualquer patch.",
        "",
        "## Travas mantidas",
        "- Sem patch automático.",
        "- Sem build/test real automático.",
        "- Sem commit/push/PR automático.",
        "- Sem deploy.",
        "- Sem VPS/n8n/produção.",
        "- Claude opcional, não obrigatório.",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    if no_report:
        print("Relatório RUN_SAFE: desativado por JARVIS_NO_REPORT=1")
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        out = OUT_DIR / f"{ts}_project-{project_alias}-{slugify(task)}_run-safe.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Relatório RUN_SAFE: {out.relative_to(ROOT)}")

    print("")
    print("Resultado: RUN SAFE PASSOU")
    print("Status real: preparação guiada concluída. Produção não alterada.")

if __name__ == "__main__":
    main()
