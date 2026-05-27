# Claude Mission Prompt — JARVIS SELF-EVOLVE

## Scope
JARVIS local lab (/Users/usuario1/Theo/JARVIS/VAMOO_JARVIS_LAB_v0_2_PRONTO)

## Mode
self-evolve

## Goal
stress-test the new JARVIS self-evolution loop end-to-end, fix only real friction, improve clarity, and stop before overengineering

## Branch registrada
- feature/jarvis-max-machine

## 1. MISSION
Evoluir o próprio JARVIS — o repositório que gera missões Claude — para
reduzir trabalho manual de Theo de forma segura e auditável.
Trabalhar apenas dentro deste repo. Não tocar projetos-alvo.

## 2. CURRENT STATE
- Sprint 1: per-project doctor/qa-sprint/goal-sprint/browser-qa/final-gate.
- Sprint 2: cockpit diário + mission-open-latest + gitignore de packs.
- Sprint 3: project-memory + project-memory-update + parser regex de relatórios.
- Branch atual: feature/jarvis-max-machine
- Gates esperados verdes: safety-gate, smoke-test, command-audit.
- Tree esperada limpa antes da edição.

## 3. TRUE NORTH
JARVIS é a HARNESS de Claude Code: prepara, copia, organiza, lembra,
valida, e sugere próximo passo. NÃO é executor de Claude. NÃO chama API.
Reduz dependência de ChatGPT para escrever prompts.
Status real sempre. Branch safe sempre. Production never.

## 4. HARD RULES
- Não tocar VPS, n8n, deploy, push, PR, main, .env ou secrets.
- Não imprimir tokens, API keys, cookies, senhas ou QR codes.
- Não rodar migrations.
- Não editar Supabase ou banco de produção.
- Não gerar PDF. Não criar fontes randômicas.
- Não usar APIs externas neste pacote.
- Não fazer commit sem autorização explícita do usuário.
- Não fazer push, PR, merge ou deploy.
- Não usar APIs pagas (Anthropic/OpenAI). Stdlib only.
- Não criar TUI/dashboard.
- Não rodar Claude em background. Não fingir autonomia.
- Não deletar comandos existentes.
- Não usar `git add .` — sempre paths explícitos.
- Não editar main/master. Se branch=main, PARE.

## 5. WHAT TO INSPECT (read-only primeiro)
- 11_SCRIPTS/jarvis_core.py — dispatcher + help
- 11_SCRIPTS/project_mission_pack.py — gerador de missions
- 11_SCRIPTS/project_memory*.py — loop de memória
- 11_SCRIPTS/self_cockpit.py — entry point self-*
- 11_SCRIPTS/claude_helpers.py — workflow Claude Code local
- 11_SCRIPTS/command_audit.py — drift detector
- 11_SCRIPTS/cli_smoke_test.py — CHECKS list
- AGENTS.md — contrato com agentes
- 01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md
- 04_PROJETOS/JARVIS_CORE/PROJECT_STATUS.md — memória atual

## 6. WHAT TO IMPROVE
Foco no objetivo declarado em ## Goal. Iterar em patches pequenos:
- inspecionar → escolher próximo patch mais alto valor / menor risco
- aplicar (≤ 2 arquivos por iteração)
- validar (bash -n + py_compile + command-audit + smoke + safety-gate)
- decidir continuar ou parar
Marcar critérios de Definition of Done mensuráveis.

## 7. WHAT NOT TO BUILD
- Web dashboard / TUI rich-textual.
- Auto-execute Claude em background.
- Integração com API paga.
- Multi-agent orquestrador.
- Refactor grande de scripts existentes (operator_workbench, run_safe).
- Deduplicar 20+ pastas em 05_EXECUCAO/ (não é o gargalo).
- Auto-detectar framework no doctor (Sprint 5+).
Se cair na tentação de algo acima → PARE e proponha sem aplicar.

## 8. IMPLEMENTATION PHASES
1. Preflight (pwd, git status, branch, safety-gate, smoke).
2. Inspect arquivos listados em ## 5.
3. Decidir 1 patch + critérios de aceite.
4. Aplicar patch (paths explícitos, sem git add .).
5. Validar (typecheck/audit/smoke/safety).
6. Commit local SE tudo verde — usar `git add <paths>`.
7. Self-audit: reduziu trabalho manual? overengineering? gates verdes?
8. Se houver outro patch de valor alto E baixo risco, repetir 3-7.
9. Senão, parar e reportar.

## 9. VALIDATION COMMANDS
```
bash -n ./jarvis
python3 -m py_compile <arquivo alterado>
./jarvis help
./jarvis command-audit
env JARVIS_NO_REPORT=1 ./jarvis smoke-test
env JARVIS_NO_REPORT=1 ./jarvis safety-gate
./jarvis self-cockpit
git diff --stat
git diff --check
git status --short
```

## 10. COMMIT RULES
- 1 commit por checkpoint validado.
- `git add <paths explícitos>` (nunca `git add .`).
- Mensagem padrão: `feat(jarvis): <verbo curto>` ou `fix(jarvis): ...`.
- HEREDOC para multi-line.
- Pre-commit hook deve passar (Python syntax + secret-block).
- Sem push, PR, merge, deploy.

## 11. SELF-AUDIT (perguntas obrigatórias antes de parar)
- Reduziu trabalho manual real do Theo?
- JARVIS está mais autônomo OU é autonomia fake?
- Status real preservado em toda saída?
- Comandos existentes ainda funcionam (command-audit OK)?
- smoke-test e safety-gate verdes pós-commit?
- Algum overengineering oculto introduzido?
- Dependências adicionadas? (espera-se: NÃO).
- Production touched? (espera-se: NÃO).

## 12. RETURN FORMAT
1. STATUS REAL (Created/Modified/Tested/Committed/Not validated/Production)
2. WHAT IMPROVED
3. COMMANDS ADDED/CHANGED
4. NEW DAILY LOOP (se mudou)
5. VALIDATION RESULTS (cada comando PASS/FAIL com números)
6. COMMITS CREATED (hash + msg)
7. FILES CHANGED (lista exata)
8. RISKS / LIMITS (honesto)
9. WHAT NOT TO BUILD NEXT
10. NEXT BEST ACTION (1 comando exato)
11. SAFE TO STOP? (yes/no)

## Tooling do projeto (referência)
- package.json: ausente

## Doctrine (não negociável)
- Status real always · Branch safe always · Read before edit
- No secrets in chat/Git/docs/logs · Production after controlled validation
- IA decide subjetivo; harness controla regras/estado/logs/validação/memória
- Tools radar ≠ permissão para instalar tudo
- created ≠ imported ≠ configured ≠ tested ≠ validated ≠ production
- Workflow pro = responde + loga + monitora + pausa + transfere + recupera + documenta
