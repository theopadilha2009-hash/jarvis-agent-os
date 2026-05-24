"""
first_run_check.py — JARVIS environment sanity check.

Usado quando Theo abre um terminal/Mac novo e quer saber se o JARVIS
está montado corretamente. Read-only, sem APIs, sem segredos.

Usage:
  ./jarvis first-run-check
  ./jarvis first-run-check --full   # também roda doctor-agent --full
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
CAPABILITY_REGISTRY = ROOT / "01_SISTEMA" / "06_CAPABILITIES" / "CAPABILITY_REGISTRY.json"

RUNTIME_DIRS = [
    "05_EXECUCAO/34_TASKS",
    "05_EXECUCAO/35_RUNS",
    "05_EXECUCAO/36_WORK_SESSIONS",
    "05_EXECUCAO/37_GATES",
    "05_EXECUCAO/38_NO_CLAUDE",
    "05_EXECUCAO/39_HANDOFFS",
]

GITIGNORE_TARGETS = [
    "05_EXECUCAO/34_TASKS/tasks.jsonl",
    "05_EXECUCAO/36_WORK_SESSIONS/current.json",
    "05_EXECUCAO/36_WORK_SESSIONS/events.jsonl",
    "05_EXECUCAO/37_GATES/latest.json",
    "05_EXECUCAO/37_GATES/events.jsonl",
    "05_EXECUCAO/38_NO_CLAUDE/foo.md",
    "05_EXECUCAO/39_HANDOFFS/foo.md",
]


def parse_args(argv):
    full = False
    for a in argv:
        if a == "--full":
            full = True
    return full


def _run(cmd, timeout=20):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=timeout)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def _which(name):
    return shutil.which(name)


def _gitignored(rel):
    code, _ = _run(["git", "check-ignore", "-q", rel])
    return code == 0


def _is_tracked(rel):
    code, _ = _run(["git", "ls-files", "--error-unmatch", rel])
    return code == 0


def section(t): print(f"## {t}")
def line(kind, label, extra=""):
    badges = {"ok": "OK   ", "warn": "AVISO", "err": "FALHA"}
    badge = badges.get(kind, "?")
    suffix = f"  {extra}" if extra else ""
    print(f"  {badge}  {label}{suffix}")


def main():
    full = parse_args(sys.argv[1:])

    print("JARVIS — First-Run Check")
    print("Status real: verificação local. Nada foi editado.")
    print("")

    failures = 0
    warnings = 0

    section("Sistema")
    py = _which("python3")
    if py:
        line("ok", f"python3: {py}")
    else:
        line("err", "python3 não encontrado no PATH")
        failures += 1
    git = _which("git")
    if git:
        line("ok", f"git: {git}")
    else:
        line("err", "git não encontrado no PATH")
        failures += 1
    pbcopy = _which("pbcopy")
    if pbcopy:
        line("ok", f"pbcopy: {pbcopy}  (macOS clipboard)")
    else:
        # macOS-specific. On Linux/other this is a warning, not a failure.
        line("warn", "pbcopy ausente (clipboard --copy não vai funcionar)")
        warnings += 1
    claude = _which("claude")
    if claude:
        line("ok", f"claude: {claude}  (será aberto manualmente por Theo)")
    else:
        line("warn", "claude CLI ausente — JARVIS não executa Claude, mas Theo precisa pra fluxo with-Claude")
        warnings += 1
    code = _which("code")
    if code:
        line("ok", f"code: {code}  (VS Code CLI, usado por project-open --code)")
    else:
        line("warn", "code (VS Code) ausente — `project-open --code` cai para print-only")
        warnings += 1
    print("")

    section("Repo")
    code_rc, branch = _run(["git", "branch", "--show-current"])
    if code_rc != 0:
        line("err", "git branch falhou — não parece ser repositório git")
        failures += 1
    elif branch in ("main", "master"):
        line("err", f"branch atual é {branch} — JARVIS não deve operar em main/master")
        failures += 1
    else:
        line("ok", f"branch: {branch}")
    print("")

    section("Registries")
    if REGISTRY.exists():
        try:
            data = json.loads(REGISTRY.read_text(encoding="utf-8"))
            projs = (data or {}).get("projects", [])
            line("ok", f"PROJECT_REGISTRY.json ({len(projs)} projeto(s))")
        except Exception as e:
            line("err", f"PROJECT_REGISTRY.json parse falhou: {e}")
            failures += 1
    else:
        line("err", "PROJECT_REGISTRY.json ausente")
        failures += 1
    if CAPABILITY_REGISTRY.exists():
        try:
            data = json.loads(CAPABILITY_REGISTRY.read_text(encoding="utf-8"))
            total = 0
            groups = (data or {}).get("groups", {}) or {}
            if isinstance(groups, dict):
                for g in groups.values():
                    total += len((g or {}).get("capabilities", []) or [])
            line("ok", f"CAPABILITY_REGISTRY.json ({total} capability(s))")
        except Exception as e:
            line("err", f"CAPABILITY_REGISTRY.json parse falhou: {e}")
            failures += 1
    else:
        line("warn", "CAPABILITY_REGISTRY.json ausente")
        warnings += 1
    print("")

    section("Runtime dirs")
    for d in RUNTIME_DIRS:
        dp = ROOT / d
        if dp.exists():
            line("ok", f"{d}/")
        else:
            line("err", f"{d}/ ausente")
            failures += 1
        kp = ROOT / d / ".gitkeep"
        if kp.exists():
            line("ok", f"{d}/.gitkeep")
        else:
            line("warn", f"{d}/.gitkeep ausente")
            warnings += 1
    print("")

    section("Gitignore de runtime")
    for rel in GITIGNORE_TARGETS:
        if _gitignored(rel):
            line("ok", f"{rel}")
        else:
            line("err", f"{rel} NÃO gitignored")
            failures += 1
    print("")

    section("Segredos não devem estar versionados")
    # Check that no env files / obvious secret-shaped files are tracked.
    secret_names = (".env", ".env.local", ".env.production", "credentials.json", "secrets.json")
    for name in secret_names:
        p = ROOT / name
        if not p.exists():
            line("ok", f"{name}: ausente do repo")
            continue
        if _is_tracked(name):
            line("err", f"{name} TRACKED no git — remova com `git rm --cached {name}`")
            failures += 1
        else:
            line("ok", f"{name} presente mas untracked (ignored pelo .gitignore)")
    # Run secret-scan as a hard check.
    code_s, out_s = _run(["./jarvis", "secret-scan"], timeout=60)
    if code_s == 0:
        line("ok", "secret-scan PASSOU")
    else:
        line("err", f"secret-scan FALHOU (exit={code_s})")
        failures += 1
    print("")

    section("Optional heavy checks")
    if full:
        code_d, _ = _run(["./jarvis", "doctor-agent", "--full"], timeout=600)
        if code_d == 0:
            line("ok", "doctor-agent --full PASSOU")
        else:
            line("err", f"doctor-agent --full FALHOU (exit={code_d})")
            failures += 1
    else:
        line("warn", "doctor-agent --full não rodado (use --full para incluir smoke-test)")

    print("")
    section("Result")
    if failures == 0:
        if warnings:
            print(f"FIRST-RUN CHECK PASSOU ({warnings} aviso(s))")
        else:
            print("FIRST-RUN CHECK PASSOU")
        print("Status real: ambiente saudável para JARVIS local-only.")
        print("Produção: nada alterado.")
        sys.exit(0)
    print(f"FIRST-RUN CHECK COM PENDÊNCIAS ({failures} falha(s), {warnings} aviso(s))")
    print("Status real: leitura local. Nada foi editado.")
    print("Produção: nada alterado.")
    sys.exit(1)


if __name__ == "__main__":
    main()
