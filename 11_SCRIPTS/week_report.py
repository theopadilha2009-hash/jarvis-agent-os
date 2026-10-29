#!/usr/bin/env python3
"""week_report.py — JARVIS relatório da semana (read-only).

Cruza agenda local, anotações (inbox), tarefas e projetos numa janela de N
dias. Nunca escreve: é a resposta para "o que eu tenho pra fazer essa semana?".

Usage:
  ./jarvis week
  ./jarvis week --days 14
  ./jarvis week --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "11_SCRIPTS") not in sys.path:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))

from local_capture import read_agenda_items, read_inbox_items  # type: ignore
from task_queue import task_events, task_state  # type: ignore


def _parse_day(value: str):
    text = (value or "").strip()
    if not text or text == "sem-data":
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def build_report(days: int = 7, today: date | None = None) -> dict:
    today = today or date.today()
    horizon = today + timedelta(days=days)

    upcoming, overdue = [], []
    for item in read_agenda_items():
        day = _parse_day(item.get("when", ""))
        if day is None:
            continue
        entry = {"when": item["when"], "text": item["text"], "day": day.isoformat()}
        if today <= day <= horizon:
            upcoming.append(entry)
        elif day < today:
            overdue.append(entry)
    upcoming.sort(key=lambda entry: entry["when"])
    overdue.sort(key=lambda entry: entry["when"])

    state = task_state()
    pending = [t for t in state.values() if t.get("status") == "pending"]
    blocked = [t for t in state.values() if t.get("status") == "blocked"]
    pending.sort(key=lambda t: t.get("ts") or "")

    done_recent = []
    window_start = today - timedelta(days=days)
    for ev in task_events():
        if ev.get("type") != "done":
            continue
        day = _parse_day(str(ev.get("ts", ""))[:10])
        if day is None or not (window_start <= day <= today):
            continue
        tid = ev.get("id")
        done_recent.append({
            "id": tid,
            "text": state.get(tid, {}).get("text", ""),
            "ts": ev.get("ts"),
        })

    projects = {}
    for task in pending + blocked:
        name = task.get("project") or "(sem projeto)"
        bucket = projects.setdefault(name, {"pending": 0, "blocked": 0})
        key = "pending" if task.get("status") == "pending" else "blocked"
        bucket[key] += 1

    notes = read_inbox_items()
    return {
        "today": today.isoformat(),
        "horizon": horizon.isoformat(),
        "days": days,
        "agenda": {"upcoming": upcoming, "overdue": overdue},
        "notes": {"items": notes[-10:], "used_as_fallback": not upcoming and not overdue},
        "tasks": {
            "pending": pending,
            "blocked": blocked,
            "done_in_window": done_recent,
        },
        "projects": projects,
    }


def render_report(data: dict) -> list[str]:
    days = data["days"]
    lines = [
        "JARVIS — Weekly Report",
        "Status real: leitura local (agenda + anotações + tarefas + projetos). Nada foi editado.",
        f"janela: {data['today']} → {data['horizon']}   |   concluídas: últimos {days} dias",
        "",
    ]

    agenda = data["agenda"]
    section = 0

    def _head(title: str) -> None:
        nonlocal section
        section += 1
        lines.append(f"## {section}. {title}")

    if data["notes"]["used_as_fallback"]:
        _head("Anotações (usando no lugar da agenda — nada marcado)")
    else:
        _head(f"Agenda (próximos {days} dias)")
    if agenda["upcoming"]:
        for item in agenda["upcoming"]:
            lines.append(f"  - [{item['when']}] {item['text']}")
    elif data["notes"]["used_as_fallback"]:
        if data["notes"]["items"]:
            for item in data["notes"]["items"]:
                lines.append(f"  - [{item['ts']}] {item['text']}")
        else:
            lines.append("  (sem agenda e sem anotações — comece com ./jarvis agenda-add)")
    else:
        lines.append("  (nada marcado na janela)")
    lines.append("")

    if not data["notes"]["used_as_fallback"]:
        _head("Anotações recentes")
        if data["notes"]["items"]:
            for item in data["notes"]["items"]:
                lines.append(f"  - [{item['ts']}] {item['text']}")
        else:
            lines.append("  (nenhuma)")
        lines.append("")

    tasks = data["tasks"]
    _head("Tarefas")
    lines.append(
        f"  pending: {len(tasks['pending'])}   blocked: {len(tasks['blocked'])}"
        f"   concluídas na janela: {len(tasks['done_in_window'])}"
    )
    for task in tasks["pending"][:10]:
        lines.append(f"  - [pending] {task.get('id')} · {task.get('text', '')}")
    for task in tasks["blocked"][:5]:
        reason = task.get("reason") or "sem motivo"
        lines.append(f"  - [blocked] {task.get('id')} · {task.get('text', '')} ({reason})")
    lines.append("")

    _head("Projetos")
    if data["projects"]:
        for name, bucket in sorted(data["projects"].items()):
            lines.append(f"  - {name}: {bucket['pending']} pending · {bucket['blocked']} blocked")
    else:
        lines.append("  (nenhuma tarefa vinculada a projeto)")
    lines.append("")

    if agenda["overdue"]:
        _head("Atrasados")
        for item in agenda["overdue"][:10]:
            lines.append(f"  - [{item['when']}] {item['text']}")
        lines.append("")

    lines.append("## Próximos comandos")
    lines.append("  ./jarvis agenda        ver a agenda completa")
    lines.append("  ./jarvis task-list     ver todas as tarefas")
    lines.append("  ./jarvis resume        retomar a sessão ativa")
    lines.append("")
    lines.append("Produção: nada alterado.")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis week")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    days = max(1, min(60, args.days))
    data = build_report(days=days)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return 0
    for line in render_report(data):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
