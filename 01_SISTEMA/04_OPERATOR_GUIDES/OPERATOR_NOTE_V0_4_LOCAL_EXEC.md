# Operator Note v0.4 — JARVIS LOCAL_EXEC

## Status real

JARVIS v0.4 está fechado como cockpit local de preparação, validação, handoff e revisão.

Ele é local/free-first. Claude é opcional e só deve ser usado quando for útil ou autorizado para uma tarefa real.

## Fluxo principal

./jarvis local-exec-session "tarefa"
./jarvis local-exec-session-latest
./jarvis local-exec-handoff-latest

## Como usar executor externo

Use Claude/VS Code apenas quando necessário. O padrão é preparar, revisar e validar primeiro.

Depois da resposta do executor, salvar em arquivo .md e rodar:
./jarvis local-exec-review caminho/da/resposta.md

## Gates obrigatórios

./jarvis quality-gate
./jarvis release-check
./jarvis safety-gate

## Ainda não faz sozinho

- patch automático
- build/test real automático
- commit/push/PR automático
- deploy
- VPS/n8n/produção

## Produção

Nada em v0.4 altera produção.
