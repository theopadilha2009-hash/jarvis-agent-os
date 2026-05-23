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

def project_state(pr):
    path = Path(pr["path"])
    exists = path.exists()
    is_git = (path / ".git").exists() if exists else False
    branch = run(["git", "branch", "--show-current"], path) if is_git else "unknown"
    status = run(["git", "status", "--short"], path) if is_git else "not-git"
    clean = status == "" if is_git else False

    return {
        "exists": exists,
        "is_git": is_git,
        "branch": branch or "unknown",
        "clean": clean,
        "status": status or "limpo",
    }

def print_card(pr):
    st = project_state(pr)
    status = "pronto" if st["exists"] and st["is_git"] and st["clean"] else "revisar"

    print(f"[{pr['alias']}] {pr['name']}")
    print(f"  status: {status}")
    print(f"  caminho: {pr['path']}")
    print(f"  branch: {st['branch']}")
    print(f"  git: {'limpo' if st['clean'] else st['status']}")
    print(f"  package: {pr.get('package_manager', 'unknown')}")
    print("")

def main():
    registry = load_registry()
    projects = registry.get("projects", [])
    aliases = {p["alias"]: p for p in projects}

    print("JARVIS — Theo Padilha AI Worker Project Menu")
    print("")
    print("Status real: menu local. Nenhum projeto foi editado.")
    print("")

    if len(sys.argv) < 2:
        print("Projetos disponíveis:")
        print("")
        for pr in projects:
            print_card(pr)

        print("Opções:")
        print("1. Ver projeto:")
        print("   ./jarvis project-menu oficina")
        print("")
        print("2. Validar projeto:")
        print("   ./jarvis project-resolve oficina")
        print("")
        print("3. Preparar sessão LOCAL_EXEC travada:")
        print('   ./jarvis local-exec-session --project oficina "descrever tarefa sem deploy"')
        print("")
        print("4. Ver último handoff:")
        print("   ./jarvis local-exec-handoff-latest")
        print("")
        print("Produção: nada alterado.")
        return

    alias = sys.argv[1].strip().lower()

    if alias not in aliases:
        print(f"FALHA: alias não registrado: {alias}")
        print("")
        print("Aliases disponíveis:")
        for key in sorted(aliases):
            print(f"- {key}")
        sys.exit(1)

    pr = aliases[alias]
    st = project_state(pr)

    print_card(pr)
    print("Ações recomendadas:")
    print("")
    print("1. Conferir projeto:")
    print(f"   ./jarvis project-resolve {alias}")
    print("")
    print("2. Preparar tarefa segura:")
    print(f'   ./jarvis local-exec-session --project {alias} "descrever tarefa sem deploy"')
    print("")
    print("3. Ver handoff depois da sessão:")
    print("   ./jarvis local-exec-handoff-latest")
    print("")
    print("4. Revisar resposta do executor depois:")
    print("   ./jarvis local-exec-review caminho/da/resposta.md")
    print("")
    print("Travas:")
    print("- sem push")
    print("- sem merge")
    print("- sem deploy")
    print("- sem VPS/n8n/produção")
    print("- Claude opcional, não obrigatório")
    print("")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
