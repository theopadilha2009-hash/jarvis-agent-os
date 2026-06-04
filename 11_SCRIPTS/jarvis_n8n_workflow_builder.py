from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO / "05_EXECUCAO" / "204_N8N_WORKFLOW_BUILDER"
OUT_ROOT.mkdir(parents=True, exist_ok=True)

PROFESSIONAL_BLOCKS = [
    "Webhook/Input",
    "Normalize payload",
    "Anti-loop / dedupe",
    "Human pause / transfer guard",
    "Business rules by IF/Switch",
    "Context/memory lookup",
    "AI subjective response",
    "Structured output guard",
    "Fallback route",
    "Structured logs",
    "Error handler recommendation",
]

LOG_FIELDS = [
    "timestamp",
    "workflow_name",
    "execution_id",
    "client_id",
    "contact_id",
    "channel",
    "action",
    "status",
    "severity",
    "model_provider",
    "human_paused",
    "error_message_sanitized",
    "resolved_at",
]

def slugify(value: str, fallback: str = "workflow") -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.lower()).strip("-")
    return s[:80] or fallback

def detect_intent(goal: str) -> dict:
    g = goal.lower()

    channel = "whatsapp" if any(x in g for x in ["whatsapp", "wpp", "uazapi", "evolution"]) else "generic_webhook"
    needs_ai = any(x in g for x in ["ia", "ai", "agent", "agente", "llm", "chat"])
    needs_crm = any(x in g for x in ["crm", "pipedrive", "hubspot", "lead", "vendas", "pipeline"])
    needs_calendar = any(x in g for x in ["agenda", "agendamento", "calendar", "horario", "horário"])
    needs_followup = any(x in g for x in ["follow", "follow-up", "retorno", "nutri", "nurture"])
    needs_handoff = any(x in g for x in ["humano", "human", "transfer", "chatwoot", "atendente"])

    return {
        "channel": channel,
        "needs_ai": needs_ai or True,
        "needs_crm": needs_crm,
        "needs_calendar": needs_calendar,
        "needs_followup": needs_followup,
        "needs_handoff": needs_handoff or True,
    }

def build_architecture(goal: str, client: str) -> dict:
    intent = detect_intent(goal)

    subflows = [
        {
            "name": "Main Conversation Orchestrator",
            "purpose": "Recebe evento, normaliza, controla pausa/anti-loop, chama IA e decide rota.",
            "status_real": "spec_only",
        },
        {
            "name": "Send Message Tool",
            "purpose": "Envia mensagem via API do canal com credenciais no n8n, nunca no JSON.",
            "status_real": "spec_only",
        },
        {
            "name": "Log Event Tool",
            "purpose": "Registra execução, status, erro sanitizado, contato e ação.",
            "status_real": "spec_only",
        },
        {
            "name": "Human Transfer Tool",
            "purpose": "Cria nota/label/pausa no Chatwoot ou fila humana quando necessário.",
            "status_real": "spec_only",
        },
    ]

    if intent["needs_calendar"]:
        subflows.append({
            "name": "Calendar Scheduling Tool",
            "purpose": "Criar/editar/cancelar agenda salvando calendar_event_id no banco.",
            "status_real": "spec_only",
        })

    if intent["needs_followup"]:
        subflows.append({
            "name": "Follow-up Scheduler",
            "purpose": "Rodar em horário comercial, limitar tentativas e parar se lead respondeu/humano assumiu.",
            "status_real": "spec_only",
        })

    tables = [
        {
            "table": "contacts",
            "fields": ["id", "client_id", "channel", "remote_id", "name", "phone", "human_paused", "created_at", "updated_at"],
        },
        {
            "table": "conversation_state",
            "fields": ["id", "contact_id", "stage", "intent", "last_message_at", "summary", "updated_at"],
        },
        {
            "table": "automation_logs",
            "fields": LOG_FIELDS,
        },
    ]

    if intent["needs_calendar"]:
        tables.append({
            "table": "appointments",
            "fields": ["id", "contact_id", "calendar_event_id", "status", "start_at", "end_at", "created_at", "updated_at"],
        })

    return {
        "client": client,
        "goal": goal,
        "intent": intent,
        "architecture_rule": "IA handles subjective decisions. n8n handles fixed rules, state, logs, fallback, sending, Error Trigger and human transfer.",
        "professional_blocks": PROFESSIONAL_BLOCKS,
        "subflows": subflows,
        "database_tables": tables,
        "guardrails": [
            "No credentials/tokens inside JSON.",
            "Workflow skeleton must stay active=false.",
            "Human approval before real send, deploy, webhook production, or client data.",
            "Sanitize logs before alerts.",
            "Use placeholders for URLs and credentials.",
            "Save external IDs for future edit/cancel actions.",
        ],
        "test_checklist": [
            "JSON imports without credentials.",
            "Webhook receives mock payload.",
            "Normalize node produces contact_id/channel/message_text.",
            "Anti-loop blocks fromMe/track_source=n8n.",
            "Human paused contact does not receive AI response.",
            "AI output is structured or fallback route catches it.",
            "Log path records every main action.",
            "Send path is dry-run/mock before real API.",
            "Error Trigger workflow is created separately.",
        ],
        "status_real": "spec_and_skeleton_only_not_production",
    }

def node(node_id: str, name: str, ntype: str, x: int, y: int, parameters: dict | None = None) -> dict:
    return {
        "parameters": parameters or {},
        "id": node_id,
        "name": name,
        "type": ntype,
        "typeVersion": 1,
        "position": [x, y],
    }

def build_n8n_skeleton(goal: str, client: str) -> dict:
    safe_name = f"JARVIS n8n Builder v1 - {client} - {slugify(goal)[:35]}"

    nodes = [
        node("sticky_1", "README - Status Real", "n8n-nodes-base.stickyNote", -760, -260, {
            "content": "Generated by JARVIS n8n Workflow Builder v1\\nStatus: skeleton/spec only. active=false. No credentials. Not production validated."
        }),
        node("webhook_1", "Webhook IN - Placeholder", "n8n-nodes-base.webhook", -760, 20, {
            "path": f"{slugify(client)}-inbound-placeholder",
            "httpMethod": "POST",
            "responseMode": "responseNode",
        }),
        node("set_normalize", "Normalize Payload", "n8n-nodes-base.set", -520, 20, {
            "values": {
                "string": [
                    {"name": "client_id", "value": client},
                    {"name": "channel", "value": "={{$json.channel || 'whatsapp'}}"},
                    {"name": "contact_id", "value": "={{$json.phone || $json.remoteJid || $json.from || 'unknown'}}"},
                    {"name": "message_text", "value": "={{$json.text || $json.message || $json.body || ''}}"},
                    {"name": "track_source", "value": "={{$json.track_source || ''}}"}
                ],
                "boolean": [
                    {"name": "from_me", "value": "={{$json.fromMe || false}}"}
                ]
            },
            "options": {},
        }),
        node("if_antiloop", "Anti-loop Guard", "n8n-nodes-base.if", -280, 20, {
            "conditions": {
                "boolean": [
                    {"value1": "={{$json.from_me}}", "value2": False}
                ],
                "string": [
                    {"value1": "={{$json.track_source}}", "operation": "notEqual", "value2": "n8n"}
                ]
            },
            "combineOperation": "all",
        }),
        node("set_context", "Load Context / Redis/Postgres Memory Placeholder", "n8n-nodes-base.set", -20, -80, {
            "values": {
                "string": [
                    {"name": "context_status", "value": "TODO: replace with Redis/Postgres/Supabase memory lookup"},
                    {"name": "redis_memory_status", "value": "TODO: Redis buffer/debounce/human pause"},
                    {"name": "postgres_state_status", "value": "TODO: Postgres/Supabase conversation_state"},
                    {"name": "human_paused", "value": "false"}
                ]
            },
        }),
        node("if_human", "Human Pause Guard", "n8n-nodes-base.if", 220, -80, {
            "conditions": {
                "string": [
                    {"value1": "={{$json.human_paused}}", "operation": "notEqual", "value2": "true"}
                ]
            }
        }),
        node("set_ai", "AI Agent Placeholder", "n8n-nodes-base.set", 480, -160, {
            "values": {
                "string": [
                    {"name": "ai_response", "value": "TODO: connect AI Agent / Structured Output Parser here"},
                    {"name": "confidence", "value": "0.70"}
                ]
            },
        }),
        node("if_confidence", "Confidence / Fallback / Error Guard", "n8n-nodes-base.if", 740, -160, {
            "conditions": {
                "number": [
                    {"value1": "={{Number($json.confidence || 0)}}", "operation": "largerEqual", "value2": 0.65}
                ]
            }
        }),
        node("set_send", "Build Send Payload - Dry Run", "n8n-nodes-base.set", 1000, -240, {
            "values": {
                "string": [
                    {"name": "send_status", "value": "dry_run_only"},
                    {"name": "number", "value": "={{$json.contact_id}}"},
                    {"name": "text", "value": "={{$json.ai_response}}"},
                    {"name": "track_source", "value": "n8n"}
                ]
            }
        }),
        node("set_handoff", "Human Transfer / Chatwoot Handoff Placeholder", "n8n-nodes-base.set", 1000, -20, {
            "values": {
                "string": [
                    {"name": "handoff_required", "value": "true"},
                    {"name": "human_transfer", "value": "TODO: create Chatwoot note/label and pause AI"},
                    {"name": "handoff_reason", "value": "low_confidence_or_human_paused"}
                ]
            }
        }),
        node("set_log", "Structured Log Placeholder - Supabase/Postgres Log", "n8n-nodes-base.set", 1260, -140, {
            "values": {
                "string": [
                    {"name": "log_status", "value": "TODO: write to Supabase/Postgres automation_logs"},
                    {"name": "log_action", "value": "conversation_or_handoff_or_fallback"},
                    {"name": "fallback_status", "value": "fallback_checked"},
                    {"name": "human_transfer_status", "value": "human_transfer_checked"},
                    {"name": "dry_run_safety", "value": "dry_run_only_until_human_approval"},
                    {"name": "status_real", "value": "skeleton_only_not_production"}
                ]
            }
        }),
        node("respond", "Respond to Webhook", "n8n-nodes-base.respondToWebhook", 1500, -140, {
            "responseBody": "={{ { ok: true, status_real: 'skeleton_only', client_id: $json.client_id, contact_id: $json.contact_id } }}",
            "options": {},
        }),
    ]

    connections = {
        "Webhook IN - Placeholder": {"main": [[{"node": "Normalize Payload", "type": "main", "index": 0}]]},
        "Normalize Payload": {"main": [[{"node": "Anti-loop Guard", "type": "main", "index": 0}]]},
        "Anti-loop Guard": {"main": [[{"node": "Load Context / Redis/Postgres Memory Placeholder", "type": "main", "index": 0}], [{"node": "Structured Log Placeholder - Supabase/Postgres Log", "type": "main", "index": 0}]]},
        "Load Context / Redis/Postgres Memory Placeholder": {"main": [[{"node": "Human Pause Guard", "type": "main", "index": 0}]]},
        "Human Pause Guard": {"main": [[{"node": "AI Agent Placeholder", "type": "main", "index": 0}], [{"node": "Human Transfer / Chatwoot Handoff Placeholder", "type": "main", "index": 0}]]},
        "AI Agent Placeholder": {"main": [[{"node": "Confidence / Fallback / Error Guard", "type": "main", "index": 0}]]},
        "Confidence / Fallback / Error Guard": {"main": [[{"node": "Build Send Payload - Dry Run", "type": "main", "index": 0}], [{"node": "Human Transfer / Chatwoot Handoff Placeholder", "type": "main", "index": 0}]]},
        "Build Send Payload - Dry Run": {"main": [[{"node": "Structured Log Placeholder - Supabase/Postgres Log", "type": "main", "index": 0}]]},
        "Human Transfer / Chatwoot Handoff Placeholder": {"main": [[{"node": "Structured Log Placeholder - Supabase/Postgres Log", "type": "main", "index": 0}]]},
        "Structured Log Placeholder - Supabase/Postgres Log": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
    }

    return {
        "name": safe_name,
        "nodes": nodes,
        "pinData": {},
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1"
        },
        "versionId": "jarvis-builder-v1",
        "meta": {
            "generated_by": "jarvis_n8n_workflow_builder.py",
            "status_real": "skeleton_only_not_production",
            "credentials_included": False,
            "requires_human_validation": True,
        },
        "tags": ["jarvis", "skeleton", "not-production", "logs", "fallback", "human-transfer", "dry-run"],
    }

def write_outputs(goal: str, client: str) -> dict:
    created_at = datetime.now().isoformat(timespec="seconds")
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slugify(client)}_{slugify(goal)}"
    out = OUT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    architecture = build_architecture(goal, client)
    workflow = build_n8n_skeleton(goal, client)

    payload = {
        "created_at": created_at,
        "verdict": "pass",
        "goal": goal,
        "client": client,
        "architecture": architecture,
        "workflow_file": "workflow_skeleton.importable.json",
        "status_real": "generated_spec_and_skeleton_only",
    }

    (out / "builder_report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "workflow_skeleton.importable.json").write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [
        "# JARVIS n8n Workflow Builder v1",
        "",
        f"Created at: `{created_at}`",
        f"Client: `{client}`",
        f"Goal: `{goal}`",
        "",
        "## Status real",
        "",
        "- Generated spec and importable skeleton only.",
        "- active=false.",
        "- No credentials included.",
        "- Not tested in n8n.",
        "- Not production validated.",
        "",
        "## Architecture rule",
        "",
        architecture["architecture_rule"],
        "",
        "## Professional blocks",
        "",
    ]

    for b in architecture["professional_blocks"]:
        md.append(f"- {b}")

    md += ["", "## Subflows/tools", ""]

    for s in architecture["subflows"]:
        md.append(f"- **{s['name']}**: {s['purpose']}")

    md += ["", "## Database/log model", ""]

    for t in architecture["database_tables"]:
        md.append(f"### {t['table']}")
        for f in t["fields"]:
            md.append(f"- {f}")
        md.append("")

    md += ["## Guardrails", ""]

    for g in architecture["guardrails"]:
        md.append(f"- {g}")

    md += ["", "## Test checklist", ""]

    for c in architecture["test_checklist"]:
        md.append(f"- [ ] {c}")

    md += [
        "",
        "## Generated files",
        "",
        "- `builder_report.json`",
        "- `workflow_skeleton.importable.json`",
        "",
        "## Claude/n8n prompt",
        "",
        "```text",
        f"""Use this generated spec to build a professional n8n workflow.

Goal:
{goal}

Rules:
- Do not include credentials in JSON.
- Keep workflow inactive until configured and tested.
- Use n8n for fixed rules, logs, state, fallback and sending.
- Use AI only for subjective response/intent/tone.
- Add human transfer guard.
- Add structured logs and Error Trigger recommendation.
- Return status real: created/imported/configured/tested/validated/production.
""",
        "```",
        "",
        "Status real: source-backed builder output. No production touched.",
    ]

    (out / "WORKFLOW_BUILDER.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    return {
        "out": str(out.relative_to(REPO)),
        "report": str((out / "WORKFLOW_BUILDER.md").relative_to(REPO)),
        "workflow": str((out / "workflow_skeleton.importable.json").relative_to(REPO)),
        "payload": payload,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS n8n Workflow Builder v1")
    parser.add_argument("goal", nargs="*", help="workflow goal")
    parser.add_argument("--client", default="demo-client")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip()
    if not goal:
        goal = "professional WhatsApp AI workflow with logs fallback and human transfer"

    result = write_outputs(goal=goal, client=args.client)

    print("N8N_WORKFLOW_BUILDER_DONE")
    print(result["report"])
    print(json.dumps({
        "verdict": result["payload"]["verdict"],
        "client": args.client,
        "goal": goal,
        "workflow": result["workflow"],
        "status_real": result["payload"]["status_real"],
    }, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
