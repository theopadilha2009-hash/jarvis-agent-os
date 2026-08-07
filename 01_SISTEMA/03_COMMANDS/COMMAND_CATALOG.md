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

## Decision log local (append-only)

- `./jarvis decision-add "escolha" [--project ALIAS] [--context "..."] [--reason "..."] [--dry-run]` — registra uma decisão operacional; `JARVIS_NO_REPORT=1` força preview.
- `./jarvis decision-list [--project ALIAS] [--limit N]` — lista decisões recentes sem editar estado.
- `./jarvis decision-show latest|ID` — exibe uma decisão por ID completo/prefixo ou a mais recente.

Storage: `05_EXECUCAO/63_DECISIONS/decisions.jsonl` (gitignored, JSONL append-only). Entradas com aparência de segredo são recusadas antes de qualquer eco ou gravação. O dashboard `./jarvis daily` mostra as três decisões seguras mais recentes.

## Utilidades pessoais locais

- `./jarvis web [--no-open|--check]` — inicia o cockpit visual, abre o navegador e conecta conversa/voz ao worker local; usa OpenRouter quando `OPENROUTER_API_KEY` estiver disponível no processo.
- `./jarvis assistant-doctor` — verifica se o macOS oferece captura, conversão, voz, abertura e clipboard.
- `./jarvis screen-capture [--interactive] [--output PATH] [--dry-run]` — captura somente quando chamado; o padrão salva em `05_EXECUCAO/64_PERSONAL_TOOLS/screenshots/`.
- `./jarvis image-to-pdf IMAGEM --dry-run` — mostra o plano, mas recusa gerar PDF enquanto `AGENTS.md` mantiver esse formato bloqueado.
- `./jarvis image-convert IMAGEM --to png|jpg|tiff [--output PATH] [--dry-run]` — usa `sips`, preserva o original e recusa sobrescrever o destino.
- `./jarvis speak "texto" [--voice VOZ] [--rate N] [--output audio.aiff] [--dry-run]` — fala ou gera AIFF localmente com `say`.
- `./jarvis message-draft --phone DDI_DDD_NUMERO "texto" [--open|--copy|--dry-run]` — prepara WhatsApp; nunca clica em Enviar.
- `./jarvis message-send --phone DDI_DDD_NUMERO "texto" [--dry-run]` — envia explicitamente pelo app Mensagens do macOS; requer conta iMessage ativa.
- `./jarvis memory-save "texto" [--kind learning|decision|preference] [--dry-run]` — grava memória Markdown local em `03_MEMORIA/`, pronta para aparecer na constelação e ser versionada.
- `./jarvis storage-scan [PASTA] [--top N] [--min-mb N]` — inventário read-only dos maiores arquivos; não lê conteúdo e não move/apaga nada.
- `./jarvis system-memory [--cleanup-jarvis] [--dry-run]` — mede pressão de memória, lista os processos mais pesados e pode encerrar somente previews/servidores temporários do próprio JARVIS; preserva Chrome, Claude, Orca, Codex e demais apps pessoais.
- `./jarvis computer list|inspect|open|close [APP] [--dry-run]` — lista/observa apps pelo Computer Use do Orca e abre ou fecha um aplicativo sob pedido explícito; Finder e Orca são preservados para manter desktop e worker ativos.
- `./jarvis computer-worker [--once|--watch|--install|--status|--uninstall] [--dry-run]` — consome a fila privada do Supabase e executa somente abrir/fechar app, captura, análise de Downloads, diagnóstico de RAM e envio explícito pelo Mensagens; `--install` mantém heartbeat leve via LaunchAgent sem armazenar chaves no plist ou aceitar shell/caminhos arbitrários.
- `./jarvis self-edit "melhoria" [--dry-run] [--publish]` — cria branch e worktree exclusivos, chama o Codex CLI para editar os próprios scripts, exige diff real, roda `bash -n`, `diff --check`, `py_compile` aplicável, `command-audit` e `safety-gate`. Sem `--publish`, termina no checkpoint local. Com `--publish` explicitamente autorizado, valida os alvos fixos, envia somente ao `jarvis-origin`, abre e mescla PR em `theopadilha2009-hash/jarvis-agent-os/main`, faz deploy somente no projeto Vercel `jarvis-agent-os`, verifica `/status`, ativa o commit localmente e reinicia o worker.
- `./jarvis files-triage [PASTA] [--limit N]` — classifica arquivos soltos por extensão e mostra origem → destino; não possui `--apply`.

Todas recusam texto com aparência de segredo. Processos nativos são executados por lista de argumentos, sem shell. Somente `message-send`, chamado de forma explícita e com destino/texto completos, envia uma mensagem; organização e limpeza continuam sem aplicação automática.

O worker principal também reconhece essas intenções: `./jarvis do "tirar um print" --dry-run`, `./jarvis do "converter foto.heic para jpg" --dry-run`, `./jarvis do 'ler em voz alta "hora de focar"' --dry-run`, `./jarvis do 'mandar mensagem para 5511... "texto"' --dry-run`, `./jarvis do "guarda que prefiro respostas curtas na memória" --dry-run` e `./jarvis do "arquivos grandes em downloads" --dry-run`.

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

## Agent OS — Sprint 3 (task queue, run logs, capabilities, project intel)

Sprint 3 adicionou **memória operacional** (tarefas + logs de execução),
**fronteira explícita** (capabilities) e **inteligência de projeto**
(project-intel). `go` ficou mais forte: cria run package gitignored,
sugere project-intel, escolhe o debrief correto (self vs project) e
imprime gates.

### Task queue (`task-add`, `task-list`, `task-next`, `task-show`, `task-done`, `task-block`)
JSONL append-only em `05_EXECUCAO/34_TASKS/tasks.jsonl` (gitignored).
Cada comando é um evento; o estado é reconstruído lendo a lista.
- `task-add "texto" [--dry-run]` — cria tarefa pending. Refuse secret-shaped.
- `task-list` — pending + blocked + done.
- `task-next` — top pending + sugestão de `./jarvis go "..."`.
- `task-show ID` — todos eventos.
- `task-done ID [--note]` — append done.
- `task-block ID --reason "..."` — append blocked.

Não tem banco, não tem web UI, não tem cron, não tem reminders.

### Run logs (`run-list`, `run-show latest|ID`, `run-latest`)
Cada `./jarvis go` cria pasta `05_EXECUCAO/35_RUNS/<ts>_<slug>/`
(gitignored) com 6 markdowns: REQUEST / INTERPRETATION / NEXT_COMMAND
/ CLAUDE_LAUNCH / DEBRIEF_INSTRUCTIONS / STATUS_REAL. Suprimível com
`--dry-run`, `--no-run-log` ou `JARVIS_NO_REPORT=1`.

### Capabilities (`capabilities`, `capability-check NAME`, `capability-plan NAME`)
Registry em `01_SISTEMA/06_CAPABILITIES/CAPABILITY_REGISTRY.json` com
quatro grupos: **available** (JARVIS faz agora), **manual** (Theo
executa o passo final), **blocked** (hard rule, nunca), **future_adapter**
(possível um dia, hoje só alternativa local + plano).

`./jarvis ask "capacidade google calendar"` roteia para
`./jarvis capability-check google_calendar` automaticamente.
`./jarvis ask "quais limites"` roteia para `./jarvis limits`.

### Project intel (`project-intel --project ALIAS`)
Inspeção read-only do projeto: branch + dirty + package manager
(bun/pnpm/yarn/npm) + scripts (dev/build/test/lint/typecheck) +
framework hints (next/vite/react/n8n) + test tools + migrations
(supabase/prisma/drizzle) + .env presence (NUNCA valores) +
comandos recomendados (não executados).

### `go` mais forte (Sprint 3)
- cria run package por default (suprimível com `--dry-run` / `--no-run-log` / `JARVIS_NO_REPORT=1`)
- sugere `./jarvis project-intel --project A` quando detecta projeto
- escolhe `self-debrief` (jarvis-core) ou `project-memory-update --project A` (outros)
- imprime bloco de gates (safety-gate / smoke-test / doctrine-check)
- termina com "O que JARVIS fez / NÃO fez"

### Referência rápida (para command-audit)

```
./jarvis task-add "tarefa" [--dry-run]
./jarvis task-list
./jarvis task-next
./jarvis task-show ID
./jarvis task-done ID [--note "..."]
./jarvis task-block ID --reason "..."
./jarvis run-list
./jarvis run-show latest
./jarvis run-show <ID>
./jarvis run-latest
./jarvis capabilities
./jarvis capability-check NAME
./jarvis capability-plan NAME
./jarvis project-intel --project ALIAS
```

Status real: todas as adições deste sprint são leitura local + append-only — Sem API Anthropic/OpenAI, sem rede, sem produção.

## Agent OS — Sprint 4 (resume, work lifecycle, report intake)

Sprint 4 transforma comandos isolados num **lifecycle**: `resume` é o
primeiro comando do dia/após interrupção; `work-start` inicia um ciclo
que conecta task queue + run log + missão Claude + debrief; `report-check`
e `report-apply` validam o relatório final do Claude e roteiam para o
writer correto (self-debrief vs project-memory-update) sem Theo
precisar lembrar o alias.

### Resume / lifecycle
- `./jarvis resume` — pickup: imprime work-status + work-next + último run + top task. **Primeiro comando após interrupção.**
- `./jarvis work-start "pedido"` — classifica, cria task, cria run package, gera missão (via go), grava session em `36_WORK_SESSIONS/current.json`.
- `./jarvis work-status` — estado atual da sessão (intent, project, status, next).
- `./jarvis work-next` — máquina de estados determinística: imprime o ÚNICO próximo comando seguro.
- `./jarvis work-block --reason "..."` — marca sessão como blocked.
- `./jarvis work-close [--force]` — fecha sessão (espera `gates_passed` ou `blocked` por default).

### Report intake
- `./jarvis report-template` — imprime o `cat > /tmp/...` exato para o projeto da sessão atual.
- `./jarvis report-status` — presença + qualidade do relatório esperado.
- `./jarvis report-check --file PATH` — valida headings + quality. Não grava nada.
- `./jarvis report-apply --file PATH [--force-weak]` — delega para `self-debrief --apply` (jarvis-core) ou `project-memory-update --project A --apply` (outros). Refusa weak por default.

### Storage runtime (gitignored)
- `05_EXECUCAO/36_WORK_SESSIONS/current.json` — sessão atual (mutável).
- `05_EXECUCAO/36_WORK_SESSIONS/events.jsonl` — append-only audit trail.
- `.gitkeep` permanece versionado.

### Referência rápida (para command-audit)

```
./jarvis resume
./jarvis work-start "pedido"
./jarvis work-status
./jarvis work-next
./jarvis work-block --reason "..."
./jarvis work-close
./jarvis report-template
./jarvis report-status
./jarvis report-check --file /tmp/jarvis-claude-out.md
./jarvis report-apply --file /tmp/jarvis-claude-out.md
```

Status real: lifecycle inteiramente local. Sem Claude em background, sem API paga, sem produção.

## Agent OS — Sprint 5 (lifecycle reliability, gate capture, cleanup, project override)

Sprint 5 fecha as lacunas confiabilidade do Sprint 4:

- **--project override** em `report-check` e `report-apply` (valida contra
  PROJECT_REGISTRY). Resolve a ambiguidade de "qual projeto vai receber o
  debrief?" sem depender só da sessão atual.
- **task-add --print-id** + work-start captura o **TASK_ID real** (não
  mais string simbólica). Falha clara em `latest_task_id=null` se a
  criação da task falhar.
- **gate-run / gate-status** roda safety+smoke+doctrine em sequência,
  captura exit code e linha "Resultado:" de cada gate, grava em
  `05_EXECUCAO/37_GATES/latest.json` (gitignored), e **avança a work
  session** para `gates_passed` (ou `gates_pending` se falhar). Não é
  fake autonomy: são os mesmos gates que Theo rodaria à mão.
- **work-next** agora aponta para `./jarvis gate-run` depois de
  `debrief_applied` — um único comando em vez de três.
- **report-apply** define `next_command = ./jarvis gate-run` após
  sucesso, fechando o loop.
- **run-prune --keep N --dry-run/--apply** limpa run packages antigos.
  Default dry-run. Safety check: nunca toca nada fora de `35_RUNS`.
  Nunca remove `.gitkeep`.
- **resume** mais conciso: 5 seções (Active Work / Latest Run / Top
  Task / Last Gates / Next Command) com indentação consistente.
  "produção: nada alterado" + "Claude não executado" no rodapé.

### Referência rápida (para command-audit)

```
./jarvis gate-run
./jarvis gate-status
./jarvis run-prune --keep 20 --dry-run
./jarvis run-prune --keep 20 --apply
./jarvis report-check --file PATH --project ALIAS
./jarvis report-apply --file PATH --project ALIAS [--force-weak]
./jarvis task-add "texto" --print-id
```

Storage runtime gitignored Sprint 5:
- `05_EXECUCAO/37_GATES/latest.json`
- `05_EXECUCAO/37_GATES/events.jsonl`

Status real: gate-run é local-only; nenhum push/PR/merge/deploy; sem produção.

## Agent OS — Sprint 6 (no-claude mode, system doctor, state repair, command shortcuts)

Sprint 6 fecha a lacuna "JARVIS depois do Claude": Theo precisa retomar
trabalho sem ChatGPT/Claude. Adiciona atalhos curtos, diagnóstico do
próprio JARVIS, reparo seguro de estado preso, modo offline, cheatsheet
e snapshot de handoff.

### Atalhos diários (não mudam comportamento — só sintaxe)

```
./jarvis now                # alias de resume — primeiro comando do dia
./jarvis start "pedido"     # alias de work-start
./jarvis next               # alias de work-next (substituiu o legado next_task)
./jarvis finish             # alias de work-close
./jarvis gates              # alias de gate-run
./jarvis health             # alias de doctor-agent
```

O comando legado `next_task()` (lê `02_TAREFAS/00_NOVAS`) continua
acessível por `./jarvis next-legacy` para manter retrocompatibilidade.

### `./jarvis doctor-agent [--full]`

Diagnóstico do próprio JARVIS (não dos projetos-alvo). Checa branch,
tree, arquivos core, runtime dirs, gitignore, registries, projetos,
gates, sessão atual, task queue, run logs, fixtures, command-audit e
doctrine-check. `--full` adiciona smoke-test completo.

Output em seções: Git / Files / Runtime State / Registries / Projects /
Gates / Commands / Result. Termina em `AGENT DOCTOR PASSOU` (exit 0) ou
`AGENT DOCTOR COM PENDÊNCIAS` (exit 1).

### `./jarvis state-status` / `state-reset` / `state-archive`

Inspeção e reparo seguro do runtime state:

```
./jarvis state-status              # leitura: sessão / tasks / gates / pacotes
./jarvis state-reset --dry-run     # mostra o que seria removido
./jarvis state-reset --apply       # remove apenas current.json
./jarvis state-archive --dry-run   # mostra cópia para archive/
./jarvis state-archive --apply     # cria cópia em 36_WORK_SESSIONS/archive/<ts>_current.json
```

Regras: default sempre `--dry-run`. `state-reset` só toca
`05_EXECUCAO/36_WORK_SESSIONS/current.json`. `events.jsonl`, tasks, runs,
gates, blueprints e plans NUNCA são removidos.

### `./jarvis no-claude "pedido"`

Modo offline: Claude indisponível, mas JARVIS ainda ajuda. Classifica o
pedido via `ask_router` (regex), detecta projeto, sugere blueprint type
(n8n/app/automation/research), enfileira task local (opcional) e gera
pacote em `05_EXECUCAO/38_NO_CLAUDE/<ts>_<slug>/`:

```
01_REQUEST.md
02_INTERPRETATION.md
03_MANUAL_PLAN.md
04_SAFE_COMMANDS.md
05_STATUS_REAL.md
```

Flags: `--dry-run` (só imprime, não grava), `--no-task` (não enfileira),
`--project ALIAS` (override de projeto). Hard rules iguais ao resto do
sistema: sem Claude, sem API paga, sem produção, sem ler .env.

### `./jarvis cheatsheet`

Uma tela com os comandos essenciais — `now`, `start`, `next`, `gates`,
`finish`, `no-claude`, `health`, `state-*`, `handoff-self`. Read-only.
Sem flags.

### `./jarvis handoff-self [--save]`

Snapshot textual do JARVIS para handoff humano (ChatGPT, time, etc.).
Inclui: branch, recent commits, work session atual, gates, top task,
último run, capabilities, comandos importantes, próximo comando
sugerido, hard rules. `--save` grava em
`05_EXECUCAO/39_HANDOFFS/<ts>_jarvis_handoff.md` (gitignored).

### Referência rápida (para command-audit)

```
./jarvis now
./jarvis start "evoluir o jarvis"
./jarvis next
./jarvis finish
./jarvis gates
./jarvis health
./jarvis doctor-agent
./jarvis doctor-agent --full
./jarvis state-status
./jarvis state-reset --dry-run
./jarvis state-reset --apply
./jarvis state-archive --dry-run
./jarvis state-archive --apply
./jarvis no-claude "workflow n8n de agendamento"
./jarvis no-claude "abre oficina" --dry-run
./jarvis cheatsheet
./jarvis handoff-self
./jarvis handoff-self --save
```

Storage runtime gitignored Sprint 6:
- `05_EXECUCAO/36_WORK_SESSIONS/archive/**` (só `.gitkeep` versionado)
- `05_EXECUCAO/38_NO_CLAUDE/**` (só `.gitkeep` versionado)
- `05_EXECUCAO/39_HANDOFFS/**` (só `.gitkeep` versionado)

Status real: comandos Sprint 6 são todos local-only; sem Claude, sem API
paga, sem deploy, sem push, sem alterar produção.

## Agent OS — Sprint 7 (release candidate, golden paths, daily dashboard, first-run check, acceptance)

Sprint 7 é a passada final de usabilidade antes de declarar release.
Faz uma escolha clara: nenhum novo comportamento perigoso, apenas três
coisas que estavam faltando:

- **um lugar pra olhar de manhã** (`./jarvis daily`)
- **um manual pra cada fluxo comum** (`./jarvis recipe-*`)
- **um snapshot pra dizer "ok, pronto"** (`./jarvis rc-status` /
  `./jarvis rc-freeze`)

### `./jarvis daily`

Dashboard de uma tela: data/branch/tree, doctor-agent quick result,
sessão ativa, próximo comando, gates, top task, último run, comandos
úteis. Não roda smoke pesado. Não edita nada. Se a árvore estiver suja,
imprime aviso.

### `./jarvis first-run-check [--full]`

Verifica ambiente local (python3, git, pbcopy, claude, code), branch
não-main, registries parseiam, runtime dirs existem, gitignore protege
runtime, segredos não estão tracked, secret-scan passa. `--full` roda
também `doctor-agent --full`. Para usar quando Theo abre Mac novo /
terminal novo.

### Golden paths (`./jarvis recipe-list` / `recipe-show NAME` / `recipe-run NAME ...`)

Seis receitas determinísticas (cada uma é uma sequência de sub-comandos
seguros existentes):

| name             | propósito                                            | requer                   |
| ---------------- | ---------------------------------------------------- | ------------------------ |
| `n8n-workflow`   | plano + blueprint local de workflow n8n              | `--goal` (opcional)      |
| `project-fix`    | preparar missão Claude para bug/feature              | `--project`, `--goal`    |
| `self-evolve`    | evoluir o próprio JARVIS                             | `--goal`                 |
| `no-claude-plan` | continuar sem Claude (pacote offline + task)         | `--goal`                 |
| `resume-stuck`   | retomar após interrupção / sessão presa              | —                        |
| `handoff`        | preparar handoff textual (ChatGPT, time, etc.)       | —                        |

`recipe-run NAME --dry-run` (default) imprime os passos. `--live` (ou
`--apply`) delega para os sub-comandos um a um. Receitas nunca executam
Claude, nunca chamam API, nunca editam projeto-alvo.

### `./jarvis rc-status` / `rc-freeze`

**rc-status**: imprime readiness (READY / READY WITH WARNINGS / NOT
READY) a partir de tree limpa, command-audit, doctor-agent, gate latest.
**rc-freeze --dry-run** (default) preview. **rc-freeze --apply** grava
snapshot textual em `05_EXECUCAO/41_RELEASE_CANDIDATES/<ts>_jarvis_rc.md`
(gitignored). Nunca cria git tag, nunca faz push, nunca dispara upload.
Bloqueia se NOT READY. Avisa se sem gate-run; `--skip-gates` força.

### `./jarvis acceptance --dry-run|--full`

Cenários locais: now, cheatsheet, no-claude n8n, project-intel
(jarvis-core + oficina-opcional), report-check good/bad, gate-status,
recipe-list, rc-status, state-status, handoff-self, daily,
first-run-check. `--full` adiciona `gate-run` completo. Termina em
`ACCEPTANCE PASSOU` ou `ACCEPTANCE COM PENDÊNCIAS`. Sem Claude. Sem API.

### Referência rápida (para command-audit)

```
./jarvis daily
./jarvis first-run-check
./jarvis first-run-check --full
./jarvis recipe-list
./jarvis recipe-show n8n-workflow
./jarvis recipe-show project-fix
./jarvis recipe-run n8n-workflow --goal "agendamento whatsapp" --dry-run
./jarvis recipe-run project-fix --project oficina --goal "bug agenda" --dry-run
./jarvis recipe-run self-evolve --goal "reduzir comandos manuais" --dry-run
./jarvis recipe-run no-claude-plan --goal "criar app simples" --dry-run
./jarvis rc-status
./jarvis rc-freeze --dry-run
./jarvis rc-freeze --apply
./jarvis acceptance --dry-run
./jarvis acceptance --full
```

Storage runtime gitignored Sprint 7:
- `05_EXECUCAO/41_RELEASE_CANDIDATES/**` (só `.gitkeep` versionado)

(Nota: `40_BLUEPRINTS` já estava em uso desde o Sprint 2; por isso o RC
usa `41_RELEASE_CANDIDATES`.)

Status real: comandos Sprint 7 são todos local-only; sem Claude, sem
API paga, sem deploy, sem push, sem alterar produção.

## Agent OS — Sprint 8 (real worker engine, `./jarvis do`)

Sprint 8 dá ao JARVIS o primeiro **worker engine real**. Antes ele era
um cockpit que sugeria comandos; agora `./jarvis do "pedido"` classifica
o pedido, escolhe uma rota segura, **executa** um pequeno loop
observe-act com comandos do allowlist, observa o resultado de cada
passo e imprime o próximo comando exato.

Continua sem fake autonomy: o allowlist é estreitíssimo, nenhum
`--apply`/`--live` é disparado automaticamente, Claude **nunca** roda,
APIs pagas **nunca** são chamadas, projetos-alvo **nunca** são editados,
produção **nunca** é tocada.

### `./jarvis do "pedido"`

Flags:
- `--project ALIAS` — força projeto (override do alias detectado pelo texto).
- `--mode safe` (default) — só comandos read-only / dry-run / runtime gitignored.
- `--mode no-claude` — força a rota offline (gera pacote real + task real).
- `--dry-run` — imprime ações planejadas mas não executa nem grava worker run.

### Rotas implementadas

| route                        | trigger                                          | ações principais                                                              |
| ---------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------- |
| `resume`                     | "o que faço agora", "continuar"                  | `./jarvis daily` + `./jarvis state-status`                                    |
| `n8n_blueprint`              | "workflow n8n …"                                 | `recipe-run n8n-workflow --dry-run` (+ `no-claude` se `--mode no-claude`)     |
| `project_fix_or_inspect`     | "abre <alias> …", "bug em <alias>", QA, browser  | `project-intel --project A` + `plan "…"`                                      |
| `self_evolve`                | "evolui o jarvis …"                              | `health` + `recipe-run self-evolve --dry-run`                                 |
| `no_claude`                  | "sem claude", "claude caiu" ou `--mode no-claude`| `no-claude "pedido"` + `task-add "no-claude: pedido"`                         |
| `capability_check`           | "google calendar", "web research", etc.          | `capability-check NAME`                                                       |
| `handoff`                    | "handoff", "passar pra chatgpt"                  | `handoff-self` (terminal-only)                                                |
| `unclear`                    | qualquer outro pedido                            | `ask "pedido" --dry-run` + `task-add "revisar request unclear" --dry-run`     |

### Safety allowlist (commands o worker pode executar)

`./jarvis daily`, `now`, `state-status`, `task-add`, `task-list`,
`task-next`, `no-claude`, `blueprint`, `project-intel`, `project-memory`,
`capability-check`, `capability-plan`, `capabilities`, `recipe-show`,
`recipe-run`, `recipe-list`, `handoff-self`, `rc-status`, `health`,
`doctor-agent`, `ask`, `plan`, `limits`.

Tokens proibidos em qualquer posição: `--apply`, `--force`,
`--force-weak`, `--live`, `report-apply`, `rc-freeze`, `state-reset`,
`state-archive`, `run-prune`, `self-debrief`, `project-memory-update`,
`gate-run`, `gates`, `push`, `deploy`, `merge`, `tag`, `pull-request`,
`pr-create`, `claude`.

Qualquer comando fora do allowlist (ou que carregue token proibido) é
**impresso como bloqueado**, nunca executado.

### Worker logs

Cada execução não-dry-run grava em
`05_EXECUCAO/42_WORKER_RUNS/<ts>_<slug>/` (gitignored) os arquivos:

```
01_REQUEST.md
02_ROUTE.md
03_ACTIONS.md
04_OBSERVATIONS.md
05_NEXT_COMMAND.md
06_STATUS_REAL.md
```

Suprimível com `--dry-run` ou `JARVIS_NO_REPORT=1`.

### Referência rápida (para command-audit)

```
./jarvis do "o que faço agora" --dry-run
./jarvis do "workflow n8n de agendamento whatsapp" --dry-run
./jarvis do "abre oficina e vê bug agenda" --dry-run
./jarvis do "evolui o jarvis para reduzir comandos" --dry-run
./jarvis do "agenda real google calendar" --dry-run
./jarvis do "pedido estranho xyz" --dry-run
./jarvis do "criar workflow n8n simples" --mode no-claude --dry-run
```

Storage runtime gitignored Sprint 8:
- `05_EXECUCAO/42_WORKER_RUNS/**` (só `.gitkeep` versionado)

Status real: o worker é o primeiro passo real para JARVIS "fazer
coisas" sozinho — mas só dentro do allowlist e sempre dentro do JARVIS
repo. Sem Claude, sem API paga, sem produção, sem edição de
projetos-alvo.

## Agent OS — Sprint 8.2 (do-history, do-show, do-learn, --reuse-last, dirty-tree resume, help split)

Sprint 8.2 fecha o loop de memória do worker e baixa a barreira de uso:

- **`./jarvis do` sem argumento** agora detecta árvore suja e PARA com
  STOP/ATENÇÃO + lista de arquivos + comandos seguros sugeridos. Não
  tenta rodar `daily` em cima de tree dirty.
- **`./jarvis do --reuse-last "tweak"`** regenera a última missão de
  projeto/self-evolve com um ajuste novo, sem sobrescrever a anterior.
  Também aciona com frases naturais ("melhora a última missão",
  "regenera", "faz dnv").
- **Worker run agora inclui `07_FULL_MISSION.md`** para rotas de projeto:
  combina project-intel + goal-sprint + return-format obrigatório com
  "NÃO pergunte ao Theo; faça best-effort e reporte". É esse o arquivo
  que `--copy` joga no clipboard — não mais o prompt cru do
  goal-sprint.
- **`./jarvis do-history [--limit N] [--route NAME] [--project ALIAS]`**
  lista worker runs recentes (rota, projeto, request, status). Read-only.
- **`./jarvis do-show {latest|ID}`** abre um worker run em detalhe
  (pedido, plano, ações, próximo, mission excerpt). Read-only.
- **`./jarvis do-learn [--dry-run|--apply]`** analisa runs `unclear` +
  ask-log e sugere onde adicionar pattern em
  `11_SCRIPTS/ask_router.py:INTENT_PATTERNS` ou em
  `_HANDOFF_HINT/_NO_CLAUDE_HINT`. `--apply` nesta versão **não** edita
  ask_router automaticamente (risco alto) — só confirma o relatório.
- **`./jarvis help` virou slim view** (interface única + lifecycle +
  recuperação). `./jarvis help --all` mantém o catálogo completo.
  `doctrine-check` e `command-audit` lêem `help --all` para auditar.

Runtime gitignored adicional Sprint 8.2:
- (mesmo dir do Sprint 8) `05_EXECUCAO/42_WORKER_RUNS/**`

Status real: tudo local-only; sem Claude, sem API paga, sem produção,
sem edição de projeto-alvo.

## Agent OS — Sprint 8.3 (deep project context + close-the-loop --report)

Sprint 8.3 fecha o ciclo Claude-handoff e injeta contexto real do
projeto na missão. Dois ganhos:

### `./jarvis do --report PATH [--project A] [--auto-finish]`
Fecha o loop em UM comando:
1. `./jarvis report-check --file PATH [--project A]`
2. `./jarvis report-apply --file PATH [--project A]`
3. `./jarvis gate-run` (safety + smoke + doctrine)
4. (com `--auto-finish`) `./jarvis work-close`

Para em qualquer falha com a razão exata e o próximo comando para
investigar. Substitui 4 comandos manuais por 1 com handoff fluido.
Bypassa o allowlist do worker porque Theo explicitamente pediu o
fechamento.

### Deep project intel em FULL_MISSION
Para rotas `project_fix_or_inspect`, JARVIS agora roda
`project_deep_intel.gather(alias, request)` e injeta no
`07_FULL_MISSION.md`:
- commits recentes (`git log --oneline -8`)
- arquivos candidatos (keywords do pedido vs `git ls-files`)
- hot files (mudaram nas últimas 2 semanas)
- testes prováveis (keywords + `*.test.*`/`*.spec.*`)
- branch + dirty count + presença de `.env` (sem conteúdo)

Claude recebe ponteiros de arquivo concretos sem Theo precisar digitar
caminhos.

### no-claude agora tem `00_SUMMARY.md` + `06_DEEP_INTEL.md`
Quando o no-claude detecta projeto, gera dois arquivos novos:
- `00_SUMMARY.md` — uma página: pedido / leitura / top 3 ações / risco
  principal / o-que-aguarda-Claude / o-que-não-aguarda.
- `06_DEEP_INTEL.md` — mesma deep intel das missões.

Hard rules:
- `project_deep_intel.py` **nunca** lê conteúdo de `.env` (apenas conta
  arquivos por nome).
- `--report` **não** entra no allowlist genérico; só Theo pode disparar.
- Sem push/PR/merge/deploy/migrations/tag em nenhum step.

Status real: tudo local-only; sem Claude, sem API paga, sem produção,
sem edição de projeto-alvo.
