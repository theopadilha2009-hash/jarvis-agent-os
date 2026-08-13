#!/usr/bin/env python3
"""Searchable local memory index for JARVIS (stdlib-only SQLite)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
MEMORY_ROOT = ROOT / "03_MEMORIA"
DEFAULT_DB = ROOT / "05_EXECUCAO" / "65_AGENT_RUNS" / "memory-index.sqlite3"
WORD_PATTERN = re.compile(r"[\wÀ-ÿ-]{2,}", re.UNICODE)


def _safe_text(path: Path, limit: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except (OSError, UnicodeError):
        return ""


def _title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        value = line.strip().lstrip("#").strip()
        if value:
            return value[:200]
    return fallback.replace("_", " ")[:200]


def _kind(path: Path) -> str:
    folded = "/".join(path.parts).casefold()
    if "aprendizado" in folded:
        return "learning"
    if "decis" in folded:
        return "decision"
    if "prefer" in folded:
        return "preference"
    return "context"


class MemoryIndex:
    def __init__(self, database: Path | None = None, memory_root: Path | None = None):
        self.database = Path(database or DEFAULT_DB)
        self.memory_root = Path(memory_root or MEMORY_ROOT)

    def connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database, timeout=3)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS memories (
                path TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                kind TEXT NOT NULL,
                project TEXT NOT NULL DEFAULT '',
                mtime_ns INTEGER NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind)")
        return connection

    def sync(self) -> dict[str, int]:
        files = sorted(self.memory_root.rglob("*.md")) if self.memory_root.is_dir() else []
        seen: set[str] = set()
        changed = 0
        with self.connect() as connection:
            existing = {row["path"]: row["mtime_ns"] for row in connection.execute("SELECT path, mtime_ns FROM memories")}
            for path in files:
                if not path.is_file() or path.name.startswith("."):
                    continue
                try:
                    relative = path.relative_to(ROOT).as_posix()
                except ValueError:
                    relative = path.relative_to(self.memory_root).as_posix()
                seen.add(relative)
                mtime_ns = path.stat().st_mtime_ns
                if existing.get(relative) == mtime_ns:
                    continue
                content = _safe_text(path)
                if not content.strip():
                    continue
                project_match = re.search(r"(?im)^##?\s*Projeto\s*\n+\s*([^\n]+)", content)
                project = project_match.group(1).strip()[:100] if project_match else ""
                connection.execute(
                    """INSERT INTO memories(path, title, content, kind, project, mtime_ns)
                       VALUES(?, ?, ?, ?, ?, ?)
                       ON CONFLICT(path) DO UPDATE SET
                         title=excluded.title, content=excluded.content, kind=excluded.kind,
                         project=excluded.project, mtime_ns=excluded.mtime_ns""",
                    (relative, _title(content, path.stem), content, _kind(path), project, mtime_ns),
                )
                changed += 1
            stale = set(existing) - seen
            if stale:
                connection.executemany("DELETE FROM memories WHERE path = ?", [(path,) for path in stale])
        return {"indexed": len(seen), "changed": changed, "removed": len(stale)}

    def search(self, query: str, limit: int = 12) -> dict[str, Any]:
        query = str(query or "").strip()[:500]
        limit = max(1, min(int(limit), 30))
        sync = self.sync()
        terms = list(dict.fromkeys(token.casefold() for token in WORD_PATTERN.findall(query)))[:10]
        with self.connect() as connection:
            if not terms:
                rows = connection.execute(
                    "SELECT path, title, content, kind, project FROM memories ORDER BY mtime_ns DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                clauses = " AND ".join("lower(content || ' ' || title || ' ' || project) LIKE ?" for _ in terms)
                rows = connection.execute(
                    f"SELECT path, title, content, kind, project FROM memories WHERE {clauses} ORDER BY mtime_ns DESC LIMIT ?",
                    (*[f"%{term}%" for term in terms], limit),
                ).fetchall()
        results = []
        for row in rows:
            content = re.sub(r"\s+", " ", row["content"]).strip()
            position = min((content.casefold().find(term) for term in terms if term in content.casefold()), default=0)
            start = max(0, position - 90)
            snippet = content[start:start + 360]
            if start:
                snippet = "…" + snippet
            if start + 360 < len(content):
                snippet += "…"
            results.append({
                "title": row["title"],
                "path": row["path"],
                "kind": row["kind"],
                "project": row["project"],
                "snippet": snippet,
                "source": "local_markdown",
            })
        return {"query": query, "count": len(results), "results": results, "index": sync}
