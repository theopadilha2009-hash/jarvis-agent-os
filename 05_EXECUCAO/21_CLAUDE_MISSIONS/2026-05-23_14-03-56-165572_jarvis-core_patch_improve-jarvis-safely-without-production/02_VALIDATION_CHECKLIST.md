# Claude Mission — Validation Checklist

## Status real
Checklist local. Rodar antes de aceitar qualquer patch ou commit.

## Itens obrigatórios
- git status --short
- python3 -m py_compile para cada script alterado em 11_SCRIPTS/
- ./jarvis command-audit
- env JARVIS_NO_REPORT=1 ./jarvis smoke-test
- ./jarvis quality-gate
- env JARVIS_NO_REPORT=1 ./jarvis safety-gate

## Bloqueios
- Não rodar deploy, push, PR, merge.
- Não tocar VPS, n8n, produção, .env, secrets.

## Produção
Nada alterado.
