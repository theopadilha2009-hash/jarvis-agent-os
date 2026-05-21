# Mode Plan — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T15:39:55

## Tarefa
investigar bug no projeto GC sem alterar produção

## Status real
Plano de modo criado localmente. Nada executado no projeto real.

## Modo sugerido
PRODUCTION_ARMED

## Regras do modo
- Modo de ação real sensível.
- Exige autorização explícita.
- Deve declarar alvo, risco, rollback e validação.
- Deve rodar safety-gate antes e registrar status real depois.

## Bloqueios permanentes
- segredo exposto em chat
- ação em produção sem modo declarado
- push/merge/deploy sem autorização explícita
- credencial salva em Git
- workflow n8n ativo sem validação

## Próximo comando seguro
`./jarvis safety-gate`

## Produção
Nada alterado.
