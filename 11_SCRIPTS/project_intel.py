"""
project_intel.py — read-only project inspection for JARVIS.

Reports basic facts about a registered project (path, branch, dirty
tree, package manager, scripts, framework / test / migration hints,
.env presence/tracking) so Theo gets a one-screen "what is this repo"
without remembering it from memory.

Hard rules:
  - read-only — never edits the project
  - never reads .env values (only presence + tracked/untracked)
  - never runs npm/bun/yarn/pnpm install
  - never runs tests/build/lint
  - never touches production
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"


def fail(msg, code=1):
    print(f"FALHA: {msg}")
    sys.exit(code)


def parse_args(argv):
    alias = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            if i + 1 < len(argv):
                alias = argv[i + 1].strip().lower()
                i += 2
                continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        i += 1
    if not alias:
        fail("Uso: ./jarvis project-intel --project ALIAS")
    return alias


def load_project(alias):
    if not REGISTRY.exists():
        fail("PROJECT_REGISTRY.json ausente.")
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_alias = {p["alias"]: p for p in data.get("projects", [])}
    if alias not in by_alias:
        print(f"FALHA: alias não registrado: {alias}")
        print("Aliases:")
        for k in sorted(by_alias):
            print(f"- {k}")
        sys.exit(1)
    return by_alias[alias]


def _run(cmd, cwd, timeout=10):
    try:
        return 0, subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def _detect_pkg_manager(path: Path):
    if (path / "bun.lockb").exists() or (path / "bun.lock").exists():
        return "bun", ("bun.lockb" if (path / "bun.lockb").exists() else "bun.lock")
    if (path / "pnpm-lock.yaml").exists():
        return "pnpm", "pnpm-lock.yaml"
    if (path / "yarn.lock").exists():
        return "yarn", "yarn.lock"
    if (path / "package-lock.json").exists():
        return "npm", "package-lock.json"
    if (path / "package.json").exists():
        return "node", "package.json"
    return None, None


def _parse_package_json(path: Path):
    pj = path / "package.json"
    if not pj.exists():
        return None
    try:
        return json.loads(pj.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def _detect_framework(pkg, path: Path):
    hints = []
    deps = {}
    if pkg:
        for key in ("dependencies", "devDependencies"):
            for k, v in (pkg.get(key) or {}).items():
                deps[k] = v
    framework_map = {
        "next": "next",
        "vite": "vite",
        "react": "react",
        "vue": "vue",
        "@nuxt/kit": "nuxt",
        "express": "express",
        "fastify": "fastify",
        "hono": "hono",
    }
    for k, label in framework_map.items():
        if k in deps:
            hints.append(label)
    # Filesystem hints for non-node repos
    if (path / "workflows").exists() and any(p.suffix == ".json" for p in (path / "workflows").glob("*.json")):
        hints.append("n8n-workflow-folder")
    if (path / "pyproject.toml").exists():
        hints.append("python")
    if (path / "Cargo.toml").exists():
        hints.append("rust")
    if (path / "go.mod").exists():
        hints.append("go")
    return hints, deps


def _detect_tests(deps):
    hints = []
    test_map = {
        "vitest": "vitest",
        "jest": "jest",
        "playwright": "playwright",
        "@playwright/test": "playwright",
        "cypress": "cypress",
        "@testing-library/react": "react-testing-library",
        "@testing-library/vue": "vue-testing-library",
    }
    for k, label in test_map.items():
        if k in deps:
            hints.append(label)
    return hints


def _detect_migrations(path: Path):
    hints = []
    if (path / "supabase" / "migrations").exists():
        try:
            count = sum(1 for _ in (path / "supabase" / "migrations").iterdir())
            hints.append(f"supabase/migrations ({count} arquivos)")
        except Exception:
            hints.append("supabase/migrations")
    if (path / "prisma" / "schema.prisma").exists():
        hints.append("prisma")
    if (path / "drizzle.config.ts").exists() or (path / "drizzle.config.js").exists():
        hints.append("drizzle")
    return hints


def _env_files(path: Path):
    found = []
    for name in (".env", ".env.example", ".env.local", ".env.production", ".env.development", ".env.sample"):
        if (path / name).exists():
            found.append(name)
    return found


def _is_tracked(path: Path, name: str):
    code, out = _run(["git", "ls-files", "--error-unmatch", name], path)
    return code == 0


def _recommended_commands(pm, scripts):
    if not pm:
        return []
    install = {"bun": "bun install", "pnpm": "pnpm install", "yarn": "yarn install", "npm": "npm install", "node": "npm install"}.get(pm, "npm install")
    run = {"bun": "bun run", "pnpm": "pnpm", "yarn": "yarn", "npm": "npm run", "node": "npm run"}.get(pm, "npm run")
    out = [install + "  # JARVIS NÃO executa — você roda se quiser"]
    for s in ("dev", "test", "build", "lint", "typecheck"):
        if scripts and s in scripts:
            out.append(f"{run} {s}")
    return out


def main():
    alias = parse_args(sys.argv[1:])
    project = load_project(alias)
    path = Path(project["path"]).expanduser()

    print("JARVIS — Project Intel (read-only)")
    print(f"Status real: inspeção local. Nada foi editado em {alias}.")
    print("")
    print(f"alias: {alias}")
    print(f"path:  {path}")
    if not path.exists():
        print("FALHA: path inexistente.")
        sys.exit(1)

    if (path / ".git").exists():
        _, branch = _run(["git", "branch", "--show-current"], path)
        _, dirty = _run(["git", "status", "--short"], path)
        print(f"branch: {branch or '(?)'}")
        dirty_lines = [l for l in (dirty or "").splitlines() if l.strip()]
        print(f"dirty:  {'sim (' + str(len(dirty_lines)) + ' arquivo(s))' if dirty_lines else 'não (tree limpa)'}")
    else:
        print("git: (não é repo)")
    print("")

    pm, lockfile = _detect_pkg_manager(path)
    print("## Package manager")
    if pm:
        print(f"- detectado: {pm}  (via {lockfile})")
    else:
        print("- nenhum (sem package.json/lockfile)")
    pkg = _parse_package_json(path)
    scripts = (pkg or {}).get("scripts") or {}
    if pkg:
        print(f"- package.json: presente ({len(scripts)} scripts)")
        if scripts:
            for s in ("dev", "build", "test", "lint", "typecheck"):
                if s in scripts:
                    print(f"  - {s}: `{scripts[s]}`")
    else:
        print("- package.json: ausente")
    print("")

    framework_hints, deps = _detect_framework(pkg, path)
    print("## Framework hints")
    if framework_hints:
        for h in framework_hints:
            print(f"- {h}")
    else:
        print("- (nenhum hint detectado)")
    print("")

    test_hints = _detect_tests(deps)
    print("## Test tools")
    if test_hints:
        for h in test_hints:
            print(f"- {h}")
    else:
        print("- (nenhum)")
    print("")

    mig_hints = _detect_migrations(path)
    print("## Migrations / DB")
    if mig_hints:
        for h in mig_hints:
            print(f"- {h}")
    else:
        print("- (nenhum)")
    print("")

    print("## .env risk (sem ler valores)")
    envs = _env_files(path)
    if not envs:
        print("- nenhum .env detectado")
    else:
        for name in envs:
            tracked = _is_tracked(path, name) if (path / ".git").exists() else False
            risk = "⚠ TRACKED no git!" if tracked else "(untracked)"
            print(f"- {name} {risk}")
    print("Lembrete: JARVIS nunca lê o conteúdo de .env.")
    print("")

    print("## Comandos recomendados (NÃO executados)")
    cmds = _recommended_commands(pm, scripts)
    if not cmds:
        print("- (não aplicável — sem package manager detectado)")
    for c in cmds:
        print(f"  $ {c}")
    print("")

    print("## Próxima ação segura")
    print(f"  ./jarvis project-open --project {alias} --print-only")
    print(f"  ./jarvis project-cockpit --project {alias}")
    print(f'  ./jarvis go "<o que você quer fazer no {alias}>"')
    print("")
    print("Produção: nada alterado. JARVIS não rodou install/test/build/lint.")


if __name__ == "__main__":
    main()
