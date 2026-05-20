# Status v0.4 Stable — JARVIS Theo Padilha AI Worker

## Data
2026-05-20T19:38:08

## Status real
Snapshot local estável. Não é produção.

## Criador / dono
Theo Padilha.

## Marco atual
JARVIS v0.4 já funciona como cockpit local para projetos, tarefas, seleção de projeto, handoff para executor manual e validação local.

## Fluxos existentes
- project-index
- project-select
- workspace-check
- task-start
- executor-handoff
- handoff-latest
- handoff-print
- commands
- task-status
- smoke-test
- release-check
- quality-gate

## Validado
- Python compile
- self-test
- quality-gate
- smoke-test
- release-check
- Git limpo após commit

## Não é ainda
- app visual
- voz
- Claude conectado automaticamente
- Gemini conectado automaticamente
- n8n conectado automaticamente
- produção
- deploy
- executor autônomo com permissão livre

## Próximo passo seguro
Criar camada de `task-brief` ou melhorar `review-outputs`, ainda sem conexão automática com Claude/Gemini/n8n.

## Regra
Tudo que é plano, prompt, handoff, task-start ou relatório é preparação. Execução real e produção continuam separadas.
