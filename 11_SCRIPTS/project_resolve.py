from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"

def run(cmd, cwd):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=10).strip()
    except Exception:
        return ""

def load_registry():
    if not REGISTRY.exists():
        print("FALHA: PROJECT_REGISTRY.json não encontrado.")
        sys.exit(1)

    return json.loads(REGISTRY.read_text(encoding="utf-8"))

def print_project(pr):
    path = Path(pr["path"])
    is_git = (path / ".git").exists() if path.exists() else False
    branch = run(["git", "branch", "--show-current"], path) if is_git else "unknown"
    status = run(["git", "status", "--short"], path) if is_git else "not-git"

    print(f"Alias: {pr['alias']}")
    print(f"Nome: {pr['name']}")
    print(f"Caminho: {pr['path']}")
    print(f"Existe: {path.exists()}")
    print(f"Git: {is_git}")
    print(f"Branch atual: {branch or 'unknown'}")
    print(f"Git status: {status or 'limpo'}")
    print(f"Package manager: {pr.get('package_manager', 'unknown')}")
    print(f"LOCAL_EXEC permitido: {pr.get('allowed_for_local_exec', False)}")
    print("")

def main():
    registry = load_registry()
    projects = registry.get("projects", [])
    aliases = {p["alias"]: p for p in projects}

    print("JARVIS — Theo Padilha AI Worker Project Resolve")
    print("")
    print("Status real: resolução local de projeto. Nenhum projeto foi editado.")
    print("")

    if len(sys.argv) < 2:
        print("Projetos disponíveis:")
        print("")
        for pr in projects:
            print(f"- {pr['alias']} -> {pr['name']}")
        print("")
        print('Uso: ./jarvis project-resolve oficina')
        print('Uso: ./jarvis project-resolve gc')
        return

    alias = sys.argv[1].strip().lower()

    if alias not in aliases:
        print(f"FALHA: alias não registrado: {alias}")
        print("")
        print("Aliases disponíveis:")
        for key in aliases:
            print(f"- {key}")
        sys.exit(1)

    pr = aliases[alias]
    print_project(pr)

    if not pr.get("allowed_for_local_exec", False):
        print("Resultado: PROJECT RESOLVE COM PENDÊNCIAS")
        print("Motivo: projeto não permitido para LOCAL_EXEC.")
        sys.exit(1)

    print("Resultado: PROJECT RESOLVE PASSOU")
    print("Próximo passo seguro:")
    print(f'./jarvis local-exec-session --project {alias} "tarefa sem deploy"')
    print("")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
