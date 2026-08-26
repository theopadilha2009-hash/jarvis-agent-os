<p align="center">
  <img src="assets/jarvis-purple-presence.png" alt="JARVIS purple cognitive presence" width="430">
</p>

<h1 align="center">JARVIS Agent OS</h1>

<p align="center">
  Personal AI operations system built by Theo Padilha.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-active-7c3aed" alt="Status: active">
  <img src="https://img.shields.io/badge/runtime-Python-6d28d9" alt="Runtime: Python">
  <img src="https://img.shields.io/badge/platform-macOS-4c1d95" alt="Platform: macOS">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-proprietary-2e1065" alt="License: proprietary"></a>
</p>

> [!IMPORTANT]
> Personal, local-first project. External actions, production changes, credentials, and destructive operations require explicit human approval.

<!-- JARVIS_FOUNDATION_START -->
## Overview

JARVIS transforms natural-language requests into project context, safe plans, bounded actions, persistent runs, evidence, and memory updates.

It combines:

- A local command-line cockpit
- A web workspace with conversation, tasks, runs, files, memory, and voice
- A serverless API gateway
- An allowlisted Mac worker
- Optional OpenRouter, ElevenLabs, Supabase, n8n, and Gmail integrations

Missing integrations fall back honestly to local, text, preview, or refusal modes. No credential belongs in the repository.
<!-- JARVIS_FOUNDATION_END -->

## Core workflow

```text
Request -> context -> safety check -> plan or action -> evidence -> memory
```

The worker never accepts arbitrary shell commands. Risky actions stop for confirmation, and queued work is never reported as completed.

## Quick start

```bash
git clone https://github.com/theopadilha2009-hash/jarvis-agent-os.git
cd jarvis-agent-os
chmod +x ./jarvis
./jarvis first-run-check
./jarvis daily
```

Local web preview:

```bash
python3 api/index.py --port 8790
```

## Main commands

| Command | Purpose |
| --- | --- |
| `./jarvis daily` | Start-of-day cockpit |
| `./jarvis go "request"` | Route a request and prepare the next safe action |
| `./jarvis do "request"` | Run the bounded local worker |
| `./jarvis next` | Show the single next safe command |
| `./jarvis health` | Diagnose the JARVIS environment |
| `./jarvis capabilities` | Show available and blocked capabilities |
| `./jarvis gates` | Run safety, smoke, and doctrine checks |

See [AGENTS.md](AGENTS.md) for the complete operational contract.

## Structure

- `01_SISTEMA/`: rules, commands, registries, and decision logic
- `03_MEMORIA/`: confirmed operational memory
- `04_PROJETOS/`: project status and next actions
- `05_EXECUCAO/`: missions, runs, sessions, and gates
- `11_SCRIPTS/`: Python runtime
- `api/`: HTTP gateway
- `web/`: web cockpit
- `supabase/`: persistence migrations

## Support

- [GitHub Sponsors](https://github.com/sponsors/theopadilha2009-hash)
- [Patreon](https://www.patreon.com/c/TheoPadilha)

## Author and license

Created by [Theo Lorentz Padilha](https://github.com/theopadilha2009-hash).

Copyright 2026 Theo Lorentz Padilha. All rights reserved. See [LICENSE](LICENSE).
