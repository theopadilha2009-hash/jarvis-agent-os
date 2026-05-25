"""
no_claude.py — JARVIS offline mode (sem Claude / sem API paga).

Quando o Claude estiver indisponível (quota, internet, etc.), Theo ainda
precisa de ajuda para destrinchar um pedido. Este módulo classifica o
pedido localmente (regex via ask_router), detecta projeto, gera um plano
manual + bloco "comandos seguros para você executar" e (opcionalmente)
um pacote local em 05_EXECUCAO/38_NO_CLAUDE/.

Usage:
  ./jarvis no-claude "pedido"               # gera pacote local (default)
  ./jarvis no-claude "pedido" --dry-run     # só imprime, não grava
  ./jarvis no-claude "pedido" --no-task     # não enfileira task
  ./jarvis no-claude "pedido" --project A   # override de projeto

Hard rules:
  - NUNCA executa Claude
  - NUNCA chama API paga / LLM
  - NUNCA toca produção / VPS / n8n real
  - NUNCA edita projetos-alvo
  - NUNCA lê .env nem imprime segredos
  - apenas planejamento local + comandos seguros
"""
from pathlib import Path
from datetime import datetime
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "38_NO_CLAUDE"

# Reuse ask_router + secret_scan from the same scripts dir.
try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from ask_router import (  # type: ignore
        detect_intent as _di,
        detect_project_alias as _dp,
        _next_command_for as _ncf,
        INTENT_N8N_BLUEPRINT,
        INTENT_APP_BLUEPRINT,
        INTENT_AUTOMATION_BLUEPRINT,
        INTENT_RESEARCH_PLAN,
        INTENT_PROJECT_FIX,
        INTENT_PROJECT_QA,
        INTENT_BROWSER_QA,
        INTENT_FINAL_GATE,
        INTENT_OPEN_PROJECT,
        INTENT_SELF_EVOLVE,
        INTENT_UNCLEAR,
    )
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []
    INTENT_N8N_BLUEPRINT = "n8n_blueprint"
    INTENT_APP_BLUEPRINT = "app_blueprint"
    INTENT_AUTOMATION_BLUEPRINT = "automation_blueprint"
    INTENT_RESEARCH_PLAN = "research_plan"
    INTENT_PROJECT_FIX = "project_fix"
    INTENT_PROJECT_QA = "project_qa"
    INTENT_BROWSER_QA = "browser_qa"
    INTENT_FINAL_GATE = "final_gate"
    INTENT_OPEN_PROJECT = "open_project"
    INTENT_SELF_EVOLVE = "self_evolve"
    INTENT_UNCLEAR = "unclear"

    def _di(text): return INTENT_UNCLEAR
    def _dp(text, override=None): return override or ""
    def _ncf(intent, project, text, copy_flag):
        return ([], "./jarvis self-cockpit", "readonly", True)


def _looks_secret_like(text: str) -> bool:
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(text or ""):
            return True
    return False


def _slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "no-claude"


def parse_args(argv):
    text_parts = []
    alias = None
    dry_run = False
    no_task = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project" and i + 1 < len(argv):
            alias = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        if a == "--no-task":
            no_task = True
            i += 1
            continue
        text_parts.append(a)
        i += 1
    return " ".join(text_parts).strip(), alias, dry_run, no_task


# Blueprint type inference for the spec block
BLUEPRINT_INTENTS = {
    INTENT_N8N_BLUEPRINT: "n8n",
    INTENT_APP_BLUEPRINT: "app",
    INTENT_AUTOMATION_BLUEPRINT: "automation",
    INTENT_RESEARCH_PLAN: "research",
}


def _summary_md(text, project, intent, btype, task_id):
    """One-page summary — first file Theo opens when Claude is down."""
    parts = [
        "# No-Claude — uma página\n\n",
        f"## O pedido\n{text}\n\n",
        "## Como JARVIS leu\n",
        f"- intent:    `{intent}`\n",
        f"- project:   `{project or '(não detectado)'}`\n",
        f"- blueprint: `{btype or '(n/a)'}`\n",
        f"- task local: `{task_id or '(não criada)'}`\n\n",
    ]
    parts.append("## Top 3 ações que VOCÊ pode fazer agora (sem Claude)\n")
    if intent == INTENT_SELF_EVOLVE:
        parts += [
            "1. `./jarvis self-cockpit` — ver onde JARVIS está.\n",
            "2. `./jarvis limits` — lembrar fronteira do robô.\n",
            "3. `./jarvis self-evolve --goal \"…\"` quando Claude voltar.\n",
        ]
    elif intent in (INTENT_PROJECT_FIX, INTENT_PROJECT_QA, INTENT_BROWSER_QA,
                    INTENT_FINAL_GATE, INTENT_OPEN_PROJECT):
        p = project or "<ALIAS>"
        parts += [
            f"1. `./jarvis project-intel --project {p}` — inspeção atual.\n",
            "2. Olhar `06_DEEP_INTEL.md` aqui no pacote — arquivos candidatos e hot files.\n",
            f"3. `./jarvis do \"{text}\" --project {p}` quando Claude voltar.\n",
        ]
    elif btype == "n8n":
        parts += [
            f"1. `./jarvis blueprint --type n8n --goal \"{text}\"`\n",
            "2. Desenhar nós/edges no papel.\n",
            "3. Quando Claude voltar: cole o blueprint no Claude para gerar JSON.\n",
        ]
    elif btype == "app":
        parts += [
            f"1. `./jarvis blueprint --type app --goal \"{text}\"`\n",
            "2. Esboçar telas + modelo de dados no papel.\n",
            "3. Quando Claude voltar: usar o blueprint como missão de scaffold.\n",
        ]
    else:
        parts += [
            "1. Ler `03_MANUAL_PLAN.md` aqui e seguir o roteiro.\n",
            "2. Anotar dúvidas com `./jarvis capture \"...\"`.\n",
            "3. Quando Claude voltar: rodar `./jarvis do \"<refinado>\"`.\n",
        ]
    parts.append("\n## Risco principal\n")
    parts.append(
        "Sem Claude, mudanças complexas viram especulação. Foque em inspecionar,\n"
        "documentar dúvidas e preparar um pedido melhor. NÃO faça refactor grande.\n"
    )
    parts.append("\n## O que aguarda Claude\n")
    parts.append(
        "- escrever código complexo (edits multi-arquivo)\n"
        "- montar workflow n8n real (JSON)\n"
        "- gerar relatório STATUS REAL do projeto\n"
        "- propor PR\n"
    )
    parts.append("\n## O que NÃO aguarda Claude (você pode fazer agora)\n")
    parts.append(
        "- ler código, entender contexto, rodar testes existentes\n"
        "- desenhar no papel, listar fontes\n"
        "- ajustar `./jarvis ask` patterns via `./jarvis do-learn`\n"
        "- planejar e capturar ideias\n"
    )
    parts.append("\n_Status real: pacote gerado offline. Claude não executado. "
                 "API paga não chamada. Produção intacta._\n")
    return "".join(parts)


def _request_md(text, project, intent, safety, ts):
    return (
        f"# No-Claude Request\n\n"
        f"## Timestamp\n{ts}\n\n"
        f"## Texto original\n{text}\n\n"
        f"## Intent detectado (regex local)\n{intent}\n\n"
        f"## Projeto detectado\n{project or '(nenhum)'}\n\n"
        f"## Safety classification\n{safety}\n\n"
        f"## Status real\n"
        f"Pacote criado offline. Claude não executado. API paga não chamada.\n"
    )


def _interpretation_md(text, project, intent, btype):
    parts = [
        "# Interpretação local (sem LLM)\n",
        "## O que JARVIS entendeu\n",
        f"- intent: `{intent}`\n",
        f"- projeto: `{project or '(não detectado)'}`\n",
    ]
    if btype:
        parts.append(f"- blueprint type sugerido: `{btype}`\n")
    parts += [
        "\n## Como JARVIS chegou aqui\n",
        "JARVIS classificou via `ask_router.detect_intent` (regex, sem LLM).\n",
        "Se o intent estiver errado, o pedido pode ser ambíguo. Use `./jarvis ask-log`\n",
        "para revisar requests que cairam em `unclear` e ajustar `INTENT_PATTERNS`.\n",
        "\n## O que JARVIS NÃO pode fazer sem Claude\n",
        "- escrever o código real\n",
        "- aplicar fix no projeto-alvo\n",
        "- escrever o workflow n8n real\n",
        "- abrir Claude Code ou rodar agente em background\n",
        "- chamar API Anthropic / OpenAI\n",
        "\n## O que JARVIS pode fazer agora\n",
        "- gerar plano manual (próximo arquivo)\n",
        "- imprimir comandos seguros que VOCÊ executa\n",
        "- gerar blueprint local (se aplicável)\n",
        "- enfileirar task local (`task-add`) para retomar quando Claude voltar\n",
    ]
    return "".join(parts)


def _manual_plan_md(text, project, intent, btype):
    lines = [
        "# Plano manual (Theo executa)\n",
        f"\n## Pedido\n{text}\n",
        f"\n## Etapas seguras propostas\n",
    ]
    if intent == INTENT_SELF_EVOLVE:
        lines += [
            "1. Rodar `./jarvis self-cockpit` para ver estado atual.\n",
            "2. Rodar `./jarvis self-next` para próximo passo seguro.\n",
            "3. Listar limitações: `./jarvis limits`.\n",
            "4. Quando Claude voltar: `./jarvis self-evolve --goal \"...\"`.\n",
        ]
    elif intent in (INTENT_PROJECT_FIX, INTENT_PROJECT_QA, INTENT_BROWSER_QA, INTENT_FINAL_GATE, INTENT_OPEN_PROJECT):
        proj = project or "<ALIAS>"
        lines += [
            f"1. Confirmar alias: `./jarvis project-resolve {proj}`.\n",
            f"2. Inspeção read-only: `./jarvis project-intel --project {proj}`.\n",
            f"3. Memória do projeto: `./jarvis project-memory --project {proj}`.\n",
            f"4. Abrir caminho do projeto (sem editar): `./jarvis project-open --project {proj} --print-only`.\n",
            "5. Anotar próximos passos manuais com `./jarvis capture \"...\"`.\n",
            "6. Quando Claude voltar: `./jarvis go \"<pedido refinado>\"` para gerar a missão.\n",
        ]
    elif btype == "n8n":
        lines += [
            "1. Gerar blueprint local: `./jarvis blueprint --type n8n --goal \"...\"` (não cria workflow real).\n",
            "2. Revisar o checklist e a spec gerados em `05_EXECUCAO/40_BLUEPRINTS/`.\n",
            "3. Manualmente desenhar nós/edges no papel ou Excalidraw.\n",
            "4. NÃO importar JSON em n8n real até validar.\n",
            "5. Quando Claude voltar: usar o blueprint como prompt.\n",
        ]
    elif btype == "app":
        lines += [
            "1. Gerar blueprint local: `./jarvis blueprint --type app --goal \"...\"`.\n",
            "2. Esboçar manualmente: telas, fluxos, modelo de dados.\n",
            "3. Decidir stack apenas no papel (sem `npm/bun init`).\n",
            "4. Quando Claude voltar: usar o blueprint como missão de scaffold.\n",
        ]
    elif btype == "automation":
        lines += [
            "1. Gerar blueprint local: `./jarvis blueprint --type automation --goal \"...\"`.\n",
            "2. Listar triggers + ações no papel.\n",
            "3. Avaliar se cabe cron / webhook / fila.\n",
            "4. NÃO ativar cron real.\n",
            "5. Quando Claude voltar: gerar missão de implementação.\n",
        ]
    elif btype == "research":
        lines += [
            "1. Gerar blueprint local: `./jarvis blueprint --type research --goal \"...\"`.\n",
            "2. Listar perguntas-chave e hipóteses no papel.\n",
            "3. Anotar fontes a ler.\n",
            "4. Quando Claude voltar: pedir síntese com `./jarvis go \"resume X sem deploy\"`.\n",
        ]
    else:
        lines += [
            "1. Rodar `./jarvis ask \"<pedido>\"` para ver classificação local + comando seguro.\n",
            "2. Se ficar `unclear`, anotar com `./jarvis capture \"...\"` ou `./jarvis agenda-add \"...\"`.\n",
            "3. Rodar `./jarvis cheatsheet` para lembrar atalhos.\n",
            "4. Rodar `./jarvis doctor-agent` se algo parecer travado.\n",
            "5. Quando Claude voltar: `./jarvis go \"<pedido refinado>\"`.\n",
        ]
    return "".join(lines)


def _safe_commands_md(text, project, btype):
    proj = project or "<ALIAS>"
    lines = [
        "# Comandos seguros (você executa)\n",
        "\n## Diagnóstico\n",
        "```\n",
        "./jarvis doctor-agent\n",
        "./jarvis state-status\n",
        "./jarvis limits\n",
        "./jarvis resume\n",
        "```\n",
        "\n## Planejamento local (sem Claude)\n",
        "```\n",
        f"./jarvis plan \"{text}\" --save\n",
        f"./jarvis ask \"{text}\"\n",
        "```\n",
    ]
    if project:
        lines += [
            "\n## Inspeção do projeto (read-only)\n",
            "```\n",
            f"./jarvis project-intel --project {proj}\n",
            f"./jarvis project-memory --project {proj}\n",
            f"./jarvis project-cockpit --project {proj}\n",
            f"./jarvis project-open --project {proj} --print-only\n",
            "```\n",
        ]
    if btype:
        lines += [
            f"\n## Blueprint local ({btype})\n",
            "```\n",
            f"./jarvis blueprint --type {btype} --goal \"{text}\"\n",
            "```\n",
        ]
    lines += [
        "\n## Gates (rodam local)\n",
        "```\n",
        "env JARVIS_NO_REPORT=1 ./jarvis safety-gate\n",
        "env JARVIS_NO_REPORT=1 ./jarvis smoke-test\n",
        "./jarvis command-audit\n",
        "./jarvis doctrine-check\n",
        "```\n",
    ]
    return "".join(lines)


def _status_real_md(text, project, intent, btype, task_id, dry_run):
    lines = [
        "# Status real\n",
        f"\n## Pedido\n{text}\n",
        f"\n## Resultado\n",
        f"- modo: {'--dry-run (nada gravado)' if dry_run else 'pacote local criado'}\n",
        f"- intent: {intent}\n",
        f"- projeto: {project or '(nenhum)'}\n",
        f"- blueprint type: {btype or '(n/a)'}\n",
        f"- task local: {task_id or '(não criada)'}\n",
        "\n## O que JARVIS NÃO fez\n",
        "- não executou Claude\n",
        "- não chamou API paga (Anthropic/OpenAI)\n",
        "- não tocou produção / VPS / n8n real\n",
        "- não editou projetos-alvo\n",
        "- não leu .env nem imprimiu segredos\n",
        "- não fez push / PR / merge / deploy\n",
        "\n## Quando Claude voltar\n",
        f"- `./jarvis go \"{text}\"`\n",
        "- ou rever a missão sugerida em `02_INTERPRETATION.md`.\n",
    ]
    return "".join(lines)


def _add_task(text, project, intent):
    """Best-effort task-add — never fails the run."""
    cmd = ["python3", "11_SCRIPTS/task_queue.py", "add", text,
           "--source", "no-claude",
           "--intent", intent]
    if project:
        cmd += ["--project", project]
    cmd += ["--print-id"]
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=10)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("TASK_ID="):
                return line.split("=", 1)[1].strip()
        return None
    except Exception:
        return None


def main():
    text, alias, dry_run, no_task = parse_args(sys.argv[1:])
    if not text:
        print("Uso: ./jarvis no-claude \"pedido\" [--project ALIAS] [--dry-run] [--no-task]")
        sys.exit(1)
    if _looks_secret_like(text):
        print("FALHA: pedido parece conter segredo (token/api key/etc). JARVIS recusa registrar.")
        sys.exit(1)

    intent = _di(text)
    project = _dp(text, alias)
    _cl, next_cmd, safety, _safe = _ncf(intent, project, text, None)
    btype = BLUEPRINT_INTENTS.get(intent)

    ts = datetime.now().isoformat(timespec="seconds")
    ts_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    slug = _slugify(text)
    pkg_rel = f"05_EXECUCAO/38_NO_CLAUDE/{ts_dir}_{slug}"

    print("JARVIS — No-Claude Mode")
    print("Status real: planejamento local. Claude não executado. API paga não chamada.")
    print("")
    print(f"## Pedido")
    print(f"  {text}")
    print(f"## Classificação local")
    print(f"  intent:    {intent}")
    print(f"  project:   {project or '(não detectado)'}")
    print(f"  safety:    {safety}")
    print(f"  blueprint: {btype or '(n/a)'}")
    print("")

    # Task add (unless --no-task or --dry-run)
    task_id = None
    if not no_task and not dry_run:
        task_id = _add_task(text, project, intent)
        if task_id:
            print(f"  task local: {task_id}  (./jarvis task-show {task_id})")
        else:
            print("  task local: (não criada — task_queue indisponível)")
    elif no_task:
        print("  task local: pulada (--no-task)")
    else:
        print("  task local: pulada (--dry-run)")
    print("")

    # Sprint 8.3 — Deep project intel for no-claude when a project is detected.
    # Theo working without Claude needs concrete file pointers, not vague advice.
    deep_intel_md = ""
    if project:
        try:
            import project_deep_intel as _pdi  # type: ignore
            deep_data = _pdi.gather(project, text)
            deep_intel_md = _pdi.render_markdown(deep_data)
        except Exception:
            pass

    # Files in package
    pkg = OUT_DIR / f"{ts_dir}_{slug}"
    files = {
        "00_SUMMARY.md": _summary_md(text, project, intent, btype, task_id),
        "01_REQUEST.md": _request_md(text, project, intent, safety, ts),
        "02_INTERPRETATION.md": _interpretation_md(text, project, intent, btype),
        "03_MANUAL_PLAN.md": _manual_plan_md(text, project, intent, btype),
        "04_SAFE_COMMANDS.md": _safe_commands_md(text, project, btype),
        "05_STATUS_REAL.md": _status_real_md(text, project, intent, btype, task_id, dry_run),
    }
    if deep_intel_md:
        files["06_DEEP_INTEL.md"] = (
            "# Project deep intel (read-only — git + grep + ls-files)\n\n"
            + deep_intel_md
            + "\n\n_Status real: leitura local do projeto. Nada foi editado._\n"
        )

    if dry_run:
        print("## Modo: --dry-run")
        print("  (nenhum arquivo gravado em 38_NO_CLAUDE)")
        print(f"  alvo seria: {pkg_rel}/")
        for name in files:
            print(f"    - {name}")
        print("")
        print("## Plano manual resumido")
        # Print plan to stdout so Theo can see it without files
        for line in _manual_plan_md(text, project, intent, btype).splitlines()[:30]:
            print(f"  {line}")
        print("")
        print("## Comandos seguros")
        # Print safe commands inline
        for line in _safe_commands_md(text, project, btype).splitlines():
            print(f"  {line}")
    else:
        try:
            pkg.mkdir(parents=True, exist_ok=True)
            for name, body in files.items():
                (pkg / name).write_text(body, encoding="utf-8")
            print(f"## Pacote gerado")
            print(f"  {pkg_rel}/")
            for name in files:
                print(f"    - {name}")
            print("")
            print(f"  Ver: cat {pkg_rel}/03_MANUAL_PLAN.md")
        except Exception as e:
            print(f"FALHA: não criei pacote: {e}")
            sys.exit(1)

    print("")
    print("## O que JARVIS NÃO fez")
    print("- não executou Claude")
    print("- não chamou API paga")
    print("- não tocou produção / VPS / n8n real")
    print("- não editou projetos-alvo")
    print("- não leu .env / não imprimiu segredos")
    print("")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
