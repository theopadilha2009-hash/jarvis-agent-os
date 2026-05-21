from pathlib import Path
from datetime import datetime
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

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "mode-plan"

def detect_mode(task):
    t = task.lower()

    production_terms = [
        "produção", "production", "deploy", "publicar", "ativar workflow",
        "ativar n8n", "push", "merge", "main", "master", "dns",
        "migration", "migrate", "banco real", "enviar mensagem real",
        "cliente real", "whatsapp real"
    ]

    infra_terms = [
        "vps", "docker", "portainer", "traefik", "n8n", "chatwoot",
        "redis", "postgres", "supabase", "uazapi", "evolution",
        "nginx", "ssl", "domínio", "dominio", "servidor"
    ]

    local_exec_terms = [
        "corrigir bug", "editar", "alterar código", "alterar codigo",
        "implementar", "refatorar", "build", "teste", "testar",
        "criar componente", "arrumar", "fix", "patch"
    ]

    readonly_terms = [
        "analisar", "investigar", "verificar", "mapear", "auditar",
        "ler", "diagnosticar", "entender", "inspecionar"
    ]

    if any(x in t for x in production_terms):
        return "PRODUCTION_ARMED"
    if any(x in t for x in infra_terms):
        return "INFRA_EXEC"
    if any(x in t for x in local_exec_terms):
        return "LOCAL_EXEC"
    if any(x in t for x in readonly_terms):
        return "READONLY"
    return "PREPARE"

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

def main():
    task = " ".join(sys.argv[1:]).strip()

    if not task:
        print('Uso: ./jarvis mode-plan "tarefa"')
        sys.exit(1)

    mode = detect_mode(task)
    rules = mode_rules(mode)
    next_step = next_command(mode, task)

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

    print("JARVIS — Theo Padilha AI Worker Mode Plan")
    print("")
    print(f"Tarefa: {task}")
    print(f"Modo sugerido: {mode}")
    print("")
    print("Regras:")
    for item in rules:
        print(f"- {item}")
    print("")
    print(f"Próximo comando seguro: {next_step}")
    print(f"Relatório: {out.relative_to(ROOT)}")
    print("")
    print("Status real: plano local. Nada executado no projeto real.")

if __name__ == "__main__":
    main()
