# System Overview — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T14:33:46

## Criador / dono
Theo Padilha

## Status real
Laboratório local estável. Não é produção.

## Git
Commit: 4ab977b
Status: M 01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md
?? 01_SISTEMA/00_REGRAS/REGRAS_EXECUCAO_FORTE_CREDENCIAIS.md
?? 03_MEMORIA/02_DECISOES/2026-05-21_decisao-execucao-forte-credenciais-protegidas.md

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
Smoke tests: 27
Release checks: 22
Checkpoints: 7

## Catálogo de comandos
01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md

## Último task-status
07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md

## Produção
Nada alterado.

## Próximo passo seguro
Consolidar revisão de outputs e depois planejar executor read-only, sem edição automática ainda.
