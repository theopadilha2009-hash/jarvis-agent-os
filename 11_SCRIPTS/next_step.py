from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"

def run(cmd, cwd=ROOT):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=10).strip()
    except Exception:
        return ""

def latest(folder, pattern="*"):
    base = ROOT / folder
    if not base.exists():
        return None
    items = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None

def rel(path):
    if not path:
        return "nenhum"
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)

def load_registry():
    if not REGISTRY.exists():
        return {"projects": []}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))

def project_state(pr):
    path = Path(pr["path"])
    exists = path.exists()
    is_git = (path / ".git").exists() if exists else False
    branch = run(["git", "branch", "--show-current"], path) if is_git else "unknown"
    status = run(["git", "status", "--short"], path) if is_git else "not-git"
    clean = status == "" if is_git else False

    if not exists:
        state = "faltando"
    elif not is_git:
        state = "não-git"
    elif clean:
        state = "pronto"
    else:
        state = "revisar"

    return {
        "state": state,
        "branch": branch or "unknown",
        "status": status or "limpo",
        "clean": clean,
    }

def print_projects(projects):
    print("Projetos:")
    print("")
    for pr in projects:
        st = project_state(pr)
        print(f"- {pr['alias']}: {pr['name']} | {st['state']} | branch {st['branch']} | {pr.get('package_manager', 'unknown')}")
    print("")

def main():
    registry = load_registry()
    projects = registry.get("projects", [])
    aliases = {p["alias"]: p for p in projects}

    alias = sys.argv[1].strip().lower() if len(sys.argv) > 1 else None

    print("JARVIS — Theo Padilha AI Worker Next Step")
    print("")
    print("Status real: orientação local. Nenhum projeto foi editado.")
    print("")

    head = run(["git", "rev-parse", "--short", "HEAD"]) or "unknown"
    status = run(["git", "status", "--short"]) or "limpo"

    print("Base JARVIS:")
    print(f"- commit: {head}")
    print(f"- git: {status}")
    print("")

    print("Últimos artefatos:")
    print(f"- sessão LOCAL_EXEC: {rel(latest('05_EXECUCAO/18_LOCAL_EXEC_SESSIONS', '*.md'))}")
    print(f"- handoff LOCAL_EXEC: {rel(latest('05_EXECUCAO/15_LOCAL_EXEC_HANDOFFS', '*'))}")
    print(f"- review LOCAL_EXEC: {rel(latest('05_EXECUCAO/16_LOCAL_EXEC_REVIEWS', '*.md'))}")
    print("")

    if not alias:
        print_projects(projects)
        print("Opções agora:")
        print("1. Ver menu de projetos:")
        print("   ./jarvis project-menu")
        print("")
        print("2. Ver projeto específico:")
        print("   ./jarvis project-menu oficina")
        print("")
        print("3. Validar projeto antes de tarefa:")
        print("   ./jarvis project-resolve oficina")
        print("")
        print("4. Preparar tarefa segura travada no projeto:")
        print('   ./jarvis local-exec-session --project oficina "descrever tarefa sem deploy"')
        print("")
        print("5. Ver último handoff:")
        print("   ./jarvis local-exec-handoff-latest")
        print("")
        print("Decisão recomendada:")
        print("- Se ainda não sabe o projeto: rode ./jarvis project-menu")
        print("- Se já sabe o projeto: rode ./jarvis project-menu ALIAS")
        print("")
        print("Produção: nada alterado.")
        return

    if alias not in aliases:
        print(f"FALHA: alias não registrado: {alias}")
        print("")
        print("Use:")
        print("./jarvis project-menu")
        sys.exit(1)

    pr = aliases[alias]
    st = project_state(pr)

    print(f"Projeto selecionado: {alias}")
    print(f"- nome: {pr['name']}")
    print(f"- caminho: {pr['path']}")
    print(f"- estado: {st['state']}")
    print(f"- branch: {st['branch']}")
    print(f"- git: {st['status']}")
    print(f"- package: {pr.get('package_manager', 'unknown')}")
    print("")

    print("Opções para este projeto:")
    print("1. Conferir alias e caminho:")
    print(f"   ./jarvis project-resolve {alias}")
    print("")
    print("2. Preparar sessão LOCAL_EXEC:")
    print(f'   ./jarvis local-exec-session --project {alias} "descrever tarefa sem deploy"')
    print("")
    print("3. Abrir último handoff depois da sessão:")
    print("   ./jarvis local-exec-handoff-latest")
    print("")
    print("4. Revisar saída de executor depois:")
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
