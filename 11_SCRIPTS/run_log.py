"""
run_log.py — local run-log packages for `./jarvis go` (no Git dirt).

Each `./jarvis go` invocation (by default) creates a small folder of 6
markdown files describing what JARVIS interpreted and which manual
steps Theo should run. The folder is GITIGNORED so the working tree
stays clean.

Sub-commands:
  list                  list latest runs
  show latest|ID        print a run's files
  latest                alias of `show latest`

Programmatic API (used by jarvis_core.go_command via subprocess):
  create  --request "..."  [--project ALIAS] [--intent X] [--safety Y]
          [--next-command "..."]  [--mission-type "..."]
          [--print-path]        # print just the created folder path on stdout

Hard rules:
  - never writes to the target project
  - never reads .env
  - refuses to create a package if the request text looks secret-like
  - directory tree is gitignored except .gitkeep
"""
from pathlib import Path
from datetime import datetime
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "05_EXECUCAO" / "35_RUNS"

try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []


def _looks_secret_like(text: str) -> bool:
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(text or ""):
            return True
    return False


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "run"


def _debrief_block(project: str) -> str:
    """Render the right debrief command depending on whether the work is on
    JARVIS itself or on a target project."""
    if project == "jarvis-core":
        return (
            "./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --dry-run\n"
            "./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --apply\n"
        )
    if project:
        return (
            f"./jarvis project-memory-update --project {project} --from-file /tmp/claude-out.md --dry-run\n"
            f"./jarvis project-memory-update --project {project} --from-file /tmp/claude-out.md --apply\n"
        )
    # Unknown project — give the safer self-debrief form as default; Theo can
    # swap aliases manually.
    return (
        "./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --dry-run\n"
        "./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --apply\n"
    )


# ── create ────────────────────────────────────────────────────────────────────

def _parse_create_args(argv):
    request = ""
    project = ""
    intent = ""
    safety = ""
    next_cmd = ""
    mission_type = ""
    print_path = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--request" and i + 1 < len(argv):
            request = argv[i + 1]
            i += 2
            continue
        if a == "--project" and i + 1 < len(argv):
            project = argv[i + 1]
            i += 2
            continue
        if a == "--intent" and i + 1 < len(argv):
            intent = argv[i + 1]
            i += 2
            continue
        if a == "--safety" and i + 1 < len(argv):
            safety = argv[i + 1]
            i += 2
            continue
        if a == "--next-command" and i + 1 < len(argv):
            next_cmd = argv[i + 1]
            i += 2
            continue
        if a == "--mission-type" and i + 1 < len(argv):
            mission_type = argv[i + 1]
            i += 2
            continue
        if a == "--print-path":
            print_path = True
            i += 1
            continue
        i += 1
    return request, project, intent, safety, next_cmd, mission_type, print_path


def cmd_create(argv):
    request, project, intent, safety, next_cmd, mission_type, print_path = _parse_create_args(argv)
    if not request:
        print("FALHA: --request obrigatório.")
        sys.exit(1)
    if _looks_secret_like(request):
        print("FALHA: request parece conter segredo. NÃO criamos run package.")
        sys.exit(2)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    slug = _slugify(request)
    target = RUNS_DIR / f"{ts}_{slug}"
    target.mkdir(parents=True, exist_ok=True)

    (target / "01_REQUEST.md").write_text(
        "# Request\n\n"
        f'"{request}"\n', encoding="utf-8")
    (target / "02_INTERPRETATION.md").write_text(
        "# Interpretation\n\n"
        f"- intent: {intent or '(?)'}\n"
        f"- project: {project or '(não detectado)'}\n"
        f"- safety: {safety or '(?)'}\n"
        f"- mission type sugerida: {mission_type or '(?)'}\n", encoding="utf-8")
    (target / "03_NEXT_COMMAND.md").write_text(
        "# Next command (seguro, local)\n\n"
        f"  {next_cmd or '(?)'} \n", encoding="utf-8")
    (target / "04_CLAUDE_LAUNCH.md").write_text(
        "# Claude launch (Theo executa manualmente)\n\n"
        f"```\n"
        f"cd {ROOT}\n"
        f"claude\n"
        f"# (cole a missão; Claude executa)\n"
        f"```\n", encoding="utf-8")
    (target / "05_DEBRIEF_INSTRUCTIONS.md").write_text(
        "# Debrief\n\n"
        "```\n"
        "cat > /tmp/jarvis-claude-out.md   # cole o RELATÓRIO FINAL e Ctrl+D\n"
        + _debrief_block(project)
        + "./jarvis self-cockpit\n"
        "env JARVIS_NO_REPORT=1 ./jarvis safety-gate\n"
        "env JARVIS_NO_REPORT=1 ./jarvis smoke-test\n"
        "./jarvis doctrine-check\n"
        "```\n", encoding="utf-8")
    (target / "06_STATUS_REAL.md").write_text(
        "# Status real\n\n"
        f"- Created: run package em {target.relative_to(ROOT)}\n"
        "- Modified: nada fora deste run package\n"
        "- Tested: nada\n"
        "- Not validated: Claude ainda não executou\n"
        "- Production: nada alterado\n", encoding="utf-8")

    if print_path:
        # Stdout is just the path so the caller can capture it.
        sys.stdout.write(str(target.relative_to(ROOT)) + "\n")
    else:
        print(f"OK — run package criado em {target.relative_to(ROOT)}/")


# ── list / show ───────────────────────────────────────────────────────────────

def _all_runs():
    if not RUNS_DIR.exists():
        return []
    return sorted([d for d in RUNS_DIR.iterdir() if d.is_dir() and d.name != ".gitkeep"],
                  key=lambda d: d.stat().st_mtime)


def cmd_list(argv):
    print("JARVIS — Run List")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    runs = _all_runs()
    print(f"diretório: {RUNS_DIR.relative_to(ROOT)} (gitignored)")
    print(f"runs: {len(runs)}")
    print("")
    for r in runs[-30:]:
        req_file = r / "01_REQUEST.md"
        first = "(sem REQUEST.md)"
        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    first = s
                    break
        print(f"- {r.name}")
        print(f"    {first}")
    if len(runs) > 30:
        print(f"... (+{len(runs) - 30} runs anteriores)")
    print("")
    print("Produção: nada alterado.")


def _resolve_run(ref: str):
    if ref == "latest":
        runs = _all_runs()
        if not runs:
            return None
        return runs[-1]
    # Match exact or prefix
    if not RUNS_DIR.exists():
        return None
    for d in _all_runs():
        if d.name == ref or d.name.startswith(ref):
            return d
    return None


def cmd_show(argv):
    print("JARVIS — Run Show")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    if not argv:
        print("Uso: ./jarvis run-show latest|ID")
        sys.exit(1)
    ref = argv[0]
    run = _resolve_run(ref)
    if run is None:
        print(f"FALHA: run não encontrado: {ref}")
        sys.exit(1)
    print(f"run: {run.relative_to(ROOT)}")
    print("")
    for name in ("01_REQUEST.md", "02_INTERPRETATION.md", "03_NEXT_COMMAND.md",
                 "04_CLAUDE_LAUNCH.md", "05_DEBRIEF_INSTRUCTIONS.md", "06_STATUS_REAL.md"):
        f = run / name
        print(f"## {name}")
        if not f.exists():
            print("  (ausente)")
        else:
            print(f.read_text(encoding="utf-8", errors="ignore"))
        print("")
    print("Produção: nada alterado.")


def cmd_latest(argv):
    cmd_show(["latest"])


# ── prune ─────────────────────────────────────────────────────────────────────

def _parse_prune_args(argv):
    keep = 20
    apply_changes = False
    dry_run = True
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--keep" and i + 1 < len(argv):
            try:
                keep = max(0, int(argv[i + 1]))
            except Exception:
                pass
            i += 2
            continue
        if a.startswith("--keep="):
            try:
                keep = max(0, int(a.split("=", 1)[1]))
            except Exception:
                pass
            i += 1
            continue
        if a == "--apply":
            apply_changes = True
            dry_run = False
            i += 1
            continue
        if a == "--dry-run":
            dry_run = True
            apply_changes = False
            i += 1
            continue
        i += 1
    return keep, apply_changes, dry_run


def _safe_under_runs(p: Path) -> bool:
    """Hard safety: refuse to touch anything outside RUNS_DIR."""
    try:
        # resolve() collapses symlinks so /runs/foo/../../etc isn't 'inside'.
        return RUNS_DIR.resolve() in p.resolve().parents or p.resolve().parent == RUNS_DIR.resolve()
    except Exception:
        return False


def cmd_prune(argv):
    keep, apply_changes, dry_run = _parse_prune_args(argv)
    print("JARVIS — Run Prune")
    print("Status real: limpeza local de run packages. Nada em produção.")
    print("")
    if not RUNS_DIR.exists():
        print(f"(diretório ausente: {RUNS_DIR.relative_to(ROOT)})")
        print("Produção: nada alterado.")
        return
    runs = _all_runs()
    print(f"diretório: {RUNS_DIR.relative_to(ROOT)}")
    print(f"runs totais: {len(runs)}")
    print(f"--keep: {keep}")
    to_delete = runs[:-keep] if keep > 0 else list(runs)
    to_keep = runs[-keep:] if keep > 0 else []
    print(f"a manter: {len(to_keep)} mais novos")
    print(f"a remover: {len(to_delete)} mais antigos")
    print("")
    if not to_delete:
        print("(nada a remover — total ≤ keep)")
        print("Produção: nada alterado.")
        return

    print("## Candidatos a remoção")
    for d in to_delete[-30:]:
        print(f"  - {d.relative_to(ROOT)}")
    if len(to_delete) > 30:
        print(f"  ... (+{len(to_delete) - 30} pastas mais antigas)")
    print("")

    if dry_run or not apply_changes:
        print("Modo: --dry-run (nada removido).")
        print("Para remover de verdade: ./jarvis run-prune --keep N --apply")
        print("Produção: nada alterado.")
        return

    import shutil
    removed = 0
    for d in to_delete:
        if d.name == ".gitkeep":
            continue
        if not _safe_under_runs(d):
            print(f"AVISO: caminho suspeito, pulando: {d}")
            continue
        try:
            shutil.rmtree(d)
            removed += 1
        except Exception as e:
            print(f"AVISO: falha removendo {d.name}: {e}")
    print(f"OK — removidas {removed} pasta(s).")
    print("Produção: nada alterado.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: run_log.py <create|list|show|latest> [args]")
        sys.exit(1)
    sub = argv[0]
    rest = argv[1:]
    if sub == "create":
        cmd_create(rest)
    elif sub == "list":
        cmd_list(rest)
    elif sub == "show":
        cmd_show(rest)
    elif sub == "latest":
        cmd_latest(rest)
    elif sub == "prune":
        cmd_prune(rest)
    else:
        print(f"FALHA: subcomando desconhecido: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
