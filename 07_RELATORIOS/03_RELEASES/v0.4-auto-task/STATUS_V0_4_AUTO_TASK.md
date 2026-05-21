# Status v0.4 Auto Task — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T14:25:54

## Status real
Snapshot local do marco auto-task. Não é produção.

## Marco
`./jarvis auto-task "tarefa"` agora executa a preparação completa local em um comando único.

## O que auto-task faz
- atualiza project-index;
- seleciona projeto provável;
- cria task-brief;
- cria task-start;
- gera executor-handoff;
- imprime handoff no terminal;
- atualiza task-status;
- roda release-check.

## O que auto-task NÃO faz
- não edita projeto real;
- não abre VS Code;
- não chama Claude/Gemini automaticamente;
- não faz push/merge/deploy;
- não mexe em produção;
- não lê ou expõe `.env`/credenciais.

## Validado
- auto-task passou em tarefa GC;
- auto-task-latest imprime o último relatório;
- smoke-test cobre comandos principais;
- release-check passou;
- quality-gate passou antes do snapshot.

## Próximo passo seguro
Melhorar `review-outputs` para receber resposta de Claude/Gemini/ChatGPT e transformar em decisão, relatório e próximo passo validável.

## Regra
Preparação automatizada não é execução no projeto real. A próxima fase deve ser read-only antes de qualquer edição automática.
