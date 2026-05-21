from pathlib import Path
from datetime import datetime
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "11_MODE_PLANS"

BLOCKERS = [
    "segredo exposto em chat",
    "ação em produção sem modo declarado",
    "push/merge/deploy sem autorização explícita",
    "credencial salva em Git",
    "workflow n8n ativo sem validação",
]

NEGATION_HINTS = [
    "não", "nao", "sem", "nunca", "no ", "not ", "without",
    "não alterar", "nao alterar", "não mexer", "nao mexer",
    "não executar", "nao executar", "não fazer", "nao fazer",
    "sem alterar", "sem mexer", "sem deploy", "sem produção",
    "sem producao", "sem push", "sem merge",
]

PRODUCTION_TERMS = [
    "produção", "producao", "production", "deploy", "publicar",
    "ativar workflow", "ativar n8n", "push", "merge", "main",
    "master", "dns", "migration", "migrate", "banco real",
    "enviar mensagem real", "cliente real", "whatsapp real"
]

INFRA_TERMS = [
    "vps", "docker", "portainer", "traefik", "n8n", "chatwoot",
    "redis", "postgres", "supabase", "uazapi", "evolution",
    "nginx", "ssl", "domínio", "dominio", "servidor",
    "credencial", "credenciais", "token", "chave", "api key"
]

LOCAL_EXEC_TERMS = [
    "corrigir bug", "editar", "alterar código", "alterar codigo",
    "implementar", "refatorar", "build", "teste", "testar",
    "criar componente", "arrumar", "fix", "patch", "rodar build",
    "local"
]

READONLY_TERMS = [
    "analisar", "investigar", "verificar", "mapear", "auditar",
    "ler", "diagnosticar", "entender", "inspecionar", "sem alterar"
]

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "mode-plan"

def context_windows(text, term, radius=45):
    low = text.lower()
    target = term.lower()
    out = []
    start = 0

    while True:
        idx = low.find(target, start)
        if idx == -1:
            break
        a = max(0, idx - radius)
        b = min(len(text), idx + len(term) + radius)
        out.append(text[a:b])
        start = idx + len(term)

    return out

def is_negated(window):
    low = window.lower()
    return any(h in low for h in NEGATION_HINTS)

def count_terms(text, terms, negation_aware=False):
    strong = []
    mitigated = []

    for term in terms:
        windows = context_windows(text, term)
        if not windows:
            continue

        if not negation_aware:
            strong.append(term)
            continue

        non_negated = [w for w in windows if not is_negated(w)]
        if non_negated:
            strong.append(term)
        else:
            mitigated.append(term)

    return sorted(set(strong)), sorted(set(mitigated))

def detect_mode(task):
    t = task.lower()

    prod_strong, prod_mitigated = count_terms(t, PRODUCTION_TERMS, negation_aware=True)
    infra_strong, infra_mitigated = count_terms(t, INFRA_TERMS, negation_aware=False)
    local_strong, local_mitigated = count_terms(t, LOCAL_EXEC_TERMS, negation_aware=False)
    readonly_strong, readonly_mitigated = count_terms(t, READONLY_TERMS, negation_aware=False)

    # If production intent is real and not negated, strongest mode wins.
    if prod_strong:
        return "PRODUCTION_ARMED", prod_strong, prod_mitigated

    # Infrastructure work is stronger than local code work, unless the task is clearly only analysis.
    if infra_strong:
        if readonly_strong and not local_strong:
            return "READONLY", infra_strong + readonly_strong, prod_mitigated + infra_mitigated
        return "INFRA_EXEC", infra_strong, prod_mitigated + infra_mitigated

    if local_strong:
        return "LOCAL_EXEC", local_strong, prod_mitigated + local_mitigated

    if readonly_strong:
        return "READONLY", readonly_strong, prod_mitigated + readonly_mitigated

    return "PREPARE", [], prod_mitigated

def mode_rules(mode):
    if mode == "PREPARE":
        return [
            "Pode criar plano, briefing, handoff, checklist, prompt e relatório.",
            "Não altera projeto real.",
            "Não acessa VPS/n8n/produção.",
        ]

    if mode == "READONLY":
        return [
            "Pode ler arquivos, logs, status, estrutura e documentação.",
            "Não altera código, banco, workflow, VPS ou produção.",
            "Pode gerar diagnóstico e próximo passo.",
        ]

    if mode == "LOCAL_EXEC":
        return [
            "Pode editar projeto local em branch segura.",
            "Deve rodar build/teste quando aplicável.",
            "Não pode fazer push, merge ou deploy sem autorização.",
            "Não pode expor .env, tokens ou credenciais.",
        ]

    if mode == "INFRA_EXEC":
        return [
            "Pode operar VPS/Docker/Portainer/n8n quando houver escopo explícito.",
            "Deve fazer checkpoint/backup antes de ação sensível.",
            "Não deve imprimir segredo no terminal ou salvar em relatório.",
            "Não deve ativar produção sem autorização.",
        ]

    if mode == "PRODUCTION_ARMED":
        return [
            "Modo de ação real sensível.",
            "Exige autorização explícita.",
            "Deve declarar alvo, risco, rollback e validação.",
            "Deve rodar safety-gate antes e registrar status real depois.",
        ]

    return ["Modo desconhecido. Parar e revisar."]

def next_command(mode, task):
    if mode == "PREPARE":
        return f'./jarvis auto-task "{task}"'
    if mode == "READONLY":
        return f'./jarvis executor-handoff "{task}"'
    if mode == "LOCAL_EXEC":
        return f'./jarvis executor-handoff "{task}"'
    if mode == "INFRA_EXEC":
        return "./jarvis safety-gate"
    if mode == "PRODUCTION_ARMED":
        return "./jarvis safety-gate"
    return "./jarvis cockpit"

def write_report(task, mode, signals, mitigated, rules, next_step):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out = OUT_DIR / f"{ts}_{slugify(task)}_mode-plan.md"

    lines = [
        "# Mode Plan — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Tarefa\n{task}",
        "",
        "## Status real",
        "Plano de modo criado localmente. Nada executado no projeto real.",
        "",
        f"## Modo sugerido\n{mode}",
        "",
        f"## Sinais usados\n{', '.join(signals) if signals else 'nenhum sinal forte detectado'}",
        "",
        f"## Sinais mitigados por negação\n{', '.join(mitigated) if mitigated else 'nenhum'}",
        "",
        "## Regras do modo",
        *[f"- {x}" for x in rules],
        "",
        "## Bloqueios permanentes",
        *[f"- {x}" for x in BLOCKERS],
        "",
        "## Próximo comando seguro",
        f"`{next_step}`",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out

def main():
    task = " ".join(sys.argv[1:]).strip()
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    if not task:
        print('Uso: ./jarvis mode-plan "tarefa"')
        sys.exit(1)

    mode, signals, mitigated = detect_mode(task)
    rules = mode_rules(mode)
    next_step = next_command(mode, task)

    print("JARVIS — Theo Padilha AI Worker Mode Plan")
    print("")
    print(f"Tarefa: {task}")
    print(f"Modo sugerido: {mode}")
    print("")
    print(f"Sinais usados: {', '.join(signals) if signals else 'nenhum'}")
    print(f"Sinais mitigados por negação: {', '.join(mitigated) if mitigated else 'nenhum'}")
    print("")
    print("Regras:")
    for item in rules:
        print(f"- {item}")
    print("")
    print(f"Próximo comando seguro: {next_step}")

    if no_report:
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
    else:
        out = write_report(task, mode, signals, mitigated, rules, next_step)
        print(f"Relatório: {out.relative_to(ROOT)}")

    print("")
    print("Status real: plano local. Nada executado no projeto real.")

if __name__ == "__main__":
    main()
