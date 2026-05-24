"""
project_status.py — compact single-screen status of a registered project.

Usage:
  python3 11_SCRIPTS/project_status.py --project <alias>          # compact
  python3 11_SCRIPTS/project_status.py --project <alias> --full   # cockpit mode

Never reads .env. Never edits anything. Never prints secrets.
"""
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
MISSIONS_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"
MEMORY_BASE = ROOT / "04_PROJETOS"

USAGE = "Uso: ./jarvis project-status --project <alias>  (ou project-cockpit)"


def fail(msg, code=1):
    print(f"FALHA: {msg}")
    sys.exit(code)


def parse_args(argv):
    alias = None
    full = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            if i + 1 >= len(argv):
                fail("--project exige alias.")
            alias = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--full":
            full = True
            i += 1
            continue
        i += 1
    if not alias:
        fail(USAGE)
    return alias, full


def load_project(alias):
    if not REGISTRY.exists():
        fail("PROJECT_REGISTRY.json não encontrado.")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    projects = {p["alias"]: p for p in registry.get("projects", [])}
    if alias not in projects:
        print(f"FALHA: project alias não registrado: {alias}")
        print("")
        print("Aliases disponíveis:")
        for key in sorted(projects):
            print(f"- {key}")
        sys.exit(1)
    return projects[alias]


def run(cmd, cwd, timeout=10):
    try:
        out = subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=timeout)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def detect_pm(path: Path):
    if (path / "bun.lockb").exists() or (path / "bun.lock").exists():
        return "bun"
    if (path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (path / "yarn.lock").exists():
        return "yarn"
    if (path / "package-lock.json").exists():
        return "npm"
    if (path / "package.json").exists():
        return "npm"
    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
        return "python"
    return "unknown"


def find_latest_mission_for_alias(alias):
    if not MISSIONS_DIR.exists():
        return None
    matches = [d for d in MISSIONS_DIR.iterdir() if d.is_dir() and f"project-{alias}_" in d.name]
    if not matches:
        return None
    return max(matches, key=lambda d: d.stat().st_mtime)


def parse_mission_name(name: str):
    # Format: <DATE>_<TIME>_project-<alias>_<mode>_<slug>
    # TS already contains one underscore (date_time), so we search for the
    # "_project-" marker instead of splitting blindly by underscore.
    marker = "_project-"
    idx = name.find(marker)
    if idx < 0:
        return None
    ts = name[:idx]
    rest = name[idx + 1:]  # strip leading underscore
    parts = rest.split("_", 2)  # project-<alias> / <mode> / <slug>
    if len(parts) < 2:
        return None
    alias = parts[0].replace("project-", "", 1)
    mode = parts[1] if len(parts) > 1 else ""
    slug = parts[2] if len(parts) > 2 else ""
    return {"ts": ts, "alias": alias, "mode": mode, "slug": slug}


def suggest_next_action(project, branch: str, dirty: bool, latest_mission_dir):
    alias = project["alias"]
    if branch in ("main", "master"):
        return [
            f"⚠ Você está em {branch}. PARE — crie/troque para branch dedicada antes de continuar.",
            f"Comando: cd {project['path']} && git checkout -b feature/<topic>",
        ]
    if dirty:
        return [
            "Árvore suja — escolha:",
            "- commitar antes de gerar nova missão, OU",
            f"- ./jarvis qa-sprint --project {alias}  (Claude pode polir o que falta)",
            f"- ./jarvis final-gate --project {alias} (validar se está pronto para PR)",
        ]
    # clean tree
    if latest_mission_dir is None:
        return [
            "Sem missão registrada. Sugestões:",
            f"- ./jarvis doctor --project {alias}",
            f"- ./jarvis qa-sprint --project {alias}",
        ]
    # have clean tree + previous mission
    return [
        "Tree limpa + missão anterior em mãos. Sugestões:",
        f"- ./jarvis final-gate --project {alias}  (decide safe-to-push/PR)",
        f"- ./jarvis goal-sprint --project {alias} --goal \"...\" (próximo objetivo)",
    ]


def print_compact(project, alias):
    path = Path(project["path"]).expanduser()
    print(f"# project-status: {alias}")
    print(f"path: {path}")
    if not path.exists():
        print("EXISTS: NO")
        print("Resultado: PROJECT STATUS FALHOU — path ausente.")
        sys.exit(1)
    is_git = (path / ".git").exists()
    if not is_git:
        print("repo: NO (sem .git)")
        return None, None, None, []

    code, branch = run(["git", "branch", "--show-current"], path)
    branch_label = branch or "<sem branch>"
    main_warn = " ⚠ MAIN" if branch in ("main", "master") else ""
    print(f"branch: {branch_label}{main_warn}")

    code, status = run(["git", "status", "--short"], path)
    dirty_lines = [l for l in status.splitlines() if l.strip()]
    dirty = bool(dirty_lines)
    print(f"dirty: {'yes ('+str(len(dirty_lines))+' arquivo(s))' if dirty else 'no'}")

    code, log = run(["git", "log", "--oneline", "-3"], path)
    if log:
        print("recent:")
        for line in log.splitlines():
            print(f"  {line}")

    pm_detected = detect_pm(path)
    pm_registered = project.get("package_manager", "unknown")
    pm_label = pm_detected if pm_detected == pm_registered or pm_registered in ("unknown", "none") else f"{pm_detected} (registry: {pm_registered})"
    print(f"pm: {pm_label}")

    pkg = path / "package.json"
    scripts = {}
    if pkg.exists():
        try:
            scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {}) or {}
        except Exception:
            scripts = {}
    key_scripts = [s for s in ("typecheck", "type-check", "test", "test:run", "build", "lint") if s in scripts]
    if key_scripts:
        print(f"scripts: {', '.join(key_scripts)}")
    elif (path / "tsconfig.json").exists():
        print("scripts: (nenhum óbvio, mas há tsconfig → npx tsc --noEmit)")

    return path, branch, dirty, dirty_lines


def alias_to_memory_dir(alias: str) -> Path:
    exact = alias.upper().replace("-", "_")
    direct = MEMORY_BASE / exact
    if direct.exists():
        return direct
    if MEMORY_BASE.exists():
        for child in MEMORY_BASE.iterdir():
            if child.is_dir() and child.name.lower().startswith(exact.lower()):
                return child
    return direct


def _is_blank_template(text: str) -> bool:
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s == "-":
            continue
        return False
    return True


def summarize_memory(memory_dir: Path):
    """Returns (status_state, status_excerpt, next_state, next_excerpt).
    State is one of: 'missing', 'blank', 'entries', 'freeform'."""
    status_md = memory_dir / "PROJECT_STATUS.md"
    next_md = memory_dir / "NEXT_ACTIONS.md"

    def _summarize(md: Path, max_lines: int):
        if not md.exists():
            return ("missing", None)
        text = md.read_text(encoding="utf-8", errors="ignore")
        if _is_blank_template(text):
            return ("blank", None)
        marker = "<!-- jarvis-memory-entry -->"
        if marker in text:
            chunks = text.split(marker)
            last = next((c for c in reversed(chunks) if c.strip()), "")
            return ("entries", "\n".join([l for l in last.splitlines() if l.strip()][:max_lines]))
        return ("freeform", "\n".join([l for l in text.splitlines() if l.strip()][:max_lines]))

    s_state, s_excerpt = _summarize(status_md, 10)
    n_state, n_excerpt = _summarize(next_md, 8)
    return s_state, s_excerpt, n_state, n_excerpt


def print_full_extras(alias, project, path, branch, dirty, latest_mission_dir):
    print("")
    if latest_mission_dir is not None:
        info = parse_mission_name(latest_mission_dir.name) or {}
        mtime_secs = int((Path(latest_mission_dir).stat().st_mtime))
        from datetime import datetime
        age = datetime.now() - datetime.fromtimestamp(mtime_secs)
        age_str = (
            f"{int(age.total_seconds()//60)}m" if age.total_seconds() < 3600
            else f"{int(age.total_seconds()//3600)}h" if age.total_seconds() < 86400
            else f"{int(age.total_seconds()//86400)}d"
        )
        print("## Última missão para este projeto")
        print(f"  pack: {latest_mission_dir.relative_to(ROOT)}")
        if info:
            print(f"  modo: {info.get('mode')}   idade: {age_str}")
        prompt = latest_mission_dir / "01_CLAUDE_PROMPT.md"
        if prompt.exists():
            print(f"  prompt: {prompt.relative_to(ROOT)}")
            print(f"  copy:  cat \"{prompt}\" | pbcopy")
    else:
        print("## Última missão para este projeto")
        print("  (nenhuma — use ./jarvis qa-sprint/goal-sprint/etc para criar)")

    # Memory block (from PROJECT_STATUS.md + NEXT_ACTIONS.md)
    memory_dir = alias_to_memory_dir(alias)
    s_state, s_excerpt, n_state, n_excerpt = summarize_memory(memory_dir)
    print("")
    print("## Estado registrado (PROJECT_STATUS.md)")
    if s_state == "missing":
        print(f"  (sem arquivo em {memory_dir.relative_to(ROOT) if memory_dir.exists() else memory_dir})")
        print(f"  criar via: ./jarvis project-memory-update --project {alias} --from-git --apply")
    elif s_state == "blank":
        print("  (template vazio — JARVIS amnésico para este projeto)")
        print(f"  preencher: ./jarvis project-memory-update --project {alias} --from-git --apply")
    else:
        for line in (s_excerpt or "").splitlines():
            print(f"  {line}")

    print("")
    print("## Próximas ações (NEXT_ACTIONS.md — intenção humana)")
    if n_state == "missing":
        print("  (sem arquivo)")
    elif n_state == "blank":
        print("  (template vazio — escreva manualmente seu próximo passo)")
    else:
        for line in (n_excerpt or "").splitlines():
            print(f"  {line}")

    print("")
    print("## Próximo passo seguro")
    for line in suggest_next_action(project, branch or "", dirty, latest_mission_dir):
        print(f"  {line}")
    # Suggestion: after Claude executes a mission, update memory.
    if latest_mission_dir is not None and s_state in ("blank", "missing"):
        print("")
        print("## Loop de memória")
        print(f"  Depois que Claude rodar a missão, registre o resultado:")
        print(f"  ./jarvis project-memory-update --project {alias} --from-git --dry-run")
        print(f"  ./jarvis project-memory-update --project {alias} --from-git --apply")


def main():
    argv = sys.argv[1:]
    alias, full = parse_args(argv)
    project = load_project(alias)

    print("JARVIS — Theo Padilha AI Worker Project Status")
    print(f"Status real: leitura local do alias={alias}. Nada foi editado.")
    print("")

    result = print_compact(project, alias)
    if result is None or not result:
        return
    path, branch, dirty, _ = result

    latest = find_latest_mission_for_alias(alias)

    if full:
        print_full_extras(alias, project, path, branch, dirty, latest)
    else:
        # compact: still show last mission line + next action one-liner
        print("")
        if latest is not None:
            info = parse_mission_name(latest.name) or {}
            print(f"last mission: {info.get('mode', '?')}  ({latest.relative_to(ROOT)})")
        else:
            print("last mission: (nenhuma)")
        nxt = suggest_next_action(project, branch or "", dirty, latest)
        print(f"next: {nxt[0]}")
        if len(nxt) > 1:
            for line in nxt[1:]:
                print(f"      {line}")

    print("")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
