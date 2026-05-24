"""
release_candidate.py — JARVIS RC status + freeze snapshot.

Read-only por padrão. `freeze --apply` grava snapshot textual em
05_EXECUCAO/41_RELEASE_CANDIDATES/<ts>_jarvis_rc.md (gitignored).
Nunca cria git tag, nunca faz push, nunca dispara upload.

Usage:
  ./jarvis rc-status
  ./jarvis rc-freeze --dry-run
  ./jarvis rc-freeze --apply [--skip-gates]
"""
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RC_DIR = ROOT / "05_EXECUCAO" / "41_RELEASE_CANDIDATES"
GATES_LATEST = ROOT / "05_EXECUCAO" / "37_GATES" / "latest.json"
CURRENT_SESSION = ROOT / "05_EXECUCAO" / "36_WORK_SESSIONS" / "current.json"
TASKS = ROOT / "05_EXECUCAO" / "34_TASKS" / "tasks.jsonl"


def _run(cmd, timeout=60):
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


def _command_count():
    code, out = _run(["./jarvis", "command-audit"], timeout=120)
    # last line typically: "Scripts Python detectados: N"
    n = None
    audit_ok = code == 0
    for line in (out or "").splitlines():
        if "Scripts Python detectados:" in line:
            try:
                n = int(line.split(":", 1)[1].strip())
            except Exception:
                pass
    return audit_ok, n


def _readiness(clean_tree, gates_ok, audit_ok, doctor_ok):
    if not clean_tree:
        return "NOT READY", "árvore suja — commit ou stash antes."
    if not audit_ok:
        return "NOT READY", "command-audit reportou pendências."
    if not doctor_ok:
        return "NOT READY", "doctor-agent reportou pendências."
    if gates_ok is False:
        return "NOT READY", "último gate-run não está all_ok."
    if gates_ok is None:
        return "READY WITH WARNINGS", "nenhum gate-run registrado — rode `./jarvis gates`."
    return "READY", "tudo verde para snapshot."


def _gather():
    """Return a dict of all the things the RC commands need."""
    _, branch = _run(["git", "branch", "--show-current"])
    _, log = _run(["git", "log", "--oneline", "-12"])
    _, dirty = _run(["git", "status", "--short"])
    _, hash_now = _run(["git", "rev-parse", "--short", "HEAD"])
    dirty_lines = [l for l in (dirty or "").splitlines() if l.strip()]
    clean = not dirty_lines

    gates = _safe_load_json(GATES_LATEST)
    if not gates:
        gates_ok = None
    else:
        gates_ok = bool(gates.get("all_ok"))

    audit_ok, n_scripts = _command_count()

    code_doctor, doctor_out = _run(["./jarvis", "doctor-agent"], timeout=60)
    doctor_summary = ""
    for ln in (doctor_out or "").splitlines():
        if ln.startswith("AGENT DOCTOR"):
            doctor_summary = ln.strip()
    doctor_ok = code_doctor == 0

    return {
        "branch": branch or "(?)",
        "commit": hash_now or "(?)",
        "log": log or "(vazio)",
        "clean": clean,
        "dirty_count": len(dirty_lines),
        "gates": gates,
        "gates_ok": gates_ok,
        "audit_ok": audit_ok,
        "n_scripts": n_scripts,
        "doctor_ok": doctor_ok,
        "doctor_summary": doctor_summary,
        "session": _safe_load_json(CURRENT_SESSION),
        "top_task": _top_task(),
    }


def cmd_status():
    print("JARVIS — RC Status")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    info = _gather()
    print(f"## Git")
    print(f"  commit: {info['commit']}")
    print(f"  branch: {info['branch']}")
    tree_desc = "limpa" if info["clean"] else f"suja ({info['dirty_count']} arquivo(s))"
    print(f"  tree:   {tree_desc}")
    print("")
    print("## Recent commits")
    for line in info["log"].splitlines()[:8]:
        print(f"  {line}")
    print("")
    print("## Gates")
    g = info["gates"]
    if not g:
        print("  (sem gate-run registrado — rode `./jarvis gates`)")
    else:
        print(f"  último:  {g.get('ts', '?')}")
        print(f"  all_ok:  {g.get('all_ok', '?')}")
        for r in g.get("results", []):
            tag = "OK   " if r.get("ok") else "FALHA"
            print(f"    {tag} {r.get('name', '?')}  exit={r.get('exit_code', '?')}")
    print("")
    print("## Doctor")
    print(f"  command-audit: {'OK' if info['audit_ok'] else 'FALHA'}  ({info['n_scripts']} script(s))")
    print(f"  doctor-agent:  {info['doctor_summary'] or '?'}")
    print("")
    print("## Sessão / task")
    s = info["session"]
    if not s:
        print("  active work: (nenhuma)")
    else:
        print(f"  active work: status={s.get('status', '?')}  intent={s.get('intent', '?')}  project={s.get('project', '?')}")
    t = info["top_task"]
    if not t:
        print("  top task:    (nenhuma)")
    else:
        tid = t.get("task_id") or t.get("id") or "?"
        text = (t.get("text") or t.get("request") or "").strip()
        print(f"  top task:    {tid}  {text[:80]}{'…' if len(text) > 80 else ''}")
    print("")
    print("## Readiness")
    state, reason = _readiness(info["clean"], info["gates_ok"], info["audit_ok"], info["doctor_ok"])
    print(f"  {state}  — {reason}")
    print("")
    if state == "READY":
        print("Próximo: ./jarvis rc-freeze --dry-run")
    elif state == "READY WITH WARNINGS":
        print("Próximo: ./jarvis gates   # gerar latest.json antes de freeze")
    else:
        print("Próximo: investigue acima antes de rc-freeze.")
    print("Produção: nada alterado.")


def _snapshot_text(info):
    ts = datetime.now().isoformat(timespec="seconds")
    g = info["gates"] or {}
    s = info["session"] or {}
    t = info["top_task"] or {}
    state, reason = _readiness(info["clean"], info["gates_ok"], info["audit_ok"], info["doctor_ok"])

    lines = []
    lines.append("# JARVIS — Release Candidate Snapshot")
    lines.append("")
    lines.append(f"## Timestamp\n{ts}")
    lines.append("")
    lines.append("## Status real\nSnapshot local. Sem Claude. Sem API paga. Sem produção. Sem git tag, sem push.")
    lines.append("")
    tree_desc = "tree limpa" if info["clean"] else f"tree suja: {info['dirty_count']} arquivo(s)"
    lines.append(f"## Commit\n`{info['commit']}` em `{info['branch']}` ({tree_desc})")
    lines.append("")
    lines.append("## Recent commits")
    lines.append("```")
    lines.append(info["log"])
    lines.append("```")
    lines.append("")
    lines.append("## Sprints (resumo dos comandos adicionados)")
    lines.append("- **Sprint 1-2:** core CLI + agent OS (ask/go/capture/inbox/agenda/blueprint/project-open/plan/limits/ask-log).")
    lines.append("- **Sprint 3:** task queue (task-add/list/next/show/done/block), run logs, capabilities, project-intel.")
    lines.append("- **Sprint 4:** work session lifecycle (work-start/status/next/block/close) + report intake (report-template/status/check/apply) + resume.")
    lines.append("- **Sprint 5:** gate-run/gate-status + run-prune + report `--project` override.")
    lines.append("- **Sprint 6:** aliases (now/start/next/finish/gates/health) + doctor-agent + state-status/reset/archive + no-claude + cheatsheet + handoff-self.")
    lines.append("- **Sprint 7:** daily + first-run-check + recipes (list/show/run) + rc-status/freeze + acceptance.")
    lines.append("")
    lines.append("## Gates")
    if not g:
        lines.append("- (sem gate-run registrado)")
    else:
        lines.append(f"- last run: `{g.get('ts', '?')}`  all_ok=`{g.get('all_ok', '?')}`")
        for r in g.get("results", []):
            tag = "OK" if r.get("ok") else "FALHA"
            lines.append(f"  - {tag} {r.get('name', '?')} exit={r.get('exit_code', '?')}")
    lines.append("")
    lines.append("## Doctor / audit")
    lines.append(f"- command-audit: {'OK' if info['audit_ok'] else 'FALHA'} ({info['n_scripts']} script(s))")
    lines.append(f"- doctor-agent: {info['doctor_summary'] or '?'}")
    lines.append("")
    lines.append("## Active state")
    if not s:
        lines.append("- work session: (nenhuma)")
    else:
        lines.append(f"- work session: status={s.get('status', '?')} intent={s.get('intent', '?')} project={s.get('project', '?')}")
    if not t:
        lines.append("- top task: (nenhuma)")
    else:
        tid = t.get("task_id") or t.get("id") or "?"
        text = (t.get("text") or t.get("request") or "").strip()
        lines.append(f"- top task: `{tid}`  {text}")
    lines.append("")
    lines.append("## Readiness")
    lines.append(f"- {state} — {reason}")
    lines.append("")
    lines.append("## Como começar depois de N horas (Theo entra fresco)")
    lines.append("```")
    lines.append("./jarvis daily            # dashboard de uma tela")
    lines.append("./jarvis first-run-check  # ambiente OK?")
    lines.append("./jarvis cheatsheet       # atalhos essenciais")
    lines.append("./jarvis recipe-list      # golden paths disponíveis")
    lines.append("```")
    lines.append("")
    lines.append("## Próximo comando")
    if state == "READY":
        lines.append("`./jarvis daily`")
    elif state == "READY WITH WARNINGS":
        lines.append("`./jarvis gates`  # gerar gate latest")
    else:
        lines.append("`./jarvis rc-status`  # investigue pendências")
    lines.append("")
    lines.append("## Hard rules")
    lines.append("- Sem API paga (Anthropic/OpenAI).")
    lines.append("- Sem deploy/push/PR/merge/migrations.")
    lines.append("- Sem edição de projetos-alvo. Sem produção.")
    lines.append("- Nunca lê `.env`. Nunca imprime tokens / cookies / QR codes.")
    lines.append("- main/master = STOP.")
    lines.append("")
    lines.append("## Produção")
    lines.append("Nada alterado.")
    lines.append("")
    return "\n".join(lines)


def cmd_freeze(argv):
    dry = True
    apply = False
    skip_gates = False
    for a in argv:
        if a == "--apply":
            apply = True
            dry = False
        elif a == "--dry-run":
            dry = True
            apply = False
        elif a == "--skip-gates":
            skip_gates = True

    print("JARVIS — RC Freeze")
    print(f"Modo: {'--apply' if apply else '--dry-run (default)'}")
    print("Status real: snapshot local. Sem git tag, sem push, sem upload.")
    print("")

    info = _gather()
    state, reason = _readiness(info["clean"], info["gates_ok"], info["audit_ok"], info["doctor_ok"])
    print(f"## Readiness: {state}")
    print(f"  motivo: {reason}")
    print("")

    if state == "NOT READY":
        print("FALHA: rc-freeze não congela com NOT READY.")
        print("Próximo: ./jarvis rc-status   # ver pendências")
        sys.exit(1)

    if state == "READY WITH WARNINGS" and not skip_gates:
        print("AVISO: nenhum gate-run registrado.")
        print("Sugestão: ./jarvis gates  (ou re-rode com --skip-gates para forçar)")
        sys.exit(1)

    snap = _snapshot_text(info)

    if dry:
        print("## Preview (primeiras 40 linhas)")
        for ln in snap.splitlines()[:40]:
            print(f"  {ln}")
        print("  …")
        print("")
        print("DRY-RUN: nenhum arquivo gravado.")
        print("Próximo: ./jarvis rc-freeze --apply   # grava em 41_RELEASE_CANDIDATES/")
        print("Produção: nada alterado.")
        return

    try:
        RC_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        target = RC_DIR / f"{ts}_jarvis_rc.md"
        target.write_text(snap, encoding="utf-8")
        print(f"## Snapshot gravado")
        print(f"  {target.relative_to(ROOT)}")
        print("Produção: nada alterado. Nenhum push/PR/merge/tag criado.")
    except Exception as e:
        print(f"FALHA: não gravei snapshot: {e}")
        sys.exit(1)


def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: release_candidate.py {status|freeze} [flags]")
        sys.exit(1)
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "status":
        cmd_status()
    elif cmd == "freeze":
        cmd_freeze(rest)
    else:
        print(f"FALHA: sub-comando desconhecido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
