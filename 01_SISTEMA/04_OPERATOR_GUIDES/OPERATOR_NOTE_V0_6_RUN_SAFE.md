# Operator Note v0.6 — JARVIS Run Safe

## Status real

JARVIS v0.6 está fechado como camada guiada de preparação segura.

O comando principal agora é:

./jarvis run-safe --project oficina "descrever tarefa sem deploy"

Ele orquestra:
- project-resolve;
- next-step;
- local-exec-session;
- local-exec-handoff-latest;
- relatório RUN_SAFE.

## Quando usar

Use `run-safe` quando existir uma tarefa real, mas ainda não for hora de editar automaticamente.

Exemplos:

./jarvis run-safe --project oficina "investigar bug de agenda sem deploy"

./jarvis run-safe --project gc "revisar erro de build sem push"

## O que ele faz

- Exige project lock com `--project`.
- Confere o projeto.
- Mostra estado e próximo passo.
- Gera sessão LOCAL_EXEC.
- Gera handoff para executor externo.
- Mantém status real claro.

## O que ele NÃO faz

- Não aplica patch automático.
- Não roda build/teste real automaticamente como decisão final.
- Não faz commit em projeto real.
- Não faz push.
- Não abre PR.
- Não faz deploy.
- Não mexe em VPS, n8n ou produção.
- Não chama Claude sozinho.

## Fluxo certo

1. Rodar `run-safe`.
2. Abrir o handoff.
3. Só usar Claude/VS Code se a tarefa realmente precisar.
4. Salvar a resposta do executor em `.md`.
5. Rodar:

./jarvis local-exec-review caminho/da/resposta.md

6. Só aceitar patch se a revisão não bloquear.

## Claude

Claude continua opcional.

Usar Claude quando:
- precisa ler/editar projeto local;
- a tarefa está clara;
- a branch está segura;
- não envolve produção;
- você autorizou explicitamente.

Não usar Claude só para programar o próprio JARVIS se não for necessário.

## Status que pode falar

Criado:
- comando `run-safe`;
- artefatos em `05_EXECUCAO/19_RUN_SAFE`;
- snapshot v0.6 run-safe core.

Configurado:
- atalho `./jarvis run-safe`;
- command-audit;
- command catalog;
- smoke-test.

Testado:
- `run-safe --project oficina`;
- smoke-test;
- release-check;
- safety-gate;
- quality-gate.

Validado localmente:
- project lock funcionou;
- handoff foi gerado;
- Git limpo;
- produção não alterada.

Ainda não é:
- patch automático;
- agente autônomo;
- deploy automático;
- produção.

## Próximo rumo

v0.7 só deve começar se for para melhorar revisão pós-executor ou criar uma camada de decisão mais clara antes de patch.

Não pular direto para automação autônoma.

## Produção

Nada em v0.6 altera produção.
