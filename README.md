<p align="center">
  <img src="assets/jarvis-purple-presence.jpg" alt="JARVIS purple cognitive presence" width="560">
</p>

<h1 align="center">JARVIS Agent OS</h1>

<p align="center">
  A personal AI operations system built by Theo Padilha for controlled execution, project context, memory, planning, and human-approved automation.
</p>

<p align="center">
  <a href="https://github.com/theopadilha2009-hash/jarvis-agent-os"><img src="https://img.shields.io/badge/status-active-7c3aed" alt="Status: active"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/runtime-Python-6d28d9" alt="Runtime: Python"></a>
  <a href="https://vercel.com/"><img src="https://img.shields.io/badge/web-Vercel-4c1d95" alt="Web: Vercel"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-proprietary-2e1065" alt="License: proprietary"></a>
</p>

> [!IMPORTANT]
> JARVIS is Theo Padilha's personal local AI worker and operational cockpit. It is not a multi-tenant product. External actions, production changes, credentials, and destructive operations require explicit human approval.

<!-- JARVIS_FOUNDATION_START -->
## Foundation

JARVIS turns natural-language requests into structured work: context discovery, safe plans, bounded execution, persistent runs, evidence, memory updates, and clear human handoffs.

The system combines a local-first command line, a web cockpit, a serverless HTTP gateway, and an allowlisted Mac worker. The hosted interface never imports the local backend that writes arbitrary files or starts unrestricted processes.

### System components

| Component | Responsibility |
| --- | --- |
| Local CLI | Daily cockpit, project routing, task lifecycle, diagnostics, gates, reports, and safe worker execution |
| Web cockpit | Conversation workspace, actions, run history, memory, tasks, files, voice controls, and system status |
| Serverless gateway | Typed HTTP contract for the web interface and approved integrations |
| Mac worker | Executes a restricted set of paired computer actions and returns evidence |
| Memory layer | Confirmed Markdown as source of truth, optional SQLite search, and optional Supabase persistence |
| Action registry | Shared definitions for actions, risks, confirmations, and executors |

### Operating modes

- `PERSONAL_MODE`: Theo's personal projects and workflows
- `WORK_ASSIST_MODE`: sanitized assistance for company work
- `FUTURE_COMPANY_MODE`: reserved boundary for a possible official company version

### Runtime V10

The web cockpit uses a compact purple cognitive presence as the visual core. Conversation is the primary workspace, while actions, memory, runs, tasks, and evidence remain available without turning the interface into a generic chatbot dashboard.

- Responses stream progressively over NDJSON.
- Runs persist plans, events, results, and evidence.
- External actions and self-editing stop for explicit confirmation.
- The 3D core loads only on suitable screens and hardware.
- Reduced-motion, mobile, and data-saving modes use a static purple mark.
- Background rendering pauses when the cockpit is outside the viewport.
- The command center provides keyboard-driven access to real actions.
- Offline requests remain visibly queued instead of being reported as completed.
- Voice supports interruption and reports provider failures honestly.

### Deterministic personal context

`GET /personal-overview` assembles conversation state, memory, agenda, Mac worker status, and recent activity. Requests such as "what can you do?" or "summarize my day" use this real state instead of asking a model to invent capabilities.

### Optional integrations

| Integration | Purpose | Required configuration |
| --- | --- | --- |
| OpenRouter | Free-model pool and text synthesis | `OPENROUTER_API_KEY` |
| ElevenLabs | Hosted voice synthesis | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` |
| Supabase | Persistent memories, tasks, runs, and worker queue | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| n8n | Approved task and agenda workflows | `N8N_WEBHOOK_URL`, optional `N8N_WEBHOOK_TOKEN` |
| Gmail | Explicit owner-approved email sending | `JARVIS_GMAIL_APP_PASSWORD` |
| Owner pairing | Protects memory, agenda, and Mac commands | `JARVIS_OWNER_TOKEN` |

No credential belongs in the repository. Missing integrations degrade explicitly to local, text, preview, or refusal modes.
<!-- JARVIS_FOUNDATION_END -->

## Core workflow

```text
Request
  -> intent and project resolution
  -> safety classification
  -> plan or bounded action
  -> evidence and real status
  -> human approval when required
  -> memory and lifecycle update
```

The standard local loop is:

```bash
./jarvis resume
./jarvis work-start "describe the goal"
./jarvis work-next
./jarvis report-check --file /tmp/jarvis-claude-out.md
./jarvis report-apply --file /tmp/jarvis-claude-out.md
./jarvis gate-run
./jarvis work-close
```

## Quick start

Requirements:

- macOS for the complete local-worker experience
- Python 3
- Bash
- Claude Code only when a generated mission requires manual model execution

```bash
git clone https://github.com/theopadilha2009-hash/jarvis-agent-os.git
cd jarvis-agent-os
chmod +x ./jarvis
./jarvis first-run-check
./jarvis daily
```

Start the local HTTP preview:

```bash
python3 api/index.py --port 8790
```

`./jarvis web` prints the address. The browser opens only when `./jarvis web --open` is used.

## Primary commands

| Command | Purpose |
| --- | --- |
| `./jarvis daily` | Compact start-of-day dashboard |
| `./jarvis go "request"` | Route a request and prepare the next safe action |
| `./jarvis do "request"` | Run the bounded local worker engine |
| `./jarvis now` | Resume the current lifecycle |
| `./jarvis next` | Print the single next safe command |
| `./jarvis health` | Diagnose the JARVIS environment |
| `./jarvis project-cockpit --project ALIAS` | Show project status, mission, and next action |
| `./jarvis task-list` | Show pending, blocked, and completed tasks |
| `./jarvis run-list` | List persistent run packages |
| `./jarvis capabilities` | Show available, manual, blocked, and future capabilities |
| `./jarvis gates` | Run safety, smoke, and doctrine validation |
| `./jarvis handoff-self` | Produce a sanitized operational handoff |

Run `./jarvis cheatsheet` for the compact command catalog or read [AGENTS.md](AGENTS.md) for the complete operational contract.

## Safety model

- The worker uses a narrow allowlist and never accepts arbitrary shell commands.
- Risky actions require an explicit confirmation boundary.
- A queued request is not reported as completed.
- Failed dependencies stop subsequent run steps.
- Runtime state, generated reports, work sessions, and private caches are gitignored.
- Secret scanning, storage checks, smoke tests, and doctrine checks are part of the release gate.
- The hosted cockpit cannot directly control the Mac without an authenticated paired worker.

## Project structure

| Path | Contents |
| --- | --- |
| `00_IDENTITY/` | Identity, modes, doctrine, and research lessons |
| `01_SISTEMA/` | System rules, command catalog, registries, and decision logic |
| `03_MEMORIA/` | Confirmed project and operational memory |
| `04_PROJETOS/` | Project-specific status and next actions |
| `05_EXECUCAO/` | Missions, runs, work sessions, gates, and worker artifacts |
| `07_RELATORIOS/` | Generated reports and validation evidence |
| `09_LOGS/` | Structured logs |
| `10_TESTES/` | Test assets and acceptance material |
| `11_SCRIPTS/` | Python implementation of the local JARVIS runtime |
| `api/` | Serverless gateway and local HTTP preview |
| `web/` | Cockpit interface and visual assets |
| `supabase/` | Database migrations and persistence setup |

## Validation

```bash
bash -n ./jarvis
./jarvis command-audit
env JARVIS_NO_REPORT=1 ./jarvis smoke-test
env JARVIS_NO_REPORT=1 ./jarvis safety-gate
./jarvis release-check
```

Checks must report real results. No untested build, prepared integration, queued action, or unverified deployment is described as completed.

## Status

JARVIS is an active personal lab with a local CLI, evolving web cockpit, persistent run lifecycle, project memory, bounded worker engine, and optional external integrations. Availability of hosted voice, model inference, persistent cloud memory, email, and n8n depends on the corresponding environment configuration and service quota.

## Support development

- [GitHub Sponsors](https://github.com/sponsors/theopadilha2009-hash)
- [Patreon](https://www.patreon.com/c/TheoPadilha)

## Author and license

Created and maintained by [Theo Lorentz Padilha](https://github.com/theopadilha2009-hash).

Copyright 2026 Theo Lorentz Padilha. All rights reserved. This repository is source-available under the terms in [LICENSE](LICENSE); copying, redistribution, rebranding, hosted derivatives, prompt extraction, and model training are not permitted without prior written authorization.
