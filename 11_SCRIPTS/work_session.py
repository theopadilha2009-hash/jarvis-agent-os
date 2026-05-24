"""
work_session.py — JARVIS local work session lifecycle (no fake autonomy).

Theo wants one verb that connects: classify → mission → Claude (manual)
→ report check → debrief apply → gates → close. This module owns the
state file that ties task queue + run logs + Claude mission + debrief
into a single thread Theo can pick back up after interruption.

Storage:
  05_EXECUCAO/36_WORK_SESSIONS/current.json   (mutable runtime state, gitignored)
  05_EXECUCAO/36_WORK_SESSIONS/events.jsonl   (append-only, gitignored)
  05_EXECUCAO/36_WORK_SESSIONS/.gitkeep       (tracked)

Sub-commands (selected via positional argv[0]):
  start "request" [--dry-run] [--project ALIAS] [--no-task]
  status
  next
  block --reason "..." [--dry-run]
  close [--dry-run] [--force]
  resume                      # alias: status + next + summary, no writes

Hard rules:
  - never executes Claude
  - never calls APIs
  - never touches the target project
  - refuses secret-shaped request / reason
  - gitignored runtime state — only .gitkeep is committed
"""
from pathlib import Path
from datetime import datetime
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "05_EXECUCAO" / "36_WORK_SESSIONS"
CURRENT = DIR / "current.json"
EVENTS = DIR / "events.jsonl"

# Reuse ask_router for classification — keeps work-start consistent with go/plan.
try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from ask_router import (  # type: ignore
        detect_intent as _di,
        detect_project_alias as _dp,
        _next_command_for as _ncf,
        INTENT_SELF_EVOLVE,
    )
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []

    def _di(text):
        return "unclear"

    def _dp(text, override=None):
        return override or ""

    def _ncf(intent, project, text, copy_flag):
        return ([], "./jarvis self-cockpit", "readonly", True)


VALID_STATUSES = (
    "started",
    "mission_generated",
    "claude_pending",
    "report_pending",
    "report_checked",
    "debrief_applied",
    "gates_pending",
    "gates_passed",
    "closed",
    "blocked",
)


def _looks_secret_like(text: str) -> bool:
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(text or ""):
            return True
    return False


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "work"


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dir():
    DIR.mkdir(parents=True, exist_ok=True)


def _load_current():
    if not CURRENT.exists():
        return None
    try:
        return json.loads(CURRENT.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_current(state: dict):
    _ensure_dir()
    state["updated_at"] = _now_iso()
    CURRENT.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_event(event: dict):
    _ensure_dir()
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _parse_common(argv):
    text_parts = []
    project = None
    dry_run = False
    force = False
    no_task = False
    reason = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            if i + 1 < len(argv):
                project = argv[i + 1].strip().lower()
                i += 2
                continue
        if a.startswith("--project="):
            project = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        if a == "--force":
            force = True
            i += 1
            continue
        if a == "--no-task":
            no_task = True
            i += 1
            continue
        if a == "--reason":
            if i + 1 < len(argv):
                reason = argv[i + 1]
                i += 2
                continue
        text_parts.append(a)
        i += 1
    return " ".join(text_parts).strip(), project, dry_run, force, no_task, reason


def _debrief_command(project: str, path: str = "/tmp/jarvis-claude-out.md"):
    if project == "jarvis-core" or not project:
        return f"./jarvis self-debrief --from-file {path} --dry-run"
    return f"./jarvis project-memory-update --project {project} --from-file {path} --dry-run"


def _next_action_for(state: dict) -> str:
    """Pure decision tree. Returns the single most useful next command."""
    if not state:
        return './jarvis task-next   # ou ./jarvis go "o que faço agora"'
    status = state.get("status", "started")
    project = state.get("project") or ""
    expected = state.get("expected_report_path") or "/tmp/jarvis-claude-out.md"
    if status == "blocked":
        return f"./jarvis work-status   # work session bloqueada (reason gravada)"
    if status == "closed":
        return './jarvis task-next   # nenhuma work session ativa'
    if status in ("started", "mission_generated", "claude_pending", "report_pending"):
        if Path(expected).exists():
            return f"./jarvis report-check --file {expected}"
        return (
            f"# abrir Claude, colar a missão, gerar relatório, salvar:\n"
            f"#   cat > {expected}\n"
            f"#   (cole o RELATÓRIO FINAL; Ctrl+D)\n"
            f"# depois:\n"
            f"./jarvis report-check --file {expected}"
        )
    if status == "report_checked":
        return f"./jarvis report-apply --file {expected}"
    if status == "debrief_applied" or status == "gates_pending":
        return (
            "env JARVIS_NO_REPORT=1 ./jarvis safety-gate\n"
            "env JARVIS_NO_REPORT=1 ./jarvis smoke-test\n"
            "./jarvis doctrine-check\n"
            "# se tudo verde: ./jarvis work-close"
        )
    if status == "gates_passed":
        return "./jarvis work-close"
    return "./jarvis self-cockpit"


# ── start ────────────────────────────────────────────────────────────────────

def cmd_start(argv):
    text, alias_override, dry_run, _force, no_task, _reason = _parse_common(argv)
    print("JARVIS — Work Start")
    print("Status real: cria sessão de trabalho local. Claude NÃO foi executado.")
    print("")
    if not text:
        print('FALHA: pedido vazio. Uso: ./jarvis work-start "pedido"')
        sys.exit(1)
    if _looks_secret_like(text):
        print("FALHA: pedido parece conter segredo. NÃO criamos sessão.")
        sys.exit(2)

    # Block creating a new session over an active (non-closed) one to avoid
    # state loss. Theo can --force or close first.
    existing = _load_current()
    if existing and existing.get("status") not in ("closed", None):
        print(f"AVISO: já existe work session ativa: id={existing.get('work_id')}  status={existing.get('status')}")
        print("Feche com: ./jarvis work-close  (ou edite manualmente current.json)")
        if not dry_run:
            sys.exit(3)

    intent = _di(text)
    project = _dp(text, alias_override) or ""
    _cl, next_cmd, safety, _safe = _ncf(intent, project, text, None)

    work_id = f"w-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{_slugify(text, 20)}"
    expected_report = "/tmp/jarvis-claude-out.md" if (project == "jarvis-core" or not project) else "/tmp/claude-out.md"
    debrief_cmd = _debrief_command(project, expected_report)
    state = {
        "schema": "jarvis-work-session-v0.1",
        "work_id": work_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "request": text,
        "intent": intent,
        "project": project,
        "safety": safety,
        "status": "started",
        "latest_run_id": "",
        "latest_task_id": "",
        "mission_prompt_path": "",
        "expected_report_path": expected_report,
        "debrief_command": debrief_cmd,
        "next_command": next_cmd,
        "production_touched": False,
    }

    print(f"work_id: {work_id}")
    print(f"request: {text}")
    print(f"intent:  {intent}")
    print(f"project: {project or '(não detectado)'}")
    print(f"safety:  {safety}")
    print(f"next:    {next_cmd}")
    print("")

    if dry_run:
        print("Modo: --dry-run (nada gravado em current.json/events.jsonl).")
        print("Produção: nada alterado.")
        return

    # Optionally create a task entry so backlog stays connected.
    task_id = ""
    if not no_task:
        try:
            args = ["python3", "11_SCRIPTS/task_queue.py", "add", text,
                    "--source", "work-start"]
            if project:
                args += ["--project", project]
            if intent:
                args += ["--intent", intent]
            # We don't capture the task id back from task_queue right now;
            # the link is by created_at proximity. Keep this lightweight.
            subprocess.call(args, cwd=ROOT, stdout=subprocess.DEVNULL)
            task_id = "(linked task created via task-add)"
        except Exception as e:
            print(f"AVISO: não consegui criar task: {e}")
    state["latest_task_id"] = task_id

    # Try to create a run package via run_log so debrief instructions exist on disk.
    run_path = ""
    try:
        out = subprocess.check_output(
            ["python3", "11_SCRIPTS/run_log.py", "create",
             "--request", text, "--project", project or "",
             "--intent", intent or "", "--safety", safety or "",
             "--next-command", next_cmd, "--print-path"],
            cwd=ROOT, text=True, timeout=10,
        ).strip()
        run_path = out.splitlines()[-1] if out else ""
    except Exception as e:
        print(f"AVISO: run package não criado: {e}")
    state["latest_run_id"] = run_path
    mission_keywords = ("self-evolve", "goal-sprint", "qa-sprint", "browser-qa", "final-gate")
    if next_cmd.startswith("./jarvis") and any(kw in next_cmd for kw in mission_keywords):
        state["status"] = "mission_generated"
    else:
        state["status"] = "started"

    _save_current(state)
    _append_event({"work_id": work_id, "ts": _now_iso(), "type": "started",
                    "request": text, "intent": intent, "project": project, "safety": safety})
    if run_path:
        _append_event({"work_id": work_id, "ts": _now_iso(), "type": "run_created", "run": run_path})
    if task_id:
        _append_event({"work_id": work_id, "ts": _now_iso(), "type": "task_linked", "note": task_id})

    print(f"current: {CURRENT.relative_to(ROOT)}  (gitignored)")
    if run_path:
        print(f"run:     {run_path}")
    if task_id:
        print(f"task:    {task_id}")
    print("")
    print("── Próximo comando (Theo executa) ──────────────────────────")
    print(_next_action_for(state))
    print("────────────────────────────────────────────────────────────")
    print("")
    print("Produção: nada alterado por JARVIS.")


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(argv):
    print("JARVIS — Work Status")
    print("Status real: leitura local da sessão atual. Nada editado.")
    print("")
    state = _load_current()
    if not state:
        print("(nenhuma work session ativa)")
        print("Sugestão:")
        print('  ./jarvis work-start "pedido"')
        print('  ./jarvis task-next')
        print('  ./jarvis go "o que faço agora"')
        print("")
        print("Produção: nada alterado.")
        return
    expected = state.get("expected_report_path") or ""
    report_present = bool(expected) and Path(expected).exists()
    print(f"work_id: {state.get('work_id')}")
    print(f"created: {state.get('created_at')}")
    print(f"updated: {state.get('updated_at')}")
    print(f"request: {state.get('request')}")
    print(f"intent:  {state.get('intent')}")
    print(f"project: {state.get('project') or '(não detectado)'}")
    print(f"safety:  {state.get('safety')}")
    print(f"status:  {state.get('status')}")
    print(f"run:     {state.get('latest_run_id') or '(?)'}")
    print(f"report:  {expected or '(?)'}  ({'presente' if report_present else 'ausente'})")
    print(f"debrief: {state.get('debrief_command')}")
    print(f"production_touched: {state.get('production_touched', False)}")
    print("")
    # Tree state for context (read-only)
    try:
        code = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, timeout=5)
        dirty = bool([l for l in code.stdout.splitlines() if l.strip()])
        print(f"tree: {'suja' if dirty else 'limpa'}")
    except Exception:
        pass
    print("")
    print("── Próximo comando ─────────────────────────────────────────")
    print(_next_action_for(state))
    print("────────────────────────────────────────────────────────────")
    print("")
    print("Produção: nada alterado.")


# ── next ──────────────────────────────────────────────────────────────────────

def cmd_next(argv):
    print("JARVIS — Work Next")
    print("Status real: decisão local. Nada editado.")
    print("")
    state = _load_current()
    print(_next_action_for(state))
    print("")
    print("Produção: nada alterado.")


# ── block ─────────────────────────────────────────────────────────────────────

def cmd_block(argv):
    _text, _project, dry_run, _force, _no_task, reason = _parse_common(argv)
    print("JARVIS — Work Block")
    print("Status real: marca sessão como blocked. Nada em produção.")
    print("")
    state = _load_current()
    if not state:
        print("FALHA: não há work session ativa para bloquear.")
        sys.exit(1)
    if not reason:
        print("FALHA: --reason obrigatório.")
        sys.exit(1)
    if _looks_secret_like(reason):
        print("FALHA: reason parece conter segredo. NÃO gravamos nada.")
        sys.exit(2)
    print(f"work_id: {state.get('work_id')}")
    print(f"reason:  {reason}")
    if dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return
    state["status"] = "blocked"
    state["block_reason"] = reason
    _save_current(state)
    _append_event({"work_id": state.get("work_id"), "ts": _now_iso(), "type": "blocked", "reason": reason})
    print("OK — sessão marcada como blocked.")
    print("Para retomar: ./jarvis work-status  e decida manualmente.")
    print("Produção: nada alterado.")


# ── close ─────────────────────────────────────────────────────────────────────

def cmd_close(argv):
    _text, _project, dry_run, force, _no_task, _reason = _parse_common(argv)
    print("JARVIS — Work Close")
    print("Status real: fecha sessão atual. Nada em produção.")
    print("")
    state = _load_current()
    if not state:
        print("(nenhuma work session ativa — nada a fechar)")
        print("Produção: nada alterado.")
        return
    status = state.get("status", "started")
    if status not in ("gates_passed", "blocked") and not force:
        print(f"AVISO: status atual = {status}; esperado 'gates_passed' ou 'blocked'.")
        print("Para forçar: ./jarvis work-close --force")
        if not dry_run:
            sys.exit(3)
    print(f"work_id: {state.get('work_id')}  prev_status={status}")
    if dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return
    state["status"] = "closed"
    _save_current(state)
    _append_event({"work_id": state.get("work_id"), "ts": _now_iso(), "type": "closed", "forced": bool(force)})
    print("OK — sessão fechada (current.json mantida em 'closed' para auditoria).")
    print("Próximo: ./jarvis task-next  ou  ./jarvis go \"...\"")
    print("Produção: nada alterado.")


# ── resume ────────────────────────────────────────────────────────────────────

def cmd_resume(argv):
    """Read-only: prints work-status + work-next + small summary so Theo
    can pick back up after interruption."""
    print("JARVIS — Resume")
    print("Status real: retomada read-only. Nada editado.")
    print("")
    state = _load_current()
    if not state:
        print("(nenhuma work session ativa)")
        print("")
        # Try to surface latest run + top task so resume is still useful.
        _print_latest_run()
        _print_top_task()
        print("Sugestão principal:")
        print('  ./jarvis work-start "pedido"   # inicia ciclo com lifecycle')
        print('  ./jarvis go "o que faço agora" --dry-run  # apenas explorar')
        print("")
        print("Produção: nada alterado.")
        return
    cmd_status([])
    print("")
    _print_latest_run()
    _print_top_task()


def _print_latest_run():
    runs_dir = ROOT / "05_EXECUCAO" / "35_RUNS"
    if not runs_dir.exists():
        return
    runs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"],
                  key=lambda d: d.stat().st_mtime)
    if not runs:
        return
    latest = runs[-1]
    req_file = latest / "01_REQUEST.md"
    first = ""
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                first = s
                break
    print("## Último run package")
    print(f"  {latest.relative_to(ROOT)}")
    if first:
        print(f"  {first}")
    print("")


def _print_top_task():
    tasks_file = ROOT / "05_EXECUCAO" / "34_TASKS" / "tasks.jsonl"
    if not tasks_file.exists():
        return
    pending = []
    seen_done_or_blocked = set()
    # naive replay
    for line in tasks_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") in ("done", "blocked"):
            seen_done_or_blocked.add(ev.get("id"))
        if ev.get("type") == "created":
            if ev.get("id") not in seen_done_or_blocked:
                pending.append(ev)
    if not pending:
        return
    top = pending[0]
    print("## Top task pendente")
    print(f"  id: {top.get('id')}")
    print(f"  text: {top.get('text','')}")
    print(f"  hint: ./jarvis task-next   # ver detalhes + comando sugerido")
    print("")


# ── status setters used by external callers (report_intake.py) ────────────────

def update_status(new_status: str, **extra):
    """Public helper for report_intake to advance the lifecycle.
    Returns True if a current session existed and was updated."""
    if new_status not in VALID_STATUSES:
        return False
    state = _load_current()
    if not state:
        return False
    state["status"] = new_status
    for k, v in extra.items():
        state[k] = v
    _save_current(state)
    _append_event({"work_id": state.get("work_id"), "ts": _now_iso(),
                    "type": "status_change", "to": new_status, "extra": list(extra.keys())})
    return True


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: work_session.py <start|status|next|block|close|resume> [args]")
        sys.exit(1)
    sub = argv[0]
    rest = argv[1:]
    if sub == "start":
        cmd_start(rest)
    elif sub == "status":
        cmd_status(rest)
    elif sub == "next":
        cmd_next(rest)
    elif sub == "block":
        cmd_block(rest)
    elif sub == "close":
        cmd_close(rest)
    elif sub == "resume":
        cmd_resume(rest)
    else:
        print(f"FALHA: subcomando desconhecido: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
