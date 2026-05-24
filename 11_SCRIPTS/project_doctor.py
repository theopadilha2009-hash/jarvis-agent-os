"""
project_doctor.py — read-only health report for a registered project.

Usage:
  python3 11_SCRIPTS/project_doctor.py --project <alias>

Never edits anything. Never reads .env. Never prints secrets.
"""
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"

USAGE = "Uso: ./jarvis doctor --project <alias>"


def fail(msg, code=1):
    print(f"FALHA: {msg}")
    sys.exit(code)


def parse_args(argv):
    alias = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            if i + 1 >= len(argv):
                fail("--project exige alias.")
            alias = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        i += 1
    if not alias:
        fail(USAGE)
    return alias


def load_project(alias):
    if not REGISTRY.exists():
        fail("PROJECT_REGISTRY.json não encontrado.")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    projects = {p["alias"]: p for p in registry.get("projects", [])}
    if alias not in projects:
        print(f"FALHA: project alias não registrado: {alias}")
        print("")
        print("Aliases disponíveis:")
        for key in sorted(projects):
            print(f"- {key}")
        sys.exit(1)
    return projects[alias]


def run(cmd, cwd):
    try:
        out = subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=15)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro ao executar: {e}>"


def detect_package_manager(path: Path):
    if (path / "bun.lockb").exists() or (path / "bun.lock").exists():
        return "bun"
    if (path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (path / "yarn.lock").exists():
        return "yarn"
    if (path / "package-lock.json").exists():
        return "npm"
    if (path / "package.json").exists():
        return "npm (default)"
    if (path / "pyproject.toml").exists():
        return "python (pyproject)"
    if (path / "requirements.txt").exists():
        return "python (pip)"
    return "unknown"


def read_package_json(path: Path):
    pkg = path / "package.json"
    if not pkg.exists():
        return None
    try:
        return json.loads(pkg.read_text(encoding="utf-8"))
    except Exception:
        return None


def detect_test_tooling(pkg):
    if not pkg:
        return {"playwright": False, "cypress": False, "vitest": False, "rtl": False, "jest": False}
    deps = {}
    deps.update(pkg.get("dependencies", {}) or {})
    deps.update(pkg.get("devDependencies", {}) or {})
    keys = set(deps.keys())
    return {
        "playwright": any(k.startswith("@playwright/") or k == "playwright" for k in keys),
        "cypress": "cypress" in keys,
        "vitest": "vitest" in keys,
        "rtl": "@testing-library/react" in keys,
        "jest": "jest" in keys,
    }


def env_warning(path: Path):
    # Just count and name without reading contents. Never opens files.
    env_files = []
    for name in (".env", ".env.local", ".env.development", ".env.production", ".env.test"):
        if (path / name).exists():
            env_files.append(name)
    return env_files


def env_tracked_in_git(path: Path):
    # Check whether any .env with potential secrets is tracked by git.
    # Excludes well-known safe templates: .env.example, .env.sample, .env.template.
    code, out = run(["git", "ls-files", "--", ".env", ".env.*"], path)
    if code != 0:
        return []
    safe_suffixes = (".example", ".sample", ".template", ".dist")
    risky = []
    for line in out.splitlines():
        name = line.strip()
        if not name:
            continue
        lower = name.lower()
        if any(lower.endswith(suffix) for suffix in safe_suffixes):
            continue
        risky.append(name)
    return risky


def main():
    argv = sys.argv[1:]
    alias = parse_args(argv)
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"  # tolerated; doctor is print-only

    project = load_project(alias)
    path = Path(project["path"]).expanduser()

    print("JARVIS — Theo Padilha AI Worker Project Doctor")
    print(f"Status real: inspeção read-only do projeto alias={alias}. Nada foi editado.")
    print("")

    # Path
    print("## Path")
    print(f"- alias: {alias}")
    print(f"- path: {path}")
    if not path.exists():
        print("- EXISTS: NO  ← path do registry não existe no disco.")
        print("")
        print("Resultado: PROJECT DOCTOR FALHOU — path ausente.")
        print("Produção: nada alterado.")
        sys.exit(1)
    if not path.is_dir():
        print("- EXISTS: NO (not a directory)")
        print("Resultado: PROJECT DOCTOR FALHOU — path inválido.")
        sys.exit(1)
    print("- EXISTS: yes")
    print("")

    is_git = (path / ".git").exists()
    if not is_git:
        print("## Git\n- repo: NO (sem .git)")
        print("")
        print("Resultado: doctor inacabado (não é repo Git).")
        return

    # Branch
    code, branch = run(["git", "branch", "--show-current"], path)
    print("## Git")
    print(f"- branch atual: {branch or '<sem branch>'}")
    if branch == "main" or branch == "master":
        print("- WARN: você está em branch protegida (main/master). Trabalhe em branch dedicada.")

    # Dirty tree
    code, status = run(["git", "status", "--short"], path)
    if status:
        print("- tree: SUJA")
        for line in status.splitlines()[:30]:
            print(f"    {line}")
        if len(status.splitlines()) > 30:
            print(f"    ... (+{len(status.splitlines()) - 30} linhas)")
    else:
        print("- tree: limpa")

    # Latest commits
    code, log = run(["git", "log", "--oneline", "-5"], path)
    if log:
        print("- últimos 5 commits:")
        for line in log.splitlines():
            print(f"    {line}")

    # Ahead of origin/main if exists
    code, ahead = run(["git", "rev-list", "--count", "origin/main..HEAD"], path)
    if code == 0 and ahead.isdigit():
        print(f"- commits à frente de origin/main: {ahead}")
    print("")

    # Package manager
    pm_registered = project.get("package_manager", "unknown")
    pm_detected = detect_package_manager(path)
    print("## Package manager")
    print(f"- registrado: {pm_registered}")
    print(f"- detectado por lockfile: {pm_detected}")
    if pm_registered != "unknown" and pm_detected != "unknown" and pm_registered not in pm_detected and pm_detected not in pm_registered:
        print("- WARN: divergência entre registry e lockfile.")
    print("")

    # Scripts available
    pkg = read_package_json(path)
    scripts = (pkg or {}).get("scripts", {}) or {}
    print("## Scripts (package.json)")
    if not pkg:
        print("- package.json ausente")
    elif not scripts:
        print("- nenhum script declarado")
    else:
        for name in sorted(scripts.keys()):
            print(f"- {name}: {scripts[name]}")
    print("")

    # Likely typecheck/test/build commands
    print("## Comandos sugeridos (não executados)")

    def find_script(*needles):
        for n in needles:
            if n in scripts:
                return n
        return None

    test_script = find_script("test", "test:run", "test:unit")
    typecheck_script = find_script("typecheck", "type-check", "tsc")
    build_script = find_script("build", "build:dev")
    lint_script = find_script("lint", "eslint")

    pm_cmd = "npm run" if pm_detected.startswith("npm") else (
        "bun run" if pm_detected == "bun" else (
            "pnpm run" if pm_detected == "pnpm" else (
                "yarn" if pm_detected == "yarn" else "npm run"
            )
        )
    )
    if typecheck_script:
        print(f"- typecheck: {pm_cmd} {typecheck_script}")
    elif (path / "tsconfig.json").exists():
        print("- typecheck: npx tsc --noEmit")
    if test_script:
        print(f"- test:      {pm_cmd} {test_script}")
    if build_script:
        print(f"- build:     {pm_cmd} {build_script}")
    if lint_script:
        print(f"- lint:      {pm_cmd} {lint_script}")
    if not any([typecheck_script, test_script, build_script, lint_script]) and not (path / "tsconfig.json").exists():
        print("- nenhum script óbvio detectado.")
    print("")

    # Test tooling
    tooling = detect_test_tooling(pkg)
    print("## Test tooling")
    print(f"- Playwright: {'sim' if tooling['playwright'] else 'não'}")
    print(f"- Cypress:    {'sim' if tooling['cypress'] else 'não'}")
    print(f"- Vitest:     {'sim' if tooling['vitest'] else 'não'}")
    print(f"- Jest:       {'sim' if tooling['jest'] else 'não'}")
    print(f"- RTL (@testing-library/react): {'sim' if tooling['rtl'] else 'não'}")
    print("")

    # .env warning (names only, never contents)
    env_files = env_warning(path)
    print("## Arquivos .env (nomes apenas — conteúdo NÃO lido)")
    if not env_files:
        print("- nenhum")
    else:
        for n in env_files:
            print(f"- {n}")
    tracked_env = env_tracked_in_git(path)
    if tracked_env:
        print("")
        print("- ALERTA: .env rastreado pelo Git:")
        for t in tracked_env:
            print(f"    {t}")
        print("  Risco: dados sensíveis podem estar versionados. NÃO foi lido.")
    print("")

    # Final
    blockers = []
    if branch in ("main", "master"):
        blockers.append("branch main/master")
    if status:
        blockers.append("tree suja")
    if tracked_env:
        blockers.append(".env rastreado")

    print("## Resultado")
    if blockers:
        print("- WARN — atenção antes de patchar:")
        for b in blockers:
            print(f"    {b}")
    else:
        print("- saudável para próximo passo seguro (patch/mission).")
    print("")
    print("Próximos comandos sugeridos:")
    print(f"- ./jarvis qa-sprint --project {alias}")
    print(f'- ./jarvis goal-sprint --project {alias} --goal "...".')
    print(f"- ./jarvis browser-qa --project {alias}")
    print(f"- ./jarvis final-gate --project {alias}")
    print("")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
