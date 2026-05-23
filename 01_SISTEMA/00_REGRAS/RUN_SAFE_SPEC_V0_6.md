# RUN_SAFE Spec v0.6 — JARVIS

## Status real

Especificação criada para a v0.6. Nada foi executado em projeto real.

## Objetivo

Criar um comando mais humano para orientar a próxima ação segura sem o usuário precisar lembrar vários comandos.

Nome provável:

./jarvis run-safe --project oficina "tarefa"

## O que o run-safe deve fazer

1. Validar o projeto com Project Registry.
2. Mostrar estado do projeto.
3. Rodar orientação de próximo passo.
4. Preparar LOCAL_EXEC Session com project lock.
5. Mostrar onde está o handoff.
6. Mostrar o que fazer depois.

## O que NÃO deve fazer na v0.6

- Não aplicar patch.
- Não editar projeto real.
- Não rodar build automático como decisão final.
- Não commitar projeto real.
- Não fazer push.
- Não abrir PR.
- Não fazer deploy.
- Não mexer em VPS/n8n/produção.
- Não usar Claude automaticamente.

## Comportamento esperado

Entrada:

./jarvis run-safe --project oficina "corrigir bug X sem deploy"

Saída esperada:
- projeto escolhido;
- branch;
- Git status;
- risco;
- comandos gerados;
- handoff criado;
- próximo passo humano.

## Claude

Claude continua opcional.

O run-safe pode gerar handoff, mas não chama Claude sozinho.

## Critério de sucesso da v0.6

- Comando mais fácil de usar.
- Project lock obrigatório para tarefa real.
- Handoff gerado.
- Gates passando.
- Nenhuma produção alterada.

## Produção

Nada nesta especificação altera produção.
