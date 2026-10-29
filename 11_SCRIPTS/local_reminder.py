#!/usr/bin/env python3
"""local_reminder.py — grava lembrete que o device worker dispara no Mac.

O worker (`device_worker.py --watch`) já lê reminders.json a cada tick e
dispara notificação + fala no prazo. Este script só escreve o arquivo, no
mesmo formato de `execute_reminder_job` — sem fila Supabase, sem migration.

Usage:
  ./jarvis reminder "sexta às 14h" "postar um vídeo"
  ./jarvis reminder "amanhã 9h" "reunião" --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "11_SCRIPTS") not in sys.path:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))

from local_capture import _infer_when, _strip_note_verb  # type: ignore

REMINDERS_FILE = (
    Path.home() / "Library" / "Application Support" / "JARVIS" / "reminders.json"
)


def load_reminders(path=None) -> list:
    target = Path(path) if path else REMINDERS_FILE
    try:
        items = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return items if isinstance(items, list) else []


def save_reminders(items: list, path=None) -> None:
    target = Path(path) if path else REMINDERS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(target)


def add_reminder(when_text: str, text: str, path=None, now=None) -> dict:
    """Grava o lembrete. Levanta ValueError quando o horário não é utilizável."""
    when = _infer_when(when_text, "")
    if not when or len(when) <= 10:
        raise ValueError("não encontrei data E hora (ex.: 'sexta às 14h' ou 'amanhã 9:00')")
    due_dt = datetime.strptime(when, "%Y-%m-%d %H:%M")
    due_epoch = due_dt.timestamp()
    current = now if now is not None else time.time()
    if due_epoch < current - 60:
        raise ValueError(f"horário no passado: {when}")
    entry = {
        "due_epoch": round(due_epoch, 3),
        "due": due_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "text": " ".join(_strip_note_verb(text).split())[:300],
    }
    if not entry["text"]:
        raise ValueError("texto vazio")
    items = load_reminders(path)
    items.append(entry)
    save_reminders(items, path)
    return entry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis reminder")
    parser.add_argument("when", nargs="?", default="")
    parser.add_argument("text", nargs="*")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    when_text = args.when or ""
    text = " ".join(args.text).strip()

    print("JARVIS — Lembrete local")
    print("Status real: grava em reminders.json; o device worker dispara no prazo.")
    print("")

    if not when_text or not text:
        print('FALHA: uso ./jarvis reminder "sexta às 14h" "o que lembrar"')
        return 2

    try:
        when = _infer_when(when_text, "")
    except Exception:
        when = None
    print(f"quando: {when or '(não reconhecido)'}")
    print(f"texto: {text}")
    print(f"alvo: {REMINDERS_FILE}")
    print("")

    if args.dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return 0

    try:
        entry = add_reminder(when_text, text)
    except ValueError as exc:
        print(f"FALHA: {exc}")
        print("Produção: nada alterado.")
        return 2

    print(f"OK — lembrete gravado para {entry['due']}.")
    print("Evidência: o worker lê este arquivo a cada tick e dispara notificação + fala.")
    print("Produção: nada alterado (só estado local).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
