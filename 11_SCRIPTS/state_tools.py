"""
state_tools.py — JARVIS local state inspection / safe reset.

Theo needs a way to recover when a work session is stuck. This module
inspects runtime state and offers a *safe* reset that only touches the
current work-session pointer (never tasks, runs, gates, blueprints,
plans, learning data — those are append-only history).

Sub-commands:
  status                      # one-screen state summary, read-only
  reset --dry-run|--apply     # removes current.json (work session pointer)
  archive --dry-run|--apply   # copies current.json into archive/<ts>_current.json

Hard rules:
  - --dry-run is the default; --apply is required to mutate
  - only touches 05_EXECUCAO/36_WORK_SESSIONS/current.json
  - never deletes events.jsonl
  - never deletes tasks, runs, gates, blueprints, plans, learning data
  - never edits projects / production
  - never reads .env or prints secrets
"""
from pathlib import Path
from datetime import datetime
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SESS_DIR = ROOT / "05_EXECUCAO" / "36_WORK_SESSIONS"
CURRENT = SESS_DIR / "current.json"
EVENTS = SESS_DIR / "events.jsonl"
ARCHIVE_DIR = SESS_DIR / "archive"
TASKS = ROOT / "05_EXECUCAO" / "34_TASKS" / "tasks.jsonl"
GATES_LATEST = ROOT / "05_EXECUCAO" / "37_GATES" / "latest.json"
GATES_EVENTS = ROOT / "05_EXECUCAO" / "37_GATES" / "events.jsonl"
RUNS_DIR = ROOT / "05_EXECUCAO" / "35_RUNS"
BLUEPRINTS_DIR = ROOT / "05_EXECUCAO" / "40_BLUEPRINTS"
PLANS_DIR = ROOT / "05_EXECUCAO" / "33_PLANS"
ASK_LEARNING = ROOT / "05_EXECUCAO" / "32_ASK_LEARNING" / "UNCLEAR_REQUESTS.md"


def _run(cmd, timeout=10):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=timeout)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def _gitignored(rel: str) -> bool:
    code, _ = _run(["git", "check-ignore", "-q", rel])
    return code == 0


def _safe_load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_dir(path: Path, suffix=None):
    if not path.exists():
        return 0
    n = 0
    for p in path.iterdir():
        if p.name.startswith("."):
            continue
        if suffix and p.suffix != suffix:
            continue
        n += 1
    return n


def cmd_status(argv):
    print("JARVIS — State Status")
    print("Status real: leitura local. Nada foi editado.")
    print("")

    print("## Work session")
    cs = _safe_load_json(CURRENT)
    if not CURRENT.exists():
        print("  (nenhuma sessão ativa)")
    elif cs is None:
        print("  current.json existe mas falhou parse — considere state-reset --dry-run")
    else:
        print(f"  status:  {cs.get('status', '?')}")
        print(f"  intent:  {cs.get('intent', '?')}")
        print(f"  project: {cs.get('project', '?')}")
        nc = cs.get("next_command")
        if nc:
            print(f"  next:    {nc}")
    print("")

    print("## Task queue")
    if TASKS.exists():
        try:
            with TASKS.open(encoding="utf-8") as f:
                n = sum(1 for line in f if line.strip())
            print(f"  tasks.jsonl: {n} linha(s) append-only")
        except Exception as e:
            print(f"  erro lendo tasks.jsonl: {e}")
    else:
        print("  (não criado)")
    print("")

    print("## Gates")
    if GATES_LATEST.exists():
        data = _safe_load_json(GATES_LATEST)
        if data:
            print(f"  último: {data.get('ts', '?')}  all_ok={data.get('all_ok', '?')}")
        else:
            print("  latest.json parse erro")
    else:
        print("  (sem gate-run ainda)")
    print("")

    print("## Pacotes")
    print(f"  run packages:    {_count_dir(RUNS_DIR)}")
    print(f"  blueprints:      {_count_dir(BLUEPRINTS_DIR)}")
    print(f"  plans salvos:    {_count_dir(PLANS_DIR, suffix='.md')}")
    print("")

    print("## Learning")
    if ASK_LEARNING.exists():
        try:
            size = ASK_LEARNING.stat().st_size
            print(f"  UNCLEAR_REQUESTS.md: presente ({size} bytes)")
        except Exception:
            print("  UNCLEAR_REQUESTS.md: presente")
    else:
        print("  UNCLEAR_REQUESTS.md: (ainda não criado)")
    print("")

    print("## Runtime gitignore")
    checks = [
        "05_EXECUCAO/34_TASKS/tasks.jsonl",
        "05_EXECUCAO/36_WORK_SESSIONS/current.json",
        "05_EXECUCAO/36_WORK_SESSIONS/events.jsonl",
        "05_EXECUCAO/37_GATES/latest.json",
        "05_EXECUCAO/37_GATES/events.jsonl",
    ]
    for rel in checks:
        ok = _gitignored(rel)
        badge = "OK   " if ok else "FALHA"
        print(f"  {badge}  {rel}")
    print("")

    print("## Próxima ação sugerida")
    if not CURRENT.exists():
        print("  ./jarvis start \"pedido\"          # iniciar nova sessão")
        print("  ./jarvis cheatsheet              # ver atalhos")
    elif cs and cs.get("status") in ("closed", "blocked"):
        print("  ./jarvis state-reset --dry-run   # remover sessão fechada/bloqueada")
        print("  ./jarvis state-archive --dry-run # ou arquivar antes")
    else:
        print("  ./jarvis next                    # próximo passo seguro do lifecycle")
        print("  ./jarvis state-reset --dry-run   # se a sessão estiver presa")
    print("")
    print("Produção: nada alterado.")


def _parse_flags(argv):
    apply = False
    dry = False
    for a in argv:
        if a == "--apply":
            apply = True
        elif a == "--dry-run":
            dry = True
    if not apply:
        dry = True
    return dry, apply


def cmd_reset(argv):
    dry, apply = _parse_flags(argv)
    print("JARVIS — State Reset")
    print(f"Modo: {'--apply' if apply else '--dry-run (default)'}")
    print("Status real: somente current.json é elegível. events.jsonl/tasks/runs/gates NUNCA são tocados.")
    print("")

    if not CURRENT.exists():
        print("  (nenhuma current.json para remover)")
        print("Produção: nada alterado.")
        return

    rel = str(CURRENT.relative_to(ROOT))
    print(f"## Alvo")
    print(f"  arquivo: {rel}")
    try:
        size = CURRENT.stat().st_size
        print(f"  bytes:   {size}")
    except Exception:
        pass
    data = _safe_load_json(CURRENT)
    if data:
        print(f"  status:  {data.get('status', '?')}")
        print(f"  intent:  {data.get('intent', '?')}")
        print(f"  project: {data.get('project', '?')}")
    print("")

    if dry:
        print("DRY-RUN: nada removido. Use --apply para confirmar.")
        print(f"Próximo: ./jarvis state-reset --apply  # removeria {rel}")
        print("Produção: nada alterado.")
        return

    # Safety: never operate outside 36_WORK_SESSIONS
    if SESS_DIR.resolve() not in CURRENT.resolve().parents:
        print(f"FALHA: alvo fora de {SESS_DIR.relative_to(ROOT)} — abortando.")
        sys.exit(1)
    try:
        CURRENT.unlink()
        print(f"REMOVIDO: {rel}")
        print("Status real: events.jsonl preservado (append-only history).")
        print("Produção: nada alterado.")
    except Exception as e:
        print(f"FALHA: não removi {rel}: {e}")
        sys.exit(1)


def cmd_archive(argv):
    dry, apply = _parse_flags(argv)
    print("JARVIS — State Archive")
    print(f"Modo: {'--apply' if apply else '--dry-run (default)'}")
    print(f"Destino: {ARCHIVE_DIR.relative_to(ROOT)}/")
    print("Status real: cópia local. Não toca current.json original.")
    print("")

    if not CURRENT.exists():
        print("  (nenhuma current.json para arquivar)")
        print("Produção: nada alterado.")
        return

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    target = ARCHIVE_DIR / f"{ts}_current.json"
    rel_src = str(CURRENT.relative_to(ROOT))
    rel_dst = str(target.relative_to(ROOT))

    print(f"## Origem")
    print(f"  {rel_src}")
    print(f"## Destino")
    print(f"  {rel_dst}")
    print("")

    if dry:
        print("DRY-RUN: nenhuma cópia feita. Use --apply para confirmar.")
        print(f"Próximo: ./jarvis state-archive --apply  # copiaria para {rel_dst}")
        print("Produção: nada alterado.")
        return

    try:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CURRENT, target)
        print(f"COPIADO: {rel_dst}")
        print(f"Status real: cópia gitignored (archive/). Original {rel_src} preservado.")
        print("Produção: nada alterado.")
    except Exception as e:
        print(f"FALHA: cópia falhou: {e}")
        sys.exit(1)


def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: state_tools.py {status|reset|archive} [flags]")
        sys.exit(1)
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "status":
        cmd_status(rest)
    elif cmd == "reset":
        cmd_reset(rest)
    elif cmd == "archive":
        cmd_archive(rest)
    else:
        print(f"FALHA: sub-comando desconhecido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
