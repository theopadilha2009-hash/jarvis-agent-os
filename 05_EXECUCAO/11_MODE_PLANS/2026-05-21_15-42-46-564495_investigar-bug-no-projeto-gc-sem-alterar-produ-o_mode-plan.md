# Mode Plan — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T15:42:46

## Tarefa
investigar bug no projeto GC sem alterar produção

## Status real
Plano de modo criado localmente. Nada executado no projeto real.

## Modo sugerido
READONLY

## Sinais usados
investigar, sem alterar

## Sinais mitigados por negação
produção

## Regras do modo
- Pode ler arquivos, logs, status, estrutura e documentação.
- Não altera código, banco, workflow, VPS ou produção.
- Pode gerar diagnóstico e próximo passo.

## Bloqueios permanentes
- segredo exposto em chat
- ação em produção sem modo declarado
- push/merge/deploy sem autorização explícita
- credencial salva em Git
- workflow n8n ativo sem validação

## Próximo comando seguro
`./jarvis executor-handoff "investigar bug no projeto GC sem alterar produção"`

## Produção
Nada alterado.
