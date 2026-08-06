"""
claude_helpers.py — local Claude Code workflow helpers (no API).

Sub-commands (selected via positional argv[0]):

  copy-latest [--project ALIAS]
      Find the latest mission prompt and pipe to pbcopy.
      Fails loud if no mission or pbcopy unavailable.

  launch --project ALIAS [--copy] [--print-only]
      Print the exact 'cd PATH; claude' block + paste instructions.
      Does NOT execute Claude. Theo runs it manually.

  save-report-template [--project ALIAS]
      Print the exact bash block for capturing Claude's final report into
      /tmp and feeding it back into project-memory-update / self-debrief.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
MISSIONS_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"


def fail(msg, code=1, to_stderr=False):
    stream = sys.stderr if to_stderr else sys.stdout
    print(f"FALHA: {msg}", file=stream)
    sys.exit(code)


def load_project(alias):
    if not REGISTRY.exists():
        fail("PROJECT_REGISTRY.json não encontrado.")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    projects = {p["alias"]: p for p in registry.get("projects", [])}
    if alias not in projects:
        print(f"FALHA: project alias não registrado: {alias}")
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


def find_latest_mission(alias=None):
    if not MISSIONS_DIR.exists():
        return None
    candidates = [d for d in MISSIONS_DIR.iterdir() if d.is_dir()]
    if alias:
        candidates = [d for d in candidates if f"project-{alias}_" in d.name]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


def parse_common(argv):
    alias = None
    copy_flag = False
    print_only = False
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
        if a == "--copy":
            copy_flag = True
            i += 1
            continue
        if a == "--print-only":
            print_only = True
            i += 1
            continue
        i += 1
    return alias, copy_flag, print_only


def _pbcopy_available():
    return shutil.which("pbcopy") is not None


def _copy_to_clipboard(text: str) -> bool:
    """Returns True on success."""
    if not _pbcopy_available():
        return False
    try:
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"), timeout=10)
        return p.returncode == 0
    except Exception:
        return False


# ── copy-latest ───────────────────────────────────────────────────────────────

def cmd_copy_latest(argv):
    alias, _copy, _print_only = parse_common(argv)
    print("JARVIS — Claude Copy Latest")
    print(f"Status real: leitura local. Nada foi editado.")
    print("")
    mission = find_latest_mission(alias)
    if mission is None:
        msg = f"nenhuma missão encontrada{' para alias=' + alias if alias else ''}."
        print(f"FALHA: {msg}")
        print('Gere uma com: ./jarvis self-evolve --goal "..." --copy')
        sys.exit(1)
    prompt = mission / "01_CLAUDE_PROMPT.md"
    if not prompt.exists():
        fail(f"01_CLAUDE_PROMPT.md ausente em {mission}")
    body = prompt.read_text(encoding="utf-8", errors="ignore")
    print(f"source: {prompt.relative_to(ROOT)}")
    print(f"bytes:  {len(body)}")
    if not _pbcopy_available():
        print("")
        print("AVISO: pbcopy não disponível neste sistema (macOS clipboard).")
        print("Fallback (copiar manualmente):")
        print(f'  cat "{prompt}" | pbcopy   # macOS')
        print(f'  cat "{prompt}" | xclip -selection clipboard   # Linux X11')
        print(f'  cat "{prompt}" | wl-copy   # Linux Wayland')
        sys.exit(2)
    ok = _copy_to_clipboard(body)
    if not ok:
        fail("pbcopy falhou.")
    print("OK — copiado para o clipboard.")
    print("")
    print("Próximo passo: abra Claude Code, cole, deixe Claude executar.")
    print("Produção: nada alterado.")


# ── launch ────────────────────────────────────────────────────────────────────

def cmd_launch(argv):
    alias, copy_flag, _print_only = parse_common(argv)
    if not alias:
        fail("--project ALIAS é obrigatório para claude-launch.")
    project = load_project(alias)
    path = resolve_project_path(project)
    print("JARVIS — Claude Launch (print-only; JARVIS não executa Claude)")
    print(f"Status real: imprimindo comandos. Nada foi executado por JARVIS.")
    print("")
    print(f"Project: {alias} -> {path}")
    print("")
    if copy_flag:
        # Try to copy latest mission first.
        mission = find_latest_mission(alias)
        if mission is None:
            print(f"⚠ --copy pediu copiar última missão, mas nenhuma existe para {alias}.")
            print(f'  Gere uma com: ./jarvis self-evolve --goal "..." --copy')
        else:
            prompt = mission / "01_CLAUDE_PROMPT.md"
            body = prompt.read_text(encoding="utf-8", errors="ignore") if prompt.exists() else ""
            ok = _pbcopy_available() and _copy_to_clipboard(body)
            if ok:
                print(f"clipboard: copiado {prompt.relative_to(ROOT)} ({len(body)} bytes)")
            else:
                print(f"clipboard: NÃO copiado automaticamente.")
                print(f'  fallback: cat "{prompt}" | pbcopy')
    print("")
    print("=== Bloco de comandos para Theo executar ===")
    print(f"cd {path}")
    print("claude")
    print("# (no Claude Code) cole a missão")
    print("# Claude executa")
    print("# salve a resposta final em arquivo:")
    print("cat > /tmp/jarvis-claude-out.md")
    print("# (cole o relatório final, Ctrl+D para fechar)")
    if alias == "jarvis-core":
        print("./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --dry-run")
        print("./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --apply")
        print("./jarvis self-cockpit")
    else:
        print(f"./jarvis project-memory-update --project {alias} --from-file /tmp/jarvis-claude-out.md --dry-run")
        print(f"./jarvis project-memory-update --project {alias} --from-file /tmp/jarvis-claude-out.md --apply")
        print(f"./jarvis project-cockpit --project {alias}")
    print("=============================================")
    print("")
    print("Produção: nada alterado. JARVIS apenas imprimiu instruções.")


# ── save-report-template ──────────────────────────────────────────────────────

def cmd_save_template(argv):
    alias, _copy, _print_only = parse_common(argv)
    target_alias = alias or "jarvis-core"
    is_self = target_alias == "jarvis-core"
    print("JARVIS — Claude Save-Report Template")
    print(f"Status real: imprimindo template. Nada foi escrito.")
    print("")
    print(f"Project alias: {target_alias}")
    print("")
    print("Após Claude executar, copie/cole o bloco abaixo no terminal:")
    print("")
    print("```bash")
    print("cat > /tmp/jarvis-claude-out.md")
    print("# (cole o relatório final do Claude, depois Ctrl+D)")
    if is_self:
        print("./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --dry-run")
        print("./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --apply")
        print("./jarvis self-cockpit")
    else:
        print(f"./jarvis project-memory-update --project {target_alias} --from-file /tmp/jarvis-claude-out.md --dry-run")
        print(f"./jarvis project-memory-update --project {target_alias} --from-file /tmp/jarvis-claude-out.md --apply")
        print(f"./jarvis project-cockpit --project {target_alias}")
    print("```")
    print("")
    print("Produção: nada alterado.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: claude_helpers.py <copy-latest|launch|save-report-template> [flags]")
        sys.exit(1)
    sub = argv[0]
    rest = argv[1:]
    if sub == "copy-latest":
        cmd_copy_latest(rest)
    elif sub == "launch":
        cmd_launch(rest)
    elif sub == "save-report-template":
        cmd_save_template(rest)
    else:
        print(f"FALHA: subcomando desconhecido: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
