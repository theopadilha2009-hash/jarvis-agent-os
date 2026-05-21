# System Overview — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T14:19:12

## Criador / dono
Theo Padilha

## Status real
Laboratório local estável. Não é produção.

## Git
Commit: 55db183
Status: M 04_PROJETOS/_INDEX/PROJECT_INDEX.json
 M 04_PROJETOS/_INDEX/PROJECT_INDEX.md
 M 07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md
 M 11_SCRIPTS/jarvis_core.py
?? 05_EXECUCAO/04_WORKSPACE_CHECKS/2026-05-21_14-19-10-337688_gc-gestao-de-cristo_workspace-check.md
?? 05_EXECUCAO/04_WORKSPACE_CHECKS/2026-05-21_14-19-11-106861_gc-gestao-de-cristo_workspace-check.md
?? 05_EXECUCAO/06_TASK_STARTS/2026-05-21_14-19-10-465526_corrigir-bug-de-visitantes-do-gc-sem-produ-o_task-start.md
?? 05_EXECUCAO/07_EXECUTOR_HANDOFFS/2026-05-21_14-19-11-113350_corrigir-bug-de-visitantes-do-gc-sem-produ-o/
?? 05_EXECUCAO/08_TASK_BRIEFS/2026-05-21_14-19-09-690097_corrigir-bug-de-visitantes-do-gc-sem-produ-o_task-brief.md
?? 06_PROMPTS/99_GENERATED/2026-05-21_14-19-10-461787_projeto-da-empresa-no-vs-code-com-executor-externo-autorizad/
?? 09_LOGS/2026-05-21_14-19-10-462533_prompt-pack-created.md
?? 11_SCRIPTS/auto_task.py

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
Smoke tests: 20
Release checks: 16
Checkpoints: 7

## Catálogo de comandos
01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md

## Último task-status
07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md

## Produção
Nada alterado.

## Próximo passo seguro
Criar `auto-task` em modo preparação apenas, sem editar projeto real.
