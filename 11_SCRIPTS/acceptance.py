"""
acceptance.py — JARVIS acceptance scenarios.

Verifies key user flows without real Claude / APIs. Each scenario runs a
real JARVIS sub-command and checks exit + expected output fragments.

Usage:
  ./jarvis acceptance --dry-run   # default: skips heavy gates
  ./jarvis acceptance --full      # also runs gate-run (safety+smoke+doctrine)
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"


def parse_args(argv):
    full = False
    dry = False
    for a in argv:
        if a == "--full":
            full = True
        elif a == "--dry-run":
            dry = True
    if not full:
        dry = True
    return dry, full


def _run(cmd, timeout=120):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=timeout)
        return 0, out
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "")
    except Exception as e:
        return 1, f"<erro: {e}>"


def _project_exists(alias):
    if not REGISTRY.exists():
        return None
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for p in data.get("projects", []):
            if p.get("alias") == alias:
                path = Path((p.get("path") or "")).expanduser()
                return path.exists()
    except Exception:
        return None
    return None


SCENARIOS = [
    {
        "name": "now",
        "cmd": ["./jarvis", "now"],
        "expect_code": 0,
        "expect_text": ["JARVIS — Resume", "Produção"],
    },
    {
        "name": "cheatsheet",
        "cmd": ["./jarvis", "cheatsheet"],
        "expect_code": 0,
        "expect_text": ["Cheatsheet", "./jarvis now", "./jarvis no-claude"],
    },
    {
        "name": "no-claude n8n dry-run",
        "cmd": ["./jarvis", "no-claude", "workflow n8n de agendamento whatsapp", "--dry-run"],
        "expect_code": 0,
        "expect_text": ["No-Claude Mode", "intent:", "blueprint:", "--dry-run"],
    },
    {
        "name": "project-intel jarvis-core",
        "cmd": ["./jarvis", "project-intel", "--project", "jarvis-core"],
        "expect_code": 0,
        "expect_text": ["Project Intel", "jarvis-core", "Produção"],
    },
    {
        "name": "project-intel oficina (optional)",
        "cmd": ["./jarvis", "project-intel", "--project", "oficina"],
        "expect_code": 0,
        "expect_text": ["Project Intel", "oficina"],
        "optional_if_missing": "oficina",  # warn instead of fail if path absent
    },
    {
        "name": "report-check good fixture",
        "cmd": ["./jarvis", "report-check", "--file", "10_TESTES/FIXTURES/good_claude_report_agent_os.md"],
        "expect_code": 0,
        "expect_text": ["Report Check", "quality: strong", "READY"],
    },
    {
        "name": "report-check bad fixture",
        "cmd": ["./jarvis", "report-check", "--file", "10_TESTES/FIXTURES/bad_claude_report_commands_only.md"],
        # report-check on weak fixture still exits 0 but prints WEAK
        "expect_code": 0,
        "expect_text": ["Report Check", "quality: weak", "WEAK"],
    },
    {
        "name": "gate-status",
        "cmd": ["./jarvis", "gate-status"],
        "expect_code": 0,
        "expect_text": ["Gate Status", "Produção"],
    },
    {
        "name": "recipe-list",
        "cmd": ["./jarvis", "recipe-list"],
        "expect_code": 0,
        "expect_text": ["Recipe List", "n8n-workflow", "project-fix", "no-claude-plan"],
    },
    {
        "name": "rc-status",
        "cmd": ["./jarvis", "rc-status"],
        "expect_code": 0,
        "expect_text": ["RC Status", "Readiness", "Produção"],
    },
    {
        "name": "state-status",
        "cmd": ["./jarvis", "state-status"],
        "expect_code": 0,
        "expect_text": ["State Status", "Runtime gitignore", "Produção"],
    },
    {
        "name": "handoff-self",
        "cmd": ["./jarvis", "handoff-self"],
        "expect_code": 0,
        "expect_text": ["Handoff Snapshot", "Comandos importantes", "Hard rules"],
    },
    {
        "name": "daily",
        "cmd": ["./jarvis", "daily"],
        "expect_code": 0,
        "expect_text": ["Daily Dashboard", "Health", "Active Work", "Useful Commands"],
    },
    {
        "name": "first-run-check",
        "cmd": ["./jarvis", "first-run-check"],
        # may have warnings (no claude/code) but should not fail unless env broken
        "expect_code": 0,
        "expect_text": ["First-Run Check", "Result", "FIRST-RUN CHECK"],
        "allow_warnings": True,
    },
]


def main():
    dry, full = parse_args(sys.argv[1:])
    print("JARVIS — Acceptance")
    print(f"Modo: {'--full' if full else '--dry-run'}")
    print("Status real: cenários locais. Sem Claude. Sem API paga. Sem produção.")
    print("")

    failures = 0
    warnings = 0
    total = 0

    for sc in SCENARIOS:
        total += 1
        name = sc["name"]
        opt = sc.get("optional_if_missing")
        if opt and _project_exists(opt) is False:
            print(f"AVISO  {name}  (pulando — alias '{opt}' aponta para path inexistente)")
            warnings += 1
            continue
        code, out = _run(sc["cmd"])
        missing = [s for s in sc["expect_text"] if s not in out]
        code_ok = code == sc["expect_code"]
        if code_ok and not missing:
            print(f"OK     {name}")
        else:
            failures += 1
            print(f"FALHA  {name}")
            if not code_ok:
                print(f"        exit={code} (esperado {sc['expect_code']})")
            if missing:
                print(f"        ausente: {', '.join(missing)}")
    print("")

    if full:
        print("## Heavy gates (--full)")
        # gate-run propagates safety+smoke+doctrine. Honor JARVIS_NO_REPORT to
        # avoid writing transient snapshots into 10_TESTES.
        code, out = _run(["env", "JARVIS_NO_REPORT=1", "./jarvis", "gate-run"], timeout=900)
        total += 1
        if code == 0:
            print("OK     gate-run (safety+smoke+doctrine)")
        else:
            print(f"FALHA  gate-run exit={code}")
            failures += 1
        print("")

    print("## Resultado")
    if failures == 0:
        if warnings:
            print(f"ACCEPTANCE PASSOU ({warnings} aviso(s), {total} cenário(s))")
        else:
            print(f"ACCEPTANCE PASSOU ({total} cenário(s))")
        print("Status real: nada alterado.")
        print("Produção: nada alterado. Claude não executado.")
        sys.exit(0)
    print(f"ACCEPTANCE COM PENDÊNCIAS ({failures} falha(s), {warnings} aviso(s), {total} cenário(s))")
    print("Status real: leitura local. Nada foi editado.")
    print("Produção: nada alterado.")
    sys.exit(1)


if __name__ == "__main__":
    main()
