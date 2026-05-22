from pathlib import Path
import subprocess
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

CRITICAL_COMMANDS = [
    "quality-gate",
    "smoke-test",
    "release-check",
    "safety-gate",
    "secret-scan",
    "storage-health",
    "cockpit",
    "mode-plan",
    "auto-task",
    "pending-artifacts",
    "readonly-run",
    "local-exec-plan",
    "local-exec-ready",
    "local-exec-handoff",
    "local-exec-review",
    "local-exec-flow",
    "local-exec-flow-latest",
    "local-exec-review-latest",
    "local-exec-handoff-latest",
    "local-exec-ready-latest",
    "local-exec-plan-latest",
    "readonly-run-latest",
    "executor-handoff",
    "handoff-latest",
    "handoff-print",
    "review-output-v2",
    "review-output-index",
    "review-output-latest",
    "snapshot-prep-core",
]

def run(cmd):
    try:
        return 0, subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.strip()

def main():
    print("JARVIS — Theo Padilha AI Worker Command Audit")
    print("Status real: auditoria local de comandos. Produção não alterada.")
    print("")

    jarvis_core = (ROOT / "11_SCRIPTS" / "jarvis_core.py").read_text(encoding="utf-8", errors="ignore")
    smoke = (ROOT / "11_SCRIPTS" / "cli_smoke_test.py").read_text(encoding="utf-8", errors="ignore")
    catalog = (ROOT / "01_SISTEMA" / "03_COMMANDS" / "COMMAND_CATALOG.md").read_text(encoding="utf-8", errors="ignore")

    code, help_out = run(["./jarvis", "help"])

    failures = []

    for cmd in CRITICAL_COMMANDS:
        in_core = f'"{cmd}"' in jarvis_core or f"'{cmd}'" in jarvis_core
        in_help = f"./jarvis {cmd}" in help_out or cmd in help_out
        in_catalog = f"./jarvis {cmd}" in catalog or f"`./jarvis {cmd}" in catalog
        in_smoke = cmd in smoke

        print(f"## {cmd}")
        print(f"- core: {'OK' if in_core else 'FALHA'}")
        print(f"- help: {'OK' if in_help else 'FALHA'}")
        print(f"- catalog: {'OK' if in_catalog else 'FALHA'}")
        print(f"- smoke: {'OK' if in_smoke else 'AVISO'}")
        print("")

        if not in_core:
            failures.append(f"{cmd}: ausente no jarvis_core")
        if not in_help:
            failures.append(f"{cmd}: ausente no help")
        if not in_catalog:
            failures.append(f"{cmd}: ausente no catalog")

    scripts = sorted((ROOT / "11_SCRIPTS").glob("*.py"))
    print(f"Scripts Python detectados: {len(scripts)}")
    print("")

    if failures:
        print("Resultado: COMMAND AUDIT COM PENDÊNCIAS")
        for f in failures:
            print(f"- {f}")
        sys.exit(1)

    print("Resultado: COMMAND AUDIT PASSOU")
    print("Status real: nada alterado.")

if __name__ == "__main__":
    main()
