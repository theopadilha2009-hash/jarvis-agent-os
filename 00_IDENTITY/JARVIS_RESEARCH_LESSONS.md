# JARVIS Research Lessons

## Source: AI agents, n8n and production automation reports

These lessons define how JARVIS should reason about professional automation architecture.

## Core principles

1. Big workflows should be split into smaller sub-workflows.
2. The main workflow should orchestrate, not do everything.
3. AI should produce structured JSON when the result will trigger actions.
4. Code or tool nodes should execute actions, not the LLM directly.
5. Error Trigger workflows should be standard in production n8n.
6. Postgres is the default for persistent memory and logs.
7. PGVector is preferred before adding a separate vector DB.
8. Redis should be used for temporary cache, locks and short-lived state, not permanent history.
9. Chatwoot should handle inbox/human support; n8n should handle logic.
10. Monitoring should include uptime, error logs, failed executions and infrastructure health.

## Agent architecture

Good agents are not one giant prompt.

Preferred pattern:

- conversation/router workflow;
- specialist sub-workflows;
- structured output;
- database state;
- human transfer;
- error workflow;
- logs and status real.

## JARVIS implication

JARVIS should help Theo design systems in this order:

1. define objective;
2. define data/state;
3. define main workflow;
4. define subflows/tools;
5. define safety gates;
6. define logs and monitoring;
7. define test path;
8. only then think about production.

## Modes impact

### PERSONAL_MODE

Use simpler/free-first versions:
- local files;
- SQLite/Postgres if needed;
- no paid API by default;
- dry-run first.

### WORK_ASSIST_MODE

Use professional patterns:
- n8n subflows;
- Postgres/Supabase;
- Redis temporary state;
- Chatwoot human handoff;
- Error Trigger;
- logs;
- no production changes without approval.

### FUTURE_COMPANY_MODE

Needs:
- permission model;
- vault;
- audit logs;
- staging;
- owner;
- security review;
- official approval.
