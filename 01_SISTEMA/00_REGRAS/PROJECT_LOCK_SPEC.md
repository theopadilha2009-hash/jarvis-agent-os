# Project Lock Spec — JARVIS v0.5

## Problema

Na v0.4, uma tarefa genérica pode ser resolvida para o projeto errado.
Exemplo real: tarefa genérica sem nome de projeto escolheu gc-gestao-de-cristo.

## Regra v0.5

Toda execução LOCAL_EXEC real deve travar o projeto explicitamente antes de gerar handoff ou executar qualquer ação.

## Formato desejado

./jarvis local-exec-session --project oficina "corrigir bug X sem deploy"
./jarvis local-exec-session --project gc "corrigir bug Y sem deploy"

## Comportamento obrigatório

- Se --project for informado, usar somente esse projeto.
- Se --project não for informado em tarefa real, avisar risco e não fingir certeza.
- Nunca escolher projeto por chute quando houver risco de edição real.
- Não editar main/master sem branch segura.
- Não abrir ou expor .env, tokens, senhas, cookies ou credenciais.
- Não fazer push, merge, PR ou deploy automático.

## Claude

Claude não é obrigatório. JARVIS continua local/free-first.
Claude ou VS Code entram apenas quando forem úteis ou autorizados para tarefa real.

## Produção

Nada nesta especificação altera produção.
