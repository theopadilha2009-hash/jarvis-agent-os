"""
task_queue.py — local append-only task queue (no DB, no web UI, no cron).

Storage:
  05_EXECUCAO/34_TASKS/tasks.jsonl

Each line is one event for a task. Reading the file rebuilds state by
taking the latest event per task id.

Sub-commands (selected via positional argv[0]):
  add "text" [--dry-run]                  create a new task
  list                                    show pending tasks
  next                                    show top pending + suggested go cmd
  show ID                                 show all events for task id
  done ID [--note "..."]                  mark task done
  block ID --reason "..."                 mark task blocked

Hard rules:
  - append-only JSONL (never overwrites past events)
  - refuses input that looks secret-like
  - no external APIs
  - no Google Calendar / reminders / cron
  - runtime file 34_TASKS/tasks.jsonl is gitignored (only .gitkeep is committed)
"""
from pathlib import Path
from datetime import datetime
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "05_EXECUCAO" / "34_TASKS"
TASKS_FILE = TASKS_DIR / "tasks.jsonl"

try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []


def _looks_secret_like(text: str) -> bool:
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(text or ""):
            return True
    return False


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "task"


def _gen_id(text: str) -> str:
    return f"t-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{_slugify(text, 20)}"


def _ensure_file():
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    if not TASKS_FILE.exists():
        TASKS_FILE.write_text("", encoding="utf-8")


def _append_event(event: dict):
    _ensure_file()
    with TASKS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_events():
    if not TASKS_FILE.exists():
        return []
    out = []
    for line in TASKS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _rebuild_state():
    """Returns dict id -> dict with latest status + create-event metadata."""
    events = _read_events()
    state = {}
    for ev in events:
        tid = ev.get("id")
        if not tid:
            continue
        if tid not in state:
            # initialize from first sighting
            state[tid] = {"id": tid, "events": [], "created": ev}
        state[tid]["events"].append(ev)
        et = ev.get("type")
        if et == "created":
            state[tid]["text"] = ev.get("text", "")
            state[tid]["status"] = "pending"
            state[tid]["source"] = ev.get("source", "manual")
            state[tid]["project"] = ev.get("project")
            state[tid]["intent"] = ev.get("intent")
            state[tid]["safety"] = ev.get("safety")
            state[tid]["ts"] = ev.get("ts")
        elif et == "done":
            state[tid]["status"] = "done"
        elif et == "blocked":
            state[tid]["status"] = "blocked"
            state[tid]["reason"] = ev.get("reason", "")
    return state


def _parse_common(argv):
    text_parts = []
    dry_run = False
    note = None
    reason = None
    source = "manual"
    project = None
    intent = None
    safety = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        if a == "--note":
            if i + 1 < len(argv):
                note = argv[i + 1]
                i += 2
                continue
        if a == "--reason":
            if i + 1 < len(argv):
                reason = argv[i + 1]
                i += 2
                continue
        if a == "--source":
            if i + 1 < len(argv):
                source = argv[i + 1].strip().lower()
                i += 2
                continue
        if a == "--project":
            if i + 1 < len(argv):
                project = argv[i + 1].strip().lower()
                i += 2
                continue
        if a == "--intent":
            if i + 1 < len(argv):
                intent = argv[i + 1].strip().lower()
                i += 2
                continue
        if a == "--safety":
            if i + 1 < len(argv):
                safety = argv[i + 1].strip().lower()
                i += 2
                continue
        text_parts.append(a)
        i += 1
    return " ".join(text_parts).strip(), dry_run, note, reason, source, project, intent, safety


# ── add ───────────────────────────────────────────────────────────────────────

def cmd_add(argv):
    text, dry_run, _note, _reason, source, project, intent, safety = _parse_common(argv)
    print("JARVIS — Task Add")
    print("Status real: append-only local. Nada em produção foi alterado.")
    print("")
    if not text:
        print('FALHA: texto vazio. Uso: ./jarvis task-add "tarefa"')
        sys.exit(1)
    if _looks_secret_like(text):
        print("FALHA: texto parece conter segredo. NÃO gravamos nada.")
        sys.exit(2)
    tid = _gen_id(text)
    ts = datetime.now().isoformat(timespec="seconds")
    ev = {
        "id": tid,
        "ts": ts,
        "type": "created",
        "text": text,
        "status": "pending",
        "source": source,
    }
    if project:
        ev["project"] = project
    if intent:
        ev["intent"] = intent
    if safety:
        ev["safety"] = safety
    print(f"id:     {tid}")
    print(f"text:   {text}")
    print(f"source: {source}")
    if project:
        print(f"project: {project}")
    if intent:
        print(f"intent: {intent}")
    if safety:
        print(f"safety: {safety}")
    print(f"alvo:   {TASKS_FILE.relative_to(ROOT)} (append, gitignored)")
    print("")
    if dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return
    _append_event(ev)
    print(f"OK — task criada.")
    print(f"Próximo: ./jarvis task-next")
    print("Produção: nada alterado.")


# ── list ──────────────────────────────────────────────────────────────────────

def _print_task_line(t):
    project = t.get("project") or "-"
    intent = t.get("intent") or "-"
    text = t.get("text", "")
    if len(text) > 70:
        text = text[:67] + "..."
    print(f"- [{t.get('status','?')}] {t['id']}  project={project} intent={intent}")
    print(f"    {text}")


def cmd_list(argv):
    print("JARVIS — Task List")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    state = _rebuild_state()
    pending = [t for t in state.values() if t.get("status") == "pending"]
    blocked = [t for t in state.values() if t.get("status") == "blocked"]
    done = [t for t in state.values() if t.get("status") == "done"]
    print(f"arquivo: {TASKS_FILE.relative_to(ROOT)} ({'existe' if TASKS_FILE.exists() else 'ausente'})")
    print(f"pending: {len(pending)}   blocked: {len(blocked)}   done: {len(done)}")
    print("")
    if pending:
        print("## Pending")
        for t in sorted(pending, key=lambda x: x.get("ts", "")):
            _print_task_line(t)
    else:
        print("## Pending\n  (nenhuma pendente)")
    if blocked:
        print("\n## Blocked")
        for t in sorted(blocked, key=lambda x: x.get("ts", "")):
            _print_task_line(t)
            if t.get("reason"):
                print(f"    reason: {t['reason']}")
    print("")
    print("Produção: nada alterado.")


# ── next ──────────────────────────────────────────────────────────────────────

def cmd_next(argv):
    print("JARVIS — Task Next")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    state = _rebuild_state()
    pending = sorted(
        [t for t in state.values() if t.get("status") == "pending"],
        key=lambda x: x.get("ts", ""),
    )
    if not pending:
        print("(nenhuma task pendente)")
        print('Sugestão: ./jarvis task-add "tarefa"  ou  ./jarvis self-cockpit')
        print("Produção: nada alterado.")
        return
    top = pending[0]
    print(f"## Top pending")
    _print_task_line(top)
    print("")
    print("Sugestão de comando seguro:")
    text = top.get("text", "")
    proj = top.get("project")
    intent = top.get("intent")
    if proj == "jarvis-core" or intent == "self_evolve":
        print(f'  ./jarvis go "{text}"')
    elif proj:
        print(f'  ./jarvis project-open --project {proj} --print-only')
        print(f'  ./jarvis go "{text}"')
    else:
        print(f'  ./jarvis plan "{text}"')
        print(f'  ./jarvis go "{text}"')
    print("")
    print("Após resolver:")
    print(f"  ./jarvis task-done {top['id']}")
    print("Produção: nada alterado.")


# ── show ──────────────────────────────────────────────────────────────────────

def cmd_show(argv):
    print("JARVIS — Task Show")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    if not argv:
        print("FALHA: id obrigatório. Uso: ./jarvis task-show <ID>")
        sys.exit(1)
    tid = argv[0]
    state = _rebuild_state()
    if tid not in state:
        print(f"FALHA: id desconhecido: {tid}")
        sys.exit(1)
    t = state[tid]
    print(f"id: {tid}")
    print(f"status: {t.get('status', '?')}")
    print(f"text: {t.get('text', '')}")
    if t.get("project"):
        print(f"project: {t['project']}")
    if t.get("intent"):
        print(f"intent: {t['intent']}")
    print("")
    print("## Events")
    for ev in t.get("events", []):
        print(f"- {ev.get('ts','?')} {ev.get('type','?')} {json.dumps({k: v for k, v in ev.items() if k not in ('id','ts','type','text')}, ensure_ascii=False)}")
    print("")
    print("Produção: nada alterado.")


# ── done / block ──────────────────────────────────────────────────────────────

def cmd_done(argv):
    text, dry_run, note, _reason, _src, _proj, _intent, _safety = _parse_common(argv)
    print("JARVIS — Task Done")
    print("Status real: append-only local. Nada em produção foi alterado.")
    print("")
    if not text:
        print("FALHA: id obrigatório. Uso: ./jarvis task-done <ID> [--note '...']")
        sys.exit(1)
    tid = text
    state = _rebuild_state()
    if tid not in state:
        print(f"FALHA: id desconhecido: {tid}")
        sys.exit(1)
    ts = datetime.now().isoformat(timespec="seconds")
    ev = {"id": tid, "ts": ts, "type": "done"}
    if note:
        if _looks_secret_like(note):
            print("FALHA: note parece conter segredo. NÃO gravamos nada.")
            sys.exit(2)
        ev["note"] = note
    print(f"id: {tid}  -> status=done")
    if dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return
    _append_event(ev)
    print("OK — evento done anexado.")
    print("Produção: nada alterado.")


def cmd_block(argv):
    text, dry_run, _note, reason, _src, _proj, _intent, _safety = _parse_common(argv)
    print("JARVIS — Task Block")
    print("Status real: append-only local. Nada em produção foi alterado.")
    print("")
    if not text:
        print("FALHA: id obrigatório. Uso: ./jarvis task-block <ID> --reason '...'")
        sys.exit(1)
    if not reason:
        print("FALHA: --reason obrigatório.")
        sys.exit(1)
    if _looks_secret_like(reason):
        print("FALHA: reason parece conter segredo. NÃO gravamos nada.")
        sys.exit(2)
    tid = text
    state = _rebuild_state()
    if tid not in state:
        print(f"FALHA: id desconhecido: {tid}")
        sys.exit(1)
    ts = datetime.now().isoformat(timespec="seconds")
    ev = {"id": tid, "ts": ts, "type": "blocked", "reason": reason}
    print(f"id: {tid}  -> status=blocked  reason={reason}")
    if dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return
    _append_event(ev)
    print("OK — evento blocked anexado.")
    print("Produção: nada alterado.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: task_queue.py <add|list|next|show|done|block> [args]")
        sys.exit(1)
    sub = argv[0]
    rest = argv[1:]
    if sub == "add":
        cmd_add(rest)
    elif sub == "list":
        cmd_list(rest)
    elif sub == "next":
        cmd_next(rest)
    elif sub == "show":
        cmd_show(rest)
    elif sub == "done":
        cmd_done(rest)
    elif sub == "block":
        cmd_block(rest)
    else:
        print(f"FALHA: subcomando desconhecido: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
