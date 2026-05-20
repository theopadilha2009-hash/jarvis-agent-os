from pathlib import Path
from datetime import datetime
import subprocess
import sys
import re

ROOT = Path(__file__).resolve().parents[1]

def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "workspace-scan"

def run(cmd, cwd):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as e:
        return f"ERRO: {e}"

def detect_projects(base):
    candidates = []
    ignore = {".git", "node_modules", "__pycache__", ".next", "dist", "build", ".cache"}

    for p in sorted(base.iterdir()):
        if not p.is_dir() or p.name in ignore or p.name.startswith("."):
            continue

        score = 0
        reasons = []

        if (p / ".git").exists():
            score += 5
            reasons.append("git")
        if (p / "package.json").exists():
            score += 3
            reasons.append("package.json")
        if (p / "src").exists():
            score += 2
            reasons.append("src")
        if list(p.glob("*.json")):
            score += 1
            reasons.append("json")
        if list(p.glob("*.md")):
            score += 1
            reasons.append("docs")

        if score > 0:
            candidates.append((p, score, reasons))

    return candidates

def main():
    base = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.cwd()

    print("JARVIS — Theo Padilha AI Worker Workspace Scan")
    print("")

    if not base.exists() or not base.is_dir():
        print(f"FALHA: pasta inválida: {base}")
        sys.exit(1)

    projects = detect_projects(base)

    out_dir = ROOT / "05_EXECUCAO" / "05_WORKSPACE_SCANS"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out = out_dir / f"{ts}_{slugify(base.name)}_workspace-scan.md"

    lines = [
        "# Workspace Scan — JARVIS",
        "",
        f"## Pasta base\n{base}",
        "",
        f"## Projetos detectados\n{len(projects)}",
        "",
    ]

    for p, score, reasons in projects:
        is_git = (p / ".git").exists()
        branch = run(["git", "branch", "--show-current"], p) if is_git else "sem git"
        status = run(["git", "status", "--short"], p) if is_git else "sem git"
        env_files = sorted([x.name for x in p.glob(".env*") if x.is_file()])

        risk = "baixo"
        if branch in ["main", "master"] or env_files or (status not in ["", "sem git"]):
            risk = "médio"

        print(f"- {p.name}")
        print(f"  Caminho: {p}")
        print(f"  Score: {score}")
        print(f"  Motivos: {', '.join(reasons)}")
        print(f"  Branch: {branch}")
        print(f"  Git status: {'limpo' if status == '' else status}")
        print(f"  Risco: {risk}")
        print("")

        lines += [
            f"## {p.name}",
            f"- Caminho: `{p}`",
            f"- Score: {score}",
            f"- Motivos: {', '.join(reasons)}",
            f"- Git: {'sim' if is_git else 'não'}",
            f"- Branch: {branch}",
            f"- Git status: {'limpo' if status == '' else status}",
            f"- .env encontrados: {', '.join(env_files) if env_files else 'nenhum'}",
            f"- Risco inicial: {risk}",
            "",
        ]

    lines += [
        "## Produção",
        "Nada alterado.",
        "",
        "## Próximo passo seguro",
        "Rodar `./jarvis workspace-check CAMINHO_DO_PROJETO` no projeto escolhido antes de usar Claude/Gemini/VS Code.",
    ]

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Relatório salvo: {out.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
