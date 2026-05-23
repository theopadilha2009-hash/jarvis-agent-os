# Claude Mission Prompt

## Scope
JARVIS local repository

## Type
patch

## Task
improve JARVIS safely without production

## Status real rules
- Status real obrigatório: dizer claramente se algo foi alterado ou não.
- Nenhuma alegação de produção. Tudo aqui é local.
- Não tocar VPS, n8n, deploy, push, PR, main, .env ou secrets.
- Não imprimir tokens, API keys, cookies, senhas ou QR codes.
- Não gerar PDF. Não criar fontes randômicas.
- Não usar APIs externas neste pacote.
- Não fazer commit sem autorização explícita do usuário.

## Git preflight
Antes de qualquer edição, rode e reporte:
- git status --short
- git branch --show-current
- git log --oneline -5
Se a árvore não estiver limpa, PARE e relate exatamente o que está sujo.

## Scope rules
- Escopo: repositório JARVIS local.
- Não quebrar command-audit, smoke-test, release-check, safety-gate, quality-gate.
- Manter JARVIS local-first. Sem produção. Sem PDFs. Sem fontes randômicas.
- Não refatorar jarvis_core.py além de registro de rota/help.

## Mode rules
- Modo PATCH: leia primeiro, edite só o mínimo aprovado.
- Não refatorar fora do escopo. Não adicionar dependências.
- Não criar arquivos fora do necessário.
- Validar localmente. Não commitar sem autorização.
- Retornar: arquivos alterados, resumo de diff, validações executadas e safe-to-commit yes/no.

## Read-only first
Modo PATCH: leitura antes da edição mínima.

## Validation checklist
- git status --short
- python3 -m py_compile para cada script alterado em 11_SCRIPTS/
- ./jarvis command-audit
- env JARVIS_NO_REPORT=1 ./jarvis smoke-test
- ./jarvis quality-gate
- env JARVIS_NO_REPORT=1 ./jarvis safety-gate

## Required return format
1. STATUS REAL — o que foi ou não foi alterado
2. FILES CHANGED
3. WHAT CHANGED (curto)
4. VALIDATION RESULTS — PASS/FAIL/PENDING por item
5. GIT STATUS final
6. RISKS / NOT VALIDATED
7. SAFE TO COMMIT? yes/no

## Commit policy
Não fazer commit sem autorização explícita. Retornar somente safe-to-commit yes/no.
