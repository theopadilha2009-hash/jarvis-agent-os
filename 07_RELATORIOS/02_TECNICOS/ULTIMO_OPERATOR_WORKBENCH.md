# Operator Workbench — JARVIS Theo Padilha AI Worker

## Data
2026-05-24T10:15:00

## Escopo
project:oficina

## Status real
Painel local para operador. Nada aplicado em projeto real. Produção não alterada.

## Current status
- Commit: 4f5a91c
- Branch: main
- Git JARVIS: limpo
- Project alias: oficina
- Project path: /Users/usuario1/VAMOO_PROJETOS/oficina
- Project Git: limpo
- Project branch: fix/patio-agenda-status-clean
- Package manager: bun
- LOCAL_EXEC permitido: True

## Gate status
| Gate          | Result          | Age  | Artifact |
|---------------|-----------------|------|----------|
| smoke-test    | PASSOU          | 3m   | 10_TESTES/SMOKE_TESTS/2026-05-24_10-11-52-494517_cli-smoke-test.md |
| release-check | PASSOU          | 2m   | 10_TESTES/RELEASE_CHECKS/2026-05-24_10-12-10-002678_release-check.md |
| safety-gate   | PASSOU          | 2m   | 10_TESTES/SAFETY_GATES/2026-05-24_10-12-11-501235_safety-gate.md |

Nota: este workbench não executa gates. Use ./jarvis quality-gate ou ./jarvis safety-gate para validar agora.

## Latest Claude mission
- Pacote: 05_EXECUCAO/21_CLAUDE_MISSIONS/2026-05-23_14-03-56-165572_jarvis-core_patch_improve-jarvis-safely-without-production
- Idade: 20h
- Comando: `./jarvis claude-mission-latest` para abrir prompt.

## Latest project lock
- Projeto: oficina
- Sessão: 05_EXECUCAO/18_LOCAL_EXEC_SESSIONS/2026-05-23_11-26-26-614007_project-oficina-snapshot-seguro-do-run-safe-sem-deploy_local-exec-session.md
- Idade: 22h
- Handoff: 05_EXECUCAO/15_LOCAL_EXEC_HANDOFFS/2026-05-23_11-26-26-605191_oficina-snapshot-seguro-do-run-safe-sem-deploy
- Última decisão de review: PODE SEGUIR COM REVISÃO

## Action menu
1. Apenas inspecionar status (sem editar nada).
2. Validar alias do projeto: project-resolve oficina.
3. Preparar run-safe travado em oficina (sem deploy).
4. Criar Claude mission segura para oficina — modo audit.
5. Revisar saída de executor externo antes de aceitar patch.
6. Fechar/snapshotar versão atual quando tudo estiver verde.

## Exact commands
- `./jarvis visual-cockpit`
- `./jarvis claude-mission-latest`
- `./jarvis quality-gate`
- `./jarvis project-resolve oficina`
- `./jarvis run-safe --project oficina "descrever tarefa sem deploy"`
- `./jarvis claude-mission --project oficina --type audit "descrever tarefa"`
- `./jarvis local-exec-review caminho/da/resposta.md`

## When to use Claude
- tarefa precisa de auditoria estruturada de código (modo audit).
- patch curto e bem delimitado (modo patch) já planejado e aprovado.
- revisar saída de executor externo antes de aceitar (modo review).
- organizar/melhorar docs locais sem alegação de produção (modo docs).

## When NOT to use Claude
- tarefa trivial que você resolve sozinho mais rápido.
- ainda não entende o problema — primeiro readonly-run/project-resolve.
- Git sujo sem revisão — limpe antes de pedir patch.
- tarefa toca produção/VPS/n8n/deploy/push — JARVIS bloqueia, não delegue.
- precisa abrir .env ou secrets — Claude não deve ver isso.

## Blocked / pending
- nada bloqueando agora

## Must NOT do
- push, merge ou deploy
- tocar VPS, n8n ou produção
- abrir/ler .env ou imprimir secrets/tokens/API keys
- rodar rm -rf, git reset --hard, force-push, drop table, chmod 0777
- alterar projetos sem LOCAL_EXEC handoff aprovado
- criar PDFs, fontes randômicas, dependências externas ou APIs externas
- commitar artefatos sem revisão humana e sem secret-scan

## Production status
Nada alterado em produção, VPS, n8n, deploy, push ou PR.
