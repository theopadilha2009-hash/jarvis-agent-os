from pathlib import Path
from datetime import datetime
import subprocess
import sys
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("~/VAMOO_PROJETOS").expanduser()
INDEX = ROOT / "04_PROJETOS" / "_INDEX" / "PROJECT_INDEX.json"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "task-start"

def run(cmd, cwd=ROOT):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        return "ERRO: " + e.output.strip()
    except Exception as e:
        return "ERRO: " + str(e)

def score_project(task, project):
    text = task.lower()
    score = 0
    reasons = []
    name = project.get("name", "").lower()
    ptype = project.get("type", "").lower()
    path = project.get("path", "").lower()

    words = re.findall(r"[a-zA-Z0-9À-ÿ_-]+", text)
    for w in words:
        w = w.lower()
        if len(w) < 3:
            continue
        if w in name:
            score += 10
            reasons.append(f"nome contém {w}")
        if w in path:
            score += 4
            reasons.append(f"caminho contém {w}")
        if w in ptype:
            score += 3
            reasons.append(f"tipo contém {w}")

    if any(x in text for x in ["bug", "corrigir", "repo", "código", "codigo", "site", "frontend"]):
        if "web-app" in ptype or project.get("git"):
            score += 6
            reasons.append("parece código/repo")

    if any(x in text for x in ["workflow", "n8n", "uazapi", "agente", "whatsapp"]):
        if "n8n" in ptype:
            score += 8
            reasons.append("parece workflow/n8n")

    if any(x in text for x in ["ls", "clinica", "clínica", "larissa"]):
        if "ls" in name:
            score += 12
            reasons.append("contexto LS Clínica")

    if any(x in text for x in ["oficina", "mecanica", "mecânica", "agenda", "os"]):
        if "oficina" in name:
            score += 12
            reasons.append("contexto oficina")

    if any(x in text for x in ["gc", "gestao", "gestão", "cristo", "visitantes"]):
        if "gc" in name or "gestao" in name:
            score += 12
            reasons.append("contexto GC")

    if project.get("status") == "limpo":
        score += 2
        reasons.append("git limpo")

    return score, reasons

def main():
    task = " ".join(sys.argv[1:]).strip()
    if not task:
        print('Uso: ./jarvis task-start "tarefa"')
        sys.exit(1)

    print("JARVIS — Theo Padilha AI Worker Task Start")
    print("")

    print("1/5 Atualizando índice de projetos...")
    print(run(["python3", "11_SCRIPTS/project_index.py", str(BASE)]))

    if not INDEX.exists():
        print("FALHA: PROJECT_INDEX.json não encontrado.")
        sys.exit(1)

    projects = json.loads(INDEX.read_text(encoding="utf-8"))
    ranked = []
    for p in projects:
        score, reasons = score_project(task, p)
        ranked.append((score, p, reasons))
    ranked.sort(key=lambda x: x[0], reverse=True)

    best_score, best, reasons = ranked[0]
    project_path = best["path"]

    print("")
    print("2/5 Projeto sugerido:")
    print(f"- {best['name']}")
    print(f"- {project_path}")
    print(f"- score {best_score}")
    print(f"- motivos: {', '.join(reasons[:8]) if reasons else 'sem match forte'}")

    print("")
    print("3/5 Rodando workspace-check...")
    workspace_check = run(["python3", "11_SCRIPTS/workspace_check.py", project_path])
    print(workspace_check)

    print("")
    print("4/5 Gerando prompt-pack manual...")
    prompt_pack = run(["./jarvis", "prompt-pack", task])
    print(prompt_pack)

    print("")
    print("5/5 Salvando task-start brief...")
    out_dir = ROOT / "05_EXECUCAO" / "06_TASK_STARTS"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out = out_dir / f"{ts}_{slugify(task)}_task-start.md"

    content = [
        "# Task Start — JARVIS Theo Padilha AI Worker",
        "",
        f"## Tarefa\n{task}",
        "",
        "## Status real\nPreparação local. Nada executado em produção.",
        "",
        f"## Projeto sugerido\n{best['name']}",
        "",
        f"## Caminho\n`{project_path}`",
        "",
        f"## Score\n{best_score}",
        "",
        f"## Motivos\n{', '.join(reasons[:12]) if reasons else 'sem match forte'}",
        "",
        f"## Tipo\n{best.get('type')}",
        "",
        f"## Branch\n{best.get('branch')}",
        "",
        f"## Status Git\n{best.get('status')}",
        "",
        f"## Risco inicial\n{best.get('risk')}",
        "",
        "## Próximo passo seguro",
        f"`./jarvis workspace-check {project_path}`",
        "",
        "Depois, abrir o projeto correto no VS Code e usar o prompt-pack manual com Claude/ChatGPT/Gemini, sem credenciais e sem produção.",
        "",
        "## Produção\nNada alterado.",
    ]

    out.write_text("\n".join(content) + "\n", encoding="utf-8")
    print(f"Brief salvo: {out.relative_to(ROOT)}")
    print("")
    print("Próximo comando seguro:")
    print(f"./jarvis workspace-check {project_path}")

if __name__ == "__main__":
    main()
