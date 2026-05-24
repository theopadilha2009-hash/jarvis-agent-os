"""
limits.py — explains JARVIS's robot boundary in one screen.

Read-only. No flags. Theo runs `./jarvis limits` when he wants to remember
(or show someone) what JARVIS can / cannot / must not do — without asking
ChatGPT or grepping AGENTS.md.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


CAN_DO = [
    "interpretar pedidos em linguagem natural (regex + registry, sem LLM)",
    "classificar intent e detectar projeto local",
    "sugerir o próximo comando seguro (`./jarvis ask`, `./jarvis go`)",
    "gerar missões Claude (`self-evolve`, `goal-sprint`, `qa-sprint`, …) e copiar para o clipboard",
    "manter inbox local append-only (`capture`/`inbox`)",
    "manter agenda local append-only com heurística de data PT (`agenda-add`/`agenda`)",
    "gerar blueprints locais (n8n/app/automation/research) com checklist",
    "ler memória de projeto (`project-memory`, `project-cockpit`)",
    "registrar debriefs validados (`project-memory-update`, `self-debrief`)",
    "recusar relatórios fracos antes de gravar memória",
    "rodar gates locais (`safety-gate`, `smoke-test`, `command-audit`, `doctrine-check`)",
    "imprimir bloco `cd PATH; claude` (`project-open`, `claude-launch`)",
    "imprimir plano de execução (`plan`)",
    "registrar requests não classificadas (`ask-log`) para futuras melhorias de patterns",
    "explicar suas próprias limitações (`limits`)",
]

CANNOT_DO_YET = [
    "executar Claude por conta própria (Theo abre o Claude Code manualmente)",
    "responder texto livre fora dos patterns (cai em UNCLEAR → self-cockpit)",
    "criar workflow n8n real, importar JSON, ativar webhook",
    "aprender padrões automaticamente (ask-log junta dados; tuning ainda é manual)",
    "abrir VS Code além de imprimir a sugestão (`code PATH`)",
    "decidir sozinho qual commit fazer ou qual branch usar",
]

REQUIRES_CLAUDE = [
    "executar a missão gerada (Theo cola o prompt no Claude Code)",
    "implementar a mudança real no projeto-alvo",
    "produzir o relatório final em STATUS REAL / WHAT IMPROVED / RISKS / SAFE TO COMMIT",
]

REQUIRES_HUMAN = [
    "decidir `--apply` no `self-debrief` / `project-memory-update`",
    "rodar `git commit` (JARVIS nunca commita sem ser explicitamente pedido)",
    "rodar push / PR / merge / deploy (JARVIS nunca faz)",
    "rodar migrations",
    "ativar workflows n8n / webhooks / cron",
    "informar segredos (.env / tokens) — JARVIS recusa lê-los ou imprimi-los",
]

FORBIDDEN = [
    "chamar Anthropic, OpenAI ou qualquer API paga",
    "executar Claude em background",
    "tocar produção, VPS, n8n real, Docker remoto, Supabase de produção",
    "editar arquivos de projetos-alvo (Oficina, GC, LS, etc.) — só leitura/cockpit",
    "fazer push / PR / merge / deploy",
    "instalar dependências (Python stdlib only)",
    "ler `.env` ou imprimir tokens / cookies / senhas / QR codes",
    "criar fontes randômicas ou gerar PDF",
    "editar `main` / `master` (se branch=main, JARVIS PARA)",
    "fazer commit sem autorização explícita do Theo",
]


def _print_section(title, items):
    print(f"## {title}")
    if not items:
        print("- (nenhum)")
    for line in items:
        print(f"- {line}")
    print("")


def main():
    print("JARVIS — Robot Limits")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    _print_section("O que JARVIS PODE fazer agora", CAN_DO)
    _print_section("O que JARVIS AINDA NÃO faz", CANNOT_DO_YET)
    _print_section("O que requer Claude (executado manualmente por Theo)", REQUIRES_CLAUDE)
    _print_section("O que requer aprovação humana", REQUIRES_HUMAN)
    _print_section("O que é PROIBIDO (hard rule, não negociável)", FORBIDDEN)
    print("Documentação completa: AGENTS.md + 01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
