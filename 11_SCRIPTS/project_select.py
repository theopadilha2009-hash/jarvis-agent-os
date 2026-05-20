from pathlib import Path
import json
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "04_PROJETOS" / "_INDEX" / "PROJECT_INDEX.json"

def score_project(task, project):
    text = task.lower()
    score = 0
    reasons = []

    name = project.get("name", "").lower()
    ptype = project.get("type", "").lower()
    path = project.get("path", "").lower()
    status = project.get("status", "")

    for word in re.findall(r"[a-zA-Z0-9À-ÿ_-]+", text):
        w = word.lower()
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
            reasons.append("tarefa parece código/repo")

    if any(x in text for x in ["workflow", "n8n", "uazapi", "agente", "whatsapp"]):
        if "n8n" in ptype:
            score += 8
            reasons.append("tarefa parece workflow/n8n")

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

    if status == "limpo":
        score += 2
        reasons.append("git limpo")

    return score, reasons

def main():
    task = " ".join(sys.argv[1:]).strip()
    if not task:
        print('Uso: python3 11_SCRIPTS/project_select.py "tarefa"')
        sys.exit(1)

    if not INDEX.exists():
        print("FALHA: PROJECT_INDEX.json não encontrado.")
        print("Rode primeiro: ./jarvis project-index ~/VAMOO_PROJETOS")
        sys.exit(1)

    projects = json.loads(INDEX.read_text(encoding="utf-8"))

    ranked = []
    for p in projects:
        score, reasons = score_project(task, p)
        ranked.append((score, p, reasons))

    ranked.sort(key=lambda x: x[0], reverse=True)

    best_score, best, reasons = ranked[0]

    print("JARVIS — Theo Padilha AI Worker Project Select")
    print("")
    print(f"Tarefa: {task}")
    print("")
    print("Projeto sugerido:")
    print(f"- Nome: {best['name']}")
    print(f"- Caminho: {best['path']}")
    print(f"- Tipo: {best['type']}")
    print(f"- Branch: {best['branch']}")
    print(f"- Status: {best['status']}")
    print(f"- Risco: {best['risk']}")
    print(f"- Score: {best_score}")
    print(f"- Motivos: {', '.join(reasons[:8]) if reasons else 'sem match forte'}")
    print("")
    print("Próximo passo seguro:")
    print(f"./jarvis workspace-check {best['path']}")
    print("")
    print("Top opções:")
    for score, p, rs in ranked[:5]:
        print(f"- {p['name']} | score {score} | {p['path']}")

if __name__ == "__main__":
    main()
