# Claude Mission — Validation Checklist

## Status real
Checklist local. Rodar antes de aceitar qualquer patch ou commit.

## Itens obrigatórios
- pwd
- git status --short (no projeto)
- git branch --show-current (no projeto)
- git log --oneline -8 (no projeto)
- bash -n ./jarvis (sintaxe entrypoint)
- python3 -m py_compile em cada script alterado
- ./jarvis command-audit (drift core/help/catalog/smoke)
- env JARVIS_NO_REPORT=1 ./jarvis smoke-test
- env JARVIS_NO_REPORT=1 ./jarvis safety-gate
- ./jarvis self-cockpit (verificar saída clara)
- git diff --check (sem whitespace bugs)
- git add <paths explícitos> antes do commit (NUNCA `git add .`)
- sem push/PR/merge/deploy

## Bloqueios
- Não tocar VPS, n8n, deploy, push, PR, main, .env ou secrets.
- Não imprimir tokens, API keys, cookies, senhas ou QR codes.
- Não rodar migrations.
- Não editar Supabase ou banco de produção.
- Não gerar PDF. Não criar fontes randômicas.
- Não usar APIs externas neste pacote.
- Não fazer commit sem autorização explícita do usuário.
- Não fazer push, PR, merge ou deploy.

## Produção
Nada alterado.
