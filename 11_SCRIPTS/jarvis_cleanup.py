#!/usr/bin/env python3
"""Regra única de limpeza e compactação do JARVIS.

Mede o que passou da validade em cada área e só apaga com --apply. O padrão é
--dry-run: mostra o que sairia, com contagem e tamanho, sem tocar em nada.

Áreas:
- fila do Mac (Supabase): comandos já concluídos (succeeded/failed)
- memória (Supabase): preferência duplicada do mesmo gatilho e linha arquivada
- execução local: pacotes de run, planos, blueprints, handoffs, gates
- logs e relatórios gerados

Nunca toca arquivo versionado: só diretório gitignored e linha já concluída.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jarvis_supabase import credentials as worker_credentials, rest  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
COMMANDS_TABLE = "jarvis_device_commands"
MEMORIES_TABLE = "jarvis_memories"

# Diretórios de runtime (gitignored). Só o que está aqui é candidato a sair.
LOCAL_AREAS = (
    ("planos", "05_EXECUCAO/33_PLANS"),
    ("runs", "05_EXECUCAO/35_RUNS"),
    ("sessoes", "05_EXECUCAO/36_WORK_SESSIONS/archive"),
    ("no-claude", "05_EXECUCAO/38_NO_CLAUDE"),
    ("handoffs", "05_EXECUCAO/39_HANDOFFS"),
    ("blueprints", "05_EXECUCAO/40_BLUEPRINTS"),
    ("release-candidates", "05_EXECUCAO/41_RELEASE_CANDIDATES"),
    ("worker-runs", "05_EXECUCAO/42_WORKER_RUNS"),
    ("logs", "09_LOGS"),
    ("relatorios", "07_RELATORIOS"),
)

DEFAULT_DAYS = 30


def human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def is_git_ignored(path: Path, root: Path | None = None) -> bool:
    """Só apaga o que o git não versiona. Ignorado = seguro."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=root or ROOT,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))


def plan_local(days: int, root: Path | None = None) -> list[dict]:
    limit = cutoff(days)
    items = []
    base_root = root or ROOT
    for area, relative in LOCAL_AREAS:
        base = base_root / relative
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if entry.name == ".gitkeep":
                continue
            try:
                modified = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if modified >= limit or not is_git_ignored(entry, base_root):
                continue
            items.append({
                "area": area,
                "target": entry,
                "size": path_size(entry),
                "detail": f"{relative}/{entry.name}",
                "when": modified.date().isoformat(),
            })
    return items


def plan_commands(base: str, key: str, days: int) -> list[dict]:
    """Comandos da fila do Mac já concluídos e velhos o bastante."""
    stamp = cutoff(days).isoformat()
    rows = rest(
        base, key, COMMANDS_TABLE,
        query=(
            "select=id,action,status&status=in.(succeeded,failed)"
            f"&completed_at=lt.{quote(stamp, safe='')}&limit=1000"
        ),
    )
    if not isinstance(rows, list) or not rows:
        return []
    return [{
        "area": "fila-do-mac",
        "table": COMMANDS_TABLE,
        "query": f"status=in.(succeeded,failed)&completed_at=lt.{quote(stamp, safe='')}",
        "count": len(rows),
        "size": 0,
        "detail": f"{len(rows)} comando(s) concluído(s) antes de {stamp[:10]}",
        "when": stamp[:10],
    }]


def plan_memories(base: str, key: str, days: int) -> list[dict]:
    """Compacta memória: gatilho repetido fica com a regra mais nova."""
    items = []
    stamp = cutoff(days).isoformat()

    preferences = rest(
        base, key, MEMORIES_TABLE,
        query=(
            "select=id,kind,metadata,created_at&kind=eq.preference"
            "&archived_at=is.null&order=created_at.desc&limit=1000"
        ),
    )
    seen = {}
    duplicates = []
    for row in preferences if isinstance(preferences, list) else []:
        metadata = row.get("metadata")
        trigger = metadata.get("trigger") if isinstance(metadata, dict) else ""
        if not trigger:
            continue
        if trigger in seen:
            duplicates.append(row["id"])
        else:
            seen[trigger] = row["id"]
    if duplicates:
        items.append({
            "area": "memoria-duplicada",
            "table": MEMORIES_TABLE,
            "query": f"id=in.({','.join(str(int(i)) for i in duplicates)})",
            "body": {"archived_at": datetime.now(timezone.utc).isoformat()},
            "method": "PATCH",
            "count": len(duplicates),
            "size": 0,
            "detail": f"{len(duplicates)} preferência(s) repetida(s) → arquivadas",
            "when": stamp[:10],
        })

    archived = rest(
        base, key, MEMORIES_TABLE,
        query=(
            "select=id&archived_at=not.is.null"
            f"&archived_at=lt.{quote(stamp, safe='')}&limit=1000"
        ),
    )
    if isinstance(archived, list) and archived:
        ids = [str(int(row["id"])) for row in archived]
        items.append({
            "area": "memoria-arquivada",
            "table": MEMORIES_TABLE,
            "query": f"id=in.({','.join(ids)})",
            "count": len(ids),
            "size": 0,
            "detail": f"{len(ids)} memória(s) arquivada(s) antes de {stamp[:10]}",
            "when": stamp[:10],
        })
    return items


def print_plan(items: list[dict], days: int, applied: bool) -> None:
    total_size = sum(item["size"] for item in items)
    print(f"janela: mais de {days} dia(s)")
    if not items:
        print("Nada fora da validade. Está tudo compacto.")
        return
    for item in items:
        if "target" in item:
            print(f"  [{item['area']}] {item['detail']} · {human_size(item['size'])} · {item['when']}")
        else:
            print(f"  [{item['area']}] {item['detail']}")
    print(f"total: {len(items)} item(ns) · {human_size(total_size)} em disco")
    print("aplicado." if applied else "nada foi apagado (use --apply).")


def apply_local(items: list[dict]) -> tuple[int, int]:
    removed = 0
    freed = 0
    for item in items:
        target = item.get("target")
        if target is None:
            continue
        try:
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        except OSError as error:
            print(f"  AVISO: não consegui remover {target}: {error}", file=sys.stderr)
            continue
        removed += 1
        freed += item["size"]
    return removed, freed


def apply_remote(base: str, key: str, items: list[dict]) -> int:
    done = 0
    for item in items:
        if "table" not in item:
            continue
        try:
            rest(base, key, item["table"], method=item.get("method", "DELETE"),
                 query=item["query"], body=item.get("body"))
        except (HTTPError, URLError, OSError, ValueError) as error:
            print(f"  AVISO: {item['area']} falhou: {error}", file=sys.stderr)
            continue
        done += 1
    return done


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis cleanup")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="idade mínima para sair (default 30)")
    parser.add_argument("--apply", action="store_true", help="apaga de verdade")
    parser.add_argument("--dry-run", action="store_true", help="só mostra (padrão)")
    parser.add_argument("--local", action="store_true", help="só arquivos locais")
    parser.add_argument("--remote", action="store_true", help="só Supabase")
    args = parser.parse_args(argv)

    applied = bool(args.apply) and not args.dry_run
    days = max(1, args.days)
    print("JARVIS — Cleanup")
    print(f"Status real: limpeza e compactação ({'apply' if applied else 'dry-run'}); produção só é tocada com --apply.")

    items = []
    if not args.remote:
        items.extend(plan_local(days))

    base, key = worker_credentials()
    if not args.local:
        if base and key:
            try:
                items.extend(plan_commands(base, key, days))
                items.extend(plan_memories(base, key, days))
            except (HTTPError, URLError, OSError, ValueError) as error:
                print(f"AVISO: Supabase indisponível para a limpeza remota ({error}).", file=sys.stderr)
        else:
            print("AVISO: worker.env sem credenciais do Supabase; limpeza remota pulada.", file=sys.stderr)

    print_plan(items, days, applied)
    if applied:
        removed, freed = apply_local(items)
        remote = apply_remote(base, key, items) if (base and key) else 0
        print(f"removidos: {removed} arquivo(s) · {human_size(freed)} · {remote} grupo(s) no Supabase")
    print("Produção: nada alterado." if not applied else "Produção: fila e memória compactadas; nenhum deploy alterado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
