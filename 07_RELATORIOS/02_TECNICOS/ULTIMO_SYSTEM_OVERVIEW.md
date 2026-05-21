# System Overview — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T14:13:19

## Criador / dono
Theo Padilha

## Status real
Laboratório local estável. Não é produção.

## Git
Commit: f69679c
Status: M 01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md
 M 07_RELATORIOS/02_TECNICOS/ULTIMO_SYSTEM_OVERVIEW.md
 M 07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md
 M 11_SCRIPTS/cli_smoke_test.py
?? 10_TESTES/SMOKE_TESTS/2026-05-21_14-13-18-502777_cli-smoke-test.md

## Capacidades atuais
- mapear projetos do Mac
- escolher projeto provável para uma tarefa
- checar workspace antes de execução
- gerar task-start
- gerar handoff para Claude/VS Code
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
- `./jarvis executor-handoff "tarefa"`
- `./jarvis handoff-print`
- `./jarvis release-check`

## Artefatos registrados
Smoke tests: 16
Release checks: 12
Checkpoints: 6

## Catálogo de comandos
01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md

## Último task-status
07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md

## Produção
Nada alterado.

## Próximo passo seguro
Criar `task-brief` para transformar uma tarefa em um briefing único pronto para execução manual.
