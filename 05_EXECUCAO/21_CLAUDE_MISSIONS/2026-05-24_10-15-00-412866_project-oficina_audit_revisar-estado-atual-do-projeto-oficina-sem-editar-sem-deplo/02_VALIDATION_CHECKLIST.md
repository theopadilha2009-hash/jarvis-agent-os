# Claude Mission — Validation Checklist

## Status real
Checklist local. Rodar antes de aceitar qualquer patch ou commit.

## Itens obrigatórios
- git status --short (no projeto)
- git branch --show-current (no projeto)
- se houver package.json: rodar build/test do package manager registrado
- não rodar deploy, push, PR ou merge

## Bloqueios
- Não rodar deploy, push, PR, merge.
- Não tocar VPS, n8n, produção, .env, secrets.

## Produção
Nada alterado.
