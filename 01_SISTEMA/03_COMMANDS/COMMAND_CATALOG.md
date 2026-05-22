# Command Catalog — JARVIS Theo Padilha AI Worker

## Status real
Catálogo local de comandos. Não é produção.

## Saúde / validação
- `./jarvis command-audit`
- `./jarvis safety-gate`
- `./jarvis secret-scan`
- `./jarvis storage-health`
- `./jarvis self-test`
- `./jarvis quality-gate`
- `./jarvis smoke-test`
- `./jarvis release-check`

## Status / checkpoint
- `./jarvis snapshot-prep-core`
- `./jarvis pending-artifacts`
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
- `./jarvis local-exec-plan "tarefa"`
- `./jarvis local-exec-ready "tarefa"`
- `./jarvis local-exec-handoff "tarefa"`
- `./jarvis local-exec-review arquivo.md`
- `./jarvis local-exec-handoff-latest`
- `./jarvis local-exec-ready-latest`
- `./jarvis local-exec-plan-latest`
- `./jarvis readonly-run "tarefa"`
- `./jarvis readonly-run-latest`
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

## Fluxo pós auto-task

Depois de `./jarvis auto-task "tarefa"`:

1. `./jarvis pending-artifacts`
2. `./jarvis secret-scan`
3. `git add ...`
4. `git commit -m "..."` 
5. `./jarvis release-check`
6. `./jarvis safety-gate`

Status real: pending-artifacts só inspeciona. Não altera nada.

## Auto-task + pending-artifacts

`./jarvis auto-task "tarefa"` agora roda `pending-artifacts` no final.

Isso não versiona nada sozinho. Só mostra o que foi gerado para o operador decidir o que commitar.

Fluxo correto:
1. `./jarvis auto-task "tarefa"`
2. revisar saída do `pending-artifacts`
3. `./jarvis secret-scan`
4. `git add ...`
5. `git commit -m "..."`
6. `./jarvis release-check`
7. `./jarvis safety-gate`

## Snapshot limpo

`./jarvis snapshot-prep-core` cria snapshot em pasta temporária primeiro e usa no-report quando aplicável.

Objetivo: evitar que snapshots gerem artefatos surpresa e quebrem o quality-gate.

## READONLY_RUN

`./jarvis readonly-run "tarefa"` faz inspeção local segura de um projeto detectado no Mac.

Ele pode:
- selecionar projeto provável;
- ler git status/branch/log;
- listar estrutura root;
- ler README;
- ler package.json;
- detectar `.env` sem abrir conteúdo.

Ele não pode:
- editar arquivos;
- rodar build;
- instalar dependências;
- abrir `.env`;
- fazer push/deploy;
- mexer em VPS, n8n ou produção.

Status real: inspeção local read-only.

## READONLY_RUN sanitiza nomes secret-like

`readonly-run` não deve salvar nomes nem conteúdos de `.env*`, chaves, tokens ou arquivos de credenciais.

Quando detectar algo secret-like, deve registrar apenas contagem/placeholder.

## READONLY_RUN no-report

`env JARVIS_NO_REPORT=1 ./jarvis readonly-run "tarefa"` executa inspeção read-only sem gravar novo relatório.

Uso correto:
- smoke-test;
- release-check;
- snapshots;
- validação rápida sem gerar artefatos.

## Release-check compila todos os scripts

`./jarvis release-check` agora compila todos os arquivos `.py` em `11_SCRIPTS/`.

Objetivo: evitar que um comando novo seja criado sem validação de sintaxe.

## Release-check inclui command-audit

`./jarvis release-check` agora roda `command-audit` diretamente.

Objetivo: detectar drift entre core, help, catalog e smoke antes de considerar a release válida.

## Safety-gate inclui command-audit

`./jarvis safety-gate` agora roda:
- secret-scan;
- storage-health;
- command-audit;
- quality-gate.

Objetivo: impedir seguir com comandos críticos fora de sincronia entre core, help, catalog e smoke.

## LOCAL_EXEC Plan

`./jarvis local-exec-plan "tarefa"` prepara plano de execução local sem editar projeto.

Ele detecta projeto provável, branch, git status, package manager e comandos sugeridos. Não roda install/build/test, não edita arquivos e não toca produção.

## LOCAL_EXEC Ready Check

`./jarvis local-exec-ready "tarefa"` checa se uma execução local pode começar.

Ele não edita projeto. Ele verifica branch, Git status, package manager provável, blockers e warnings.

## LOCAL_EXEC Handoff

`./jarvis local-exec-handoff "tarefa"` gera pacote curto para Claude/VS Code executar edição local em branch segura.

Status real: cria handoff. Não edita projeto, não faz build, não faz push, não faz deploy.

## Cockpit detecta diretórios de handoff

`./jarvis cockpit` deve mostrar o último pacote `local-exec-handoff`, mesmo sendo diretório e não arquivo `.md`.

Correção: usar detecção de path mais recente para handoffs.

## LOCAL_EXEC Review

`./jarvis local-exec-review arquivo.md` revisa a saída de Claude/VS Code depois de uma execução local.

Status real: cria revisão. Não aplica patch, não commita, não faz push e não faz deploy.

## LOCAL_EXEC Review negation-aware

`local-exec-review` deve diferenciar risco real de frase negada.

Exemplo:
- “Fiz push” bloqueia.
- “Não fiz push” não bloqueia.
- “Rodei deploy” bloqueia.
- “Não fiz deploy” não bloqueia.
