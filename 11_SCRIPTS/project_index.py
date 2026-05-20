from pathlib import Path
from datetime import datetime
import subprocess
import sys
import json
import re

ROOT = Path(__file__).resolve().parents[1]

def run(cmd, cwd):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except Exception:
        return ""

def classify_project(p):
    if (p / "package.json").exists() and (p / "src").exists():
        return "web-app/código"
    if list(p.glob("*.workflow.json")) or (p / "03_OUTPUT").exists():
        return "n8n/workflow"
    if list(p.glob("*.md")) and not (p / "package.json").exists():
        return "docs/memória"
    return "geral"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "project-index"

def main():
    base = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path("~/VAMOO_PROJETOS").expanduser()

    if not base.exists():
        print(f"FALHA: pasta não existe: {base}")
        sys.exit(1)

    projects = []
    for p in sorted(base.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue

        is_git = (p / ".git").exists()
        if not is_git and not (p / "package.json").exists() and not list(p.glob("*.md")) and not (p / "03_OUTPUT").exists():
            continue

        branch = run(["git", "branch", "--show-current"], p) if is_git else "sem git"
        status = run(["git", "status", "--short"], p) if is_git else "sem git"
        env_files = sorted([x.name for x in p.glob(".env*") if x.is_file()])

        risk = "baixo"
        if branch in ["main", "master"] or status or env_files:
            risk = "médio"

        projects.append({
            "name": p.name,
            "path": str(p),
            "type": classify_project(p),
            "git": is_git,
            "branch": branch,
            "status": "limpo" if status == "" else status,
            "env_files": env_files,
            "risk": risk,
            "next": f"./jarvis workspace-check {p}",
        })

    out_dir = ROOT / "04_PROJETOS" / "_INDEX"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_file = out_dir / "PROJECT_INDEX.json"
    md_file = out_dir / "PROJECT_INDEX.md"

    json_file.write_text(json.dumps(projects, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Project Index — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Base analisada\n{base}",
        "",
        f"## Projetos detectados\n{len(projects)}",
        "",
    ]

    for prj in projects:
        lines += [
            f"## {prj['name']}",
            f"- Caminho: `{prj['path']}`",
            f"- Tipo: {prj['type']}",
            f"- Git: {'sim' if prj['git'] else 'não'}",
            f"- Branch: {prj['branch']}",
            f"- Status: {prj['status']}",
            f"- .env: {', '.join(prj['env_files']) if prj['env_files'] else 'nenhum'}",
            f"- Risco: {prj['risk']}",
            f"- Próximo comando: `{prj['next']}`",
            "",
        ]

    lines += [
        "## Produção",
        "Nada alterado.",
        "",
        "## Próximo passo seguro",
        "Escolher um projeto e rodar workspace-check antes de usar Claude/Gemini/VS Code.",
    ]

    md_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Projetos indexados: {len(projects)}")
    print(f"MD: {md_file.relative_to(ROOT)}")
    print(f"JSON: {json_file.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
