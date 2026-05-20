from pathlib import Path
from datetime import datetime
import subprocess
import sys
import json
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "04_PROJETOS" / "_INDEX" / "PROJECT_INDEX.json"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "executor-handoff"

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

    for w in re.findall(r"[a-zA-Z0-9À-ÿ_-]+", text):
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

    if any(x in text for x in ["gc", "gestao", "gestão", "cristo", "visitantes"]):
        if "gc" in name or "gestao" in name:
            score += 12
            reasons.append("contexto GC")

    if any(x in text for x in ["ls", "clinica", "clínica", "larissa"]):
        if "ls" in name:
            score += 12
            reasons.append("contexto LS Clínica")

    if any(x in text for x in ["oficina", "mecanica", "mecânica", "agenda", "os"]):
        if "oficina" in name:
            score += 12
            reasons.append("contexto Oficina")

    if project.get("status") == "limpo":
        score += 2
        reasons.append("git limpo")

    return score, reasons

def main():
    task = " ".join(sys.argv[1:]).strip()
    if not task:
        print('Uso: ./jarvis executor-handoff "tarefa"')
        sys.exit(1)

    print("JARVIS — Theo Padilha AI Worker Executor Handoff")
    print("")

    print("1/4 Atualizando índice...")
    print(run(["./jarvis", "project-index", "~/VAMOO_PROJETOS"]))

    if not INDEX.exists():
        print("FALHA: PROJECT_INDEX.json não encontrado.")
        sys.exit(1)

    projects = json.loads(INDEX.read_text(encoding="utf-8"))
    ranked = []
    for p in projects:
        score, reasons = score_project(task, p)
        ranked.append((score, p, reasons))
    ranked.sort(key=lambda x: x[0], reverse=True)

    score, project, reasons = ranked[0]
    project_path = project["path"]

    print("")
    print("2/4 Projeto selecionado:")
    print(f"- {project['name']}")
    print(f"- {project_path}")
    print(f"- score {score}")

    print("")
    print("3/4 Rodando workspace-check...")
    print(run(["./jarvis", "workspace-check", project_path]))

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out_dir = ROOT / "05_EXECUCAO" / "07_EXECUTOR_HANDOFFS" / f"{ts}_{slugify(task)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    company = "/VAMOO_PROJETOS/" in project_path or "VAMOO_PROJETOS" in project_path
    profile = "COMPANY_WORKSPACE" if company else "THEO_OWNER"

    context = [
        "# Executor Handoff — JARVIS Theo Padilha AI Worker",
        "",
        f"## Tarefa\n{task}",
        "",
        f"## Projeto selecionado\n{project['name']}",
        "",
        f"## Caminho\n`{project_path}`",
        "",
        f"## Perfil\n{profile}",
        "",
        f"## Tipo\n{project.get('type')}",
        "",
        f"## Branch atual\n{project.get('branch')}",
        "",
        f"## Git status no índice\n{project.get('status')}",
        "",
        f"## Risco inicial\n{project.get('risk')}",
        "",
        f"## Motivos\n{', '.join(reasons) if reasons else 'sem match forte'}",
        "",
        "## Status real",
        "Handoff local criado. Claude/Gemini/ChatGPT ainda não foram conectados automaticamente.",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    claude = [
        "# Prompt para Claude / Claude Code",
        "",
        "Você é executor técnico. Trabalhe em modo seguro.",
        "",
        f"Projeto: {project['name']}",
        f"Caminho local: {project_path}",
        f"Tarefa: {task}",
        "",
        "Regras obrigatórias:",
        "- Comece read-only.",
        "- Rode/peça `git status` antes de alterar.",
        "- Confirme branch atual.",
        "- Não mexa em main/master sem autorização.",
        "- Não leia, copie ou exponha `.env`, tokens, senhas ou credenciais.",
        "- Não faça deploy, push, merge ou alteração em produção.",
        "- Faça patch mínimo.",
        "- Após alteração, informe arquivos alterados e testes/build executados.",
        "",
        "Saída obrigatória:",
        "1. diagnóstico",
        "2. arquivos relevantes",
        "3. plano curto",
        "4. alterações feitas ou sugeridas",
        "5. validações rodadas",
        "6. riscos restantes",
        "7. próximo passo seguro",
    ]

    commands = [
        "# Comandos seguros sugeridos",
        "",
        "```bash",
        f"cd {project_path}",
        "pwd",
        "git status --short",
        "git branch --show-current",
        "```",
        "",
        "Se precisar criar branch segura:",
        "",
        "```bash",
        "git checkout -b fix/jarvis-safe-task",
        "```",
        "",
        "Não rodar deploy/push/merge sem autorização.",
    ]

    review = [
        "# Prompt de revisão para ChatGPT Cockpit",
        "",
        "Revise a saída do executor com foco em:",
        "- se respeitou escopo",
        "- se evitou credenciais",
        "- se não mexeu em produção",
        "- se os arquivos alterados fazem sentido",
        "- se há teste/build suficiente",
        "- se pode virar commit/PR ou precisa correção",
    ]

    files = {
        "00_CONTEXT.md": context,
        "01_CLAUDE_HANDOFF.md": claude,
        "02_SAFE_COMMANDS.md": commands,
        "03_CHATGPT_REVIEW_PROMPT.md": review,
    }

    for name, lines in files.items():
        (out_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("")
    print("4/4 Handoff salvo:")
    print(out_dir.relative_to(ROOT))
    print("")
    print("Próximo passo seguro:")
    print(f"open {out_dir}")

if __name__ == "__main__":
    main()
