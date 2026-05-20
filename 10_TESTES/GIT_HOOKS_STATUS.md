# Git Hooks Status — JARVIS Theo Padilha

## Status real
Pre-commit hook versionado em `.githooks/pre-commit` e ativado localmente com `core.hooksPath`.

## O que ele valida
- Python syntax de `11_SCRIPTS/jarvis_core.py`
- bloqueio básico de `.env`, `.pem` e `.key`

## Produção
Nada alterado.

## Observação
Agora o hook fica versionado no repositório. Em outro Mac, basta rodar:
`git config core.hooksPath .githooks`
