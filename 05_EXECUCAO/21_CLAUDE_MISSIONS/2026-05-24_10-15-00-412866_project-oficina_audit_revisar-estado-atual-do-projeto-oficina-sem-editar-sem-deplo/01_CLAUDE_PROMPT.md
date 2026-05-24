# Claude Mission Prompt

## Scope
project oficina (/Users/usuario1/VAMOO_PROJETOS/oficina)

## Type
audit

## Task
revisar estado atual do projeto oficina sem editar, sem deploy, e propor a próxima correção segura

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
- Escopo: projeto oficina -> /Users/usuario1/VAMOO_PROJETOS/oficina
- Branch atual registrada: fix/patio-agenda-status-clean
- Confirme pasta/projeto/branch antes de qualquer leitura ou edição.
- Não mexer em main sem autorização explícita.
- Não fazer deploy, push, PR ou merge.
- Respeitar project lock: somente este projeto.

## Mode rules
- Modo AUDIT: somente leitura. Nenhuma edição neste pacote.
- Retornar: diagnóstico, riscos, arquivos relevantes, próxima patch recomendada (sem aplicá-la).

## Read-only first
Este modo é read-only. Não editar arquivos.

## Validation checklist
- git status --short (no projeto)
- git branch --show-current (no projeto)
- se houver package.json: rodar build/test do package manager registrado
- não rodar deploy, push, PR ou merge

## Required return format
1. STATUS REAL — nenhuma edição
2. DIAGNÓSTICO
3. RISCOS
4. ARQUIVOS RELEVANTES
5. PRÓXIMA PATCH RECOMENDADA (descritiva, não aplicada)
6. SAFE TO PROCEED? yes/no

## Commit policy
Não fazer commit sem autorização explícita. Retornar somente safe-to-commit yes/no.
