# Claude Mission — Validation Checklist

## Status real
Checklist local. Rodar antes de aceitar qualquer patch ou commit.

## Itens obrigatórios
- pwd
- git status --short (no projeto)
- git branch --show-current (no projeto)
- git log --oneline -8 (no projeto)
- npx tsc --noEmit (se TS)
- script de test do package manager registrado
- não rodar deploy/push/PR/merge

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
