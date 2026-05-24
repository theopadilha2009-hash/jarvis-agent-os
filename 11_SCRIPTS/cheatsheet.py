"""
cheatsheet.py — JARVIS pocket cheatsheet (uma tela).

Theo chega cansado, abre o terminal e digita uma coisa só:
  ./jarvis cheatsheet

E sai do terminal sabendo o que fazer.

Read-only. Sem flags. Não toca produção.
"""
import sys


CHEATSHEET = """\
JARVIS — Cheatsheet (uma tela)
Status real: leitura local. Nada foi editado.

## Comece por aqui
  ./jarvis now                          # retomar (status + último run + próximo passo)

## Lifecycle (com Claude disponível)
  ./jarvis start "pedido"               # inicia sessão (task+run+missão)
  ./jarvis next                         # próximo passo seguro
  ./jarvis report-template              # cat > /tmp/... para colar relatório
  ./jarvis report-check --file PATH     # valida relatório (sem gravar)
  ./jarvis report-apply --file PATH     # aplica debrief (registra memória)
  ./jarvis gates                        # roda safety+smoke+doctrine
  ./jarvis finish                       # fecha sessão (após gates_passed)

## Sem Claude (quota acabou, sem internet, etc.)
  ./jarvis no-claude "pedido"           # plano manual + comandos seguros
  ./jarvis no-claude "pedido" --dry-run # sem gravar pacote

## Saúde / diagnóstico
  ./jarvis health                       # alias de doctor-agent
  ./jarvis doctor-agent                 # diagnóstico local rápido
  ./jarvis doctor-agent --full          # + smoke-test completo

## Estado preso? Recuperação segura
  ./jarvis state-status                 # ver o que está em memória
  ./jarvis state-reset --dry-run        # mostra o que seria removido
  ./jarvis state-reset --apply          # remove current.json (events.jsonl fica)
  ./jarvis state-archive --dry-run      # mostra cópia para archive/
  ./jarvis state-archive --apply        # cria cópia em archive/<ts>_current.json

## Limpeza
  ./jarvis run-prune --keep 20 --dry-run
  ./jarvis run-prune --keep 20 --apply

## Quando pedirem contexto / handoff
  ./jarvis handoff-self                 # snapshot do JARVIS (terminal)
  ./jarvis handoff-self --save          # grava em 39_HANDOFFS/

## Fora de uso: sempre seguro de rodar (read-only)
  ./jarvis limits                       # fronteira do robô
  ./jarvis resume                       # mesmo que `now`
  ./jarvis cheatsheet                   # essa tela
  ./jarvis doctrine-check               # drift de docs/help/catalog

## Regras invariáveis
- JARVIS nunca executa Claude. Theo abre o Claude Code manualmente.
- Sem API paga (Anthropic/OpenAI). Stdlib Python apenas.
- Sem deploy / push / PR / merge / migrations.
- Nunca lê .env. Nunca imprime tokens, cookies, QR codes.
- main/master = STOP.

Produção: nada alterado.
"""


def main():
    print(CHEATSHEET, end="")


if __name__ == "__main__":
    main()
