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
- `./jarvis visual-cockpit`
- `./jarvis claude-mission --jarvis-core --type audit "tarefa"`
- `./jarvis claude-mission --project ALIAS --type audit "tarefa"`
- `./jarvis claude-mission-latest`
- `./jarvis operator-workbench`
- `./jarvis operator-workbench --jarvis-core`
- `./jarvis operator-workbench --project ALIAS`
- `./jarvis workbench` (alias de operator-workbench)
- `./jarvis execution-modes`
- `./jarvis report`
- `./jarvis summary`
- `./jarvis overview`
- `./jarvis task-status`
- `./jarvis checkpoint`

## Project max-machine (v1.1)

Trabalhos repetidos por projeto agora têm comandos diretos. Cada um respeita: sem deploy, sem push, sem PR, sem merge, sem .env, sem migrations, sem secrets.

- `./jarvis doctor --project ALIAS` — diagnóstico read-only do projeto (branch, dirty tree, package manager, scripts, tooling de test, .env warning).
- `./jarvis qa-sprint --project ALIAS` — gera mission Claude focada em QA sprint local (inspeção + validação + patches pequenos com orçamento apertado).
- `./jarvis goal-sprint --project ALIAS --goal "..."` — gera mission orientada a objetivo com Definition of Done mensurável e loop iterativo de patches seguros.
- `./jarvis browser-qa --project ALIAS` — gera mission de QA de UI: usa Playwright/Cypress se já instalados; senão recomenda Vitest+RTL para componentes alterados. NÃO instala ferramentas.
- `./jarvis final-gate --project ALIAS` — gera mission que decide safe/not-safe para push/PR/deploy a partir de checagens objetivas (git/typecheck/tests/diff). NÃO executa push/PR/deploy.

Todas as missões salvam pacote em `05_EXECUCAO/21_CLAUDE_MISSIONS/<TS>_project-ALIAS_<modo>_<slug>/` e podem ser revisadas via `./jarvis claude-mission-latest`.

A pasta `05_EXECUCAO/21_CLAUDE_MISSIONS/` é gitignored. Mission packs são voláteis por design: gerá-los não suja a árvore, então `./jarvis safety-gate` continua verde. Se quiser persistir um pack específico, use `git add -f <pack>`.

## Project max-machine (v1.2 — daily cockpit)

- `./jarvis project-status --project ALIAS` — status compacto de 1 tela (path/branch/dirty/recent/pm/scripts/last mission/next).
- `./jarvis project-cockpit --project ALIAS` — versão completa: status + última missão + memória registrada + próximas ações + próximo passo seguro com comandos exatos.
- `./jarvis mission-open-latest [--project ALIAS]` — imprime path absoluto do prompt mais recente em uma linha. Útil para pipe: `cat "$(./jarvis mission-open-latest)" | pbcopy`.

## Project memory (v1.3 — fim da amnésia)

JARVIS deixa de ser amnésico entre sessões. Memória mora em `04_PROJETOS/<ALIAS_UPPER>/PROJECT_STATUS.md` (cumulativa, append-only) e `NEXT_ACTIONS.md` (intenção humana — JARVIS **nunca** escreve aí).

- `./jarvis project-memory --project ALIAS` — read-only. Imprime memória atual: estado registrado, próximas ações, última missão, recent commits, avisos. Output redatado (secret_scan patterns).
- `./jarvis project-memory-update --project ALIAS --from-git [--dry-run|--apply]` — gera entrada de debrief a partir do estado Git do projeto-alvo. Default é preview; só grava com `--apply`. Append-only com marcador `<!-- jarvis-memory-entry -->`. Refuse de gravar se padrão de secret cru sobreviver à redação.
- `./jarvis project-memory-update --project ALIAS --from-file PATH [--dry-run|--apply]` — parser regex-only (sem LLM) de output de Claude/agent. Extrai seções STATUS REAL / WHAT CHANGED / FILES CHANGED / VALIDATION RESULTS / RISKS / SAFE TO COMMIT. Redação antes da escrita.

### Loop seguro de uso diário

```
./jarvis project-cockpit --project oficina
./jarvis qa-sprint --project oficina           # gera missão Claude
cat "$(./jarvis mission-open-latest)" | pbcopy # cola no Claude Code
# (Claude executa; salva resposta final em /tmp/claude-out.md)
./jarvis project-memory-update --project oficina --from-file /tmp/claude-out.md --dry-run
./jarvis project-memory-update --project oficina --from-file /tmp/claude-out.md --apply
./jarvis project-cockpit --project oficina     # cockpit agora mostra debrief
```

Garantias:
- JARVIS **nunca** edita o projeto-alvo (Oficina/etc).
- Mission packs em `21_CLAUDE_MISSIONS/**` são gitignored — gerar missão não suja `safety-gate`.
- Memory writes só atingem `04_PROJETOS/<ALIAS_UPPER>/PROJECT_STATUS.md` neste repo.

## Self-evolution (v1.4 — JARVIS usa Claude Code como motor de execução)

JARVIS agora prepara, organiza, lembra e valida missões Claude **para si mesmo**, sem API paga. Workflow oficial:

- `./jarvis self-cockpit` — primeiro comando do dia. Mostra estado JARVIS + última missão + memória + próximo passo.
- `./jarvis self-status` — versão compacta.
- `./jarvis self-next` — só o próximo comando seguro.
- `./jarvis self-evolve --goal "..." [--copy]` — gera **mission pack** com template SELF-EVOLVE (12 seções: MISSION/CURRENT STATE/TRUE NORTH/HARD RULES/INSPECT/IMPROVE/NOT BUILD/PHASES/VALIDATION/COMMIT/SELF-AUDIT/RETURN). `--copy` joga o prompt no clipboard via `pbcopy`.
- `./jarvis claude-launch --project ALIAS [--copy] [--print-only]` — imprime o bloco exato `cd PATH; claude` + instrução de paste. **NÃO executa Claude**.
- `./jarvis claude-copy-latest [--project ALIAS]` — copia o último prompt no clipboard.
- `./jarvis claude-save-report-template [--project ALIAS]` — imprime template bash para capturar resposta do Claude em `/tmp/jarvis-claude-out.md` e alimentar de volta no debrief.
- `./jarvis self-debrief --from-git|--from-file PATH [--dry-run|--apply]` — wrapper de `project-memory-update --project jarvis-core`. Append-only em `04_PROJETOS/JARVIS_CORE/PROJECT_STATUS.md`.

### Daily loop (evoluir JARVIS sem API paga)

```
./jarvis self-cockpit
./jarvis self-evolve --goal "..." --copy
cd ~/Theo/JARVIS/VAMOO_JARVIS_LAB_v0_2_PRONTO
claude
# (cole a missão; Claude executa)
cat > /tmp/jarvis-claude-out.md
# (cole o relatório final; Ctrl+D)
./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --dry-run
./jarvis self-debrief --from-file /tmp/jarvis-claude-out.md --apply
./jarvis self-cockpit
env JARVIS_NO_REPORT=1 ./jarvis safety-gate
env JARVIS_NO_REPORT=1 ./jarvis smoke-test
```

Garantias adicionais:
- Sem API Anthropic/OpenAI paga.
- JARVIS nunca executa `claude` em background.
- JARVIS imprime sempre o comando exato; Theo decide quando rodar.
- Mission packs continuam gitignored; gerar missão não suja gates.

## Doctrine check (v1.4.1)

- `./jarvis doctrine-check` — verifica drift entre AGENTS.md, COMMAND_CATALOG, `./jarvis help`, PROJECT_REGISTRY e os HARD_RULES dos mission templates. Falha (exit 1) se algum slot crítico estiver fora de sync. Read-only, nada editado.

### Exemplos

```
./jarvis doctor --project oficina
./jarvis doctor --project jarvis-core
./jarvis qa-sprint --project oficina
./jarvis goal-sprint --project oficina --goal "fechar QA local com segurança antes de PR"
./jarvis browser-qa --project oficina
./jarvis final-gate --project oficina
./jarvis claude-mission-latest
```

Status real: pacotes locais. Não editam projeto, não fazem build, não fazem commit, não fazem push, não fazem deploy.

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
- `./jarvis local-exec-flow "tarefa"`
- `./jarvis local-exec-session "tarefa"`
- `./jarvis local-exec-session-latest`
- `./jarvis local-exec-flow-latest`
- `./jarvis local-exec-review-latest`
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

## LOCAL_EXEC Flow

`./jarvis local-exec-flow "tarefa"` mostra o fluxo seguro completo:
PREPARE → READONLY → PLAN → READY → HANDOFF → REVIEW.

Status real: guia operacional. Não edita projeto, não faz build, não faz commit, não faz push e não faz deploy.

## LOCAL_EXEC Session

`./jarvis local-exec-session "tarefa"` prepara em um comando:
flow, readonly-run, local-exec-plan, local-exec-ready e local-exec-handoff.

Status real: cria artefatos de preparação. Não edita projeto, não faz build, não commita, não faz push e não faz deploy.

## Project Resolve

`./jarvis project-resolve` lista aliases disponíveis.

`./jarvis project-resolve oficina` valida o alias e mostra caminho, branch, Git status e próximo passo seguro.

Status real: não edita projeto, não faz build, não faz push e não faz deploy.

## LOCAL_EXEC Session com Project Lock

`./jarvis local-exec-session --project oficina "tarefa"` prepara sessão travada no projeto informado.

Status real: prepara flow/read-only/plan/ready/handoff. Não edita projeto, não faz build, não faz push e não faz deploy.

## Project Menu

`./jarvis project-menu` mostra os projetos disponíveis e opções práticas.

`./jarvis project-menu oficina` mostra o estado do projeto e comandos recomendados.

Status real: menu local. Não edita projeto, não faz build, não faz push e não faz deploy.

## Next Step

`./jarvis next-step` mostra o estado atual e opções humanas do próximo passo.

`./jarvis next-step oficina` mostra comandos seguros para o projeto escolhido.

Status real: orientação local. Não edita projeto, não faz build, não faz push e não faz deploy.

## Future Tools Radar

`./jarvis future-tools-radar` imprime o radar de ferramentas futuras.

Status real: leitura local. Não instala, não configura, não conecta API, não cria conta e não altera produção.

## Run Safe

`./jarvis run-safe --project oficina "tarefa"` orquestra project-resolve, next-step, local-exec-session e handoff.

Status real: preparação local guiada. Não aplica patch, não roda build/test real como decisão final, não faz commit/push/PR e não faz deploy.

## Operator Workbench

`./jarvis operator-workbench` mostra o painel humano do operador local. Resume status do Git, gates recentes, última Claude mission, último project lock, action menu numerado, comandos exatos, quando usar/não usar Claude, bloqueios e travas.

Modos:
- `./jarvis operator-workbench`           geral
- `./jarvis operator-workbench --jarvis-core`  modo repositório JARVIS
- `./jarvis operator-workbench --project ALIAS` modo projeto travado
- `./jarvis workbench`                    alias de operator-workbench

Saída local em `07_RELATORIOS/02_TECNICOS/ULTIMO_OPERATOR_WORKBENCH.md` (gitignored). Com `JARVIS_NO_REPORT=1` o relatório não é escrito.

Status real: leitura local. Workbench não executa gates, não edita projeto, não commita, não faz push, não faz deploy e não toca VPS/n8n/produção.

## Agent OS — natural-language interface

O "Agent OS" do JARVIS deixa Theo digitar pedidos em linguagem natural
e converte (localmente, com regex + registry — **sem LLM, sem API
paga**) para o próximo comando seguro.

### `./jarvis ask "pedido"`
Router puro: classifica intent, detecta alias de projeto e imprime o
próximo comando seguro. Não delega por padrão. Flags:
`--project ALIAS`, `--dry-run`, `--copy`, `--no-copy`, `--explain`.

Exemplos:
- `./jarvis ask "o que faço agora"` → `./jarvis self-cockpit`
- `./jarvis ask "evolui o jarvis para reduzir trabalho manual"` → `./jarvis self-evolve --goal "..."`
- `./jarvis ask "abre oficina e corrige bug da agenda"` → `./jarvis goal-sprint --project oficina --goal "..."`
- `./jarvis ask "coloca amanhã revisar LS na agenda"` → `./jarvis agenda-add "..."`
- `./jarvis ask "quero criar workflow n8n de agendamento whatsapp"` → `./jarvis blueprint --type n8n --goal "..."`

### `./jarvis go "pedido"`
Power-wrapper: roda `ask --copy` (delega ao sub-comando) e imprime, em
seguida, o bloco de instruções para Theo abrir Claude manualmente,
salvar o relatório final em `/tmp/jarvis-claude-out.md` e rodar
`self-debrief`. Não executa Claude.

### Inbox / agenda locais (append-only)
- `./jarvis capture "ideia"` → 05_EXECUCAO/30_INBOX/INBOX.md
- `./jarvis inbox`
- `./jarvis agenda-add "amanhã revisar LS"` → 05_EXECUCAO/31_AGENDA/AGENDA.md
- `./jarvis agenda`

Refusam input com padrão secret-like. Sem Google Calendar, sem reminders, sem APIs externas.

### `./jarvis blueprint --type <T> --goal "..."`
Gera blueprint local (5 arquivos) em `05_EXECUCAO/40_BLUEPRINTS/<ts>_<type>_<slug>/`.
Tipos: `n8n`, `app`, `automation`, `research`.
Sempre local — nenhum n8n real, nenhuma credencial, nenhum deploy.

Status real: todo este surface é apenas roteamento e geração local — Sem API Anthropic/OpenAI, sem rede, sem produção.

## Agent OS — Sprint 2 (project-open, plan, limits, ask-log)

Sprint 2 adicionou a camada de **abrir projeto**, **planejar a tarefa**,
**explicar limites do robô** e **aprender com requests não classificados**.
Também consertou propagação de exit code dos wrappers novos: `./jarvis`
agora falha de verdade quando o script Python recusa (ex.: `self-debrief
--apply` em relatório fraco).

### `./jarvis project-open --project ALIAS [--print-only|--copy-cd|--code]`
Imprime o bloco seguro para abrir o projeto:
```
cd <PATH>
git status --short
git branch --show-current
claude
./jarvis project-cockpit --project ALIAS
```
Modos:
- `--print-only` (default): só imprime.
- `--copy-cd`: copia `cd PATH` para o clipboard (pbcopy).
- `--code`: sugere `code PATH` se a CLI do VS Code existir (não executa).

Nunca edita arquivos, nunca executa build/test, nunca roda Claude.
`ask "abre <alias>"` roteia automaticamente para esse comando.

### `./jarvis plan "pedido" [--save]`
Gera **plano de execução local** de uma frase. Diferente de blueprint
(que cria pacote de spec), plan responde "o que fazer JÁ sobre ISSO,
e o que é seguro". Saída inclui intent, projeto, safety level, próximo
comando, missão Claude sugerida, validação esperada e o que JARVIS
**não vai** fazer. `--save` grava em `05_EXECUCAO/33_PLANS/`.

### `./jarvis limits`
Imprime a fronteira do robô em uma tela: o que JARVIS pode, o que ainda
não faz, o que requer Claude, o que requer humano, o que é proibido.
Substitui ter que perguntar ao ChatGPT "esse comando é seguro?".

### `./jarvis ask-log`
Mostra as últimas requests cuja intent ficou `unclear` (gravadas
automaticamente em `05_EXECUCAO/32_ASK_LEARNING/UNCLEAR_REQUESTS.md`).
Append-only, secret-safe (requests com aparência de segredo são
recusadas antes de gravar). Usado para tunar os patterns em
`11_SCRIPTS/ask_router.py` sem precisar de LLM.

### Exit-code propagation
Wrappers novos (`ask`, `go`, `capture`, `inbox`, `agenda-add`, `agenda`,
`blueprint`, `project-open`, `plan`, `limits`, `ask-log`, `self-debrief`,
`project-memory-update`) agora propagam o `returncode` do Python via
`sys.exit`. Recusas (ex.: `--apply` em relatório fraco) realmente fazem
o `./jarvis` retornar não-zero.

Status real: todas essas adições são leitura/append-only locais — Sem API Anthropic/OpenAI, sem produção, sem deploy.
