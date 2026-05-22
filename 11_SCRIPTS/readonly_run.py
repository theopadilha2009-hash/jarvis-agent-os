from pathlib import Path
from datetime import datetime
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "12_READONLY_RUNS"
PROJECT_ROOTS = [
    Path.home() / "VAMOO_PROJETOS",
    Path.home() / "Theo",
]

SKIP_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", ".turbo",
    "__pycache__", ".venv", "venv", ".cache"
}

SECRET_NAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "id_rsa", "id_ed25519"
}

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "readonly-run"

def run(cmd, cwd):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=20).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()
    except Exception as e:
        return f"ERRO: {e}"


def is_secret_like_name(name):
    low = name.lower()
    return (
        low.startswith(".env")
        or low in {"id_rsa", "id_ed25519"}
        or low.endswith((".pem", ".key", ".p12", ".pfx"))
        or "token" in low
        or "secret" in low
        or "credential" in low
        or "credencial" in low
    )

def display_name(path):
    if is_secret_like_name(path.name):
        return "[SECRET-LIKE FILE HIDDEN]"
    return path.name

def safe_read(path, max_chars=8000):
    if is_secret_like_name(path.name):
        return "[SKIPPED SECRET-LIKE FILE]"
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:max_chars]
    except Exception as e:
        return f"[READ ERROR: {e}]"

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
            if any(p.glob("*.json")):
                score += 1
                reasons.append("json")
            if (p / "README.md").exists():
                score += 1
                reasons.append("readme")

            if score > 0:
                projects.append({
                    "path": p,
                    "name": p.name,
                    "score": score,
                    "reasons": reasons,
                })

    return sorted(projects, key=lambda x: x["score"], reverse=True)

def pick_project(task):
    task_l = task.lower()
    projects = find_projects()

    if not projects:
        return None, []

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
    return scored[0][1], scored

def tree_snapshot(path, max_items=80):
    items = []

    for child in sorted(path.iterdir(), key=lambda x: x.name.lower()):
        if child.name in SKIP_DIRS or child.name.startswith(".DS_Store"):
            continue
        marker = "/" if child.is_dir() else ""
        name = display_name(child)
        rendered = name + marker
        if name == "[SECRET-LIKE FILE HIDDEN]" and any("[SECRET-LIKE FILE HIDDEN]" in x for x in items):
            continue
        items.append(rendered)
        if len(items) >= max_items:
            break

    return items

def package_info(path):
    pkg = path / "package.json"
    if not pkg.exists():
        return "package.json não encontrado"

    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Erro lendo package.json: {e}"

    lines = []
    lines.append(f"name: {data.get('name', 'não informado')}")
    lines.append(f"version: {data.get('version', 'não informada')}")

    scripts = data.get("scripts") or {}
    if scripts:
        lines.append("scripts:")
        for k, v in scripts.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("scripts: nenhum")

    deps = list((data.get("dependencies") or {}).keys())
    dev = list((data.get("devDependencies") or {}).keys())

    lines.append(f"dependencies: {len(deps)}")
    lines.append(f"devDependencies: {len(dev)}")

    return "\n".join(lines)

def env_check(path):
    hits = []
    for p in path.iterdir():
        if is_secret_like_name(p.name):
            hits.append("[SECRET-LIKE FILE HIDDEN]")

    if not hits:
        return "Nenhum arquivo secret-like no root detectado."

    return f"{len(hits)} arquivo(s) secret-like detectado(s) no root. Nomes e conteúdos ocultados."

def main():
    task = " ".join(sys.argv[1:]).strip()
    if not task:
        print('Uso: ./jarvis readonly-run "tarefa"')
        sys.exit(1)

    project, scored = pick_project(task)

    print("JARVIS — Theo Padilha AI Worker READONLY RUN")
    print("")
    print("Status real: inspeção local read-only. Nada alterado.")
    print(f"Tarefa: {task}")
    print("")

    if not project:
        print("FALHA: nenhum projeto local encontrado.")
        sys.exit(1)

    path = project["path"]
    print(f"Projeto selecionado: {project['name']}")
    print(f"Caminho: {path}")
    print(f"Motivos: {', '.join(project['reasons'])}")
    print("")

    git_branch = run(["git", "branch", "--show-current"], cwd=path) if (path / ".git").exists() else "não é git"
    git_status = run(["git", "status", "--short"], cwd=path) if (path / ".git").exists() else "não é git"
    git_log = run(["git", "log", "--oneline", "-5"], cwd=path) if (path / ".git").exists() else "não é git"

    top = tree_snapshot(path)
    pkg = package_info(path)
    env = env_check(path)
    readme = safe_read(path / "README.md", max_chars=3000) if (path / "README.md").exists() else "README.md não encontrado"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out = OUT_DIR / f"{ts}_{slugify(task)}_readonly-run.md"

    lines = [
        "# READONLY RUN — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Tarefa\n{task}",
        "",
        "## Status real",
        "Inspeção local read-only. Nada alterado no projeto real.",
        "",
        f"## Projeto selecionado\n{project['name']}",
        "",
        f"## Caminho\n`{path}`",
        "",
        f"## Motivos\n{', '.join(project['reasons'])}",
        "",
        "## Git branch",
        "```text",
        git_branch or "sem branch",
        "```",
        "",
        "## Git status",
        "```text",
        git_status or "limpo",
        "```",
        "",
        "## Últimos commits",
        "```text",
        git_log or "não disponível",
        "```",
        "",
        "## Estrutura root",
        *[f"- {x}" for x in top],
        "",
        "## package.json",
        "```text",
        pkg,
        "```",
        "",
        "## Secret-like file check",
        env,
        "",
        "## README preview",
        "```text",
        readme,
        "```",
        "",
        "## Próximo passo seguro",
        "Se for continuar: gerar executor-handoff ou task-brief. Não editar sem mudar para LOCAL_EXEC/INFRA_EXEC/PRODUCTION_ARMED conforme o caso.",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Branch: {git_branch or 'sem branch'}")
    print(f"Git status: {git_status or 'limpo'}")
    print(f"Relatório: {out.relative_to(ROOT)}")
    print("")
    print("Próximo passo seguro: revisar relatório e só depois decidir modo seguinte.")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
