# Claude Mission Prompt

## Scope
project oficina (/Users/usuario1/VAMOO_PROJETOS/oficina)

## Mode
qa-sprint

## Goal
QA sprint local sem editar produção

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

## Missão QA-SPRINT
Foco: aumentar a solidez local da branch via inspeção, validação e patches mínimos.

### Inspeção (read-only primeiro)
- git diff --stat origin/main..HEAD (se origin/main existir)
- git diff --name-only origin/main..HEAD
- listar arquivos alterados; mapear testes existentes para esses arquivos
- identificar caminhos sem cobertura automatizada

### Validação atual
- rodar typecheck do projeto (se houver)
- rodar a suíte de testes (se houver)
- rodar build apenas se for rápido e seguro localmente
- registrar ruído de stderr e classificar (pré-existente vs novo)

### Patches permitidos (orçamento apertado)
- adicionar 1–2 testes pequenos com alto valor (ex.: lock-in de bugfix da branch)
- corrigir issues triviais de teste/lint que sejam comprovadamente isolados
- NÃO refatorar nada além do mínimo
- limite duro: até 2 arquivos modificados + até 1 arquivo novo de teste

### Bloqueios duros
- sem migrations
- sem deploy/push/PR/merge
- sem secrets/.env
- sem mudança de comportamento de produção

## Tooling do projeto (referência)
- package manager: bun
- scripts úteis: test, build, lint
- typecheck: npx tsc --noEmit (ou script equivalente)
- bibliotecas de teste detectadas: vitest, rtl

## Formato obrigatório de retorno
1. STATUS REAL (Edited / Created / Tested / Production)
2. INSPEÇÃO — o que mudou na branch e o que tem/não tem cobertura
3. PATCH APPLIED? (yes/no — arquivos e linhas)
4. VALIDATION RESULTS — typecheck/tests/lint PASS/FAIL com números
5. RUÍDO DE TESTE — quem é intencional, quem é regressão
6. RISKS / NOT VALIDATED
7. NEXT BEST PATCH (uma sugestão concreta) OU STOP
8. SAFE TO COMMIT? (yes/no; se yes, comando exato — não commitar)
