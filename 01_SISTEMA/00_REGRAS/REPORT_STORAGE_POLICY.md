# Report Storage Policy — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T15:13:21

## Status real
Política local de armazenamento. Não é produção.

## Decisão
Relatórios `ULTIMO_*.md` são artefatos vivos e voláteis. Eles podem existir localmente, mas não devem ficar versionados no Git.

## Por quê
Comandos como `cockpit`, `overview`, `task-status`, `review-output-index`, `summary` e `release-check` atualizam relatórios de estado. Se esses arquivos forem versionados, o Git fica sujo toda hora e gera commits de limpeza sem valor real.

## O que fica ignorado
- `07_RELATORIOS/02_TECNICOS/ULTIMO_*.md`

## O que continua versionado
- scripts em `11_SCRIPTS/`;
- regras em `01_SISTEMA/`;
- decisões em `03_MEMORIA/02_DECISOES/`;
- snapshots em `07_RELATORIOS/03_RELEASES/`;
- smoke tests em `10_TESTES/SMOKE_TESTS/`;
- release checks em `10_TESTES/RELEASE_CHECKS/`;
- safety gates em `10_TESTES/SAFETY_GATES/`;
- checkpoints em `10_TESTES/CHECKPOINTS/`;
- handoffs, briefs e auto-task runs quando representam marco útil.

## Regra prática
Relatório vivo mostra estado atual. Snapshot versionado prova um marco.

## Status real correto
Ignorar `ULTIMO_*.md` não apaga os arquivos locais. Só impede rework e commits inúteis.
