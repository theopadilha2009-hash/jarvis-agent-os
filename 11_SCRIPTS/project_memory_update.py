"""
project_memory_update.py — controlled writer for project memory entries.

Modes:
  --from-git              derive entry from git state of the target project
  --from-file PATH        parse a Claude/agent report file (no LLM)

Actions:
  (default)               preview only — nothing written
  --dry-run               explicit preview (same as default; clearer intent)
  --apply                 append to 04_PROJETOS/<ALIAS_UPPER>/PROJECT_STATUS.md

Hard rules:
  - Never writes to the target project directory.
  - Never overwrites history — append-only, marker-fenced.
  - Refuses to write if generated entry contains raw secret patterns.
  - Never touches NEXT_ACTIONS.md (human intent).
  - Never reads .env contents.
  - Caps file excerpts to avoid huge entries.
"""
from pathlib import Path
from datetime import datetime
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
MISSIONS_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"
MEMORY_BASE = ROOT / "04_PROJETOS"
TEMPLATE_STATUS = MEMORY_BASE / "_TEMPLATE" / "PROJECT_STATUS.md"

MARKER_BEGIN = "<!-- jarvis-memory-entry -->"
MAX_DIFF_LINES = 20
MAX_FILE_EXCERPT_LINES = 60

# Reuse SECRET_PATTERNS from secret_scan.py.
try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []

USAGE = (
    "Uso:\n"
    "  ./jarvis project-memory-update --project ALIAS --from-git [--dry-run|--apply]\n"
    "  ./jarvis project-memory-update --project ALIAS --from-file PATH [--dry-run|--apply]\n"
)


def fail(msg, code=1):
    print(f"FALHA: {msg}")
    sys.exit(code)


def parse_args(argv):
    alias = None
    from_git = False
    from_file = None
    apply_changes = False
    dry_run = False
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
        if a == "--from-git":
            from_git = True
            i += 1
            continue
        if a == "--from-file":
            if i + 1 >= len(argv):
                fail("--from-file exige caminho.")
            from_file = argv[i + 1]
            i += 2
            continue
        if a.startswith("--from-file="):
            from_file = a.split("=", 1)[1]
            i += 1
            continue
        if a == "--apply":
            apply_changes = True
            i += 1
            continue
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        i += 1
    if not alias:
        fail(USAGE)
    if not from_git and not from_file:
        fail("Modo obrigatório: --from-git ou --from-file PATH.")
    if from_git and from_file:
        fail("Use somente um modo: --from-git OU --from-file.")
    return alias, from_git, from_file, apply_changes, dry_run


def load_project(alias):
    if not REGISTRY.exists():
        fail("PROJECT_REGISTRY.json não encontrado.")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    projects = {p["alias"]: p for p in registry.get("projects", [])}
    if alias not in projects:
        print(f"FALHA: project alias não registrado: {alias}")
        sys.exit(1)
    return projects[alias]


def alias_to_memory_dir(alias: str) -> Path:
    exact = alias.upper().replace("-", "_")
    direct = MEMORY_BASE / exact
    if direct.exists():
        return direct
    if MEMORY_BASE.exists():
        for child in MEMORY_BASE.iterdir():
            if not child.is_dir():
                continue
            if child.name.lower().startswith(exact.lower()):
                return child
    return direct


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for _name, pattern in SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def contains_raw_secret(text: str) -> bool:
    """True if ANY secret pattern still matches after a redact pass."""
    redacted = redact(text)
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(redacted):
            return True
    return False


def run(cmd, cwd, timeout=15):
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


def detect_suspicious_diff(path: Path) -> list:
    """Names in current diff that look secret-like. Names only, no contents."""
    code, out = run(["git", "diff", "--name-only", "HEAD"], path)
    suspicious = []
    if code == 0 and out:
        for name in out.splitlines():
            lower = name.lower()
            if "/.env" in lower or lower.endswith("/.env") or lower == ".env":
                # exclude .env.example/.env.sample/.env.template/.env.dist
                if not any(lower.endswith(s) for s in (".example", ".sample", ".template", ".dist")):
                    suspicious.append(name)
            for needle in ("token", "secret", "password", "cookie", "service_role", "api_key", "apikey"):
                if needle in lower and name not in suspicious:
                    suspicious.append(name)
    return suspicious


def build_entry_from_git(alias, project) -> str:
    path = Path(project["path"]).expanduser()
    ts = datetime.now().isoformat(timespec="seconds")

    branch = ""
    dirty = ""
    log_lines = ""
    diff_stat = ""
    if (path / ".git").exists():
        _, branch = run(["git", "branch", "--show-current"], path)
        _, dirty = run(["git", "status", "--short"], path)
        _, log_lines = run(["git", "log", "--oneline", "-5"], path)
        # diff stat vs origin/main only when origin/main actually resolves
        ref_code, _ = run(["git", "rev-parse", "--verify", "origin/main"], path)
        if ref_code == 0:
            _, diff_stat = run(["git", "diff", "--stat", "origin/main..HEAD"], path)

    latest = find_latest_mission(alias)
    mission_block = "(nenhuma missão registrada)"
    if latest is not None:
        info = parse_mission_name(latest.name) or {}
        mission_block = f"{info.get('mode', '?')} @ {latest.relative_to(ROOT)}"

    suspicious = detect_suspicious_diff(path) if (path / ".git").exists() else []

    dirty_status = "limpa"
    if dirty:
        dirty_count = len([l for l in dirty.splitlines() if l.strip()])
        dirty_status = f"suja ({dirty_count} arquivo(s))"

    lines = [
        MARKER_BEGIN,
        f"### {ts} — debrief (from-git)",
        "",
        f"- alias: {alias}",
        f"- path: {path}",
        f"- branch: {branch or '<sem branch>'}",
        f"- tree: {dirty_status}",
        f"- última missão: {mission_block}",
        "",
        "**Status real (derivado de Git)**",
        "- Created: (preencher manualmente ou via --from-file)",
        "- Modified: ver `git diff --stat` abaixo",
        "- Tested: (não validado por JARVIS; rodar localmente)",
        "- Not validated: (depende do que Claude fez)",
        "- Production: **nada alterado**",
        "",
    ]
    if log_lines:
        lines.append("**Últimos commits**")
        for l in log_lines.splitlines()[:5]:
            lines.append(f"- {redact(l)}")
        lines.append("")
    if diff_stat:
        lines.append("**Diff stat vs origin/main (truncado)**")
        for l in diff_stat.splitlines()[:MAX_DIFF_LINES]:
            lines.append(f"    {redact(l)}")
        if len(diff_stat.splitlines()) > MAX_DIFF_LINES:
            lines.append(f"    ... (+{len(diff_stat.splitlines()) - MAX_DIFF_LINES} linhas)")
        lines.append("")
    if suspicious:
        lines.append("⚠ **Arquivos suspeitos no diff (nomes apenas — conteúdo NÃO lido)**")
        for s in suspicious:
            lines.append(f"- {s}")
        lines.append("Antes de qualquer commit/push: confirmar que não são segredos reais.")
        lines.append("")
    lines.append("**Próxima ação sugerida**")
    if branch in ("main", "master"):
        lines.append(f"- ⚠ branch {branch} — criar branch dedicada antes de qualquer coisa")
    elif dirty:
        lines.append(f"- revisar `git diff` em {path}")
        lines.append(f"- decidir: commitar ou rodar `./jarvis final-gate --project {alias}`")
    else:
        lines.append(f"- `./jarvis final-gate --project {alias}` para decidir push/PR")
    lines.append("")
    return "\n".join(lines)


# ── Parser for Claude/agent report files (no LLM) ─────────────────────────

SECTION_HEADINGS = (
    "STATUS REAL",
    "WHAT CHANGED",
    "FILES CHANGED",
    "VALIDATION RESULTS",
    "RISKS / NOT VALIDATED",
    "RISKS",
    "SAFE TO COMMIT",
)


def _normalize_heading_line(line: str) -> str:
    """Strip leading markdown noise so we can compare against a clean heading.
    Also drops '?' anywhere (covers 'SAFE TO COMMIT? yes')."""
    s = line.strip()
    prev = None
    while s != prev:
        prev = s
        s = re.sub(r"^#+\s*", "", s)
        s = re.sub(r"^\d+[\.\)]\s*", "", s)
        s = re.sub(r"^\*+\s*", "", s)
        s = re.sub(r"\s*\*+$", "", s)
    # Drop '?' globally — known section names never contain it legitimately,
    # and forms like 'SAFE TO COMMIT? yes' should normalize to 'SAFE TO COMMIT yes'.
    s = s.replace("?", "")
    return re.sub(r"\s+", " ", s).strip()


def extract_section(full_text: str, heading: str, max_lines: int = MAX_FILE_EXCERPT_LINES):
    """Extract a section body. Tolerant to '## 1. STATUS REAL',
    '**STATUS REAL**', 'STATUS REAL:', etc."""
    lines = full_text.splitlines()
    heading_upper = heading.upper()
    start = None
    for i, line in enumerate(lines):
        norm = _normalize_heading_line(line).upper()
        # Allow either exact match or 'STATUS REAL: ...' / 'STATUS REAL ...'
        if norm == heading_upper or norm.startswith(heading_upper + " ") or norm.startswith(heading_upper + ":"):
            start = i + 1
            break
    if start is None:
        return None
    out = []
    for line in lines[start:]:
        norm = _normalize_heading_line(line).upper()
        # Stop when we hit ANY other known section heading.
        hit_next = False
        for other in SECTION_HEADINGS:
            if other == heading:
                continue
            ou = other.upper()
            if norm == ou or norm.startswith(ou + " ") or norm.startswith(ou + ":"):
                hit_next = True
                break
        if hit_next:
            break
        out.append(line)
        if len(out) >= max_lines:
            break
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) if out else None


def extract_safe_to_commit(full_text: str):
    """Returns 'yes', 'no', or None based on a SAFE TO COMMIT section.
    Handles both 'SAFE TO COMMIT?\n\nyes' and inline 'SAFE TO COMMIT? yes'."""
    # First pass: look for the heading line itself; capture inline yes/no.
    for line in full_text.splitlines():
        norm = _normalize_heading_line(line).upper()
        if norm == "SAFE TO COMMIT" or norm.startswith("SAFE TO COMMIT "):
            tail = norm[len("SAFE TO COMMIT"):].strip()
            if tail:
                if re.search(r"\byes\b", tail.lower()):
                    return "yes"
                if re.search(r"\bno\b", tail.lower()):
                    return "no"
            break
    # Second pass: examine the section body's first non-empty line.
    body = extract_section(full_text, "SAFE TO COMMIT", max_lines=8)
    if not body:
        return None
    for line in body.splitlines():
        s = line.strip().lower()
        if not s:
            continue
        # Skip code-fence delimiters.
        if s.startswith("```"):
            continue
        if re.search(r"\byes\b", s) and not re.search(r"\bno\b", s):
            return "yes"
        if re.search(r"\bno\b", s) and not re.search(r"\byes\b", s):
            return "no"
        return None
    return None


def build_entry_from_file(alias, project, file_path: Path) -> str:
    if not file_path.exists():
        fail(f"Arquivo não encontrado: {file_path}")
    raw = file_path.read_text(encoding="utf-8", errors="ignore")
    redacted = redact(raw)
    ts = datetime.now().isoformat(timespec="seconds")

    # Sort by length descending so longer headings (e.g. "RISKS / NOT VALIDATED")
    # match before their substrings (e.g. "RISKS").
    extracted = {}
    for heading in sorted(SECTION_HEADINGS, key=len, reverse=True):
        sect = extract_section(redacted, heading)
        if sect:
            extracted[heading] = sect
    # If we already have "RISKS / NOT VALIDATED", drop the duplicate "RISKS".
    if "RISKS / NOT VALIDATED" in extracted and "RISKS" in extracted:
        del extracted["RISKS"]

    safe_decision = extract_safe_to_commit(redacted)

    lines = [
        MARKER_BEGIN,
        f"### {ts} — debrief (from-file: {file_path.name})",
        "",
        f"- alias: {alias}",
        f"- source file: {file_path}  ({len(raw)} bytes)",
        f"- parser: regex-only (no LLM)",
        f"- safe to commit (parsed): {safe_decision or 'desconhecido'}",
        "",
    ]
    if not extracted:
        lines += [
            "**(parser não achou seções estruturadas — preview de 30 primeiras linhas)**",
            "",
        ]
        for l in redacted.splitlines()[:30]:
            lines.append(f"    {l}")
        lines.append("")
    else:
        for heading in SECTION_HEADINGS:
            if heading in extracted:
                lines.append(f"**{heading}**")
                for l in extracted[heading].splitlines()[:MAX_FILE_EXCERPT_LINES]:
                    lines.append(f"    {l}")
                lines.append("")

    lines.append("Production: **nada alterado por JARVIS — apenas registrado**.")
    lines.append("")
    return "\n".join(lines)


def ensure_status_file(memory_dir: Path):
    memory_dir.mkdir(parents=True, exist_ok=True)
    status_md = memory_dir / "PROJECT_STATUS.md"
    if not status_md.exists():
        if TEMPLATE_STATUS.exists():
            status_md.write_text(TEMPLATE_STATUS.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            status_md.write_text("# Project Status\n\n", encoding="utf-8")
    return status_md


def main():
    argv = sys.argv[1:]
    alias, from_git, from_file, apply_changes, dry_run = parse_args(argv)
    project = load_project(alias)

    print("JARVIS — Theo Padilha AI Worker Project Memory Update")
    print(f"Status real: gerador de entrada de memória para alias={alias}.")
    print("")

    memory_dir = alias_to_memory_dir(alias)
    status_md = memory_dir / "PROJECT_STATUS.md"

    if from_git:
        entry = build_entry_from_git(alias, project)
    else:
        entry = build_entry_from_file(alias, project, Path(from_file).expanduser())

    # Safety: refuse to write if raw secret pattern remains after redaction.
    if contains_raw_secret(entry):
        print("FALHA: a entrada gerada ainda contém padrões secret-like após redação.")
        print("Causa provável: novo padrão de secret não coberto por SECRET_PATTERNS.")
        print("Ação segura: NÃO gravamos nada. Investigue antes de tentar de novo.")
        sys.exit(2)

    # Always show preview.
    print(f"Memory dir alvo: {memory_dir.relative_to(ROOT)}")
    print(f"Arquivo alvo:    {status_md.relative_to(ROOT) if status_md.exists() else (memory_dir.relative_to(ROOT) / 'PROJECT_STATUS.md (será criado)')}")
    print("")
    print("=== PREVIEW DA ENTRADA ===")
    print(entry)
    print("=== FIM DA PREVIEW ===")
    print("")

    if not apply_changes:
        if dry_run:
            print("Modo: --dry-run (preview apenas, nada gravado).")
        else:
            print("Modo: preview (default — nada gravado). Use --apply para anexar.")
        print("Produção: nada alterado.")
        return

    # --apply path: normalize newlines so the file always ends with exactly
    # one '\n' and there is exactly one blank line between previous content
    # and the new entry.
    target = ensure_status_file(memory_dir)
    existing = target.read_text(encoding="utf-8").rstrip("\n")
    entry_clean = entry.rstrip("\n")
    target.write_text(existing + "\n\n" + entry_clean + "\n", encoding="utf-8")
    print(f"OK — entrada anexada em {target.relative_to(ROOT)}")
    print("Status real: arquivo de memória do JARVIS atualizado. Projeto-alvo NÃO modificado.")
    print("Produção: nada alterado em projeto real, VPS, n8n ou produção.")


if __name__ == "__main__":
    main()
