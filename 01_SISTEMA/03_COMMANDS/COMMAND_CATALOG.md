# Command Catalog — JARVIS Theo Padilha AI Worker

## Status real
Catálogo local de comandos. Não é produção.

## Saúde / validação
- `./jarvis safety-gate`
- `./jarvis secret-scan`
- `./jarvis storage-health`
- `./jarvis self-test`
- `./jarvis quality-gate`
- `./jarvis smoke-test`
- `./jarvis release-check`

## Status / checkpoint
- `./jarvis report-policy`
- `./jarvis cockpit`
- `./jarvis execution-modes`
- `./jarvis report`
- `./jarvis summary`
- `./jarvis overview`
- `./jarvis task-status`
- `./jarvis checkpoint`

## Tasks
- `./jarvis intake "pedido"`
- `./jarvis next`
- `./jarvis close-task "texto"`
- `./jarvis backlog`

## Projetos do Mac
- `./jarvis workspace-scan ~/VAMOO_PROJETOS`
- `./jarvis project-index ~/VAMOO_PROJETOS`
- `./jarvis project-select "tarefa"`
- `./jarvis workspace-check /caminho/do/projeto`

## Execução assistida
- `./jarvis mode-plan "tarefa"`
- `./jarvis task-brief "tarefa"`
- `./jarvis task-brief-latest`
- `./jarvis auto-task "tarefa"`
- `./jarvis auto-task-latest`
- `./jarvis task-start "tarefa"`
- `./jarvis executor-handoff "tarefa"`
- `./jarvis handoff-latest`
- `./jarvis handoff-print`
- `./jarvis review-outputs`
- `./jarvis review-output-v2 arquivo.md`
- `./jarvis review-output-latest`
- `./jarvis review-output-index`

## Prompts / executores
- `./jarvis prompt-pack "pedido"`
- `./jarvis tools`
- `./jarvis profiles`

## Fluxo recomendado para tarefa real
0. `./jarvis overview`
1. `./jarvis project-index ~/VAMOO_PROJETOS`
2. `./jarvis project-select "sua tarefa"`
3. `./jarvis task-brief "sua tarefa"`
4. `./jarvis task-start "sua tarefa"`
5. `./jarvis executor-handoff "sua tarefa"`
6. `./jarvis handoff-print`
7. Usar Claude/ChatGPT/Gemini manualmente
8. Salvar output em `00_COLE_AQUI/03_OUTPUTS_CLAUDE_CHATGPT/`
9. `./jarvis review-outputs`
10. `./jarvis quality-gate`

## Regra
Plano, prompt, handoff e task-start não significam execução feita. Produção só com autorização.

## Atalho de preparação completa
- `./jarvis auto-task "sua tarefa"` roda a preparação local completa: índice, seleção, briefing, task-start, handoff, print, status e release-check.
- `./jarvis auto-task-latest` imprime o último relatório sem criar novo run.

Status real: `auto-task` prepara e valida localmente; não edita projeto real e não significa produção.

## Direção futura — execução forte

JARVIS deve evoluir para operar:
- projetos locais;
- VPS;
- Docker/Portainer/Traefik;
- n8n workflows;
- credenciais locais protegidas;
- deploys e produção somente em modo autorizado.

Regra: segredo pode ser usado localmente quando autorizado, mas não pode ser salvo em Git, relatório, chat ou prompt externo.

## Release forte

- `./jarvis safety-gate` roda secret-scan, storage-health e quality-gate.
- `./jarvis release-check` agora inclui compile, secret-scan, storage-health, quality-gate e smoke-test com validação de conteúdo.

Status real: validação local forte. Não altera projeto real, VPS, n8n ou produção.

## Planejamento por modo

- `./jarvis mode-plan "tarefa"` classifica a tarefa em PREPARE, READONLY, LOCAL_EXEC, INFRA_EXEC ou PRODUCTION_ARMED.
- Nenhuma execução forte deve acontecer sem modo declarado.
- O modo define o próximo comando seguro e os bloqueios.

Status real: classificação local. Não executa projeto real.

## Auto-task com mode-plan

`./jarvis auto-task "tarefa"` agora começa executando `mode-plan` em modo no-report.

Isso garante que a preparação já declare se a tarefa parece PREPARE, READONLY, LOCAL_EXEC, INFRA_EXEC ou PRODUCTION_ARMED antes de criar handoff e próximos passos.

Status real: continua sendo preparação local. Não edita projeto real.

## Auto-task preparation-only

`./jarvis auto-task "tarefa"` prepara a tarefa e gera artefatos locais. Ele não deve rodar `release-check` internamente porque os próprios artefatos deixam o Git sujo.

Fluxo correto:
1. rodar auto-task;
2. revisar/trackear artefatos gerados;
3. commitar;
4. rodar release-check;
5. rodar safety-gate.

Status real: auto-task prepara. Não valida release sozinho.
