"""
project_memory.py — read-only project memory display.

Reads:
  - PROJECT_STATUS.md (cumulative status + memory entries appended by
    project_memory_update.py)
  - NEXT_ACTIONS.md   (human intent — never touched by JARVIS)
  - Latest git commits in the target project
  - Latest mission pack for the alias

Output is redacted via SECRET_PATTERNS from secret_scan.py before printing.
Never reads .env contents. Never edits anything.
"""
from pathlib import Path
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
MISSIONS_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"
MEMORY_BASE = ROOT / "04_PROJETOS"

# Reuse the secret patterns defined in secret_scan.py so we have one source of
# truth. We import lazily to avoid a hard dependency cycle.
try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []

USAGE = "Uso: ./jarvis project-memory --project <alias>"


def fail(msg, code=1):
    print(f"FALHA: {msg}")
    sys.exit(code)


def parse_args(argv):
    alias = None
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
        i += 1
    if not alias:
        fail(USAGE)
    return alias


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


def alias_to_memory_dir(alias: str) -> Path:
    """Map alias to memory dir under 04_PROJETOS/.
    Convention: lower-with-hyphens → UPPER_WITH_UNDERSCORE.
    `jarvis-core` → JARVIS_CORE; `oficina` → OFICINA; `ls` → LS (or LS_CLINICA
    if it exists; we try the exact mapping first, then a case-insensitive
    prefix match).
    """
    exact = alias.upper().replace("-", "_")
    direct = MEMORY_BASE / exact
    if direct.exists():
        return direct
    # try case-insensitive prefix match against existing dirs
    if MEMORY_BASE.exists():
        for child in MEMORY_BASE.iterdir():
            if not child.is_dir():
                continue
            if child.name.lower().startswith(exact.lower()):
                return child
    return direct  # may not exist yet; caller decides


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for _name, pattern in SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def run(cmd, cwd, timeout=10):
    try:
        return 0, subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def find_latest_mission(alias):
    if not MISSIONS_DIR.exists():
        return None
    matches = [d for d in MISSIONS_DIR.iterdir() if d.is_dir() and f"project-{alias}_" in d.name]
    if not matches:
        return None
    return max(matches, key=lambda d: d.stat().st_mtime)


def parse_mission_name(name: str):
    marker = "_project-"
    idx = name.find(marker)
    if idx < 0:
        return None
    ts = name[:idx]
    rest = name[idx + 1:]
    parts = rest.split("_", 2)
    if len(parts) < 2:
        return None
    return {"ts": ts, "alias": parts[0].replace("project-", "", 1), "mode": parts[1], "slug": parts[2] if len(parts) > 2 else ""}


def is_blank_template(text: str) -> bool:
    """A template is 'blank' if every non-header line is empty or '-'."""
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s == "-":
            continue
        return False
    return True


def summarize_md(md_path: Path, max_lines: int = 12):
    if not md_path.exists():
        return None, "missing"
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    if is_blank_template(text):
        return text, "blank"
    # Take last MEMORY entry if there is a marker; otherwise first non-empty lines.
    marker = "<!-- jarvis-memory-entry -->"
    if marker in text:
        chunks = text.split(marker)
        # Take last non-empty chunk (the most recent entry written by update).
        last = next((c for c in reversed(chunks) if c.strip()), "")
        lines = [l for l in last.splitlines() if l.strip()][:max_lines]
        return "\n".join(lines), "entries"
    lines = [l for l in text.splitlines() if l.strip()][:max_lines]
    return "\n".join(lines), "freeform"


def suggest_next_action(project, branch: str, dirty: bool, latest_mission_dir, status_state: str):
    alias = project["alias"]
    if branch in ("main", "master"):
        return [
            f"⚠ Branch {branch} — PARE. Crie/troque para branch dedicada.",
            f"  cd {project['path']} && git checkout -b feature/<topic>",
        ]
    if dirty:
        if latest_mission_dir is None:
            return [
                "Tree suja sem missão registrada.",
                f"  ./jarvis qa-sprint --project {alias}",
            ]
        return [
            "Tree suja com missão anterior — provavelmente Claude editou.",
            f"  ./jarvis project-memory-update --project {alias} --from-git --dry-run",
            f"  (e depois --apply quando estiver satisfeito)",
        ]
    # clean tree
    if latest_mission_dir is None:
        return [
            "Sem missão registrada para este projeto.",
            f"  ./jarvis doctor --project {alias}",
            f"  ./jarvis qa-sprint --project {alias}",
        ]
    if status_state == "blank":
        return [
            "Tree limpa + missão em mãos + memória vazia.",
            f"  ./jarvis project-memory-update --project {alias} --from-git --dry-run",
            "  (revise, depois rode com --apply para registrar o estado)",
        ]
    return [
        "Tree limpa + memória registrada.",
        f"  ./jarvis final-gate --project {alias}  (decidir push/PR)",
        f'  ./jarvis goal-sprint --project {alias} --goal "..."',
    ]


def main():
    argv = sys.argv[1:]
    alias = parse_args(argv)
    project = load_project(alias)
    path = Path(project["path"]).expanduser()
    memory_dir = alias_to_memory_dir(alias)

    print("JARVIS — Theo Padilha AI Worker Project Memory")
    print(f"Status real: leitura local do alias={alias}. Nada foi editado.")
    print("")

    # Header block
    print(f"alias: {alias}")
    print(f"project path: {path}")
    print(f"memory dir:   {memory_dir.relative_to(ROOT) if memory_dir.exists() else '(ainda não criada)'}")

    if not path.exists():
        print("EXISTS: NO — path do registry não existe no disco.")
        sys.exit(1)

    is_git = (path / ".git").exists()
    branch = ""
    dirty = False
    if is_git:
        _, branch = run(["git", "branch", "--show-current"], path)
        _, status_short = run(["git", "status", "--short"], path)
        dirty_lines = [l for l in status_short.splitlines() if l.strip()]
        dirty = bool(dirty_lines)
        warn_main = " ⚠ MAIN" if branch in ("main", "master") else ""
        print(f"branch: {branch}{warn_main}")
        print(f"dirty: {'yes ('+str(len(dirty_lines))+' arquivo(s))' if dirty else 'no'}")
        _, log = run(["git", "log", "--oneline", "-5"], path)
        if log:
            print("recent commits:")
            for line in log.splitlines():
                print(f"  {redact(line)}")
    else:
        print("repo: NO (sem .git)")
    print("")

    # Latest mission for alias
    latest = find_latest_mission(alias)
    print("## Última missão")
    if latest is None:
        print("  (nenhuma — use ./jarvis qa-sprint/goal-sprint/etc para criar)")
    else:
        info = parse_mission_name(latest.name) or {}
        prompt = latest / "01_CLAUDE_PROMPT.md"
        print(f"  pack: {latest.relative_to(ROOT)}")
        if info:
            print(f"  modo: {info.get('mode')}")
        if prompt.exists():
            print(f"  prompt: {prompt.relative_to(ROOT)}")
    print("")

    # PROJECT_STATUS summary
    status_md = memory_dir / "PROJECT_STATUS.md"
    print("## PROJECT_STATUS.md")
    status_text, status_state = summarize_md(status_md, max_lines=14)
    if status_state == "missing":
        print(f"  (ainda não criado em {memory_dir.relative_to(ROOT) if memory_dir.exists() else memory_dir})")
    elif status_state == "blank":
        print("  (template vazio — sem entradas de memória ainda)")
    else:
        for line in (status_text or "").splitlines()[:14]:
            print(f"  {redact(line)}")
    print("")

    # NEXT_ACTIONS summary
    next_md = memory_dir / "NEXT_ACTIONS.md"
    print("## NEXT_ACTIONS.md (intenção humana — JARVIS não escreve)")
    next_text, next_state = summarize_md(next_md, max_lines=10)
    if next_state == "missing":
        print(f"  (ainda não criado)")
    elif next_state == "blank":
        print("  (template vazio — escreva manualmente seu próximo passo)")
    else:
        for line in (next_text or "").splitlines()[:10]:
            print(f"  {redact(line)}")
    print("")

    # Detected warnings
    warnings = []
    if branch in ("main", "master"):
        warnings.append(f"branch protegida ({branch}) — não patchar diretamente")
    if dirty:
        warnings.append("tree suja — talvez memória precise atualizar")
    if status_state == "blank":
        warnings.append("PROJECT_STATUS.md vazio — JARVIS amnésico para este projeto")
    if warnings:
        print("## Avisos")
        for w in warnings:
            print(f"  - {w}")
        print("")

    # Next action
    print("## Próxima ação sugerida")
    for line in suggest_next_action(project, branch or "", dirty, latest, status_state):
        print(f"  {line}")
    print("")

    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
