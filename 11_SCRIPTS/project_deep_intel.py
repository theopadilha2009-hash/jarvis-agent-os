"""
project_deep_intel.py — JARVIS Sprint 8.3 deep project context.

Goes beyond `project-intel` (which describes package/scripts/framework) and
gathers *behavioral* signals about the project at this moment:

- recent commits (git log)
- candidate source files matching keywords from the user's request
- hot files (most-modified in the last 2 weeks)
- tests likely related to keywords
- branch / dirty / tracked .env presence (without ever reading content)

The output is a markdown-rendered block to be injected into FULL_MISSION.md
so Claude knows where to look without Theo typing file paths.

Hard rules:
- read-only inspection of the target project's git + filesystem
- never reads .env content
- never prints values from any tracked file beyond commit titles
- subprocess timeouts to avoid hangs
- output is capped to keep prompts manageable
"""
from __future__ import annotations
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"

# Stop words stripped from the request before grep/find — keep keywords focused.
_STOP_WORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "da", "do", "das", "dos", "no", "na", "nos", "nas",
    "em", "por", "para", "pra", "pro", "com", "sem",
    "e", "ou", "que", "se", "ser", "estar", "ter",
    "the", "a", "an", "of", "in", "on", "to", "for", "with",
    "and", "or", "is", "are", "be", "fix", "bug",  # bug/fix too common
    "criar", "fazer", "ver", "olhar", "checar",
}

# File-extensions to consider as source for keyword matching.
_SOURCE_EXTS = (
    ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs",
    ".sql", ".vue", ".svelte", ".java", ".kt", ".rb",
)
_TEST_GLOBS = ("*.test.*", "*.spec.*", "test_*.py", "*_test.py")


def _run(cmd, cwd, timeout=8):
    try:
        out = subprocess.check_output(
            cmd, cwd=cwd, text=True,
            stderr=subprocess.STDOUT, timeout=timeout,
        )
        return 0, out
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output or ""
    except Exception:
        return 1, ""


def _load_project(alias: str) -> dict | None:
    if not REGISTRY.exists():
        return None
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return None
    for p in data.get("projects", []) or []:
        if (p.get("alias") or "").lower() == (alias or "").lower():
            return p
    return None


def _extract_keywords(text: str, max_words: int = 5) -> list[str]:
    if not text:
        return []
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", text.lower())
    seen = set()
    out = []
    for w in words:
        if w in _STOP_WORDS:
            continue
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= max_words:
            break
    return out


def _git_recent_commits(cwd: Path, n: int = 8) -> list[str]:
    rc, out = _run(
        ["git", "log", "--oneline", "--no-decorate", f"-{n}"],
        cwd=cwd,
    )
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()][:n]


def _candidate_files(cwd: Path, keywords: list[str], cap: int = 8) -> list[str]:
    if not keywords:
        return []
    # Use git ls-files to respect .gitignore; fall back to find.
    rc, out = _run(["git", "ls-files"], cwd=cwd, timeout=10)
    if rc != 0 or not out:
        return []
    all_files = [f.strip() for f in out.splitlines() if f.strip()]
    # Filter source-ish files only.
    sources = [
        f for f in all_files
        if (any(f.endswith(ext) for ext in _SOURCE_EXTS)
            or f.endswith(".md"))
    ]
    # Score files by keyword hits in path.
    scored = []
    for path in sources:
        low = path.lower()
        score = sum(2 if k in Path(low).stem else (1 if k in low else 0)
                    for k in keywords)
        if score > 0 and "/node_modules/" not in low and "/dist/" not in low:
            scored.append((score, path))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [p for _, p in scored[:cap]]


def _hot_files(cwd: Path, cap: int = 8) -> list[tuple[str, int]]:
    """Files most-modified in the last 2 weeks (git log --since)."""
    rc, out = _run(
        ["git", "log", "--since=2 weeks ago", "--name-only", "--pretty=format:"],
        cwd=cwd, timeout=10,
    )
    if rc != 0:
        return []
    counts: dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if "/node_modules/" in line or "/dist/" in line:
            continue
        if any(line.endswith(ext) for ext in _SOURCE_EXTS) or line.endswith(".md"):
            counts[line] = counts.get(line, 0) + 1
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return items[:cap]


def _likely_tests(cwd: Path, keywords: list[str], cap: int = 6) -> list[str]:
    rc, out = _run(["git", "ls-files"], cwd=cwd, timeout=10)
    if rc != 0:
        return []
    candidates = []
    for f in out.splitlines():
        f = f.strip()
        if not f:
            continue
        base = Path(f).name.lower()
        is_test = (
            ".test." in base
            or ".spec." in base
            or base.startswith("test_")
            or base.endswith("_test.py")
        )
        if not is_test:
            continue
        if keywords:
            low = f.lower()
            if not any(k in low for k in keywords):
                continue
        candidates.append(f)
    return candidates[:cap]


def _branch(cwd: Path) -> str:
    rc, out = _run(["git", "branch", "--show-current"], cwd=cwd, timeout=5)
    return (out.strip() if rc == 0 else "?") or "?"


def _dirty_count(cwd: Path) -> int:
    rc, out = _run(["git", "status", "--short"], cwd=cwd, timeout=5)
    if rc != 0:
        return 0
    return len([l for l in out.splitlines() if l.strip()])


def _env_warning(cwd: Path) -> str:
    """Report ONLY presence of .env files. NEVER read or print content."""
    matches = []
    for p in cwd.glob(".env*"):
        if p.is_file():
            matches.append(p.name)
    if not matches:
        return "(nenhum .env detectado)"
    return f"{len(matches)} arquivo(s) detectado(s): " + ", ".join(matches[:5]) + " — JARVIS NUNCA lê conteúdo"


def gather(alias: str, request_text: str = "") -> dict:
    """Return deep intel about the project. Safe to call when project
    doesn't exist — returns an empty-ish dict."""
    proj = _load_project(alias)
    if not proj or not proj.get("path"):
        return {"available": False, "alias": alias}
    path = Path(proj["path"])
    if not path.exists():
        return {"available": False, "alias": alias, "missing_path": str(path)}

    keywords = _extract_keywords(request_text)
    return {
        "available": True,
        "alias": alias,
        "path": str(path),
        "branch": _branch(path),
        "dirty_count": _dirty_count(path),
        "keywords": keywords,
        "recent_commits": _git_recent_commits(path),
        "candidate_files": _candidate_files(path, keywords),
        "hot_files": _hot_files(path),
        "likely_tests": _likely_tests(path, keywords),
        "env_warning": _env_warning(path),
    }


def render_markdown(data: dict) -> str:
    """Render the gathered data as a markdown block for FULL_MISSION."""
    if not data or not data.get("available"):
        if data and data.get("missing_path"):
            return f"_Deep intel indisponível: path `{data['missing_path']}` não existe._\n"
        return "_Deep intel indisponível (projeto não registrado)._\n"

    lines = []
    lines.append(f"- alias: `{data['alias']}`")
    lines.append(f"- path: `{data['path']}`")
    lines.append(f"- branch: `{data['branch']}`")
    dirty = data.get("dirty_count", 0)
    if dirty:
        lines.append(f"- ATENÇÃO: árvore suja ({dirty} arquivo(s) modificado(s))")
    else:
        lines.append("- tree: limpa")
    lines.append(f"- keywords inferidas do pedido: `{', '.join(data['keywords']) or '(nenhuma)'}`")
    lines.append(f"- env files: {data.get('env_warning', '')}")
    lines.append("")

    rc = data.get("recent_commits") or []
    if rc:
        lines.append("### Commits recentes (git log --oneline -8)")
        for c in rc:
            lines.append(f"  {c}")
        lines.append("")

    cf = data.get("candidate_files") or []
    if cf:
        lines.append("### Arquivos candidatos (match com keywords)")
        for f in cf:
            lines.append(f"  - `{f}`")
        lines.append("")

    hf = data.get("hot_files") or []
    if hf:
        lines.append("### Hot files (mudaram nas últimas 2 semanas)")
        for f, n in hf:
            lines.append(f"  - `{f}` ({n} commit(s))")
        lines.append("")

    lt = data.get("likely_tests") or []
    if lt:
        lines.append("### Testes prováveis (match com keywords)")
        for f in lt:
            lines.append(f"  - `{f}`")
        lines.append("")
    else:
        lines.append("### Testes prováveis (match com keywords)")
        lines.append("  - (nenhum encontrado — considere criar test antes do fix)")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # CLI mode: ./jarvis project-deep-intel --project oficina "bug agenda"
    import sys
    alias = None
    text_parts = []
    i = 0
    argv = sys.argv[1:]
    while i < len(argv):
        a = argv[i]
        if a == "--project" and i + 1 < len(argv):
            alias = argv[i + 1].lower()
            i += 2
            continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].lower()
            i += 1
            continue
        text_parts.append(a)
        i += 1
    if not alias:
        print("Uso: project_deep_intel.py --project ALIAS [texto do pedido]")
        sys.exit(1)
    data = gather(alias, " ".join(text_parts))
    print("JARVIS — Project Deep Intel (read-only)")
    print(f"Status real: leitura local de {data.get('path', '?')}. Nada editado.\n")
    print(render_markdown(data))
    print("Produção: nada alterado.")
