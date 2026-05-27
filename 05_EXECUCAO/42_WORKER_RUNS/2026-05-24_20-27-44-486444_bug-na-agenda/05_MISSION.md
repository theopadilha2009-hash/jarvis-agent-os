# Mission excerpt

_File: `05_EXECUCAO/21_CLAUDE_MISSIONS/2026-05-24_20-27-44-352199_project-oficina_goal-sprint_bug-na-agenda/01_CLAUDE_PROMPT.md`_

```
# Claude Mission Prompt

## Scope
project oficina (/Users/usuario1/VAMOO_PROJETOS/oficina)

## Mode
goal-sprint

## Goal
bug na agenda

## Branch registrada
- fix/patio-agenda-status-clean

## Hard rules
- Não tocar VPS, n8n, deploy, push, PR, main, .env ou secrets.
- Não imprimir tokens, API keys, cookies, senhas ou QR codes.
- Não rodar migrations.
- Não editar Supabase ou banco de produção.
- Não gerar PDF. Não criar fontes randômicas.
- Não usar APIs externas neste pacote.
- Não fazer commit sem autorização explícita do usuário.
- Não fazer push, PR, merge ou deploy.

## Git preflight
- pwd
- git status --short
- git branch --show-current
- git log --oneline -8
Se a árvore estiver suja antes da edição, PARE e reporte exatamente o que está sujo.
Se a branch for main/master, PARE — esta missão exige branch dedicada (registrada: fix/patio-agenda-status-clean).

## Missão GOAL-SPRINT
Objetivo declarado: "bug na agenda"

### Definition of Done
- Listar 3–6 critérios mensuráveis para considerar o objetivo cumprido.
- Cada critério deve poder ser provado por código/tests/typecheck — sem 'parece OK'.
- Se algum critério depende de browser/manual, marcar explicitamente como 'human-only'.

### Loop iterativo
1. Inspecionar estado atual da branch (changed files, testes, ruído).
2. Escolher o próximo patch de maior valor e menor risco.
3. Aplicar patch mínimo (até 2 arquivos por iteração).
4. Validar (typecheck + tests + lint relevantes).
5. Repetir enquanto houver patch seguro de alto valor.
6. Parar quando o próximo patch for: arriscado, refator grande, ou ROI baixo.

### Critérios de parada (não overengineer)
- 'Posso provar com código?' Se não, é human-only — registrar e parar.
- 'Custo > benefício?' Se sim, parar.
- 'Arquitetura?' Se sim, propor sem aplicar.

### Bloqueios duros
- Não tocar VPS, n8n, deploy, push, PR, main, .env ou secrets.
- Não imprimir tokens, API keys, cookies, senhas ou QR codes.
- Não rodar migrations.
- Não editar Supabase ou banco de produção.
- Não gerar PDF. Não criar fontes randômicas.
- Não usar APIs externas neste pacote.
- Não fazer commit sem autorização explícita do usuário.
- Não fazer push, PR, merge ou deploy.

## Tooling do projeto (referência)
- package manager: bun
- scripts úteis: test, build, lint
- typecheck: npx tsc --noEmit (ou script equivalente)
- bibliotecas de teste detectadas: vitest, rtl

## Formato obrigatório de retorno
1. STATUS REAL
2. DEFINITION OF DONE (lista mensurável)
3. ITERAÇÕES APLICADAS (cada uma: patch, validação, decisão)
4. CRITÉRIOS ATENDIDOS vs NÃO ATENDIDOS
5. RESTANTE HUMAN-ONLY (lista mínima — só o que código não prova)
6. EXACT NEXT ACTION (comando ou STOP)
7. SAFE TO COMMIT? (yes/no; se yes, comando exato — não commitar)
```
