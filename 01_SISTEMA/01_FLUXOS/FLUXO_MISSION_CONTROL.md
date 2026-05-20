# Mission Control — JARVIS Theo Padilha AI Worker

## Status real
Camada local de missão. Não executa produção, VPS, deploy, credenciais, cliente real ou API paga.

## Objetivo
Transformar um pedido bruto em uma missão organizada com:
- task;
- roteamento;
- plano seguro;
- mission brief;
- log;
- próximo passo seguro.

## Fluxo
Pedido do usuário
→ ./jarvis launch
→ detecta tipo e risco
→ escolhe perfil e ferramenta sugerida
→ cria task em 02_TAREFAS/00_NOVAS
→ cria plano seguro em 05_EXECUCAO/00_PLANOS_SEGUROS
→ cria mission brief em 05_EXECUCAO/01_MISSOES
→ registra log em 09_LOGS
→ usuário decide próximo passo

## Regra
Launch organiza e prepara. Não executa ação perigosa.
