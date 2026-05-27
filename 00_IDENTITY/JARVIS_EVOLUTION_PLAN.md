# JARVIS Evolution Plan

## Goal

Evolve JARVIS from a safe local assistant into Theo's personal AI operating layer.

JARVIS must work without Claude by default, but stay ready to use Claude later as an optional executor.

## Current foundation

JARVIS already has:

- private GitHub sync;
- home/school branch workflow;
- safety gate;
- secret scan;
- quality gate;
- no-Claude package generation;
- task queue;
- blueprint generation;
- identity and modes;
- research sources for n8n, agents and production architecture.

## Main problem now

JARVIS can classify research/foundation requests, but `./jarvis do` is still too conservative.

Expected behavior:

`./jarvis do "criar plano usando deep research"`

Should call:

`./jarvis blueprint --type research --goal "..."`

Instead of falling back to:

`./jarvis no-claude "..."`

## Architecture lessons from research

JARVIS should guide automation design using this pattern:

1. Main workflow orchestrates.
2. Sub-workflows execute focused tasks.
3. AI outputs structured JSON.
4. Code/tool nodes execute actions.
5. Postgres stores persistent state and logs.
6. Redis stores only temporary state, locks and cache.
7. Chatwoot handles inbox and human support.
8. n8n handles workflow logic.
9. Error Trigger handles failures.
10. Monitoring checks uptime, errors and infrastructure health.

## Next implementation phases

### Phase 1 — Fix routing

Make `./jarvis do` obey these intents directly:

- `research_plan` → `./jarvis blueprint --type research`
- `n8n_blueprint` → `./jarvis blueprint --type n8n`
- `automation_blueprint` → `./jarvis blueprint --type automation`
- `app_blueprint` → `./jarvis blueprint --type app`

### Phase 2 — Builder mode

Create:

`./jarvis build "project idea"`

Expected output:

- local project folder;
- README;
- STATUS_REAL;
- source files;
- validation checklist;
- next steps.

### Phase 3 — Research ingestion

Make JARVIS read local source folders and generate distilled lessons.

Target:

`./jarvis research-digest 02_SOURCES/DEEP_RESEARCH`

Expected output:

- summary;
- reusable rules;
- architecture checklist;
- project ideas;
- risks.

### Phase 4 — Agent architecture assistant

Make JARVIS generate professional n8n agent plans with:

- main workflow;
- subflows;
- database schema;
- memory design;
- logging;
- Error Trigger;
- test plan;
- production checklist.

### Phase 5 — Tool adapters

Future adapters start read-only or dry-run:

- GitHub;
- n8n;
- SSH/Termius;
- browser/Playwright;
- Chatwoot;
- Supabase/Postgres;
- local vault/keychain.

## Hard rule

JARVIS must never turn research into production action directly.

Research → plan → local artifact → validation → human approval → only then execution.
