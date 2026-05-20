# Workspace Scan — JARVIS

## Pasta base
/Users/usuario1/VAMOO_PROJETOS

## Projetos detectados
3

## gc-gestao-de-cristo
- Caminho: `/Users/usuario1/VAMOO_PROJETOS/gc-gestao-de-cristo`
- Score: 12
- Motivos: git, package.json, src, json, docs
- Git: sim
- Branch: analise-inicial-theo
- Git status: M src/app/(dashboard)/gcs/page.tsx
 M src/features/gcs/components/gcs-list-client.tsx
 M src/server/queries/gcs.ts
 M tests/server/queries/gcs-visitor-count.test.ts
- .env encontrados: .env.local, .env.local.backup-antes-supabase-url, .env.local.backup-antes-vercel-real, .env.vercel.check
- Risco inicial: médio

## ls-clinica-agent
- Caminho: `/Users/usuario1/VAMOO_PROJETOS/ls-clinica-agent`
- Score: 6
- Motivos: git, docs
- Git: sim
- Branch: analysis/ls-v1-4-3-polish
- Git status: ?? 03_OUTPUT/ls-v1-2-inbound-final-uazapi-safe.workflow.json
?? 03_OUTPUT/ls-v1-3-1-staging-safe-early-allowlist.workflow.json
?? 03_OUTPUT/ls-v1-3-2-polish-cost-fallback.workflow.json
?? 03_OUTPUT/ls-v1-3-3-test-safe-final.workflow.json
?? 03_OUTPUT/ls-v1-3-4-sensitive-quickreply-fix.workflow.json
?? 03_OUTPUT/ls-v1-3-final-uazapi-real-architecture.workflow.json
?? 03_OUTPUT/ls-v1-4-1-final-staging-polish.workflow.json
?? 03_OUTPUT/ls-v1-4-2-sdr-kommo-cutoff.workflow.json
?? 03_OUTPUT/ls-v1-4-conversation-state-scheduling.workflow.json
- .env encontrados: nenhum
- Risco inicial: médio

## oficina
- Caminho: `/Users/usuario1/VAMOO_PROJETOS/oficina`
- Score: 12
- Motivos: git, package.json, src, json, docs
- Git: sim
- Branch: fix/bugs-oficina-20260519-1516
- Git status: limpo
- .env encontrados: .env, .env.example
- Risco inicial: médio

## Produção
Nada alterado.

## Próximo passo seguro
Rodar `./jarvis workspace-check CAMINHO_DO_PROJETO` no projeto escolhido antes de usar Claude/Gemini/VS Code.
