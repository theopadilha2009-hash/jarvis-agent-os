from pathlib import Path
from datetime import datetime
import subprocess
import sys
import re

ROOT = Path(__file__).resolve().parents[1]

def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "workspace"

def run(cmd, cwd):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as e:
        return f"ERRO: {e}"

def main():
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.cwd()

    print("JARVIS — Theo Padilha AI Worker Workspace Check")
    print("")

    if not target.exists() or not target.is_dir():
        print(f"FALHA: pasta inválida: {target}")
        sys.exit(1)

    is_git = (target / ".git").exists()
    branch = run(["git", "branch", "--show-current"], target) if is_git else "sem git"
    status = run(["git", "status", "--short"], target) if is_git else "sem git"
    env_files = sorted([p.name for p in target.glob(".env*") if p.is_file()])
    package_json = (target / "package.json").exists()
    src_dir = (target / "src").exists()

    risk = "baixo"
    if branch in ["main", "master"] or env_files or (status not in ["", "sem git"]):
        risk = "médio"

    print(f"Pasta: {target}")
    print(f"Git: {'sim' if is_git else 'não'}")
    print(f"Branch: {branch}")
    print(f"Git status: {'limpo' if status == '' else status}")
    print(f".env encontrados: {', '.join(env_files) if env_files else 'nenhum'}")
    print(f"package.json: {'sim' if package_json else 'não'}")
    print(f"src: {'sim' if src_dir else 'não'}")
    print(f"Risco inicial: {risk}")
    print("")
    print("Regras:")
    print("- confirmar pasta certa")
    print("- não expor .env/credenciais")
    print("- evitar main/master")
    print("- branch segura antes de editar")
    print("- sem deploy/push/produção sem autorização")

    out_dir = ROOT / "05_EXECUCAO" / "04_WORKSPACE_CHECKS"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out = out_dir / f"{ts}_{slugify(target.name)}_workspace-check.md"

    report = [
        "# Workspace Check — JARVIS",
        "",
        f"## Pasta\n{target}",
        "",
        f"## Git\n{'sim' if is_git else 'não'}",
        "",
        f"## Branch\n{branch}",
        "",
        f"## Git status\n{'limpo' if status == '' else status}",
        "",
        f"## .env encontrados\n{', '.join(env_files) if env_files else 'nenhum'}",
        "",
        f"## package.json\n{'sim' if package_json else 'não'}",
        "",
        f"## src\n{'sim' if src_dir else 'não'}",
        "",
        f"## Risco inicial\n{risk}",
        "",
        "## Produção\nNada alterado.",
        "",
        "## Próximo passo seguro\nConfirmar branch, escopo e autorização antes de usar executor externo.",
    ]

    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("")
    print(f"Relatório salvo: {out.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
