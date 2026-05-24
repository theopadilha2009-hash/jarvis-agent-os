"""
doctrine_check.py — verifies AGENTS.md, COMMAND_CATALOG, help and mission
templates stay in sync. Complements command_audit.py (which only checks
command-name drift).

Read-only. Never edits anything. Exit code 1 on failure.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CATALOG = ROOT / "01_SISTEMA" / "03_COMMANDS" / "COMMAND_CATALOG.md"
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
MISSION_PACK = ROOT / "11_SCRIPTS" / "project_mission_pack.py"

# Phrases that must appear somewhere in each doc for doctrine consistency.
AGENTS_REQUIRED = [
    "Hard rules",
    "Self-evolution",
    "./jarvis self-cockpit",
    "./jarvis self-evolve",
    "Status real",
    "stdlib only",
]
CATALOG_REQUIRED = [
    "Self-evolution",
    "./jarvis self-cockpit",
    "./jarvis self-evolve",
    "Project memory",
    "claude-launch",
    "Sem API Anthropic/OpenAI",
]
HELP_REQUIRED_COMMANDS = [
    "self-status",
    "self-cockpit",
    "self-next",
    "self-evolve",
    "self-debrief",
    "claude-copy-latest",
    "claude-launch",
    "claude-save-report-template",
    "project-cockpit",
    "project-memory",
    "project-memory-update",
    "mission-open-latest",
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
]
MISSION_HARD_RULE_SIGNALS = [
    "Não fazer push, PR, merge ou deploy",
    "Não imprimir tokens",
    "Não rodar migrations",
    "Não editar Supabase",
    "Não fazer commit sem autorização",
]


def run(cmd):
    try:
        return 0, subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=15).strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def check_file_contains(path: Path, needles, label):
    if not path.exists():
        return [f"FALHA: {label} ausente ({path})"]
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [n for n in needles if n not in text]
    if missing:
        return [f"FALHA: {label} sem '{m}'" for m in missing]
    return []


def check_help():
    code, out = run(["./jarvis", "help"])
    if code != 0:
        return [f"FALHA: ./jarvis help retornou {code}"]
    missing = [c for c in HELP_REQUIRED_COMMANDS if c not in out]
    return [f"FALHA: ./jarvis help sem '{m}'" for m in missing]


def check_registry_jarvis_core():
    if not REGISTRY.exists():
        return ["FALHA: PROJECT_REGISTRY.json ausente"]
    text = REGISTRY.read_text(encoding="utf-8", errors="ignore")
    failures = []
    if '"alias": "jarvis-core"' not in text:
        failures.append("FALHA: registry sem alias jarvis-core")
    if '"allowed_for_local_exec": true' not in text:
        failures.append("FALHA: registry sem allowed_for_local_exec=true")
    return failures


def check_mission_pack():
    return check_file_contains(MISSION_PACK, MISSION_HARD_RULE_SIGNALS, "project_mission_pack.HARD_RULES")


def main():
    print("JARVIS — Theo Padilha AI Worker Doctrine Check")
    print("Status real: leitura local. Nada foi editado.")
    print("")

    all_failures = []
    checks = [
        ("AGENTS.md", lambda: check_file_contains(AGENTS, AGENTS_REQUIRED, "AGENTS.md")),
        ("COMMAND_CATALOG.md", lambda: check_file_contains(CATALOG, CATALOG_REQUIRED, "COMMAND_CATALOG.md")),
        ("./jarvis help", check_help),
        ("PROJECT_REGISTRY.json", check_registry_jarvis_core),
        ("mission HARD_RULES", check_mission_pack),
    ]
    for label, fn in checks:
        failures = fn()
        if failures:
            print(f"## {label}: PENDÊNCIAS")
            for f in failures:
                print(f"  - {f}")
            all_failures.extend(failures)
        else:
            print(f"## {label}: OK")
        print("")

    if all_failures:
        print(f"Resultado: DOCTRINE CHECK COM PENDÊNCIAS ({len(all_failures)} item(ns))")
        print("Status real: nada editado. Apenas reportei drift.")
        sys.exit(1)
    print("Resultado: DOCTRINE CHECK PASSOU")
    print("Status real: nada alterado.")


if __name__ == "__main__":
    main()
