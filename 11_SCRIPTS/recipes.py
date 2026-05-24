"""
recipes.py — JARVIS golden paths.

Receitas deterministas para os fluxos mais comuns. Não substitui as
comandos atômicos — encadeia a sequência segura.

Hard rules:
- nenhuma receita executa Claude
- nenhuma receita chama API paga
- nenhuma receita edita projeto-alvo
- nenhuma receita faz deploy/push/PR/merge
- --dry-run (default) só imprime; live delega para comandos locais seguros

Usage:
  ./jarvis recipe-list
  ./jarvis recipe-show NAME
  ./jarvis recipe-run NAME [--project ALIAS] [--goal "..."] [--dry-run]
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd, timeout=60):
    """Run a JARVIS sub-command and propagate output."""
    return subprocess.call(cmd, cwd=ROOT)


# ── Recipes ───────────────────────────────────────────────────────────────────

RECIPES = {
    "n8n-workflow": {
        "purpose": "Preparar plano + blueprint local de workflow n8n (sem n8n real).",
        "requires": [],
        "optional": ["--goal"],
        "intro": (
            "JARVIS gera plano offline e blueprint local. NÃO importa em n8n real, "
            "NÃO ativa webhook, NÃO toca workflow de produção."
        ),
        "steps": [
            # Each step: (label, command-list-using-jarvis, requires-goal)
            ("Plano offline (sem Claude)",
             lambda g, p: ["./jarvis", "no-claude", f"workflow n8n: {g}", "--dry-run"]),
            ("Blueprint local",
             lambda g, p: ["./jarvis", "blueprint", "--type", "n8n", "--goal", g, "--dry-run"]),
            ("Iniciar lifecycle (quando Claude voltar)",
             lambda g, p: ["./jarvis", "start", f"criar workflow n8n: {g}", "--dry-run"]),
        ],
        "after_live": "Quando Claude voltar: `./jarvis next` → cole missão → relatório → `./jarvis gates`.",
    },
    "project-fix": {
        "purpose": "Preparar missão Claude para corrigir bug/feature em projeto registrado.",
        "requires": ["--project", "--goal"],
        "optional": [],
        "intro": (
            "Inspeciona projeto (read-only), monta plano local, prepara work-start. "
            "JARVIS nunca edita o projeto — somente Claude (manual) faz isso."
        ),
        "steps": [
            ("Inspeção read-only do projeto",
             lambda g, p: ["./jarvis", "project-intel", "--project", p]),
            ("Plano local",
             lambda g, p: ["./jarvis", "plan", f"{g} no projeto {p} sem produção"]),
            ("Iniciar lifecycle",
             lambda g, p: ["./jarvis", "start", f"{p}: {g}", "--dry-run"]),
        ],
        "after_live": (
            "Quando confirmar live: `./jarvis next` → Claude manual → "
            "`./jarvis report-check --file PATH --project ALIAS` → "
            "`./jarvis report-apply --file PATH --project ALIAS` → `./jarvis gates`."
        ),
    },
    "self-evolve": {
        "purpose": "Evoluir o próprio JARVIS (jarvis-core).",
        "requires": ["--goal"],
        "optional": [],
        "intro": (
            "Health quick → start no jarvis-core → quando Claude voltar, "
            "report-check/apply + gates. JARVIS nunca executa Claude."
        ),
        "steps": [
            ("Health check",
             lambda g, p: ["./jarvis", "health"]),
            ("Iniciar lifecycle no jarvis-core",
             lambda g, p: ["./jarvis", "start", f"evoluir o JARVIS: {g}", "--dry-run"]),
        ],
        "after_live": (
            "Depois: cole missão no Claude → relatório → "
            "`./jarvis report-apply --file /tmp/claude-out.md` → `./jarvis gates`."
        ),
    },
    "no-claude-plan": {
        "purpose": "Continuar sem Claude (quota acabou ou offline).",
        "requires": ["--goal"],
        "optional": [],
        "intro": (
            "Gera pacote offline + enfileira task + abre state-status. "
            "NÃO chama API. NÃO executa Claude."
        ),
        "steps": [
            ("Pacote offline",
             lambda g, p: ["./jarvis", "no-claude", g, "--dry-run"]),
            ("Enfileirar task local",
             lambda g, p: ["./jarvis", "task-add", g, "--dry-run"]),
            ("Estado runtime",
             lambda g, p: ["./jarvis", "state-status"]),
        ],
        "after_live": "Live: troque `--dry-run` por nada para gravar pacote + task.",
    },
    "resume-stuck": {
        "purpose": "Retomar após interrupção / sessão presa.",
        "requires": [],
        "optional": [],
        "intro": (
            "Sequência segura para reentrar no estado. Se ainda travar, "
            "rode state-reset --dry-run para ver o que seria removido."
        ),
        "steps": [
            ("Resume",
             lambda g, p: ["./jarvis", "now"]),
            ("Estado runtime",
             lambda g, p: ["./jarvis", "state-status"]),
            ("Status do relatório esperado",
             lambda g, p: ["./jarvis", "report-status"]),
            ("Último gate-run",
             lambda g, p: ["./jarvis", "gate-status"]),
        ],
        "after_live": (
            "Se a sessão estiver realmente presa: "
            "`./jarvis state-archive --dry-run` depois `./jarvis state-reset --dry-run`."
        ),
    },
    "handoff": {
        "purpose": "Preparar handoff textual (ChatGPT, time, etc.).",
        "requires": [],
        "optional": [],
        "intro": "Snapshot + cheatsheet + estado. Sem segredos.",
        "steps": [
            ("Snapshot do JARVIS",
             lambda g, p: ["./jarvis", "handoff-self", "--save"]),
            ("Cheatsheet",
             lambda g, p: ["./jarvis", "cheatsheet"]),
            ("Estado runtime",
             lambda g, p: ["./jarvis", "state-status"]),
        ],
        "after_live": (
            "Cole o arquivo de 05_EXECUCAO/39_HANDOFFS/ no ChatGPT/Slack. "
            "Nenhum segredo é incluído."
        ),
    },
}


# ── Arg parsing ───────────────────────────────────────────────────────────────

def parse_args(argv):
    project = None
    goal_parts = []
    dry = False
    live = False
    name = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project" and i + 1 < len(argv):
            project = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--project="):
            project = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--goal" and i + 1 < len(argv):
            goal_parts.append(argv[i + 1])
            i += 2
            continue
        if a.startswith("--goal="):
            goal_parts.append(a.split("=", 1)[1])
            i += 1
            continue
        if a == "--dry-run":
            dry = True
            i += 1
            continue
        if a == "--live" or a == "--apply":
            live = True
            i += 1
            continue
        if name is None and not a.startswith("--"):
            name = a
            i += 1
            continue
        i += 1
    goal = " ".join(goal_parts).strip()
    return name, project, goal, dry, live


# ── Output helpers ────────────────────────────────────────────────────────────

def cmd_list():
    print("JARVIS — Recipe List")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    print("## Receitas disponíveis")
    for name in sorted(RECIPES):
        r = RECIPES[name]
        req = ""
        if r["requires"]:
            req = " (requer " + ", ".join(r["requires"]) + ")"
        print(f"  {name}{req}")
        print(f"    {r['purpose']}")
    print("")
    print('## Uso')
    print('  ./jarvis recipe-show NAME')
    print('  ./jarvis recipe-run NAME [--project ALIAS] [--goal "..."] [--dry-run]')
    print("")
    print("Produção: nada alterado.")


def _show_recipe(name, project="<ALIAS>", goal="<GOAL>"):
    r = RECIPES.get(name)
    if not r:
        print(f"FALHA: recipe desconhecida: {name}")
        print("Disponíveis: " + ", ".join(sorted(RECIPES)))
        sys.exit(1)
    print(f"## Recipe: {name}")
    print(f"  Purpose: {r['purpose']}")
    if r["requires"]:
        print(f"  Requires: {', '.join(r['requires'])}")
    if r["optional"]:
        print(f"  Optional: {', '.join(r['optional'])}")
    print("")
    print("## Intro")
    print(f"  {r['intro']}")
    print("")
    print("## Steps")
    g = goal or "<GOAL>"
    p = project or "<ALIAS>"
    for i, (label, builder) in enumerate(r["steps"], 1):
        cmd = builder(g, p)
        print(f"  {i}. {label}")
        print(f"     $ {' '.join(cmd)}")
    print("")
    print("## After live")
    print(f"  {r['after_live']}")
    print("")


def cmd_show(name):
    print("JARVIS — Recipe Show")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    _show_recipe(name)
    print("Produção: nada alterado.")


def cmd_run(name, project, goal, dry, live):
    r = RECIPES.get(name)
    if not r:
        print(f"FALHA: recipe desconhecida: {name}")
        print("Disponíveis: " + ", ".join(sorted(RECIPES)))
        sys.exit(1)

    # Default behavior: dry-run unless --live (or --apply) explicit.
    if not dry and not live:
        dry = True

    # Validate required flags
    missing = []
    if "--project" in r["requires"] and not project:
        missing.append("--project")
    if "--goal" in r["requires"] and not goal:
        missing.append("--goal")
    if missing:
        print(f"FALHA: recipe '{name}' requer: {', '.join(missing)}")
        print(f"Exemplo: ./jarvis recipe-run {name} " +
              " ".join([f"{x} <valor>" for x in missing]))
        sys.exit(1)

    print(f"JARVIS — Recipe Run: {name}")
    print(f"Modo: {'--live' if live else '--dry-run'}")
    print("Status real: receita determinista. Sem Claude, sem API, sem produção.")
    print("")
    _show_recipe(name, project=project, goal=goal)

    if dry:
        print("## Resultado")
        print("  DRY-RUN: nenhum comando foi executado.")
        print("  Re-rode com --live (ou --apply) para delegar passo-a-passo.")
        print("Produção: nada alterado.")
        return 0

    # Live mode: run each step sequentially.
    print("## Live execution")
    g = goal or ""
    p = project or ""
    last_rc = 0
    for i, (label, builder) in enumerate(r["steps"], 1):
        cmd = builder(g, p)
        print("")
        print(f"## Step {i}: {label}")
        print(f"   $ {' '.join(cmd)}")
        print("")
        rc = _run(cmd)
        if rc != 0:
            print(f"AVISO: step {i} retornou exit={rc} — continuando para os demais.")
            last_rc = rc
    print("")
    print("## Resultado")
    if last_rc == 0:
        print("  Todos os steps retornaram exit=0.")
    else:
        print(f"  Algum step falhou (exit={last_rc}). Veja saída acima.")
    print(f"  After live: {r['after_live']}")
    print("Produção: nada alterado.")
    return last_rc


def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: recipes.py {list|show|run} ...")
        sys.exit(1)
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "list":
        cmd_list()
    elif cmd == "show":
        if not rest:
            print("Uso: recipe-show NAME")
            sys.exit(1)
        cmd_show(rest[0])
    elif cmd == "run":
        name, project, goal, dry, live = parse_args(rest)
        if not name:
            print("Uso: recipe-run NAME [--project ALIAS] [--goal \"...\"] [--dry-run|--live]")
            sys.exit(1)
        rc = cmd_run(name, project, goal, dry, live)
        sys.exit(rc or 0)
    else:
        print(f"FALHA: sub-comando desconhecido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
