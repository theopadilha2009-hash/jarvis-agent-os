"""
do_history.py — JARVIS Sprint 8.2 worker-runs memory layer.

Three sub-commands routed via jarvis_core:

  ./jarvis do-history [--limit N] [--route NAME] [--project ALIAS]
  ./jarvis do-show {latest|ID}
  ./jarvis do-learn [--dry-run|--apply]

Read-only by default. `do-learn --apply` is reserved for the future; this
version only suggests INTENT_PATTERNS additions, never edits ask_router.py.

Hard rules: never executes Claude, never reads .env, never prints secrets,
never edits projects-alvo, never touches production.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "05_EXECUCAO" / "42_WORKER_RUNS"
ASK_UNCLEAR = ROOT / "05_EXECUCAO" / "32_ASK_LEARNING" / "UNCLEAR_REQUESTS.md"


# ── Parsing run package files ─────────────────────────────────────────────────

def _read(p: Path, max_chars: int | None = None) -> str:
    if not p.exists():
        return ""
    try:
        t = p.read_text(encoding="utf-8")
    except Exception:
        return ""
    if max_chars and len(t) > max_chars:
        return t[:max_chars] + "\n…(truncado)…"
    return t


def _parse_run(run_dir: Path) -> dict:
    """Extract a compact summary of a worker run package."""
    request = _read(run_dir / "01_REQUEST.md", 4000)
    plan = _read(run_dir / "02_PLAN.md", 4000)
    actions = _read(run_dir / "03_ACTIONS.md", 8000)
    next_md = _read(run_dir / "04_NEXT.md", 4000)

    def _extract_line(blob: str, header: str) -> str:
        for line in blob.splitlines():
            line = line.strip()
            if line.lower().startswith(header.lower()):
                rest = line.split(":", 1)[1].strip() if ":" in line else ""
                return rest.strip("`")
        return ""

    request_text = ""
    in_block = False
    for raw in request.splitlines():
        if raw.strip() == "## Texto original":
            in_block = True
            continue
        if in_block:
            if raw.startswith("## "):
                break
            request_text += raw + "\n"
    request_text = request_text.strip() or "(vazio)"

    route = _extract_line(plan, "- route") or "?"
    intent = _extract_line(plan, "- intent") or "?"
    project = _extract_line(plan, "- project") or "(nenhum)"
    mode = _extract_line(plan, "- mode") or "?"
    risk = _extract_line(plan, "- risk") or "?"

    n_exec = actions.count("- status: EXECUTADO")
    n_blocked = actions.count("- status: BLOQUEADO")
    n_fail = actions.count("FAIL(rc=")
    artifact = ""
    for line in next_md.splitlines():
        if line.startswith("- pasta:") or line.strip().startswith("- prompt:"):
            artifact = line.split("`")[1] if "`" in line else line
            break
    next_cmd = ""
    in_code = False
    for line in next_md.splitlines():
        if line.strip() == "```":
            in_code = not in_code
            continue
        if in_code and line.strip():
            next_cmd = line.strip()
            break

    ts = ""
    for raw in request.splitlines():
        if raw.strip() == "## Timestamp":
            continue
        if raw.strip() and not raw.startswith("#"):
            ts = raw.strip()
            break
    if not ts:
        ts = run_dir.name.split("_")[0] + " " + run_dir.name.split("_")[1].replace("-", ":")

    return {
        "dir": run_dir,
        "id": run_dir.name,
        "ts": ts,
        "request": request_text,
        "route": route,
        "intent": intent,
        "project": project,
        "mode": mode,
        "risk": risk,
        "n_exec": n_exec,
        "n_blocked": n_blocked,
        "n_fail": n_fail,
        "next_cmd": next_cmd,
        "artifact": artifact,
    }


def _list_runs() -> list[Path]:
    if not WORKER_DIR.exists():
        return []
    return sorted(
        [p for p in WORKER_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")],
        reverse=True,
    )


def _resolve_id(ident: str) -> Path | None:
    if not ident or ident == "latest":
        runs = _list_runs()
        return runs[0] if runs else None
    cand = WORKER_DIR / ident
    if cand.exists() and cand.is_dir():
        return cand
    for p in _list_runs():
        if ident in p.name:
            return p
    return None


# ── do-history ────────────────────────────────────────────────────────────────

def parse_history_args(argv):
    limit = 20
    route = None
    project = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--limit" and i + 1 < len(argv):
            try:
                limit = int(argv[i + 1])
            except ValueError:
                pass
            i += 2
            continue
        if a == "--route" and i + 1 < len(argv):
            route = argv[i + 1].strip()
            i += 2
            continue
        if a == "--project" and i + 1 < len(argv):
            project = argv[i + 1].strip().lower()
            i += 2
            continue
        i += 1
    return limit, route, project


def cmd_history(argv):
    limit, route_filter, project_filter = parse_history_args(argv)
    print("JARVIS — Do History")
    print("Status real: leitura local de 05_EXECUCAO/42_WORKER_RUNS/. Nada editado.")
    print("")
    runs = _list_runs()
    if not runs:
        print("## Resumo (0 de 0 run(s))")
        print("  ações:    0 executadas / 0 bloqueadas / 0 falhas")
        print("")
        print("## Runs (mais recentes primeiro)")
        print("  (nenhum worker run ainda — rode `./jarvis do \"algo\"`)")
        print("")
        print('Próximo: ./jarvis do "algo"')
        print("Produção: nada alterado.")
        return 0

    parsed = []
    for p in runs:
        try:
            parsed.append(_parse_run(p))
        except Exception as e:
            parsed.append({"id": p.name, "request": f"<erro: {e}>", "route": "?",
                           "project": "?", "n_exec": 0, "n_blocked": 0, "n_fail": 0,
                           "next_cmd": "", "artifact": "", "ts": "?"})

    filtered = parsed
    if route_filter:
        filtered = [r for r in filtered if r.get("route") == route_filter]
    if project_filter:
        filtered = [r for r in filtered if r.get("project", "").lower() == project_filter]
    filtered = filtered[:limit]

    routes_count = {}
    for r in filtered:
        routes_count[r["route"]] = routes_count.get(r["route"], 0) + 1

    print(f"## Resumo ({len(filtered)} de {len(parsed)} run(s))")
    if routes_count:
        parts = [f"{name}={n}" for name, n in sorted(routes_count.items(),
                                                      key=lambda kv: -kv[1])]
        print("  por rota: " + ", ".join(parts))
    n_fail_total = sum(r.get("n_fail", 0) for r in filtered)
    n_exec_total = sum(r.get("n_exec", 0) for r in filtered)
    n_block_total = sum(r.get("n_blocked", 0) for r in filtered)
    print(f"  ações:    {n_exec_total} executadas / {n_block_total} bloqueadas / {n_fail_total} falhas")
    print("")

    print("## Runs (mais recentes primeiro)")
    for r in filtered:
        req = (r["request"] or "").splitlines()[0] if r["request"] else "(vazio)"
        if len(req) > 60:
            req = req[:57] + "..."
        proj = r["project"]
        if proj == "(nenhum)":
            proj = "-"
        tag = "OK " if r["n_fail"] == 0 else "FAIL"
        print(f"  [{tag}] {r['id'][:30]}…  route={r['route']:<24}  project={proj:<12}  \"{req}\"")
    print("")
    print('Próximo: ./jarvis do-show latest   # ou ./jarvis do-show <ID>')
    print("Produção: nada alterado.")
    return 0


# ── do-show ───────────────────────────────────────────────────────────────────

def cmd_show(argv):
    ident = argv[0] if argv else "latest"
    run = _resolve_id(ident)
    print("JARVIS — Do Show")
    if not run:
        print("Status real: leitura local; nenhum worker run disponível. Nada editado.")
        print("")
        print(f"FALHA: worker run não encontrado: {ident}")
        print("Disponíveis: ./jarvis do-history")
        print("")
        print("## Run\n  (nenhum)")
        print("\n## Pedido\n  (nenhum)")
        print("\n## Plano\n  (nenhum)")
        print("\nProdução: nada alterado.")
        return 1
    print(f"Status real: leitura local de {run.relative_to(ROOT)}/. Nada editado.")
    print("")
    info = _parse_run(run)
    print(f"## Run")
    print(f"  id:       {info['id']}")
    print(f"  ts:       {info['ts']}")
    print(f"  route:    {info['route']}")
    print(f"  intent:   {info['intent']}")
    print(f"  project:  {info['project']}")
    print(f"  mode:     {info['mode']}")
    print(f"  risk:     {info['risk']}")
    print(f"  exec:     {info['n_exec']}")
    print(f"  blocked:  {info['n_blocked']}")
    print(f"  failures: {info['n_fail']}")
    print("")
    print("## Pedido")
    for line in info["request"].splitlines():
        print(f"  {line}")
    print("")
    print("## Plano")
    plan_text = _read(run / "02_PLAN.md", 3000)
    for line in plan_text.splitlines():
        if line.startswith("# "):
            continue
        print(f"  {line}")
    print("")
    print("## Ações")
    actions_text = _read(run / "03_ACTIONS.md", 5000)
    for line in actions_text.splitlines():
        if line.startswith("# "):
            continue
        print(f"  {line}")
    print("")
    print("## Próximo")
    next_text = _read(run / "04_NEXT.md", 3000)
    for line in next_text.splitlines():
        if line.startswith("# "):
            continue
        print(f"  {line}")
    print("")
    mission_path = run / "05_MISSION.md"
    if mission_path.exists():
        print("## Mission (excerpt)")
        mission_text = _read(mission_path, 3500)
        for line in mission_text.splitlines()[:60]:
            if line.startswith("# "):
                continue
            print(f"  {line}")
        print("")
    print(f"Pasta completa: {run.relative_to(ROOT)}/")
    print("Produção: nada alterado.")
    return 0


# ── do-learn ──────────────────────────────────────────────────────────────────

def _read_unclear_log() -> list[str]:
    if not ASK_UNCLEAR.exists():
        return []
    try:
        t = ASK_UNCLEAR.read_text(encoding="utf-8")
    except Exception:
        return []
    out = []
    for line in t.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            out.append(line[2:].strip())
        else:
            out.append(line)
    return out


def _collect_unclear_runs() -> list[dict]:
    runs = _list_runs()
    parsed = []
    for p in runs:
        try:
            info = _parse_run(p)
            if info.get("route") == "unclear":
                parsed.append(info)
        except Exception:
            pass
    return parsed


_PATTERN_HINTS = [
    # (regex on lower-cased request, suggested intent name, human label)
    (re.compile(r"\b(deploy|push|merge|tag|prod(?:u(?:ção|cao))?)\b"),
     "BLOCKED_HINT", "ação restrita — não criar pattern, melhorar capability hint"),
    (re.compile(r"\b(bug|fix|consert|corrig|arrum|resolv)\b"),
     "INTENT_PROJECT_FIX", "soa como project_fix — adicione fragmento ao pattern existente"),
    (re.compile(r"\b(test|teste|qa|quality)\b"),
     "INTENT_PROJECT_QA", "soa como project_qa"),
    (re.compile(r"\b(refator|refact|limpar|cleanup|organiz)\b"),
     "INTENT_PROJECT_FIX", "soa como project_fix (refator)"),
    (re.compile(r"\b(documenta(?:r|ção|cao)|docs|readme)\b"),
     "INTENT_PROJECT_FIX", "soa como project_fix (docs)"),
    (re.compile(r"\b(workflow|automação|automacao|n8n)\b"),
     "INTENT_N8N_BLUEPRINT", "soa como n8n_blueprint"),
    (re.compile(r"\b(agendamento|calend|reminder|lembrete)\b"),
     "INTENT_CAPABILITY_CHECK", "soa como capability_check (calendar)"),
    (re.compile(r"\b(handoff|chatgpt)\b"),
     "HANDOFF_HINT", "soa como handoff — ajustar _HANDOFF_HINT em worker_engine"),
    (re.compile(r"\b(claude (?:caiu|fora|indispon))\b"),
     "NO_CLAUDE_HINT", "soa como no-claude — ajustar _NO_CLAUDE_HINT em worker_engine"),
]


def _classify_unclear(text: str) -> list[tuple[str, str]]:
    lower = (text or "").lower()
    hits = []
    for pat, name, label in _PATTERN_HINTS:
        if pat.search(lower):
            hits.append((name, label))
    return hits


def parse_learn_args(argv):
    dry_run = True
    apply_ = False
    for a in argv:
        if a == "--apply":
            apply_ = True
            dry_run = False
        elif a == "--dry-run":
            dry_run = True
            apply_ = False
    return dry_run, apply_


def cmd_learn(argv):
    dry_run, apply_ = parse_learn_args(argv)
    print("JARVIS — Do Learn")
    print("Status real: análise local de unclear-routes + UNCLEAR_REQUESTS log.")
    print(f"Modo: {'--apply' if apply_ else '--dry-run (default)'}")
    print("")

    unclear_runs = _collect_unclear_runs()
    unclear_log = _read_unclear_log()

    print(f"## Fontes")
    print(f"  worker runs (unclear): {len(unclear_runs)}")
    print(f"  UNCLEAR_REQUESTS log:  {len(unclear_log)}")
    print("")

    samples = []
    for r in unclear_runs:
        samples.append(("worker", r["request"], r["id"]))
    for line in unclear_log[-30:]:
        samples.append(("ask-log", line, ""))

    if not samples:
        print("(nada para analisar — sem unclear runs nem entradas em ask-log)")
        print("")
        print("## Sugestões")
        print("  (nenhuma)")
        print("")
        print("## Próximo")
        print("  Rode `./jarvis do-learn --dry-run` após acumular pedidos unclear.")
        print("Produção: nada alterado.")
        return 0

    suggestions = {}
    untouched = []
    for source, text, run_id in samples:
        text = (text or "").strip()
        if not text:
            continue
        hits = _classify_unclear(text)
        if not hits:
            untouched.append((source, text, run_id))
            continue
        for name, label in hits:
            suggestions.setdefault(name, []).append((source, text, run_id, label))

    print("## Sugestões")
    if not suggestions:
        print("  (nenhuma — todos unclear caíram fora dos hints conhecidos)")
    else:
        for name, items in sorted(suggestions.items(), key=lambda kv: -len(kv[1])):
            print(f"\n### {name} — {len(items)} pedido(s)")
            label_seen = set()
            for source, text, _run_id, label in items[:5]:
                excerpt = text.replace("\n", " ")
                if len(excerpt) > 70:
                    excerpt = excerpt[:67] + "..."
                print(f"  [{source}] {excerpt}")
                label_seen.add(label)
            for lab in sorted(label_seen):
                print(f"  → ação sugerida: {lab}")
    print("")

    if untouched:
        print(f"## Unclear sem hint claro ({len(untouched)})")
        for source, text, _ in untouched[:8]:
            excerpt = (text or "").replace("\n", " ")
            if len(excerpt) > 70:
                excerpt = excerpt[:67] + "..."
            print(f"  [{source}] {excerpt}")
        if len(untouched) > 8:
            print(f"  …({len(untouched) - 8} mais)")
        print("")

    print("## Próximo")
    if apply_:
        print("  --apply ainda não auto-edita ask_router.py (risco alto).")
        print("  Use as sugestões acima para adicionar manualmente em")
        print("  11_SCRIPTS/ask_router.py:INTENT_PATTERNS ou em")
        print("  11_SCRIPTS/worker_engine.py:_HANDOFF_HINT / _NO_CLAUDE_HINT.")
    else:
        print("  Re-rode com --apply para confirmar (ainda assim, só sugere).")
    print("Produção: nada alterado.")
    return 0


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: do_history.py {history|show|learn} [...]")
        sys.exit(1)
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "history":
        sys.exit(cmd_history(rest))
    if cmd == "show":
        sys.exit(cmd_show(rest))
    if cmd == "learn":
        sys.exit(cmd_learn(rest))
    print(f"FALHA: sub-comando desconhecido: {cmd}")
    sys.exit(1)


if __name__ == "__main__":
    main()
