from pathlib import Path
import subprocess
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

CRITICAL_COMMANDS = [
    "project-resolve",
    "project-menu",
    "next-step",
    "run-safe",
    "future-tools-radar",
    "quality-gate",
    "smoke-test",
    "release-check",
    "safety-gate",
    "secret-scan",
    "storage-health",
    "cockpit",
    "visual-cockpit",
    "claude-mission",
    "claude-mission-latest",
    "operator-workbench",
    "mode-plan",
    "auto-task",
    "pending-artifacts",
    "readonly-run",
    "local-exec-plan",
    "local-exec-ready",
    "local-exec-handoff",
    "local-exec-review",
    "local-exec-flow",
    "local-exec-session",
    "local-exec-session-latest",
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
    "qa-sprint",
    "goal-sprint",
    "browser-qa",
    "final-gate",
    "project-status",
    "project-cockpit",
    "mission-open-latest",
    "project-memory",
    "project-memory-update",
    "self-status",
    "self-cockpit",
    "self-next",
    "self-evolve",
    "self-debrief",
    "claude-copy-latest",
    "claude-launch",
    "claude-save-report-template",
    "doctrine-check",
    "ask",
    "go",
    "capture",
    "inbox",
    "agenda-add",
    "agenda",
    "blueprint",
    "project-open",
    "plan",
    "limits",
    "ask-log",
    "task-add",
    "task-list",
    "task-next",
    "task-show",
    "task-done",
    "task-block",
    "run-list",
    "run-show",
    "run-latest",
    "capabilities",
    "capability-check",
    "capability-plan",
    "project-intel",
    "resume",
    "work-start",
    "work-status",
    "work-next",
    "work-block",
    "work-close",
    "report-template",
    "report-status",
    "report-check",
    "report-apply",
    "gate-run",
    "gate-status",
    "run-prune",
    "doctor-agent",
    "state-status",
    "state-reset",
    "state-archive",
    "no-claude",
    "cheatsheet",
    "handoff-self",
    "now",
    "start",
    "finish",
    "gates",
    "health",
    "daily",
    "first-run-check",
    "recipe-list",
    "recipe-show",
    "recipe-run",
    "rc-status",
    "rc-freeze",
    "acceptance",
    "do",
    "do-history",
    "do-show",
    "do-learn",
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

    # Sprint 8.2 — `./jarvis help` is the slim view; audit reads `--all`.
    code, help_out = run(["./jarvis", "help", "--all"])

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
