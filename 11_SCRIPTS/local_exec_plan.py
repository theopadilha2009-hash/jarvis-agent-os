from pathlib import Path
from datetime import datetime
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "13_LOCAL_EXEC_PLANS"
PROJECT_ROOTS = [
    Path.home() / "VAMOO_PROJETOS",
    Path.home() / "Theo",
]

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "local-exec-plan"

def run(cmd, cwd):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=20).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()
    except Exception as e:
        return f"ERRO: {e}"

def find_projects():
    projects = []

    for base in PROJECT_ROOTS:
        if not base.exists():
            continue

        for p in base.iterdir():
            if not p.is_dir():
                continue

            score = 0
            reasons = []

            if (p / ".git").exists():
                score += 5
                reasons.append("git")
            if (p / "package.json").exists():
                score += 4
                reasons.append("package.json")
            if (p / "src").exists():
                score += 3
                reasons.append("src")
            if (p / "README.md").exists():
                score += 1
                reasons.append("readme")
            if any(p.glob("*.json")):
                score += 1
                reasons.append("json")

            if score > 0:
                projects.append({"path": p, "name": p.name, "score": score, "reasons": reasons})

    return sorted(projects, key=lambda x: x["score"], reverse=True)

def pick_project(task):
    task_l = task.lower()
    projects = find_projects()

    scored = []
    for pr in projects:
        score = pr["score"]
        name_l = pr["name"].lower()

        for token in re.findall(r"[a-zA-Z0-9_-]+", task_l):
            if len(token) >= 3 and token in name_l:
                score += 10

        if "gc" in task_l and ("gc" in name_l or "gestao" in name_l or "cristo" in name_l):
            score += 20
        if "oficina" in task_l and "oficina" in name_l:
            score += 20
        if "ls" in task_l and "ls" in name_l:
            score += 20

        scored.append((score, pr))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None

def package_manager(path):
    if (path / "bun.lockb").exists() or (path / "bun.lock").exists():
        return "bun"
    if (path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (path / "yarn.lock").exists():
        return "yarn"
    if (path / "package-lock.json").exists():
        return "npm"
    if (path / "package.json").exists():
        return "npm"
    return "unknown"

def commands_for(pm):
    if pm == "bun":
        return ["bun install", "bun run build", "bun test"]
    if pm == "pnpm":
        return ["pnpm install", "pnpm build", "pnpm test"]
    if pm == "yarn":
        return ["yarn install", "yarn build", "yarn test"]
    if pm == "npm":
        return ["npm install", "npm run build", "npm test"]
    return ["# definir stack antes de rodar comandos"]

def main():
    task = " ".join(sys.argv[1:]).strip()
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    if not task:
        print('Uso: ./jarvis local-exec-plan "tarefa"')
        sys.exit(1)

    project = pick_project(task)

    print("JARVIS — Theo Padilha AI Worker LOCAL_EXEC Plan")
    print("")
    print("Status real: plano local. Nenhum arquivo do projeto foi alterado.")
    print(f"Tarefa: {task}")
    print("")

    if not project:
        print("FALHA: nenhum projeto local encontrado.")
        sys.exit(1)

    path = project["path"]
    branch = run(["git", "branch", "--show-current"], cwd=path) if (path / ".git").exists() else "não é git"
    status = run(["git", "status", "--short"], cwd=path) if (path / ".git").exists() else "não é git"
    pm = package_manager(path)
    suggested = commands_for(pm)

    risk = "alto" if branch in ["main", "master"] else "médio"
    branch_action = "criar branch segura antes de editar" if branch in ["main", "master"] else "branch não é main/master; confirmar escopo antes de editar"

    lines = [
        "# LOCAL_EXEC Plan — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Tarefa\n{task}",
        "",
        "## Status real",
        "Plano local criado. Nenhum arquivo do projeto foi alterado.",
        "",
        f"## Projeto selecionado\n{project['name']}",
        "",
        f"## Caminho\n`{path}`",
        "",
        f"## Motivos\n{', '.join(project['reasons'])}",
        "",
        f"## Branch\n`{branch}`",
        "",
        "## Git status do projeto",
        "```text",
        status or "limpo",
        "```",
        "",
        f"## Package manager provável\n{pm}",
        "",
        f"## Risco inicial\n{risk}",
        "",
        "## Ação de branch",
        branch_action,
        "",
        "## Comandos sugeridos, ainda não executados",
        "```bash",
        *suggested,
        "```",
        "",
        "## Bloqueios",
        "- não editar main/master sem branch segura;",
        "- não fazer push;",
        "- não fazer merge;",
        "- não fazer deploy;",
        "- não abrir/copiar `.env`; usar apenas variáveis locais existentes;",
        "- não alterar produção.",
        "",
        "## Próximo passo seguro",
        "Gerar handoff para executor ou pedir autorização explícita para LOCAL_EXEC real em branch segura.",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    print(f"Projeto selecionado: {project['name']}")
    print(f"Caminho: {path}")
    print(f"Branch: {branch}")
    print(f"Git status: {status or 'limpo'}")
    print(f"Package manager provável: {pm}")
    print(f"Risco inicial: {risk}")
    print(f"Ação de branch: {branch_action}")
    print("")

    if no_report:
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        out = OUT_DIR / f"{ts}_{slugify(task)}_local-exec-plan.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Relatório: {out.relative_to(ROOT)}")

    print("")
    print("Próximo passo seguro: revisar plano antes de qualquer edição.")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
