# System Overview — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T14:45:41

## Criador / dono
Theo Padilha

## Status real
Laboratório local estável. Não é produção.

## Git
Commit: a2d1ec7
Status: M 07_RELATORIOS/02_TECNICOS/ULTIMO_SYSTEM_OVERVIEW.md
 M 07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md
 M 11_SCRIPTS/cli_smoke_test.py
?? 10_TESTES/SMOKE_TESTS/2026-05-21_14-45-41-077917_cli-smoke-test.md

## Capacidades atuais
- mapear projetos do Mac
- escolher projeto provável para uma tarefa
- checar workspace antes de execução
- gerar task-start
- gerar handoff para Claude/VS Code
- rodar preparação completa com auto-task
- imprimir último handoff no terminal
- revisar outputs manuais
- rodar smoke-test, release-check e quality-gate
- salvar checkpoints e releases locais

## Comandos-chave
- `./jarvis commands`
- `./jarvis task-status`
- `./jarvis project-index ~/VAMOO_PROJETOS`
- `./jarvis project-select "tarefa"`
- `./jarvis task-start "tarefa"`
- `./jarvis auto-task "tarefa"`
- `./jarvis auto-task-latest`
- `./jarvis executor-handoff "tarefa"`
- `./jarvis handoff-print`
- `./jarvis release-check`

## Artefatos registrados
Smoke tests: 33
Release checks: 25
Checkpoints: 7

## Catálogo de comandos
01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md

## Último task-status
07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md

## Produção
Nada alterado.

## Próximo passo seguro
Consolidar revisão de outputs e depois planejar executor read-only, sem edição automática ainda.
