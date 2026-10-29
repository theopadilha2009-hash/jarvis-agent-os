# Auditoria — 16 varreduras, 2026-10-29

Varredura read-only de ~121K LOC em dois projetos que compartilham o mesmo `.git`:

- **JARVIS** — 293 arquivos `.py`, 109K LOC (274 em `11_SCRIPTS/`)
- **copytrade** — 75 arquivos `.ts/.tsx`, 12K LOC

16 subagentes com escopos disjuntos. Nenhum arquivo foi alterado durante a varredura.

**Linha de base:** JARVIS `375 testes / OK / 4.8s`. copytrade sem `node_modules` — `tsc`/`lint`/`test` não executados.

---

## P0 — segurança

### copytrade: rotas de execução sem autenticação
- `apps/web/src/app/api/orders/route.ts:12,21` — `POST /api/orders` assina e envia ordem com a chave do servidor.
- `apps/web/src/app/api/settings/kill-switch/route.ts:16` — liga/desliga o bloqueio de entradas.
- `GET /api/orders` devolve 100 registros.
- Não existe `middleware.ts` nem checagem de auth no repo; `vercel.json` publica o app.
- **Se o deploy estiver no ar, é exposição real.** Projeto em F0/`paper_only`, mas a chave é do servidor.

### copytrade: kill switch falha aberto
`apps/web/src/lib/execution/store.ts:52-60` — `JSON.parse` de `settings.json` lança, o `catch` retorna `{ blockEntries: false }`. Escrita truncada (processo morto no `writeFileSync` da linha 78, disco cheio) desliga o freio em silêncio. `place-order.ts:89-90` consulta essa função para autorizar entrada.

### JARVIS: secret-scan passa quando o git falha
`11_SCRIPTS/secret_scan.py:50-54,104` — `run()` engole `CalledProcessError`; `tracked = run(["git","ls-files"]).splitlines()` vira texto de erro, nenhum arquivo existe, zero hits.
Prova: `GIT_DIR=/nonexistent GIT_WORK_TREE=/nonexistent python3 11_SCRIPTS/secret_scan.py` → `SECRET SCAN PASSOU`, `EXIT=0`. `safety_gate.py:10,39` só olha exit code + a string, então o gate inteiro passa junto.

### JARVIS: diff review esconde credencial nos arquivos de segurança
`11_SCRIPTS/jarvis_diff_review_gate.py:83-126` — em `safety_files` (`jarvis_ship_guard.py`, `jarvis_autoship.py`, `jarvis_safe_apply*.py`), linha contendo `token`/`secret`/`password`/`.env` é descartada antes do scan.
Prova: `+TOKEN = "ghp_1234..."` em `foo.py` → `hits=['token']`; o mesmo em `jarvis_ship_guard.py` → `hits=[]`.

### JARVIS: path traversal com comentário que mente
`11_SCRIPTS/device_worker.py:588` diz "Segmentos `.` e `..` não passam". O regex só barra `..` do segundo segmento em diante.
Prova: `theo/../../alvo` → False, mas `theo/x/../../alvo` → **True** e `theo/1-x/../../secret` → **True**. Mesmo regex em `delete_private_artifact:616`, que apaga.

### JARVIS: secret scan fail-open em 5 lugares
Padrão `except Exception: SECRET_PATTERNS = []` — desliga o detector em silêncio:
- `report_intake.py:45-64` (protege `report-check`/`report-apply`)
- `work_session.py:50`
- `task_queue.py:40`
- `ask_router.py:42`
- `project_memory.py:28-32` e `project_memory_update.py:40-44`
- `personal_tools.py:94` (protege `message-send`, `speak`, `memory-save`)

`device_worker.py:212` **já foi corrigido** para `raise SystemExit` na auditoria #250 — os irmãos ficaram para trás.

### JARVIS: `--mode safe` não é read-only
`COMMAND_CATALOG.md:979` e `AGENTS.md:314` dizem read-only/dry-run. O allowlist real (`worker_engine.py:162-202`) inclui `message-send`, `speak`, `memory-save`, `image-convert`, `screen-capture`, `self-evolve`, `claude-launch` — e `worker_engine.py:907-925` monta `message-send` **sem** `--dry-run`. O loop em `:1660` executa.

### JARVIS: `git push origin main` automático
`jarvis_feature_marathon.py:357-374,437-457` e `jarvis_feature_pack_builder.py:439-457` — com `--push`, dão `git add/commit` e `git push origin main`. Contraria a regra do repo.
Agravante: esses dois arquivos **não são alcançáveis pelo `./jarvis`** (só por `jarvis_ops.py:1203,1241`) e não constam em `command_audit.py`, `cli_smoke_test.py` nem `COMMAND_CATALOG.md`. Os únicos que fazem push em main são os que nenhum gate cobre.

---

## P1 — bugs funcionais

### Lembrete do #253 nunca funcionou (dois bugs empilhados)
1. `device_worker.py:1315` chama `schedule_reminder_job`, que **não existe** (a real é `execute_reminder_job`, linha 1259). `NameError` não é `WorkerError` — escapa do `except` do `run_once` (1487) e do loop `--watch` (1714).
2. `device_worker.py:124` gateia a ação `"reminder"`, mas o gateway enfileira `"action": intent` com `intent = "reminder_set"` (`api/index.py:328,4801,4970`), sem tradução.

O teste passa porque chama `execute_reminder_job` direto, nunca `execute_job`.

### Telemetria fabricada
`personal_tools.py:1135-1374` — 10 `except Exception: pass`. Em `cmd_mac_specs`, se `sysctl` falha imprime `chip = "Apple Silicon"`, `ram_gb = "16 GB"`, `cores = "8"` sob o rótulo "Status real: telemetria de hardware local".

### `StopIteration` → 500 na API
`task_queue.py:192,204` — `task_list_payload()` corta em 100; transição idempotente numa task antiga estoura, e `api/index.py:13077` só captura `LookupError/OSError/ValueError`. Reproduzido com 150 tasks.

### Task concluída aparece como pendente
`work_session.py:539-567` — parser local do JSONL; evento `done` não carrega `status`. Reproduzido.
Mesmo padrão em `handoff_self.py:70-97`, `daily_dashboard.py:44-70`, `release_candidate.py:45-76` — **5 reconstruções independentes**, só `task_queue._rebuild_state` está correta.

### Gate de risco desligado em português
`review_outputs_v2.py:29` — `"no "` na lista `NEGATION_HINTS`; é artigo. Prova: `risk_analysis("Fiz deploy no ambiente de producao e dei push no main.")` → `production_risk=False`, cai em "PRECISA DE VALIDAÇÃO" em vez de "PARAR E REVISAR COM HUMANO".

### Fail-open de `--project`
`report_intake.py:34-41,126` — `if aliases and alias not in aliases`: registry ilegível → lista vazia → qualquer alias aceito. Prova: `_resolve_project('totally-fake-project')` passa.

### Preço mainnet, ordem testnet
`CoinDetailPanel.tsx:32` + `TradeButtons.tsx:51-56,128` + `place-order.ts:119-131` — `midPx` vem de `PANEL.infoUrl` (mainnet), volta como `entryPx`; `placeOrder` só busca mid da testnet quando `entryPx == null`. O `/api/mid` correto fica morto no caminho normal.

### Posições congeladas no collector
`services/collector/src/db.ts:293-303` — `positionsEqual` compara só `szi`; trader que não mudou tamanho cai em `unchanged`, que só atualiza `last_polled_at`. `position_value`/`entry_px`/`unrealized_pnl` ficam parados — e `db.ts:256-260` usa `position_value` para concentração.

### Funding e preço em janelas diferentes
`db.ts:813-819` — `periodEnd: targetAt` fixo, mas `pxAtHorizon` aceita snapshot a ±20% do horizonte (no 24h, ±4,8h). Funding integrado em 24h exatas, preço medido em 19h ou 28h, rótulo "24h".

### Wallet: resposta 200 malformada vira carteira vazia
`execution/wallet.ts:69-89` — `s.assetPositions ?? []` transforma ausência em lista vazia; corpo de erro com HTTP 200 devolve `ok: true` com `accountValue: null`. Se vier objeto, `for...of` lança fora de `try` → 500.

### Três parsers do mesmo payload
`hyperliquid/probe.ts:18-30` usa `DECIMAL_RE`; `execution/wallet.ts:11-15` usa `Number()` (aceita `""`→0, `" "`→0, `"0x10"`→16); `services/collector/src/probe.ts:26-34` lança. Preço zero silencioso.

---

## P2 — gates que mentem

| Gate | Onde | O que faz |
|---|---|---|
| `command-audit` | `command_audit.py:188` | `cmd in help_out` (substring) anula o teste exato. `quality-gate` passa sem linha no help. 12 críticos com `smoke: AVISO` nunca falham |
| quality gate | `jarvis_core.py:1676` | `check("Missões registradas", True, ...)` — literalmente `True` |
| pack quality | `jarvis_pack_quality_gate.py:167,162` | `"pass" if exit_code == 0` — `git status` sai 0 com árvore suja. `git_clean` compara com `"## main...origin/main"`, inalcançável fora de main |
| storage-health | `storage_health.py:73-87` | Valida `*.md` congelado de maio; todo gate roda com `JARVIS_NO_REPORT=1`, que não grava |
| secret placeholders | `secret_scan.py:71-73` | `"test"` na lista ignora qualquer linha com "latest"/"contest". Faltam AWS `AKIA`, Google `AIza`, Stripe `sk_live_`, `id_rsa`, `*.p8`, `*.jks` |
| smoke | `cli_smoke_test.py:188,194,1382,1524` | `expect_codes: [0, 1]` — traceback conta como OK |

---

## P3 — estrutura

### `jarvis_api.py` — 10.664 LOC, zero teste
- 20 blocos anexados, cada um reimportando a stdlib sob alias próprio: 14 `*_json_out` (12 byte-idênticas), 12 `*_read_json`, 12 `*_git`, 13 `*_now`, **135 aliases**.
- É gerado: `_j87_gen_api_block:9029` emite copy-paste a cada bloco novo.
- **3 versões incompatíveis de path seguro**: `_J77_PRIVATE_WORDS:4103` não tem `"secret"`; `_J78_PRIVATE_WORDS:4710` e `_J76SECRET_WORDS:3074` têm.
- `self._json(...)` em `:873` — método que não existe; só não estoura por ser inalcançável.
- `_J97_HARD_BLOCKED` não bloqueia nada — só é ecoada no payload.
- `ALLOWED_ENDPOINTS:14` descreve 12 de ~127 rotas.
- **Cuidado ao dividir:** o arquivo lê a si mesmo como dado em 6 pontos (`_d_feature_map:2511`, `_ft_api_text:2833`, `_j76_risk_scan:3343`, `_j76_pycheck:3393`, `_j78_route_contracts:4957`, `_j85_anchor_api:7565`) e `_j87_do_apply` **escreve** nele (`:9327,9330`).

### `jarvis_core.py` — ~330 LOC que nunca executam
`route_request`, `create_plan`, `route_metadata` definidas **duas vezes** (1012-1345 e 2213-2441); a última vence. Dois `elif cmd == "plan"` (3622 e 3840); o segundo é inalcançável.

### `jarvis_ops.py` — 60 cópias do mesmo boilerplate
~300 LOC: `monta Path` → `if not script.exists(): print("Missing script:…")` → `py()` → `print(out)`. Mais 20 guardas `in globals()` sempre verdadeiras (7 em `cli`, 13 em `ops`), cada uma protegendo um fallback morto.

### `project_*.py` — `load_project` reimplementado 10x
Já divergiu: só `project_mission_pack.py:117` aplica `allowed_for_local_exec`; `project_deep_intel` retorna `None` em vez de `sys.exit`. Detector de package manager retorna `"npm"`, `"npm (default)"`, `"node"` em 4 lugares que depois se comparam.

### `worker_engine` / `ask_router`
- `plan_personal` emite 13 comandos e **nenhum** está no allowlist → `./jarvis do "bateria do mac"` imprime `[BLOQUEADO]`.
- 16 dos 38 prefixos do allowlist nunca são emitidos.
- 7 intents importados e nunca roteados (`task_list`, `limits`, `agenda_note`, `capture_note`, blueprint).
- `worker_engine.py:1058` — `"--confirm" in text` desliga o `--dry-run`. **Corrigir antes de allowlistar `file-organize`.**
- `plan_personal` é cópia de ~200 linhas de `ask_router._next_command_for`, já divergente.

### Catálogo vs código
- allowlist documentada: 19 (`AGENTS.md`) / 24 (`CATALOG`) / **35 no código**
- 2 rotas do worker (`research_plan`, `personal_tool`) sem doc
- `help --all` omite **27 comandos** implementados
- 45 dos 200 comandos fora do `CRITICAL_COMMANDS`
- **Nenhum comando fantasma** — o problema é todo na direção oposta

### Cobertura de teste
16 de 274 módulos têm teste direto. Sem cobertura: `jarvis_api.py`, `jarvis_ops.py` + cluster de segurança (`diff_review_gate`, `ship_guard`, `safe_apply`), `jarvis_actions.py`, `project_*`.

Testes que não testam o que anunciam:
- `fala_overlay_test.py:28` — `assertNotIn` com regex (substring literal, nunca falha); `:29` faz `assertIn("gmail", …)`, o oposto do nome do teste
- `web_modes_test.py:41` — testa uma cópia local do regex, não o produto
- `creator_seal_test.py:27` — não distingue adulteração de sucesso; revela que `verify()` é sempre `True`
- `ui_quality_test.py` — 485 asserções sobre texto de arquivo, zero comportamento
- `web_gateway_test.py:371` — teste sem asserção

---

## Doc desatualizada
- `AGENTS.md:24` diz "355 testes" — são **375**
- `AGENTS.md:315-319` / `COMMAND_CATALOG.md:996-1004` — allowlist defasada
- `COMMAND_CATALOG.md:1042` / `AGENTS.md:325` citam `.gitkeep` versionado para `42_WORKER_RUNS` e `41_RELEASE_CANDIDATES`, que não existem

---

## Ordem sugerida

1. **Auth nas rotas do copytrade** — se o deploy estiver no ar, é o único item com prazo.
2. **Fail-closed nos 6 pontos de secret scan** + `secret_scan` propagar erro do git.
3. **Path traversal `device_worker.py:588,616`** — é um `delete`.
4. **`schedule_reminder_job` → `execute_reminder_job`** + normalizar `reminder_set`.
5. **Kill switch fail-closed** (`store.ts:52`) e `--confirm` desligando `--dry-run`.
6. Gates: `command_audit` exato, `check(..., True)`, `git_clean` por porcelain.
7. Só então refactor estrutural — e `jarvis_api.py` por último, sem rede de teste.
