from pathlib import Path
from datetime import datetime
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "15_LOCAL_EXEC_HANDOFFS"
PROJECT_ROOTS = [
    Path.home() / "VAMOO_PROJETOS",
    Path.home() / "Theo",
]

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "local-exec-handoff"

def run(cmd, cwd):
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=20).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()
    except Exception as e:
        return f"ERRO: {e}"

def find_projects():
    projects = []

    for base in PROJECT_ROOTS:
        if not base.exists():
            continue

        for p in base.iterdir():
            if not p.is_dir():
                continue

            score = 0
            reasons = []

            if (p / ".git").exists():
                score += 5
                reasons.append("git")
            if (p / "package.json").exists():
                score += 4
                reasons.append("package.json")
            if (p / "src").exists():
                score += 3
                reasons.append("src")
            if (p / "README.md").exists():
                score += 1
                reasons.append("readme")
            if any(p.glob("*.json")):
                score += 1
                reasons.append("json")

            if score > 0:
                projects.append({"path": p, "name": p.name, "score": score, "reasons": reasons})

    return sorted(projects, key=lambda x: x["score"], reverse=True)

def pick_project(task):
    task_l = task.lower()
    projects = find_projects()
    scored = []

    for pr in projects:
        score = pr["score"]
        name_l = pr["name"].lower()

        for token in re.findall(r"[a-zA-Z0-9_-]+", task_l):
            if len(token) >= 3 and token in name_l:
                score += 10

        if "gc" in task_l and ("gc" in name_l or "gestao" in name_l or "cristo" in name_l):
            score += 20
        if "oficina" in task_l and "oficina" in name_l:
            score += 20
        if "ls" in task_l and "ls" in name_l:
            score += 20

        scored.append((score, pr))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None

def package_manager(path):
    if (path / "bun.lockb").exists() or (path / "bun.lock").exists():
        return "bun"
    if (path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (path / "yarn.lock").exists():
        return "yarn"
    if (path / "package-lock.json").exists():
        return "npm"
    if (path / "package.json").exists():
        return "npm"
    return "unknown"

def build_commands(pm):
    if pm == "bun":
        return ["bun run build"]
    if pm == "pnpm":
        return ["pnpm build"]
    if pm == "yarn":
        return ["yarn build"]
    if pm == "npm":
        return ["npm run build"]
    return ["# definir comando de build antes de executar"]

def test_commands(pm):
    if pm == "bun":
        return ["bun test"]
    if pm == "pnpm":
        return ["pnpm test"]
    if pm == "yarn":
        return ["yarn test"]
    if pm == "npm":
        return ["npm test"]
    return ["# definir comando de teste antes de executar"]

def write_file(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    task = " ".join(sys.argv[1:]).strip()
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    if not task:
        print('Uso: ./jarvis local-exec-handoff "tarefa"')
        sys.exit(1)

    project = pick_project(task)

    print("JARVIS — Theo Padilha AI Worker LOCAL_EXEC Handoff")
    print("")
    print("Status real: pacote de execução local. Nenhum arquivo do projeto foi alterado.")
    print(f"Tarefa: {task}")
    print("")

    if not project:
        print("FALHA: nenhum projeto local encontrado.")
        sys.exit(1)

    path = project["path"]
    branch = run(["git", "branch", "--show-current"], cwd=path) if (path / ".git").exists() else "não é git"
    status = run(["git", "status", "--short"], cwd=path) if (path / ".git").exists() else "não é git"
    pm = package_manager(path)
    build = build_commands(pm)
    tests = test_commands(pm)

    print(f"Projeto selecionado: {project['name']}")
    print(f"Caminho: {path}")
    print(f"Branch: {branch}")
    print(f"Git status: {status or 'limpo'}")
    print(f"Package manager provável: {pm}")

    if no_report:
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
        print("")
        print("Status real: preview local. Nada gerado.")
        return

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out_dir = OUT_DIR / f"{ts}_{slugify(task)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    context = [
        "# LOCAL_EXEC Context — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Tarefa\n{task}",
        "",
        "## Status real",
        "Pacote local criado para executor. Nenhum arquivo do projeto foi alterado pelo JARVIS.",
        "",
        f"## Projeto selecionado\n{project['name']}",
        "",
        f"## Caminho\n`{path}`",
        "",
        f"## Branch atual\n`{branch}`",
        "",
        "## Git status do projeto",
        "```text",
        status or "limpo",
        "```",
        "",
        f"## Package manager provável\n{pm}",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    claude = [
        "# Prompt para Claude / VS Code — LOCAL_EXEC",
        "",
        "Você é executor técnico local. Trabalhe com patch mínimo e modo seguro.",
        "",
        f"Projeto: {project['name']}",
        f"Caminho local: {path}",
        f"Tarefa: {task}",
        "",
        "Regras obrigatórias:",
        "- Comece com `git status --short`.",
        "- Confirme branch atual.",
        "- Não mexa em main/master sem autorização.",
        "- Não abra, copie, imprima ou salve conteúdo de `.env`, tokens, senhas, cookies, QR codes ou credenciais.",
        "- Não faça push.",
        "- Não faça merge.",
        "- Não faça deploy.",
        "- Não altere VPS, n8n, banco real ou produção.",
        "- Faça patch mínimo.",
        "- Rode build/teste quando aplicável.",
        "- Se encontrar risco de produção, pare e peça autorização.",
        "",
        "Saída obrigatória:",
        "1. diagnóstico",
        "2. arquivos alterados",
        "3. diff/resumo do patch",
        "4. validações executadas",
        "5. riscos restantes",
        "6. próximo passo seguro",
    ]

    safe_commands = [
        "# Safe Commands — LOCAL_EXEC",
        "",
        "```bash",
        f"cd {path}",
        "git status --short",
        "git branch --show-current",
        *build,
        *tests,
        "```",
        "",
        "Não executar push/merge/deploy sem autorização explícita.",
    ]

    review = [
        "# Review Checklist — LOCAL_EXEC",
        "",
        "- [ ] Branch não é main/master ou há autorização explícita.",
        "- [ ] Git status inicial registrado.",
        "- [ ] Arquivos alterados são esperados.",
        "- [ ] Nenhum `.env`/segredo foi aberto ou exposto.",
        "- [ ] Build/teste rodado ou justificativa registrada.",
        "- [ ] Sem push.",
        "- [ ] Sem merge.",
        "- [ ] Sem deploy.",
        "- [ ] Produção não alterada.",
    ]

    write_file(out_dir / "00_CONTEXT.md", context)
    write_file(out_dir / "01_CLAUDE_LOCAL_EXEC.md", claude)
    write_file(out_dir / "02_SAFE_COMMANDS.md", safe_commands)
    write_file(out_dir / "03_REVIEW_CHECKLIST.md", review)

    print("")
    print(f"Pacote criado: {out_dir.relative_to(ROOT)}")
    print(f"Arquivo principal: {(out_dir / '01_CLAUDE_LOCAL_EXEC.md').relative_to(ROOT)}")
    print("")
    print("Status real: pacote criado. Projeto não alterado.")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
