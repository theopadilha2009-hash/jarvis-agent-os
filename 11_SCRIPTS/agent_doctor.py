"""
agent_doctor.py — JARVIS self-diagnostic.

Theo wants to know if JARVIS itself is healthy (branch, files, runtime
dirs, registries, gates, doctrine). Complements `./jarvis doctor` (which
inspects target projects) and `./jarvis self-cockpit` (which is a
strategic cockpit, not a health check).

Usage:
  ./jarvis doctor-agent          # quick local diagnosis
  ./jarvis doctor-agent --full   # additionally runs full smoke-test

Hard rules:
  - read-only — never edits anything
  - never calls Claude / APIs / paid LLMs
  - never reads .env values (only presence)
  - never touches target projects
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "11_SCRIPTS"
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
CAPABILITY_REGISTRY = ROOT / "01_SISTEMA" / "06_CAPABILITIES" / "CAPABILITY_REGISTRY.json"

CORE_FILES = [
    "jarvis_core.py",
    "work_session.py",
    "report_intake.py",
    "gate_runner.py",
    "task_queue.py",
    "run_log.py",
    "ask_router.py",
    "project_intel.py",
    "capabilities.py",
    "blueprint.py",
    "plan_request.py",
    "self_cockpit.py",
    "limits.py",
    "command_audit.py",
    "doctrine_check.py",
    "cli_smoke_test.py",
    "secret_scan.py",
    "safety_gate.py",
]

RUNTIME_DIRS = [
    "05_EXECUCAO/34_TASKS",
    "05_EXECUCAO/35_RUNS",
    "05_EXECUCAO/36_WORK_SESSIONS",
    "05_EXECUCAO/37_GATES",
]

RUNTIME_FILES_GITIGNORED = [
    "05_EXECUCAO/34_TASKS/tasks.jsonl",
    "05_EXECUCAO/36_WORK_SESSIONS/current.json",
    "05_EXECUCAO/36_WORK_SESSIONS/events.jsonl",
    "05_EXECUCAO/37_GATES/latest.json",
    "05_EXECUCAO/37_GATES/events.jsonl",
]

FIXTURES = [
    ("10_TESTES/FIXTURES/bad_claude_report_commands_only.md", "weak report fixture"),
    ("10_TESTES/FIXTURES/good_claude_report_agent_os.md", "good report fixture"),
]


def parse_args(argv):
    full = False
    for a in argv:
        if a == "--full":
            full = True
    return full


def _run(cmd, cwd=ROOT, timeout=20):
    try:
        out = subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=timeout)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def _git_branch():
    code, out = _run(["git", "branch", "--show-current"])
    if code != 0:
        return None
    return out.strip()


def _git_dirty():
    code, out = _run(["git", "status", "--short"])
    if code != 0:
        return None
    lines = [l for l in out.splitlines() if l.strip()]
    return len(lines)


def _gitignored(path: str) -> bool:
    code, _ = _run(["git", "check-ignore", "-q", path])
    return code == 0


def _safe_load_json(path: Path):
    if not path.exists():
        return None, "ausente"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"erro parse: {e}"


def section(title):
    print(f"## {title}")


def line(ok, label, extra=""):
    badge = "OK   " if ok is True else ("AVISO" if ok is None else "FALHA")
    suffix = f"  {extra}" if extra else ""
    print(f"  {badge}  {label}{suffix}")


def main():
    full = parse_args(sys.argv[1:])

    print("JARVIS — Agent Doctor")
    print("Status real: diagnóstico local. Nada foi editado.")
    print("")

    failures = 0
    warnings = 0

    # ── Git ──
    section("Git")
    branch = _git_branch()
    if branch is None:
        line(False, "não é repositório git")
        failures += 1
    else:
        if branch in ("main", "master"):
            line(False, f"branch atual é {branch} (perigoso para JARVIS)")
            failures += 1
        else:
            line(True, f"branch: {branch}")
    dirty = _git_dirty()
    if dirty is None:
        line(None, "git status indisponível")
        warnings += 1
    elif dirty == 0:
        line(True, "tree limpa")
    else:
        line(None, f"tree suja ({dirty} arquivo(s))")
        warnings += 1
    print("")

    # ── Files ──
    section("Files")
    for fname in CORE_FILES:
        fp = SCRIPTS / fname
        if fp.exists():
            line(True, f"11_SCRIPTS/{fname}")
        else:
            line(False, f"11_SCRIPTS/{fname} ausente")
            failures += 1
    print("")

    # ── Runtime State ──
    section("Runtime State")
    for d in RUNTIME_DIRS:
        dp = ROOT / d
        if dp.exists() and dp.is_dir():
            line(True, f"{d}/")
        else:
            line(False, f"{d}/ ausente")
            failures += 1
    # gitkeeps
    for d in RUNTIME_DIRS:
        kp = ROOT / d / ".gitkeep"
        if kp.exists():
            line(True, f"{d}/.gitkeep")
        else:
            line(None, f"{d}/.gitkeep ausente")
            warnings += 1
    # runtime files gitignored
    for f in RUNTIME_FILES_GITIGNORED:
        ignored = _gitignored(f)
        if ignored:
            line(True, f"{f} gitignored")
        else:
            line(False, f"{f} NÃO gitignored")
            failures += 1
    print("")

    # ── Registries ──
    section("Registries")
    if REGISTRY.exists():
        data, err = _safe_load_json(REGISTRY)
        if err:
            line(False, f"PROJECT_REGISTRY.json {err}")
            failures += 1
        else:
            projs = data.get("projects", []) if isinstance(data, dict) else []
            line(True, f"PROJECT_REGISTRY.json ({len(projs)} projeto(s))")
    else:
        line(False, "PROJECT_REGISTRY.json ausente")
        failures += 1
    if CAPABILITY_REGISTRY.exists():
        data, err = _safe_load_json(CAPABILITY_REGISTRY)
        if err:
            line(False, f"CAPABILITY_REGISTRY.json {err}")
            failures += 1
        else:
            total = 0
            if isinstance(data, dict):
                groups = data.get("groups", {}) or {}
                if isinstance(groups, dict):
                    for g in groups.values():
                        caps = (g or {}).get("capabilities", []) or []
                        total += len(caps)
                if not total:
                    total = len(data.get("capabilities", []) or [])
            line(True, f"CAPABILITY_REGISTRY.json ({total} capability(s))")
    else:
        line(None, "CAPABILITY_REGISTRY.json ausente")
        warnings += 1
    print("")

    # ── Projects ──
    section("Projects")
    data, err = _safe_load_json(REGISTRY)
    if err or not data:
        line(None, "registry indisponível, pulando")
        warnings += 1
    else:
        for p in data.get("projects", []):
            alias = p.get("alias", "?")
            raw = (p.get("path") or "").strip()
            path = Path(raw).expanduser() if raw else None
            if path and path.exists():
                line(True, f"{alias}: {path}")
            else:
                line(None, f"{alias}: path inexistente ({raw})")
                warnings += 1
    print("")

    # ── Gates ──
    section("Gates")
    gates_path = ROOT / "05_EXECUCAO" / "37_GATES" / "latest.json"
    if gates_path.exists():
        data, err = _safe_load_json(gates_path)
        if err:
            line(False, f"latest.json {err}")
            failures += 1
        else:
            ts = data.get("ts", "?")
            all_ok = data.get("all_ok", False)
            tag = "all_ok=True" if all_ok else "all_ok=False"
            line(all_ok, f"último gate-run: {ts} ({tag})")
    else:
        line(None, "ainda não rodou gate-run (use ./jarvis gates)")
        warnings += 1
    # current work session
    cs = ROOT / "05_EXECUCAO" / "36_WORK_SESSIONS" / "current.json"
    if cs.exists():
        data, err = _safe_load_json(cs)
        if err:
            line(False, f"current.json {err}")
            failures += 1
        else:
            line(True, f"work session ativa: status={data.get('status', '?')}")
    else:
        line(None, "nenhuma work session ativa")
    # task queue
    tq = ROOT / "05_EXECUCAO" / "34_TASKS" / "tasks.jsonl"
    if tq.exists():
        try:
            n = sum(1 for _ in tq.open(encoding="utf-8") if _.strip())
            line(True, f"tasks.jsonl ({n} linha(s) append-only)")
        except Exception as e:
            line(False, f"tasks.jsonl erro: {e}")
            failures += 1
    else:
        line(None, "tasks.jsonl ainda não criado")
    # run dirs safe
    runs = ROOT / "05_EXECUCAO" / "35_RUNS"
    if runs.exists():
        try:
            n = sum(1 for p in runs.iterdir() if p.is_dir() and not p.name.startswith("."))
            line(True, f"35_RUNS/ ({n} run package(s))")
        except Exception as e:
            line(False, f"35_RUNS/ erro: {e}")
            failures += 1
    else:
        line(False, "35_RUNS/ ausente")
        failures += 1
    # fixtures
    for rel, label in FIXTURES:
        fp = ROOT / rel
        if fp.exists():
            line(True, f"{label}: {rel}")
        else:
            line(False, f"{label} ausente: {rel}")
            failures += 1
    print("")

    # ── Commands ──
    section("Commands")
    code_audit, _ = _run(["./jarvis", "command-audit"], timeout=60)
    if code_audit == 0:
        line(True, "command-audit PASSOU")
    else:
        line(False, f"command-audit FALHOU (exit={code_audit})")
        failures += 1
    code_doctrine, _ = _run(["./jarvis", "doctrine-check"], timeout=60)
    if code_doctrine == 0:
        line(True, "doctrine-check PASSOU")
    else:
        line(False, f"doctrine-check FALHOU (exit={code_doctrine})")
        failures += 1
    if full:
        code_smoke, _ = _run(["env", "JARVIS_NO_REPORT=1", "./jarvis", "smoke-test"], timeout=600)
        if code_smoke == 0:
            line(True, "smoke-test PASSOU (--full)")
        else:
            line(False, f"smoke-test FALHOU (--full, exit={code_smoke})")
            failures += 1
    else:
        line(None, "smoke-test não rodado (use --full)")
    print("")

    # ── Result ──
    section("Result")
    if failures == 0:
        if warnings:
            print(f"AGENT DOCTOR PASSOU ({warnings} aviso(s))")
        else:
            print("AGENT DOCTOR PASSOU")
        print("Status real: nada alterado. JARVIS está saudável localmente.")
        print("Produção: nada alterado. Claude não executado.")
        sys.exit(0)
    print(f"AGENT DOCTOR COM PENDÊNCIAS ({failures} falha(s), {warnings} aviso(s))")
    print("Status real: leitura local. Nada foi editado.")
    print("Produção: nada alterado.")
    sys.exit(1)


if __name__ == "__main__":
    main()
