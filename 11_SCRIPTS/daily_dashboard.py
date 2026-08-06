"""
daily_dashboard.py — JARVIS one-screen daily dashboard.

Read-only summary: data/branch/tree/health/work/gates/top-task/next.
Nunca chama API, nunca executa Claude, nunca edita.

Usage:
  ./jarvis daily
"""
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys

from decision_log import read_decisions

ROOT = Path(__file__).resolve().parents[1]
GATES_LATEST = ROOT / "05_EXECUCAO" / "37_GATES" / "latest.json"
CURRENT_SESSION = ROOT / "05_EXECUCAO" / "36_WORK_SESSIONS" / "current.json"
TASKS = ROOT / "05_EXECUCAO" / "34_TASKS" / "tasks.jsonl"
RUNS_DIR = ROOT / "05_EXECUCAO" / "35_RUNS"


def _run(cmd, timeout=10):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=timeout)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def _safe_load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _top_task():
    if not TASKS.exists():
        return None
    try:
        seen = {}
        with TASKS.open(encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except Exception:
                    continue
                tid = ev.get("task_id") or ev.get("id")
                if not tid:
                    continue
                if tid not in seen:
                    seen[tid] = ev
                else:
                    seen[tid].update(ev)
        for tid, ev in seen.items():
            if ev.get("status") in ("pending", None):
                return ev
        return None
    except Exception:
        return None


def _latest_run():
    if not RUNS_DIR.exists():
        return None
    dirs = sorted(
        [p for p in RUNS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")],
        key=lambda p: p.name,
        reverse=True,
    )
    return dirs[0] if dirs else None


def _agent_doctor_quick():
    """Return (status_word, message) — never blocks, ~2s."""
    code, out = _run(["./jarvis", "doctor-agent"], timeout=30)
    last = ""
    for line in (out or "").splitlines():
        if line.startswith("AGENT DOCTOR"):
            last = line.strip()
    if code == 0 and last:
        return ("OK", last)
    if code != 0 and last:
        return ("PENDÊNCIAS", last)
    return ("?", "agent doctor não retornou linha de resultado")


def _next_command(session):
    if not session:
        return './jarvis start "pedido"   # iniciar lifecycle do dia'
    st = session.get("status")
    nc = session.get("next_command")
    if nc:
        return nc
    if st in ("started", "mission_generated"):
        return "./jarvis next"
    if st == "report_pending":
        return "./jarvis report-template"
    if st in ("report_checked", "debrief_applied"):
        return "./jarvis gates"
    if st == "gates_passed":
        return "./jarvis finish"
    if st == "blocked":
        return "./jarvis state-reset --dry-run"
    return "./jarvis next"


def main():
    print("JARVIS — Daily Dashboard")
    print("Status real: leitura local. Nada foi editado.")
    print("")

    now = datetime.now().isoformat(timespec="seconds")
    _, branch = _run(["git", "branch", "--show-current"])
    _, dirty = _run(["git", "status", "--short"])
    dirty_lines = [l for l in (dirty or "").splitlines() if l.strip()]
    dirty_flag = bool(dirty_lines)

    print(f"## 0. Now")
    print(f"  data:   {now}")
    print(f"  branch: {branch or '(?)'}")
    if dirty_flag:
        print(f"  tree:   suja ({len(dirty_lines)} arquivo(s))   ⚠ STOP: rode `git status --short`")
    else:
        print(f"  tree:   limpa")
    print("")

    print("## 1. Health")
    word, msg = _agent_doctor_quick()
    print(f"  doctor-agent: {word}")
    print(f"  {msg}")
    print("")

    print("## 2. Active Work")
    session = _safe_load_json(CURRENT_SESSION)
    if not session:
        print("  (nenhuma sessão ativa)")
    else:
        print(f"  status:  {session.get('status', '?')}")
        print(f"  intent:  {session.get('intent', '?')}")
        print(f"  project: {session.get('project', '?')}")
        req = session.get("request") or ""
        if req:
            print(f"  request: {req[:80]}{'…' if len(req) > 80 else ''}")
    print("")

    print("## 3. Next")
    print(f"  {_next_command(session)}")
    print("")

    print("## 4. Gates")
    g = _safe_load_json(GATES_LATEST)
    if not g:
        print("  (sem gate-run ainda — `./jarvis gates`)")
    else:
        ok = g.get("all_ok", False)
        print(f"  último: {g.get('ts', '?')}  all_ok={ok}")
        for r in g.get("results", []):
            tag = "OK   " if r.get("ok") else "FALHA"
            print(f"    {tag} {r.get('name', '?')}  exit={r.get('exit_code', '?')}")
    print("")

    print("## 5. Top Task")
    t = _top_task()
    if not t:
        print("  (nenhuma task)")
    else:
        tid = t.get("task_id") or t.get("id") or "?"
        text = (t.get("text") or t.get("request") or "").strip()
        print(f"  {tid}  {text[:80]}{'…' if len(text) > 80 else ''}")
    print("")

    print("## 6. Recent Decisions")
    decisions = read_decisions()[-3:]
    if not decisions:
        print("  (nenhuma — use `./jarvis decision-add \"...\" --dry-run` para preview)")
    else:
        for decision in reversed(decisions):
            text = str(decision.get("decision", ""))
            project = decision.get("project") or "-"
            print(f"  {decision.get('id', '?')}  project={project}  {text[:80]}{'…' if len(text) > 80 else ''}")
    print("")

    print("## 7. Latest Run")
    r = _latest_run()
    if not r:
        print("  (nenhum)")
    else:
        print(f"  {r.relative_to(ROOT)}")
    print("")

    print("## 8. Useful Commands")
    print("  ./jarvis decision-list                    # decisões operacionais recentes")
    print("  ./jarvis assistant-doctor                 # captura/imagem/voz/mensagem")
    print("  ./jarvis storage-scan ~/Downloads         # arquivos grandes, sem apagar")
    print("  ./jarvis files-triage ~/Downloads         # organização em preview")
    print("  ./jarvis cheatsheet                       # atalhos essenciais")
    print("  ./jarvis recipe-list                      # golden paths")
    print('  ./jarvis no-claude "pedido"               # offline mode')
    print("  ./jarvis handoff-self --save              # snapshot para handoff")
    print("  ./jarvis health                           # doctor-agent")
    print("  ./jarvis rc-status                        # release readiness")
    print("")

    if dirty_flag:
        print("Aviso: árvore suja — resolva antes de rodar `./jarvis gates`.")
    print("Produção: nada alterado. Claude não executado.")


if __name__ == "__main__":
    main()
