"""
handoff_self.py — JARVIS snapshot para handoff humano (ChatGPT, time, etc.).

Quando Theo precisar trocar de IDE/AI ou contar para alguém "onde a coisa
está", roda:
  ./jarvis handoff-self
  ./jarvis handoff-self --save   # grava em 39_HANDOFFS/

Output: status de JARVIS (branch, commits, sessão, gates, top task, run,
capabilities, próximos comandos) — sem segredos, sem APIs.

Hard rules:
  - read-only
  - sem API paga
  - sem segredos (não lê .env, não imprime tokens)
  - sem produção
"""
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HANDOFF_DIR = ROOT / "05_EXECUCAO" / "39_HANDOFFS"
CAPABILITY_REGISTRY = ROOT / "01_SISTEMA" / "06_CAPABILITIES" / "CAPABILITY_REGISTRY.json"
GATES_LATEST = ROOT / "05_EXECUCAO" / "37_GATES" / "latest.json"
CURRENT_SESSION = ROOT / "05_EXECUCAO" / "36_WORK_SESSIONS" / "current.json"
TASKS = ROOT / "05_EXECUCAO" / "34_TASKS" / "tasks.jsonl"
RUNS_DIR = ROOT / "05_EXECUCAO" / "35_RUNS"


def parse_args(argv):
    save = False
    for a in argv:
        if a == "--save":
            save = True
    return save


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


def _last_lines(path: Path, n: int):
    if not path.exists():
        return []
    try:
        lines = [l for l in path.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
        return lines[-n:]
    except Exception:
        return []


def _top_task():
    """Best-effort: read tasks.jsonl, find oldest pending."""
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
                    # updates may change status
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
    if not dirs:
        return None
    return dirs[0]


def _capability_summary():
    data = _safe_load_json(CAPABILITY_REGISTRY)
    if not data or not isinstance(data, dict):
        return None
    by_group = {}
    groups = data.get("groups", {}) or {}
    if isinstance(groups, dict):
        for gname, g in groups.items():
            caps = (g or {}).get("capabilities", []) or []
            by_group[gname] = len(caps)
    if not by_group:
        caps = data.get("capabilities", []) or []
        for c in caps:
            g = c.get("group", "?")
            by_group.setdefault(g, 0)
            by_group[g] += 1
    return by_group


def build_snapshot():
    lines = []
    lines.append("# JARVIS Handoff Snapshot")
    lines.append("")
    lines.append(f"## Timestamp\n{datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Status real")
    lines.append("Snapshot local. Claude não executado. API paga não chamada. Sem segredos.")
    lines.append("")

    # Git
    _, branch = _run(["git", "branch", "--show-current"])
    _, log = _run(["git", "log", "--oneline", "-12"])
    _, dirty = _run(["git", "status", "--short"])
    lines.append("## Git")
    lines.append(f"- branch: `{branch or '(?)'}`")
    dirty_lines = [l for l in (dirty or "").splitlines() if l.strip()]
    lines.append(f"- tree: {'suja (' + str(len(dirty_lines)) + ')' if dirty_lines else 'limpa'}")
    lines.append("")
    lines.append("### Recent commits")
    lines.append("```")
    lines.append(log or "(vazio)")
    lines.append("```")
    lines.append("")

    # Work session
    lines.append("## Work session atual")
    cs = _safe_load_json(CURRENT_SESSION)
    if cs is None and CURRENT_SESSION.exists():
        lines.append("- current.json existe mas falhou parse (use ./jarvis state-reset --dry-run)")
    elif cs is None:
        lines.append("- (nenhuma sessão ativa)")
    else:
        lines.append(f"- status:  `{cs.get('status', '?')}`")
        lines.append(f"- intent:  `{cs.get('intent', '?')}`")
        lines.append(f"- project: `{cs.get('project', '?')}`")
        nc = cs.get("next_command")
        if nc:
            lines.append(f"- next_command: `{nc}`")
    lines.append("")

    # Gates
    lines.append("## Latest gates")
    g = _safe_load_json(GATES_LATEST)
    if not g:
        lines.append("- (sem gate-run registrado)")
    else:
        lines.append(f"- ts: `{g.get('ts', '?')}`")
        lines.append(f"- all_ok: `{g.get('all_ok', '?')}`")
        for r in g.get("results", []):
            tag = "OK   " if r.get("ok") else "FALHA"
            lines.append(f"  - {tag} {r.get('name', '?')}: exit={r.get('exit_code', '?')}")
    lines.append("")

    # Top task
    lines.append("## Top task pendente")
    t = _top_task()
    if not t:
        lines.append("- (nenhuma)")
    else:
        tid = t.get("task_id") or t.get("id") or "?"
        text = (t.get("text") or t.get("request") or "")
        lines.append(f"- id: `{tid}`")
        lines.append(f"- texto: {text!r}")
    lines.append("")

    # Latest run
    lines.append("## Latest run package")
    r = _latest_run()
    if not r:
        lines.append("- (nenhum)")
    else:
        lines.append(f"- {r.relative_to(ROOT)}")
        req = r / "01_REQUEST.md"
        if req.exists():
            first = req.read_text(encoding="utf-8", errors="ignore").splitlines()
            first = [l for l in first if l.strip()][:5]
            lines.append("```")
            lines.extend(first)
            lines.append("```")
    lines.append("")

    # Capabilities
    lines.append("## Capabilities (resumo)")
    cap = _capability_summary()
    if not cap:
        lines.append("- (registry indisponível)")
    else:
        for g, n in sorted(cap.items()):
            lines.append(f"- {g}: {n}")
    lines.append("")

    # Important commands
    lines.append("## Comandos importantes (cheatsheet)")
    lines.append("```")
    lines.append("./jarvis now                       # retomar")
    lines.append("./jarvis start \"pedido\"            # iniciar lifecycle")
    lines.append("./jarvis next                      # próximo passo seguro")
    lines.append("./jarvis gates                     # safety+smoke+doctrine")
    lines.append("./jarvis finish                    # fechar sessão")
    lines.append("./jarvis no-claude \"pedido\"        # offline mode")
    lines.append("./jarvis health                    # doctor-agent")
    lines.append("./jarvis state-status              # ver estado")
    lines.append("./jarvis state-reset --dry-run     # destravar")
    lines.append("./jarvis cheatsheet                # essa tela")
    lines.append("```")
    lines.append("")

    # Next command
    next_cmd = "./jarvis now"
    if cs:
        st = cs.get("status")
        if st in ("started", "mission_generated"):
            next_cmd = "./jarvis next  # gerar/aplicar relatório"
        elif st == "report_pending":
            next_cmd = "./jarvis report-template"
        elif st in ("report_checked", "debrief_applied"):
            next_cmd = "./jarvis gates"
        elif st == "gates_passed":
            next_cmd = "./jarvis finish"
        elif st == "blocked":
            next_cmd = "./jarvis state-reset --dry-run"
    lines.append("## Próximo comando sugerido")
    lines.append(f"`{next_cmd}`")
    lines.append("")

    # Hard rules
    lines.append("## Hard rules (não negociáveis)")
    lines.append("- Sem API paga (Anthropic/OpenAI).")
    lines.append("- Sem deploy/push/PR/merge.")
    lines.append("- Sem migrations / produção / VPS / n8n real.")
    lines.append("- Sem ler .env. Sem imprimir tokens.")
    lines.append("- main/master = STOP.")
    lines.append("")
    lines.append("## Produção")
    lines.append("Nada alterado.")
    lines.append("")
    return "\n".join(lines)


def main():
    save = parse_args(sys.argv[1:])
    snap = build_snapshot()

    print("JARVIS — Handoff Self")
    print("Status real: snapshot local. Claude não executado. Sem segredos.")
    print("")
    print(snap)

    if save:
        try:
            HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
            target = HANDOFF_DIR / f"{ts}_jarvis_handoff.md"
            target.write_text(snap, encoding="utf-8")
            print("")
            print(f"## Arquivo gravado")
            print(f"  {target.relative_to(ROOT)}")
            print("Produção: nada alterado.")
        except Exception as e:
            print(f"FALHA: não gravei snapshot: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
