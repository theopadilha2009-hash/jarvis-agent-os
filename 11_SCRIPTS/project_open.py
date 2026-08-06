"""
project_open.py — print safe instructions to open a registered project.

Default mode is `--print-only`: emit the exact `cd PATH; git status; claude`
block Theo can read or paste. Optional flags:
  --copy-cd    copy just the `cd PATH` line to the macOS clipboard via pbcopy
  --code       suggest `code PATH` (VS Code) if the `code` binary exists

Hard rules:
  - never edits files
  - never runs Claude
  - never runs build/test/migrations
  - never touches production
  - never reads .env
  - never prints secrets
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"


def fail(msg, code=1):
    print(f"FALHA: {msg}")
    sys.exit(code)


def parse_args(argv):
    alias = None
    mode = "print-only"
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            if i + 1 < len(argv):
                alias = argv[i + 1].strip().lower()
                i += 2
                continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--print-only":
            mode = "print-only"
            i += 1
            continue
        if a == "--copy-cd":
            mode = "copy-cd"
            i += 1
            continue
        if a == "--code":
            mode = "code"
            i += 1
            continue
        i += 1
    if not alias:
        fail("Uso: ./jarvis project-open --project ALIAS [--print-only|--copy-cd|--code]")
    return alias, mode


def load_project(alias):
    if not REGISTRY.exists():
        fail("PROJECT_REGISTRY.json não encontrado.")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    projects = {p["alias"]: p for p in registry.get("projects", [])}
    if alias not in projects:
        print(f"FALHA: alias não registrado: {alias}")
        print("Aliases:")
        for k in sorted(projects):
            print(f"- {k}")
        sys.exit(1)
    return projects[alias]


def resolve_project_path(project):
    path = Path(str(project["path"])).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _pbcopy(text: str) -> bool:
    if not shutil.which("pbcopy"):
        return False
    try:
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"), timeout=5)
        return p.returncode == 0
    except Exception:
        return False


def main():
    alias, mode = parse_args(sys.argv[1:])
    project = load_project(alias)
    path = resolve_project_path(project)

    print("JARVIS — Project Open (apenas instruções; nada executado)")
    print(f"Status real: leitura local. Nada foi editado.")
    print("")
    print(f"Project: {alias} -> {path}")
    if project.get("profile"):
        print(f"Profile: {project['profile']}")
    if project.get("package_manager"):
        print(f"Package manager: {project['package_manager']}")
    print("")
    print("=== Bloco seguro para Theo (copiar/colar) ===")
    print(f"cd {path}")
    print("git status --short")
    print("git branch --show-current")
    print("claude                       # abrir Claude Code manualmente")
    print(f"./jarvis project-cockpit --project {alias}  # cockpit pós-abertura")
    print("=============================================")
    print("")

    if mode == "copy-cd":
        ok = _pbcopy(f"cd {path}\n")
        if ok:
            print("clipboard: `cd PATH` copiado (pbcopy).")
        else:
            print("clipboard: NÃO foi possível copiar (pbcopy indisponível).")
            print(f'  fallback: echo "cd {path}" | pbcopy')
    elif mode == "code":
        if shutil.which("code"):
            print("Sugestão: abrir no VS Code:")
            print(f"  code {path}")
            print("(JARVIS NÃO executou `code` — apenas sugeriu.)")
        else:
            print("AVISO: binário `code` não encontrado no PATH.")
            print("Instale o VS Code CLI (Cmd+Shift+P → 'Install code command in PATH') antes de usar --code.")
    else:
        print("Modo: --print-only (default). Nada foi copiado ou aberto.")

    print("")
    print("O que JARVIS NÃO fez:")
    print("- não rodou Claude")
    print("- não rodou build/test/lint")
    print("- não tocou a tree do projeto")
    print("- não tocou produção / VPS / n8n")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
