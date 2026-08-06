"""Append-only local decision log for the JARVIS operator.

Storage stays in a gitignored JSONL file. The command never calls a network,
never reads credentials and refuses text that matches the repository's secret
scanner. ``JARVIS_NO_REPORT=1`` always turns writes into preview mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECISIONS_DIR = ROOT / "05_EXECUCAO" / "63_DECISIONS"
DECISIONS_FILE = DECISIONS_DIR / "decisions.jsonl"
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"

try:
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []


def _looks_secret_like(text: str) -> bool:
    return any(pattern.search(text or "") for _name, pattern in SECRET_PATTERNS)


def _known_projects() -> set[str]:
    if not REGISTRY.exists():
        return set()
    try:
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {
        str(item.get("alias", "")).strip().lower()
        for item in payload.get("projects", [])
        if item.get("alias")
    }


def _decision_id(decision: str, project: str | None) -> str:
    now = datetime.now()
    raw = f"{now.isoformat(timespec='microseconds')}|{project or '-'}|{decision}"
    suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"d-{now.strftime('%Y%m%d-%H%M%S-%f')}-{suffix}"


def read_decisions() -> list[dict]:
    if not DECISIONS_FILE.exists():
        return []
    rows = []
    for raw in DECISIONS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        # Manual edits must not turn read commands into a secret printer.
        if _looks_secret_like(raw):
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if row.get("id") and row.get("decision"):
            rows.append(row)
    return rows


def _append_decision(row: dict) -> None:
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    with DECISIONS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _print_row(row: dict, compact: bool = False) -> None:
    decision = str(row.get("decision", ""))
    if compact and len(decision) > 100:
        decision = decision[:97] + "..."
    print(f"- {row.get('id', '?')}  project={row.get('project') or '-'}")
    print(f"  {decision}")
    if not compact:
        print(f"  created_at: {row.get('created_at', '?')}")
        print(f"  context: {row.get('context') or '-'}")
        print(f"  reason: {row.get('reason') or '-'}")


def cmd_add(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="./jarvis decision-add")
    parser.add_argument("decision", nargs="+")
    parser.add_argument("--project")
    parser.add_argument("--context", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    decision = " ".join(args.decision).strip()
    project = (args.project or "").strip().lower() or None
    combined = "\n".join([decision, args.context or "", args.reason or ""])

    print("JARVIS — Decision Add")
    print("Status real: decision log local append-only. Produção não alterada.")
    print("")

    if not decision:
        print("FALHA: decisão vazia. Nada foi gravado.")
        print("Produção: nada alterado.")
        return 1
    if _looks_secret_like(combined):
        print("FALHA: o texto parece conter segredo. Nada foi exibido ou gravado.")
        print("Produção: nada alterado.")
        return 2
    known = _known_projects()
    if project and project not in known:
        print(f"FALHA: projeto não registrado: {project}")
        print(f"Aliases: {', '.join(sorted(known)) or '(nenhum)'}")
        print("Produção: nada alterado.")
        return 1

    row = {
        "id": _decision_id(decision, project),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision,
        "project": project,
        "context": (args.context or "").strip(),
        "reason": (args.reason or "").strip(),
        "source": "manual",
    }
    _print_row(row)
    print(f"  target: {DECISIONS_FILE.relative_to(ROOT)}")
    print("")

    preview = args.dry_run or os.environ.get("JARVIS_NO_REPORT") == "1"
    if preview:
        print("Modo: PREVIEW (nada gravado).")
    else:
        _append_decision(row)
        print("OK — decisão registrada.")
        print(f"Próximo: ./jarvis decision-show {row['id']}")
    print("Produção: nada alterado.")
    return 0


def cmd_list(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="./jarvis decision-list")
    parser.add_argument("--project")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    project = (args.project or "").strip().lower() or None
    limit = max(1, min(args.limit, 100))
    rows = read_decisions()
    if project:
        rows = [row for row in rows if row.get("project") == project]
    rows = rows[-limit:]

    print("JARVIS — Decision Log")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    print(f"arquivo: {DECISIONS_FILE.relative_to(ROOT)} ({'existe' if DECISIONS_FILE.exists() else 'ausente'})")
    print(f"decisões exibidas: {len(rows)}")
    if project:
        print(f"project: {project}")
    print("")
    if not rows:
        print("(nenhuma decisão registrada)")
    else:
        for row in reversed(rows):
            _print_row(row, compact=True)
    print("")
    print("Produção: nada alterado.")
    return 0


def cmd_show(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="./jarvis decision-show")
    parser.add_argument("decision_id", nargs="?", default="latest")
    args = parser.parse_args(argv)
    rows = read_decisions()

    print("JARVIS — Decision Show")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    if not rows:
        print("(nenhuma decisão registrada)")
        print("Produção: nada alterado.")
        return 0

    if args.decision_id == "latest":
        match = rows[-1]
    else:
        matches = [row for row in rows if str(row.get("id", "")).startswith(args.decision_id)]
        if len(matches) != 1:
            print("FALHA: ID ausente ou ambíguo. Nada foi alterado.")
            print("Produção: nada alterado.")
            return 1
        match = matches[0]
    _print_row(match)
    print("")
    print("Produção: nada alterado.")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: decision_log.py add|list|show ...")
        return 1
    action = sys.argv[1]
    argv = sys.argv[2:]
    if action == "add":
        return cmd_add(argv)
    if action == "list":
        return cmd_list(argv)
    if action == "show":
        return cmd_show(argv)
    print(f"FALHA: ação desconhecida: {action}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
