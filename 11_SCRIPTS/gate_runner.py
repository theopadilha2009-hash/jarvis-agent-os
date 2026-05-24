"""
gate_runner.py — run the local JARVIS health gates and capture results.

This is **not** fake autonomy: safety-gate / smoke-test / doctrine-check are
already local validation commands Theo would run by hand. gate-run just
sequences them, captures the result line + exit code, and advances the
work session lifecycle from `debrief_applied` → `gates_passed` (or
`gates_pending` on failure).

Sub-commands (positional argv[0]):
  run                 execute the three gates, write latest.json + events.jsonl
  status              read latest.json and print a summary

Storage:
  05_EXECUCAO/37_GATES/latest.json   (mutable runtime state, gitignored)
  05_EXECUCAO/37_GATES/events.jsonl  (append-only, gitignored)
  05_EXECUCAO/37_GATES/.gitkeep      (tracked)

Hard rules:
  - never executes Claude
  - never calls APIs
  - never touches production
  - never reads .env contents
"""
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "05_EXECUCAO" / "37_GATES"
LATEST = DIR / "latest.json"
EVENTS = DIR / "events.jsonl"

# Reuse the work-session state advance helper (no extra subprocess hop).
try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from work_session import update_status, _load_current  # type: ignore
except Exception:
    def update_status(*a, **k):
        return False

    def _load_current():
        return None


GATES = [
    {
        "name": "safety-gate",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "safety-gate"],
        "expect": "SAFETY GATE PASSOU",
    },
    {
        "name": "smoke-test",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "smoke-test"],
        "expect": "CLI SMOKE TEST PASSOU",
    },
    {
        "name": "doctrine-check",
        "cmd": ["./jarvis", "doctrine-check"],
        "expect": "DOCTRINE CHECK PASSOU",
    },
]


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dir():
    DIR.mkdir(parents=True, exist_ok=True)


def _summary_line(output: str, expect: str) -> str:
    """Return the most informative single line we can find."""
    if not output:
        return "(sem output)"
    # First, prefer the canonical "Resultado: ..." line.
    for line in reversed(output.splitlines()):
        s = line.strip()
        if s.startswith("Resultado:"):
            return s
    # Otherwise, the expected pass phrase if present.
    if expect in output:
        return expect
    # Otherwise the last non-empty line.
    for line in reversed(output.splitlines()):
        s = line.strip()
        if s:
            return s
    return "(vazio)"


# ── run ───────────────────────────────────────────────────────────────────────

def cmd_run(argv):
    print("JARVIS — Gate Run")
    print("Status real: roda gates locais (safety/smoke/doctrine). Produção não tocada.")
    print("")
    _ensure_dir()

    results = []
    overall_ok = True
    for gate in GATES:
        print(f"-> {gate['name']} ...")
        try:
            proc = subprocess.run(
                gate["cmd"], cwd=ROOT, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180,
            )
            output = proc.stdout or ""
            code = proc.returncode
        except subprocess.TimeoutExpired:
            output = "(timeout 180s)"
            code = 124
        except Exception as e:
            output = f"(erro ao executar: {e})"
            code = 1
        ok = (code == 0) and (gate["expect"] in output)
        summary = _summary_line(output, gate["expect"])
        if not ok:
            overall_ok = False
        results.append({
            "name": gate["name"],
            "ok": ok,
            "exit_code": code,
            "summary": summary,
        })
        print(f"   {'OK   ' if ok else 'FALHA'}  exit={code}  {summary}")
    print("")

    payload = {
        "schema": "jarvis-gates-v0.1",
        "ts": _now_iso(),
        "all_ok": overall_ok,
        "results": results,
    }
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    if overall_ok:
        print("Resultado: GATES PASSARAM")
        # Advance work session if applicable.
        state = _load_current()
        if state and state.get("status") in ("debrief_applied", "gates_pending"):
            update_status("gates_passed",
                          next_command="./jarvis work-close",
                          gates_passed_at=_now_iso())
            print("Work session atualizada: status=gates_passed (next: ./jarvis work-close).")
        else:
            print("Work session: nada para atualizar (sem sessão ativa ou status incompatível).")
    else:
        print("Resultado: GATES COM PENDÊNCIAS")
        state = _load_current()
        if state and state.get("status") in ("debrief_applied", "gates_pending"):
            update_status("gates_pending",
                          next_command="./jarvis gate-run",
                          gates_failed_at=_now_iso())
            print("Work session atualizada: status=gates_pending (corrija e rode de novo).")
    print(f"latest: {LATEST.relative_to(ROOT)}  (gitignored)")
    print("Produção: nada alterado.")
    if not overall_ok:
        sys.exit(1)


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(argv):
    print("JARVIS — Gate Status")
    print("Status real: leitura local. Nada editado.")
    print("")
    if not LATEST.exists():
        print("(sem gate run registrado — rode ./jarvis gate-run)")
        print("Produção: nada alterado.")
        return
    try:
        data = json.loads(LATEST.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"FALHA: latest.json inválido: {e}")
        sys.exit(1)
    print(f"timestamp: {data.get('ts')}")
    print(f"all_ok: {data.get('all_ok')}")
    for r in data.get("results", []):
        flag = "OK   " if r.get("ok") else "FALHA"
        print(f"  {flag}  {r.get('name')}  exit={r.get('exit_code')}  {r.get('summary')}")
    print("")
    state = _load_current()
    if state:
        print(f"work session ativa: {state.get('work_id')} status={state.get('status')}")
        print(f"  next_command: {state.get('next_command') or '(?)'}")
    else:
        print("work session: (nenhuma ativa)")
    print("")
    print("Produção: nada alterado.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: gate_runner.py <run|status>")
        sys.exit(1)
    sub = argv[0]
    rest = argv[1:]
    if sub == "run":
        cmd_run(rest)
    elif sub == "status":
        cmd_status(rest)
    else:
        print(f"FALHA: subcomando desconhecido: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
