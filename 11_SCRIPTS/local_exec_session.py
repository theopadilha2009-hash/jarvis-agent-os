from pathlib import Path
from datetime import datetime
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "18_LOCAL_EXEC_SESSIONS"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "local-exec-session"

def run(cmd):
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=90).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()
    except Exception as e:
        return f"ERRO: {e}"

def latest(pattern_root, pattern):
    base = ROOT / pattern_root
    if not base.exists():
        return "nenhum"
    items = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(items[0].relative_to(ROOT)) if items else "nenhum"

def main():
    task = " ".join(sys.argv[1:]).strip()
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    if not task:
        print('Uso: ./jarvis local-exec-session "tarefa"')
        sys.exit(1)

    print("JARVIS — Theo Padilha AI Worker LOCAL_EXEC Session")
    print("")
    print("Status real: sessão de preparação local. Nenhum projeto foi editado.")
    print(f"Tarefa: {task}")
    print("")

    steps = [
        ("FLOW", ["./jarvis", "local-exec-flow", task]),
        ("READONLY", ["./jarvis", "readonly-run", task]),
        ("PLAN", ["./jarvis", "local-exec-plan", task]),
        ("READY", ["./jarvis", "local-exec-ready", task]),
        ("HANDOFF", ["./jarvis", "local-exec-handoff", task]),
    ]

    outputs = []

    for name, cmd in steps:
        print(f"=== {name} ===")
        out = run(cmd)
        outputs.append((name, cmd, out))
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
        "Abrir o handoff gerado e enviar para Claude/VS Code. Depois salvar a resposta em arquivo e rodar `./jarvis local-exec-review arquivo.md`.",
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
        out = OUT_DIR / f"{ts}_{slugify(task)}_local-exec-session.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Relatório: {out.relative_to(ROOT)}")

    print("")
    print("Status real: sessão preparada. Projeto não editado.")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
