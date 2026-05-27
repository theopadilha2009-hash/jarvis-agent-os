# JARVIS — Mission para Claude Code (assembled by ./jarvis do)

**Status real**: Esta missão foi montada por JARVIS local. JARVIS NÃO executou
Claude. Você (Claude) deve executar as ações dentro do projeto-alvo, mas
respeitando todas as regras abaixo.

## Regras invariáveis (não negociar)
- NUNCA faça push, PR, merge, deploy, tag, migrações ou tocar produção.
- NUNCA leia conteúdo de `.env`, NUNCA imprima tokens / cookies / API keys
  / QR codes / segredos / senhas.
- NUNCA chame API paga (Anthropic, OpenAI, etc.) — você é o LLM, não chame
  outro LLM.
- NUNCA execute Claude em background.
- Se o projeto-alvo estiver em main/master, PARE e reporte.
- Edite só o necessário para cumprir o objetivo. Sem refactor agressivo.

## Comportamento esperado
- NÃO pergunte ao Theo. Faça best-effort dentro das regras e reporte.
- Se faltar info, marque RISCO em STATUS REAL e siga com a melhor hipótese.
- Prefira mudanças pequenas, testáveis, reversíveis.
- Sempre rode os checks locais (typecheck/tests/lint) que o projeto já tem.
- Termine com o bloco STATUS REAL completo no final do output.

## Projeto
- alias: `oficina`
- objetivo: bug na agenda

## Contexto do projeto (project-intel, read-only)
```
JARVIS — Project Intel (read-only)
Status real: inspeção local. Nada foi editado em oficina.

alias: oficina
path:  /Users/usuario1/VAMOO_PROJETOS/oficina
branch: fix/patio-agenda-status-clean
dirty:  sim (1 arquivo(s))

## Package manager
- detectado: bun  (via bun.lockb)
- package.json: presente (10 scripts)
  - dev: `vite`
  - build: `vite build`
  - test: `vitest run`
  - lint: `eslint .`

## Framework hints
- vite
- react

## Test tools
- vitest
- react-testing-library

## Migrations / DB
- supabase/migrations (96 arquivos)

## .env risk (sem ler valores)
- .env (untracked)
- .env.example ⚠ TRACKED no git!
Lembrete: JARVIS nunca lê o conteúdo de .env.

## Comandos recomendados (NÃO executados)
  $ bun install  # JARVIS NÃO executa — você roda se quiser
  $ bun run dev
  $ bun run test
  $ bun run build
  $ bun run lint

## Próxima ação segura
  ./jarvis project-open --project oficina --print-only
  ./jarvis project-cockpit --project oficina
  ./jarvis go "<o que você quer fazer no oficina>"

Produção: nada alterado. JARVIS não rodou install/test/build/lint.
```

## Missão detalhada (goal-sprint)
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



## Formato de retorno obrigatório (no fim do output)

```
## STATUS REAL
- branch: <nome>
- arquivos tocados: <lista>
- typecheck: <PASS/FAIL/NOT_RUN>
- tests:     <PASS/FAIL/NOT_RUN>
- lint:      <PASS/FAIL/NOT_RUN>

## WHAT CHANGED
<bullets curtos>

## WHAT IMPROVED
<bullets curtos>

## RISKS
<bullets — ou "nenhum identificado">

## SAFE TO COMMIT
<yes/no + motivo curto>
```

Status real: este pacote foi montado por JARVIS local sem chamar API paga
e sem executar Claude. Produção: nada alterado por JARVIS.
