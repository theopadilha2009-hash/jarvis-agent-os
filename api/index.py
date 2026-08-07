#!/usr/bin/env python3
"""JARVIS web gateway for Vercel and local HTTP verification.

The desktop API is intentionally not imported here: it owns local files and
processes, while a Vercel Function is stateless and cannot control the owner's
Mac. This gateway keeps the cockpit useful on the web and hands device actions
back to the local worker explicitly.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen
import argparse
from datetime import datetime, timezone
import hmac
import json
import mimetypes
import os
import re
import shlex
import subprocess
import threading
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
UI_FILE = WEB_DIR / "index.html"
UI_ASSET_DIR = ROOT / "11_SCRIPTS" / "jarvis_ui_assets"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_ELEVENLABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"
DEFAULT_ELEVENLABS_MODEL = "eleven_multilingual_v2"
MAX_BODY_BYTES = 32_768
MAX_PROMPT_CHARS = 8_000
SUPABASE_MEMORY_TABLE = "jarvis_memories"
SUPABASE_DEVICE_COMMANDS_TABLE = "jarvis_device_commands"
SUPABASE_DEVICE_WORKERS_TABLE = "jarvis_device_workers"
REMOTE_DEVICE_INTENTS = {"open_application", "close_application", "system_memory"}
MEMORY_KIND_LABELS = {
    "learning": "APRENDIZADOS",
    "decision": "DECISOES",
    "preference": "PREFERENCIAS",
    "context": "CONTEXTO",
}

ASSET_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".ico": "image/x-icon",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}

BASE_WEB_CAPABILITIES = [
    {
        "name": "cockpit_web",
        "status": "available",
        "what": "Cockpit visual acessível pelo navegador.",
    },
    {
        "name": "assistant_chat",
        "status": "configured" if bool(os.environ.get("OPENROUTER_API_KEY")) else "needs_environment",
        "what": "Conversa via OpenRouter usando o roteador de modelos gratuitos.",
    },
    {
        "name": "assistant_voice",
        "status": "available",
        "what": "Entrada por voz no navegador e saída ElevenLabs quando a chave estiver configurada.",
    },
    {
        "name": "feature_planning",
        "status": "available",
        "what": "Planos, briefs, checklists e triagem sem escrita persistente.",
    },
    {
        "name": "local_worker_handoff",
        "status": "available",
        "what": "Transforma pedidos de dispositivo em comandos explícitos para o worker local.",
    },
    {
        "name": "persistent_memory",
        "status": "available_on_local_worker",
        "what": "Grava memória local ou persistente no Supabase e atualiza a constelação visual.",
    },
    {
        "name": "mac_messages",
        "status": "available_on_local_worker",
        "what": "Envia mensagens explícitas pelo app Mensagens do macOS.",
    },
    {
        "name": "n8n_agenda",
        "status": "needs_environment",
        "what": "Agenda e tarefas por webhook n8n configurado pelo operador.",
    },
]

APPLICATION_INTENT_PATTERNS = {
    "open_application": re.compile(
        r"^\s*(?:jarvis[,\s]+)?(?:abr(?:a|e|ir)|inici(?:a|e|ar))\s+(?:o\s+|a\s+)?(?:app(?:licativo)?\s+)?(?P<app>[\wÀ-ÿ ._-]{2,80}?)(?:\s+(?:por\s+favor|pra\s+mim|para\s+mim))?[.!?]*\s*$",
        re.I,
    ),
    "close_application": re.compile(
        r"^\s*(?:jarvis[,\s]+)?(?:fech(?:a|e|ar)|encerr(?:a|e|ar)|sai(?:a|r)\s+d[oa])\s+(?:o\s+|a\s+)?(?:app(?:licativo)?\s+)?(?P<app>[\wÀ-ÿ ._-]{2,80}?)(?:\s+(?:por\s+favor|pra\s+mim|para\s+mim))?[.!?]*\s*$",
        re.I,
    ),
}

APPLICATION_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "código": "Visual Studio Code",
    "mensagens": "Messages",
}

LOCAL_INTENTS = (
    (re.compile(r"\b(tir(?:a|e|ar)|captur(?:a|e|ar)|faz(?:er)?)\b.{0,40}\b(print|screenshot|tela)\b", re.I), "screen_capture"),
    (re.compile(r"\b(ler em voz alta|falar no mac|dizer no mac)\b", re.I), "speak"),
    (re.compile(r"\b(convert(?:a|er)|transform(?:a|ar))\b.{0,60}\b(imagem|foto|png|jpe?g|heic|tiff)\b", re.I), "image_convert"),
    (re.compile(r"\b(mensagem\s+(?:no|pelo)\s+whatsapp|whatsapp\s+para|rascunho\s+de\s+mensagem)\b", re.I), "message_draft"),
    (re.compile(r"\b(mand(?:a|ar)|envi(?:a|ar)|escrev(?:a|er))\b.{0,40}\b(mensagem|msg)\b", re.I), "message_send"),
    (re.compile(r"\b(guard(?:a|e|ar)|salv(?:a|e|ar)|registr(?:a|e|ar)|grav(?:a|e|ar)|lembr(?:a|e|ar))\b.{0,100}\b(mem[oó]ria|prefer[eê]ncia|aprendizado|decis[aã]o)\b", re.I), "memory_save"),
    (re.compile(r"\b(coloc(?:a|ar)|adicion(?:a|ar)|marc(?:a|ar))\b.{0,100}\b(agenda|lembrete)\b", re.I), "agenda_note"),
    (re.compile(r"\b(ver|mostr(?:a|ar)|list(?:a|ar)|consult(?:a|ar))\b.{0,80}\b(agenda|compromissos|eventos)\b", re.I), "agenda_view"),
    (re.compile(r"\b(anot(?:a|ar)|captur(?:a|ar)|registr(?:a|ar))\b.{0,100}\b(ideia|inbox|nota)\b", re.I), "capture_note"),
    (re.compile(r"\b(adicion(?:a|ar)|cri(?:a|ar))\b.{0,60}\b(tarefa|task)\b", re.I), "task_add"),
    (re.compile(r"\b(abr(?:e|ir))\b.{0,40}\b(projeto|oficina|jarvis|gc|ls)\b", re.I), "open_project"),
    (APPLICATION_INTENT_PATTERNS["open_application"], "open_application"),
    (APPLICATION_INTENT_PATTERNS["close_application"], "close_application"),
    (re.compile(r"(?:\b(computador|mac|mem[oó]ria|ram)\b.{0,80}\b(trav(?:a|ando)|lent[oa]|pesad[oa]|limp(?:a|ar))\b|\b(limp(?:a|ar)|fech(?:a|ar)|trav(?:a|ando))\b.{0,80}\b(computador|mac|mem[oó]ria|ram|processos?\s+(?:tempor[aá]rios?\s+)?(?:do\s+)?jarvis)\b)", re.I), "system_memory"),
    (re.compile(r"\b(ver|listar|encontrar|procurar)\b.{0,40}\b(armazenamento|arquivos grandes|espaço em disco)\b", re.I), "storage_scan"),
    (re.compile(r"\b(organiz(?:a|ar)|arrum(?:a|ar))\b.{0,40}\barquivos\b", re.I), "files_triage"),
)

MEMORY_SIGNAL_PATTERNS = (
    re.compile(r"\b(eu\s+prefir[oa]|minha\s+prefer[eê]ncia)\b", re.I),
    re.compile(r"\b(eu\s+sempre|eu\s+nunca|a\s+partir\s+de\s+agora)\b", re.I),
    re.compile(r"\b(decidi|decidimos)\s+que\b", re.I),
    re.compile(r"\b(meu\s+objetivo(?:\s+principal)?\s+[eé]|quero\s+que\s+(?:voc[eê]|o\s+jarvis)\s+sempre)\b", re.I),
)

SECRET_PATTERNS = (
    re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{12,}\b", re.I),
    re.compile(r"\bsbp_[A-Za-z0-9_-]{12,}\b", re.I),
    re.compile(r"\bvcp_[A-Za-z0-9_-]{12,}\b", re.I),
    re.compile(
        r"\b(?:api[_ -]?key|token|password|senha|authorization|bearer)\b\s*[:=]\s*\S{8,}",
        re.I,
    ),
)

COMMAND_ROUTES = {
    "status": ("/status", "GET"),
    "health": ("/health", "GET"),
    "capabilities": ("/capabilities", "GET"),
    "sources": ("/sources", "GET"),
    "next": ("/next", "GET"),
    "self-test": ("/self-test", "POST"),
    "selftest": ("/self-test", "POST"),
}

PLANNING_PATHS = {
    "/acceptance-checklist",
    "/autopilot-run",
    "/feature-autopilot",
    "/operator-brief",
    "/spec-to-tasks",
}


def has_secret_like_text(value):
    text = str(value or "")
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def clean_text(value, limit=MAX_PROMPT_CHARS):
    return str(value or "").replace("\x00", "").strip()[:limit]


def supabase_configured():
    url = clean_text(os.environ.get("SUPABASE_URL"), 500).rstrip("/")
    key = clean_text(os.environ.get("SUPABASE_SERVICE_ROLE_KEY"), 2_000)
    parsed = urlparse(url)
    return bool(parsed.scheme == "https" and parsed.netloc and key)


def owner_pairing_required():
    return bool(clean_text(os.environ.get("JARVIS_OWNER_TOKEN"), 2_000))


def owner_token_matches(value):
    expected = clean_text(os.environ.get("JARVIS_OWNER_TOKEN"), 2_000)
    provided = clean_text(value, 2_000)
    return bool(expected and provided and hmac.compare_digest(expected, provided))


def pairing_required_payload():
    return {
        "ok": False,
        "endpoint": "POST /command",
        "status_real": "owner_pairing_required",
        "visual_state": "error",
        "error": "Conecte este navegador ao JARVIS pelo painel Sistema para usar memória, agenda ou o Mac.",
        "pairing_required": True,
    }, 401


def memory_suggestion(value):
    text = clean_text(value, 600)
    if len(text) < 12:
        return ""
    return text if any(pattern.search(text) for pattern in MEMORY_SIGNAL_PATTERNS) else ""


def web_capabilities():
    rows = [dict(row) for row in BASE_WEB_CAPABILITIES]
    configured = {
        "assistant_chat": bool(os.environ.get("OPENROUTER_API_KEY")),
        "assistant_voice": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "n8n_agenda": bool(os.environ.get("N8N_WEBHOOK_URL")),
    }
    for row in rows:
        if row["name"] == "persistent_memory":
            row["status"] = "configured" if supabase_configured() else "available_on_local_worker"
            continue
        if row["name"] in configured:
            if row["name"] == "assistant_voice" and not configured[row["name"]]:
                row["status"] = "input_only_requires_elevenlabs_key"
            else:
                row["status"] = "configured" if configured[row["name"]] else "needs_environment"
    return rows


def request_route(raw_path):
    parsed = urlparse(raw_path)
    query = parse_qs(parsed.query)
    rewritten = clean_text((query.get("jarvis_path") or [""])[0], 2_000)
    path = unquote(rewritten or parsed.path or "/")
    if path in {"/api", "/api/", "/api/index", "/api/index.py"}:
        path = "/"
    if not path.startswith("/"):
        path = "/" + path
    return path, query


def public_sources():
    return [
        {"name": "COCKPIT", "path": "web/cockpit", "category": "interface"},
        {"name": "FREE AI", "path": "openrouter/free", "category": "assistant"},
        {"name": "PLANNER", "path": "web/planner", "category": "reasoning"},
        {"name": "LOCAL WORKER", "path": "local/jarvis-do", "category": "device"},
        {"name": "CAPABILITIES", "path": "web/capabilities", "category": "system"},
    ]


def supabase_request(method="GET", query="", body=None, prefer="", table=SUPABASE_MEMORY_TABLE):
    if not supabase_configured():
        raise ValueError("supabase not configured")
    base_url = clean_text(os.environ.get("SUPABASE_URL"), 500).rstrip("/")
    api_key = clean_text(os.environ.get("SUPABASE_SERVICE_ROLE_KEY"), 2_000)
    if table not in {
        SUPABASE_MEMORY_TABLE,
        SUPABASE_DEVICE_COMMANDS_TABLE,
        SUPABASE_DEVICE_WORKERS_TABLE,
    }:
        raise ValueError("supabase table not allowed")
    url = f"{base_url}/rest/v1/{table}"
    if query:
        url = f"{url}?{query}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=15) as response:
        raw = response.read(1_000_000)
    return json.loads(raw.decode("utf-8")) if raw else []


def supabase_memory_rows(limit=80):
    safe_limit = max(1, min(int(limit), 80))
    query = (
        "select=id,kind,content,source,created_at"
        "&owner_id=eq.theo&archived_at=is.null"
        f"&order=created_at.desc&limit={safe_limit}"
    )
    rows = supabase_request(query=query)
    return rows if isinstance(rows, list) else []


def supabase_device_enqueue(command, intent):
    target = ""
    if intent in {"open_application", "close_application"}:
        command_args = computer_app_command(command, intent)
        if not command_args:
            return {
                "ok": False,
                "endpoint": "POST /command",
                "status_real": "application_target_missing",
                "visual_state": "error",
                "error": "Diga exatamente qual aplicativo devo abrir ou fechar.",
                "intent": intent,
            }, 400
        target = clean_text(command_args[-1], 120)
    row = {
        "owner_id": "theo",
        "action": intent,
        "target": target,
        "request_text": clean_text(command, 8_000),
        "status": "pending",
    }
    try:
        result = supabase_request(
            "POST",
            body=row,
            prefer="return=representation",
            table=SUPABASE_DEVICE_COMMANDS_TABLE,
        )
        saved = result[0] if isinstance(result, list) and result else None
        if not isinstance(saved, dict) or not saved.get("id"):
            raise ValueError("missing queued command")
        return {
            "ok": True,
            "endpoint": "POST /command",
            "status_real": "device_command_queued",
            "visual_state": "local",
            "message": "Pedido enviado ao worker do Mac. Estou acompanhando a execução.",
            "intent": intent,
            "provider": "supabase_device_bridge",
            "job": {
                "id": saved["id"],
                "status": "pending",
                "action": intent,
                "target": target,
            },
        }, 202
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "device_command_queue_failed",
            "visual_state": "error",
            "error": f"O Supabase recusou a fila do Mac (HTTP {error.code}).",
            "intent": intent,
        }, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "device_command_queue_unavailable",
            "visual_state": "error",
            "error": "A fila do Mac não confirmou o pedido.",
            "intent": intent,
        }, 504


def supabase_device_command(command_id):
    if not re.fullmatch(r"[0-9]{1,18}", str(command_id or "")):
        return {
            "ok": False,
            "endpoint": "GET /device-command",
            "status_real": "device_command_id_invalid",
            "error": "Identificador de ação inválido.",
        }, 400
    try:
        query = (
            "select=id,action,target,status,result,created_at,claimed_at,completed_at"
            f"&owner_id=eq.theo&id=eq.{command_id}&limit=1"
        )
        rows = supabase_request(query=query, table=SUPABASE_DEVICE_COMMANDS_TABLE)
        row = rows[0] if isinstance(rows, list) and rows else None
        if not isinstance(row, dict):
            return {
                "ok": False,
                "endpoint": "GET /device-command",
                "status_real": "device_command_not_found",
                "error": "Ação do Mac não encontrada.",
            }, 404
        status = clean_text(row.get("status"), 40)
        succeeded = status == "succeeded"
        failed = status == "failed"
        messages = {
            "pending": "Pedido aguardando o worker do Mac.",
            "running": "O worker do Mac está executando o pedido.",
            "succeeded": "Ação concluída no Mac.",
            "failed": "O worker tentou executar, mas não confirmou a conclusão.",
        }
        return {
            "ok": not failed,
            "endpoint": "GET /device-command",
            "status_real": f"device_command_{status or 'unknown'}",
            "visual_state": "success" if succeeded else "error" if failed else "local",
            "message": messages.get(status, "Estado da ação desconhecido."),
            "provider": "supabase_device_bridge",
            "job": {
                "id": row.get("id"),
                "action": clean_text(row.get("action"), 60),
                "target": clean_text(row.get("target"), 120),
                "status": status,
                "result": clean_text(row.get("result"), 8_000),
                "created_at": clean_text(row.get("created_at"), 80),
                "claimed_at": clean_text(row.get("claimed_at"), 80),
                "completed_at": clean_text(row.get("completed_at"), 80),
            },
        }, 200
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "GET /device-command",
            "status_real": "device_command_read_failed",
            "error": f"O Supabase recusou a consulta da ação (HTTP {error.code}).",
        }, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "GET /device-command",
            "status_real": "device_command_read_unavailable",
            "error": "O estado do worker do Mac não respondeu.",
        }, 504


def device_worker_status_payload():
    try:
        query = "select=worker_id,hostname,version,last_seen_at&owner_id=eq.theo&order=last_seen_at.desc&limit=1"
        rows = supabase_request(query=query, table=SUPABASE_DEVICE_WORKERS_TABLE)
        row = rows[0] if isinstance(rows, list) and rows else None
        if not isinstance(row, dict):
            return {
                "ok": True,
                "endpoint": "GET /device-worker-status",
                "status_real": "device_worker_never_seen",
                "online": False,
                "message": "O worker do Mac ainda não enviou heartbeat.",
            }, 200
        raw_seen = clean_text(row.get("last_seen_at"), 80)
        seen = datetime.fromisoformat(raw_seen.replace("Z", "+00:00"))
        age_seconds = max(0, int((datetime.now(timezone.utc) - seen.astimezone(timezone.utc)).total_seconds()))
        online = age_seconds <= 20
        return {
            "ok": True,
            "endpoint": "GET /device-worker-status",
            "status_real": "device_worker_online" if online else "device_worker_offline",
            "online": online,
            "age_seconds": age_seconds,
            "hostname": clean_text(row.get("hostname"), 255),
            "version": clean_text(row.get("version"), 40),
            "message": "Worker do Mac conectado." if online else "Worker do Mac sem heartbeat recente.",
        }, 200
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "GET /device-worker-status",
            "status_real": "device_worker_status_unavailable",
            "online": False,
            "error": "Não consegui consultar o heartbeat do Mac.",
        }, 503


def local_memory_tree_payload():
    memory_root = ROOT / "03_MEMORIA"
    nodes = []
    edges = []
    if memory_root.is_dir():
        for path in sorted(memory_root.rglob("*.md"), reverse=True)[:80]:
            relative = path.relative_to(memory_root)
            category = relative.parts[0] if len(relative.parts) > 1 else "MEMORIA"
            node_id = str(relative).replace(os.sep, "/")
            label = path.stem.replace("_", " ").replace("-", " ")[:80]
            nodes.append({
                "id": node_id,
                "label": label,
                "category": category,
                "path": f"03_MEMORIA/{node_id}",
            })
            edges.append({"source": category, "target": node_id})
    categories = sorted({node["category"] for node in nodes})
    return {
        "ok": True,
        "endpoint": "GET /memory-tree",
        "status_real": "local_memory_index_read",
        "visual_state": "memory",
        "nodes": nodes,
        "edges": edges,
        "categories": categories,
        "count": len(nodes),
        "persistent_write": False,
        "provider": "local_markdown",
    }


def memory_tree_payload():
    if not supabase_configured():
        return local_memory_tree_payload()
    try:
        rows = supabase_memory_rows(80)
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "GET /memory-tree",
            "status_real": "supabase_memory_read_failed",
            "visual_state": "error",
            "error": f"O Supabase recusou a leitura da memória (HTTP {error.code}).",
            "nodes": [],
            "edges": [],
            "categories": [],
            "count": 0,
            "persistent_write": True,
            "provider": "supabase",
        }
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "GET /memory-tree",
            "status_real": "supabase_memory_read_unavailable",
            "visual_state": "error",
            "error": "A memória do Supabase não respondeu a tempo.",
            "nodes": [],
            "edges": [],
            "categories": [],
            "count": 0,
            "persistent_write": True,
            "provider": "supabase",
        }

    nodes = []
    edges = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        memory_id = clean_text(row.get("id"), 100)
        content = clean_text(row.get("content"), 4_000)
        kind = clean_text(row.get("kind"), 40).lower()
        if not memory_id or not content:
            continue
        category = MEMORY_KIND_LABELS.get(kind, "MEMORIA")
        node_id = f"supabase:{memory_id}"
        nodes.append({
            "id": node_id,
            "label": content[:120],
            "content": content,
            "category": category,
            "path": f"supabase/{SUPABASE_MEMORY_TABLE}/{memory_id}",
            "created_at": clean_text(row.get("created_at"), 80),
        })
        edges.append({"source": category, "target": node_id})
    categories = sorted({node["category"] for node in nodes})
    return {
        "ok": True,
        "endpoint": "GET /memory-tree",
        "status_real": "supabase_memory_index_read",
        "visual_state": "memory",
        "nodes": nodes,
        "edges": edges,
        "categories": categories,
        "count": len(nodes),
        "persistent_write": True,
        "provider": "supabase",
    }


def status_payload(owner_authenticated=False):
    ai_ready = bool(os.environ.get("OPENROUTER_API_KEY"))
    elevenlabs_ready = bool(os.environ.get("ELEVENLABS_API_KEY"))
    n8n_ready = bool(os.environ.get("N8N_WEBHOOK_URL"))
    return {
        "ok": True,
        "endpoint": "GET /status",
        "service": "jarvis-web",
        "runtime": "vercel_serverless" if os.environ.get("VERCEL") else "local_web_preview",
        "status_real": "web_cockpit_ready",
        "mode": "personal_single_operator",
        "ai": {
            "provider": "openrouter",
            "model": os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
            "configured": ai_ready,
            "privacy": "Prompts sent to free models may be retained by their providers; do not send secrets.",
        },
        "voice": {
            "provider": "elevenlabs" if elevenlabs_ready else "browser",
            "configured": elevenlabs_ready,
            "voice_id": os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID),
            "model": os.environ.get("ELEVENLABS_MODEL", DEFAULT_ELEVENLABS_MODEL),
            "fallback": "text_only",
        },
        "automations": {
            "n8n": {"configured": n8n_ready, "agenda": n8n_ready},
        },
        "memory": {
            "provider": "supabase" if supabase_configured() else "local_markdown",
            "configured": supabase_configured(),
            "persistent": supabase_configured(),
        },
        "owner_pairing": {
            "required": owner_pairing_required(),
            "authenticated": bool(owner_authenticated),
        },
        "device_bridge": {
            "configured": bool(supabase_configured() and owner_pairing_required()),
            "execution": "local_worker",
        },
        "capabilities": web_capabilities(),
        "device_actions": "local_worker_required",
        "blocked": ["arbitrary_shell", "secret_exposure", "silent_external_side_effects"],
        "production_touched": False,
    }


def owner_mode_payload():
    return {
        "ok": True,
        "endpoint": "GET /owner-dev",
        "runtime": "web",
        "status_real": "owner_web_mode",
        "owner_dev_mode": True,
        "owner_mode_enabled_setting": True,
        "localhost_confirmed": False,
        "public_mode_locked": False,
        "message": "OWNER WEB MODE ON — chat, planning and local-worker handoff are available.",
        "safe_dev_actions": [
            "assistant_chat",
            "feature_planning",
            "capability_inspection",
            "local_worker_handoff",
        ],
        "still_blocked": ["arbitrary_shell", "secret_exposure", "silent_external_side_effects"],
    }


def planning_payload(path, body):
    goal = clean_text(
        body.get("goal")
        or body.get("target")
        or body.get("topic")
        or body.get("command")
        or "melhorar o JARVIS"
    )
    if has_secret_like_text(goal):
        return {
            "ok": False,
            "endpoint": f"POST {path}",
            "error": "O pedido parece conter uma credencial. Remova o segredo e tente novamente.",
        }, 400

    steps = [
        {"step": 1, "action": "Definir o resultado e a evidência de conclusão.", "status": "ready"},
        {"step": 2, "action": "Mapear arquivos, integrações e riscos envolvidos.", "status": "ready"},
        {"step": 3, "action": "Executar primeiro a menor mudança reversível.", "status": "ready"},
        {"step": 4, "action": "Validar comportamento, erros e experiência visual.", "status": "ready"},
        {"step": 5, "action": "Entregar diff, testes e próximo comando explícito.", "status": "ready"},
    ]
    return {
        "ok": True,
        "endpoint": f"POST {path}",
        "status_real": "web_plan_generated_no_persistent_write",
        "visual_state": "planning",
        "goal": goal,
        "title": "JARVIS execution brief",
        "summary": f"Plano direto para: {goal}",
        "steps": steps,
        "acceptance": [
            "A mudança principal funciona no fluxo real.",
            "Falhas retornam mensagem compreensível.",
            "Nenhuma credencial aparece no código ou na resposta.",
            "Ações de dispositivo são encaminhadas ao worker local.",
        ],
        "requires_local_worker": any(pattern.search(goal) for pattern, _ in LOCAL_INTENTS),
        "persistent_write": False,
    }, 200


def memory_details(command):
    text = clean_text(command, 600)
    kind = "preference" if re.search(r"\bprefer[eê]ncia\b", text, re.I) else "decision" if re.search(r"\bdecis[aã]o\b", text, re.I) else "learning"
    body = re.sub(
        r"^\s*(?:guard(?:a|e|ar)|salv(?:a|e|ar)|registr(?:a|e|ar)|grav(?:a|e|ar)|lembr(?:a|e|ar))\s*",
        "",
        text,
        flags=re.I,
    ).strip(" :-")
    body = re.sub(
        r"^(?:isso\s+)?(?:na\s+mem[oó]ria)(?:\s+como\s+(?:prefer[eê]ncia|aprendizado|decis[aã]o))?\s*",
        "",
        body,
        flags=re.I,
    ).strip(" :-")
    body = re.sub(
        r"^como\s+(?:prefer[eê]ncia|aprendizado|decis[aã]o)\s*",
        "",
        body,
        flags=re.I,
    ).strip(" :-")
    body = re.sub(
        r"\s+(?:na|como)\s+(?:mem[oó]ria|prefer[eê]ncia|aprendizado|decis[aã]o)\s*$",
        "",
        body,
        flags=re.I,
    ).strip(" :-")
    body = re.sub(r"^que\s+", "", body, flags=re.I).strip()
    if len(body) < 3 or body.casefold() in {"isso", "isto", "essa", "esta", "aquilo"}:
        return None
    return {"content": body, "kind": kind}


def memory_write_command(command):
    memory = memory_details(command)
    if not memory:
        return None
    return ["./jarvis", "memory-save", memory["content"], "--kind", memory["kind"]]


def supabase_memory_save(command):
    memory = memory_details(command)
    if not memory:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "memory_content_missing",
            "visual_state": "error",
            "message": "Diga exatamente o que devo guardar; não vou fingir que salvei um ‘isso’ sem contexto.",
            "intent": "memory_save",
        }, 400
    if has_secret_like_text(memory["content"]):
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "memory_secret_refused",
            "visual_state": "error",
            "error": "Não salvo credenciais na memória.",
            "intent": "memory_save",
        }, 400
    row = {
        "owner_id": "theo",
        "kind": memory["kind"],
        "content": memory["content"],
        "source": "jarvis-web",
        "metadata": {"schema_version": 1},
    }
    try:
        result = supabase_request("POST", body=row, prefer="return=representation")
        saved = result[0] if isinstance(result, list) and result else None
        if not isinstance(saved, dict) or not saved.get("id"):
            raise ValueError("missing persisted row")
        return {
            "ok": True,
            "endpoint": "POST /command",
            "status_real": "supabase_memory_persisted",
            "visual_state": "memory",
            "message": "Guardei isso na memória permanente.",
            "intent": "memory_save",
            "provider": "supabase",
            "persistent_write": True,
            "memory": {
                "id": saved["id"],
                "kind": clean_text(saved.get("kind"), 40),
                "content": clean_text(saved.get("content"), 4_000),
                "created_at": clean_text(saved.get("created_at"), 80),
            },
        }, 201
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "supabase_memory_write_failed",
            "visual_state": "error",
            "error": f"O Supabase recusou a gravação da memória (HTTP {error.code}).",
            "intent": "memory_save",
            "provider": "supabase",
        }, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "supabase_memory_write_unavailable",
            "visual_state": "error",
            "error": "A memória do Supabase não confirmou a gravação.",
            "intent": "memory_save",
            "provider": "supabase",
        }, 504


def computer_app_command(command, intent):
    pattern = APPLICATION_INTENT_PATTERNS.get(intent)
    match = pattern.fullmatch(clean_text(command, 300)) if pattern else None
    if not match:
        return None
    app = re.sub(r"\s+", " ", match.group("app")).strip(" .")
    app = APPLICATION_ALIASES.get(app.casefold(), app)
    if app.casefold() in {"projeto", "arquivo", "pasta", "memória", "memoria"}:
        return None
    action = "open" if intent == "open_application" else "close"
    return ["./jarvis", "computer", action, app]


def local_handoff(command, intent, execute=False):
    if intent == "memory_save":
        command_args = memory_write_command(command)
    elif intent in {"open_application", "close_application"}:
        command_args = computer_app_command(command, intent)
    elif intent == "system_memory":
        cleanup_requested = bool(
            re.search(r"\b(limp(?:a|e|ar)|fech(?:a|e|ar))\b.{0,100}\b(jarvis|tempor[aá]rios?|processos?)\b", command, re.I)
        )
        command_args = ["./jarvis", "system-memory"]
        if cleanup_requested:
            command_args.append("--cleanup-jarvis")
    else:
        command_args = ["./jarvis", "do", command]
    if not command_args:
        application_intent = intent in {"open_application", "close_application"}
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "application_target_missing" if application_intent else "memory_content_missing",
            "visual_state": "error",
            "message": (
                "Diga exatamente qual aplicativo devo abrir ou fechar."
                if application_intent
                else "Diga exatamente o que devo guardar; não vou fingir que salvei um ‘isso’ sem contexto."
            ),
            "intent": intent,
            "executed_locally": False,
        }
    safe_command = shlex.join(command_args)
    if execute:
        try:
            result = subprocess.run(
                command_args,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=90,
                env=os.environ.copy(),
            )
            output = (result.stdout or result.stderr or "").strip()[-8_000:]
            action_succeeded = result.returncode == 0
            if intent == "memory_save":
                action_succeeded = action_succeeded and "Memória criada:" in output
            success_messages = {
                "memory_save": "Guardei isso na memória local.",
                "message_send": "Mensagem entregue ao app Mensagens do Mac.",
                "screen_capture": "Captura concluída no seu Mac.",
                "system_memory": "Diagnóstico do Mac concluído; somente temporários do JARVIS foram elegíveis para limpeza.",
                "open_application": "Aplicativo aberto no seu Mac.",
                "close_application": "Aplicativo fechado no seu Mac.",
            }
            return {
                "ok": action_succeeded,
                "endpoint": "POST /command",
                "status_real": "local_action_executed" if action_succeeded else "local_action_failed",
                "visual_state": "memory" if action_succeeded and intent == "memory_save" else "success" if action_succeeded else "error",
                "message": success_messages.get(intent, "Feito no seu Mac.") if action_succeeded else "Tentei fazer no Mac, mas não recebi evidência de conclusão.",
                "intent": intent,
                "executed_locally": True,
                "exit_code": result.returncode,
                "result": output,
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "endpoint": "POST /command",
                "status_real": "local_action_timeout",
                "visual_state": "error",
                "message": "A ação no Mac demorou mais do que o esperado e foi interrompida.",
                "intent": intent,
                "executed_locally": True,
            }
    return {
        "ok": True,
        "endpoint": "POST /command",
        "status_real": "web_to_local_handoff",
        "visual_state": "memory" if intent == "memory_save" else "local",
        "message": "A memória está preparada para o worker local do Mac." if intent == "memory_save" else "Esse pedido precisa rodar no Mac. O handoff está pronto para o worker local.",
        "intent": intent,
        "requires_local_worker": True,
        "local_command": safe_command,
        "copy_command": safe_command,
        "why": "Uma função na Vercel não tem acesso à tela, voz, WhatsApp ou arquivos do seu computador.",
    }


def n8n_automation(command, intent):
    webhook_url = clean_text(os.environ.get("N8N_WEBHOOK_URL"), 2_000)
    parsed = urlparse(webhook_url)
    if parsed.scheme != "https" or not parsed.netloc:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "n8n_not_configured",
            "visual_state": "error",
            "error": "O webhook HTTPS do n8n ainda não está configurado.",
            "intent": intent,
        }, 503

    request_body = json.dumps({
        "source": "jarvis-web",
        "operator": "theo",
        "intent": intent,
        "command": command,
    }, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Jarvis-Source": "web"}
    token = os.environ.get("N8N_WEBHOOK_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = Request(webhook_url, data=request_body, headers=headers, method="POST")
        with urlopen(req, timeout=20) as response:
            raw = response.read(1_000_000).decode("utf-8", errors="replace")
        try:
            result = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            result = {"result": raw}
        result_message = ""
        if isinstance(result, dict):
            result_message = result.get("message") or result.get("output") or ""
        message = clean_text(result_message, 2_000) or (
            "Agenda atualizada pelo n8n."
            if intent == "agenda_note"
            else "Agenda consultada pelo n8n."
        )
        return {
            "ok": True,
            "endpoint": "POST /command",
            "status_real": "n8n_automation_completed",
            "visual_state": "success",
            "message": message,
            "intent": intent,
            "provider": "n8n",
            "result": result,
        }, 200
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "n8n_automation_failed",
            "visual_state": "error",
            "error": f"O n8n recusou a automação (HTTP {error.code}).",
            "intent": intent,
        }, 502
    except (URLError, TimeoutError):
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "n8n_automation_timeout",
            "visual_state": "error",
            "error": "O n8n não respondeu a tempo.",
            "intent": intent,
        }, 504


def elevenlabs_speech(body):
    text = clean_text(body.get("text") or body.get("message"), 2_200)
    if not text:
        return {"ok": False, "error": "Texto vazio para síntese de voz."}, 400
    if has_secret_like_text(text):
        return {"ok": False, "error": "Não envio credenciais para síntese de voz."}, 400
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "status_real": "elevenlabs_key_required",
            "error": "ElevenLabs ainda não está configurado.",
            "fallback": "text_only",
        }, 503
    voice_id = clean_text(os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_ELEVENLABS_VOICE_ID, 100)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
        return {"ok": False, "error": "Voice ID inválido."}, 500
    payload = json.dumps({
        "text": text,
        "model_id": os.environ.get("ELEVENLABS_MODEL", DEFAULT_ELEVENLABS_MODEL),
        "language_code": "pt",
        "voice_settings": {
            "stability": 0.42,
            "similarity_boost": 0.78,
            "style": 0.0,
            "use_speaker_boost": True,
            "speed": 1.02,
        },
    }, ensure_ascii=False).encode("utf-8")
    url = f"{ELEVENLABS_URL}/{quote(voice_id)}?output_format=mp3_44100_128"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    try:
        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=25) as response:
            audio = response.read(8_000_000)
        if not audio:
            raise ValueError("empty audio")
        return audio, 200
    except HTTPError as error:
        if error.code == 402:
            return {
                "ok": False,
                "error": "ElevenLabs sem créditos disponíveis (HTTP 402).",
                "error_code": "elevenlabs_quota",
                "fallback": "text_only",
            }, 502
        if error.code in {401, 403}:
            return {
                "ok": False,
                "error": "A chave ou a voz da ElevenLabs não foi autorizada.",
                "error_code": "elevenlabs_authorization",
                "fallback": "text_only",
            }, 502
        if error.code == 429:
            return {
                "ok": False,
                "error": "O limite temporário da ElevenLabs foi atingido.",
                "error_code": "elevenlabs_rate_limit",
                "fallback": "text_only",
            }, 502
        return {
            "ok": False,
            "error": f"ElevenLabs recusou a voz (HTTP {error.code}).",
            "error_code": "elevenlabs_provider_error",
            "fallback": "text_only",
        }, 502
    except (URLError, TimeoutError, ValueError):
        return {"ok": False, "error": "ElevenLabs não respondeu com áudio válido.", "fallback": "text_only"}, 504


def normalize_messages(body):
    rows = body.get("messages") if isinstance(body.get("messages"), list) else []
    messages = []
    for row in rows[-12:]:
        if not isinstance(row, dict):
            continue
        role = row.get("role") if row.get("role") in {"user", "assistant"} else "user"
        content = clean_text(row.get("content"), 4_000)
        if content:
            messages.append({"role": role, "content": content})

    prompt = clean_text(body.get("prompt") or body.get("command"))
    if prompt and (not messages or messages[-1].get("content") != prompt):
        messages.append({"role": "user", "content": prompt})
    return messages[-12:]


def assistant_response(body, origin="", local_execute=False, owner_authenticated=False):
    messages = normalize_messages(body)
    if not messages:
        return {"ok": False, "error": "Escreva uma mensagem para o JARVIS."}, 400

    if any(has_secret_like_text(row["content"]) for row in messages):
        return {
            "ok": False,
            "error": "A mensagem parece conter uma credencial. Remova o segredo antes de usar um modelo externo.",
        }, 400

    latest = messages[-1]["content"]
    for pattern, intent in LOCAL_INTENTS:
        if pattern.search(latest):
            if owner_pairing_required() and not owner_authenticated and intent in {
                "memory_save", "agenda_note", "agenda_view", "task_add", *REMOTE_DEVICE_INTENTS
            }:
                return pairing_required_payload()
            if intent == "memory_save" and supabase_configured():
                return supabase_memory_save(latest)
            if intent in REMOTE_DEVICE_INTENTS and supabase_configured() and not local_execute:
                return supabase_device_enqueue(latest, intent)
            return local_handoff(latest, intent, execute=local_execute), 200

    suggested_memory = memory_suggestion(latest)
    memory_context = []
    if supabase_configured() and (owner_authenticated or not owner_pairing_required()):
        try:
            memory_context = supabase_memory_rows(12)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            memory_context = []

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        payload, status = planning_payload("/assistant", {"goal": latest})
        payload.update({
            "message": "A IA online ainda não está conectada; organizei um plano direto como alternativa.",
            "ai_configured": False,
        })
        return payload, status

    system = {
        "role": "system",
        "content": (
            "Você é JARVIS, o assistente pessoal de Theo. Fale em português brasileiro natural, elegante, "
            "calmo e direto. Tenha humor seco e inteligente quando combinar com a conversa, sem forçar piadas, "
            "sem ser caricato e sem encher a resposta de emojis. Se Theo pedir humor explicitamente, inclua uma "
            "única observação espirituosa curta, com ironia contida e sem transformar a resposta em stand-up. "
            "Comece pela resposta mais útil; depois mostre "
            "brevemente as razões e o próximo passo relevante. Questione uma premissa ruim em vez de concordar "
            "automaticamente. Preserve o contexto da conversa e não encerre de modo abrupto quando houver uma "
            "continuação realmente útil. Em decisões, previsões ou inferências incertas, informe uma estimativa "
            "honesta de confiança em porcentagem e a principal razão; não invente precisão e não use porcentagens "
            "para fatos simples. Ajude a pensar, planejar, escrever e decidir. Nunca alegue ter executado ações no "
            "computador ou em serviços externos sem evidência real. Nunca peça, repita ou exponha credenciais. "
            "Quando algo exigir o Mac, diga com clareza que o worker local deve executar."
            " A interface do JARVIS usa ElevenLabs para ler suas respostas em voz alta. Você é o cérebro textual "
            "dessa voz: nunca diga que não possui voz, que seu som só existe em texto ou que pode apenas imitar "
            "uma voz. Se Theo pedir para ouvir você, responda com uma frase curta, natural e boa de falar; não "
            "explique a infraestrutura. A própria interface comunica qualquer falha real do áudio."
            + (
                "\n\nMemórias persistentes fornecidas por Theo; use somente quando forem relevantes e "
                "não invente informações além delas:\n"
                + "\n".join(
                    f"- [{clean_text(row.get('kind'), 40)}] {clean_text(row.get('content'), 600)}"
                    for row in memory_context
                    if isinstance(row, dict) and clean_text(row.get("content"), 600)
                )[:4_000]
                if memory_context
                else ""
            )
        ),
    }
    request_body = json.dumps(
        {
            "model": os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
            "messages": [system, *messages],
            "temperature": 0.5,
            "max_tokens": 1_200,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-OpenRouter-Title": "Theo JARVIS",
    }
    if origin.startswith(("https://", "http://")):
        headers["HTTP-Referer"] = origin[:200]

    try:
        req = Request(OPENROUTER_URL, data=request_body, headers=headers, method="POST")
        with urlopen(req, timeout=25) as response:
            result = json.loads(response.read().decode("utf-8"))
        choice = (result.get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                str(item.get("text") or "") for item in content if isinstance(item, dict)
            ).strip()
        content = clean_text(content, 20_000)
        if not content:
            raise ValueError("empty model response")
        payload = {
            "ok": True,
            "endpoint": "POST /assistant",
            "status_real": "assistant_response_from_openrouter",
            "visual_state": "memory" if suggested_memory else "response",
            "message": content,
            "content": content,
            "model": clean_text(result.get("model") or DEFAULT_MODEL, 200),
            "provider": "openrouter",
            "external_processing": True,
            "memory_context_count": len(memory_context),
        }
        if suggested_memory:
            payload["memory_suggestion"] = suggested_memory
        return payload, 200
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "POST /assistant",
            "error": f"OpenRouter recusou a requisição (HTTP {error.code}).",
            "retryable": error.code in {408, 409, 429, 500, 502, 503, 504},
        }, 502
    except (URLError, TimeoutError):
        return {
            "ok": False,
            "endpoint": "POST /assistant",
            "error": "O modelo externo não respondeu a tempo.",
            "retryable": True,
        }, 504
    except (ValueError, KeyError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "POST /assistant",
            "error": "O modelo externo retornou uma resposta inválida.",
            "retryable": True,
        }, 502


def command_payload(body, origin="", local_execute=False, owner_authenticated=False):
    command = clean_text(body.get("command") or body.get("prompt"))
    if not command:
        return {"ok": False, "error": "Comando vazio."}, 400
    if has_secret_like_text(command):
        return {
            "ok": False,
            "endpoint": "POST /command",
            "error": "O comando parece conter uma credencial. Remova o segredo e tente novamente.",
        }, 400

    if re.search(r"\b(mostr(?:a|ar)|abr(?:e|ir)|ver|list(?:a|ar))\b.{0,60}\b(mem[oó]ria|mem[oó]rias|aprendizados|decis[oõ]es)\b", command, re.IGNORECASE):
        if owner_pairing_required() and not owner_authenticated:
            return pairing_required_payload()
        payload = memory_tree_payload()
        payload.update({
            "message": (
                f"Abri sua constelação com {payload['count']} memórias persistentes."
                if payload.get("ok") and payload.get("provider") == "supabase"
                else f"Abri sua constelação com {payload['count']} memórias locais."
                if payload.get("ok")
                else payload.get("error", "A memória não está disponível.")
            ),
            "mode": "memory",
            "sources": payload["nodes"][:12],
        })
        return payload, 200 if payload.get("ok") else 503

    for pattern, intent in LOCAL_INTENTS:
        if pattern.search(command):
            if owner_pairing_required() and not owner_authenticated and intent in {
                "memory_save", "agenda_note", "agenda_view", "task_add", *REMOTE_DEVICE_INTENTS
            }:
                return pairing_required_payload()
            if intent == "memory_save" and supabase_configured():
                return supabase_memory_save(command)
            if intent in REMOTE_DEVICE_INTENTS and supabase_configured() and not local_execute:
                return supabase_device_enqueue(command, intent)
            if intent in {"agenda_note", "agenda_view", "task_add"} and os.environ.get("N8N_WEBHOOK_URL"):
                return n8n_automation(command, intent)
            return local_handoff(command, intent, execute=local_execute), 200

    clean = command.lstrip("/").strip()
    first = clean.split(maxsplit=1)[0].lower() if clean else ""
    if first in COMMAND_ROUTES:
        route, method = COMMAND_ROUTES[first]
        return {
            "ok": True,
            "endpoint": "POST /command",
            "status_real": "web_command_routed",
            "message": f"Abrindo {route}.",
            "routed_to": route,
            "method": method,
        }, 200

    if command.startswith("/"):
        goal = clean.split(maxsplit=1)[1] if " " in clean else clean
        payload, status = planning_payload("/command", {"goal": goal})
        payload["message"] = f"Comando {first} interpretado como planejamento web."
        payload["command"] = command
        return payload, status

    return assistant_response(
        {"command": command, "messages": body.get("messages")},
        origin=origin,
        local_execute=local_execute,
        owner_authenticated=owner_authenticated,
    )


class handler(BaseHTTPRequestHandler):
    server_version = "JarvisWeb/1.0"

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, status, body, content_type, cache="public, max-age=31536000, immutable"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError as error:
            raise ValueError("invalid content length") from error
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            value = json.loads(raw or "{}")
        except json.JSONDecodeError as error:
            raise ValueError("invalid JSON body") from error
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def serve_ui(self):
        try:
            body = UI_FILE.read_bytes()
        except OSError:
            return self.send_json(500, {"ok": False, "error": "cockpit asset is unavailable"})
        self.send_bytes(200, body, "text/html; charset=utf-8", "public, max-age=60")

    def serve_asset(self, relative):
        try:
            base = UI_ASSET_DIR.resolve()
            target = (base / unquote(relative).lstrip("/")).resolve()
            if target != base and base not in target.parents:
                return self.send_json(403, {"ok": False, "error": "asset path not allowed"})
            if not target.is_file():
                return self.send_json(404, {"ok": False, "error": "asset not found"})
            content_type = ASSET_TYPES.get(target.suffix.lower())
            if not content_type:
                content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            return self.send_bytes(200, target.read_bytes(), content_type)
        except OSError:
            return self.send_json(404, {"ok": False, "error": "asset not found"})

    def serve_web_asset(self, relative):
        try:
            base = WEB_DIR.resolve()
            target = (base / unquote(relative).lstrip("/")).resolve()
            if target != base and base not in target.parents:
                return self.send_json(403, {"ok": False, "error": "web asset path not allowed"})
            if not target.is_file() or target == UI_FILE.resolve():
                return self.send_json(404, {"ok": False, "error": "web asset not found"})
            content_type = ASSET_TYPES.get(target.suffix.lower())
            if not content_type:
                content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            return self.send_bytes(200, target.read_bytes(), content_type)
        except OSError:
            return self.send_json(404, {"ok": False, "error": "web asset not found"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self._security_headers()
        self.end_headers()

    def do_GET(self):
        path, query = request_route(self.path)
        owner_authenticated = owner_token_matches(self.headers.get("X-Jarvis-Owner-Token"))
        if path == "/":
            return self.serve_ui()
        if path == "/favicon.ico":
            return self.send_bytes(200, b"", "image/x-icon", "public, max-age=86400")
        if path.startswith("/ui/"):
            return self.serve_web_asset(path[len("/ui/"):])
        if path.startswith("/asset/"):
            return self.serve_asset(path[len("/asset/"):])
        if path in {"/health", "/status", "/runtime"}:
            payload = status_payload(owner_authenticated=owner_authenticated)
            payload["endpoint"] = f"GET {path}"
            return self.send_json(200, payload)
        if path == "/owner-dev":
            return self.send_json(200, owner_mode_payload())
        if path in {"/capabilities", "/capability-matrix"}:
            return self.send_json(200, {
                "ok": True,
                "endpoint": f"GET {path}",
                "status_real": "web_capabilities",
                "capabilities": web_capabilities(),
                "device_actions": [intent for _, intent in LOCAL_INTENTS],
            })
        if path in {"/sources", "/sources-data", "/sources-dashboard"}:
            sources = public_sources()
            return self.send_json(200, {
                "ok": True,
                "endpoint": f"GET {path}",
                "status_real": "public_capability_sources",
                "sources": sources,
                "items": sources,
                "count": len(sources),
                "total_sources": len(sources),
                "returned": len(sources),
            })
        if path == "/memory-tree":
            if owner_pairing_required() and not owner_authenticated:
                payload, status = pairing_required_payload()
                payload["endpoint"] = "GET /memory-tree"
                return self.send_json(status, payload)
            payload = memory_tree_payload()
            return self.send_json(200 if payload.get("ok") else 503, payload)
        if path == "/device-command":
            if owner_pairing_required() and not owner_authenticated:
                payload, status = pairing_required_payload()
                payload["endpoint"] = "GET /device-command"
                return self.send_json(status, payload)
            payload, status = supabase_device_command((query.get("id") or [""])[0])
            return self.send_json(status, payload)
        if path == "/device-worker-status":
            if owner_pairing_required() and not owner_authenticated:
                payload, status = pairing_required_payload()
                payload["endpoint"] = "GET /device-worker-status"
                return self.send_json(status, payload)
            payload, status = device_worker_status_payload()
            return self.send_json(status, payload)
        if path in {"/next", "/latest", "/feature-backlog", "/autopilot-dashboard"}:
            return self.send_json(200, {
                "ok": True,
                "endpoint": f"GET {path}",
                "status_real": "web_runtime_stateless",
                "message": "Digite um objetivo no cockpit; o JARVIS conversa, planeja ou encaminha ao worker local.",
                "next_action": "Use a barra central com um pedido em linguagem natural.",
                "persistent_history": supabase_configured(),
            })
        if path in {"/artifact", "/source", "/source-search", "/sources-search", "/sources-insight", "/sources-health"}:
            term = clean_text((query.get("q") or [""])[0], 200)
            return self.send_json(200, {
                "ok": True,
                "endpoint": f"GET {path}",
                "status_real": "web_public_view",
                "query": term,
                "sources": public_sources(),
                "message": "A edição web expõe somente fontes públicas de capacidade; arquivos locais ficam no Mac.",
            })
        return self.send_json(404, {
            "ok": False,
            "endpoint": f"GET {path}",
            "error": "Rota não disponível no runtime web.",
            "next_action": "Use /status, /capabilities, /sources ou a barra de comando.",
        })

    def do_POST(self):
        path, _ = request_route(self.path)
        try:
            body = self.read_json()
        except ValueError as error:
            return self.send_json(400, {"ok": False, "error": str(error)})

        origin = clean_text(self.headers.get("Origin") or self.headers.get("Referer"), 200)
        owner_authenticated = owner_token_matches(self.headers.get("X-Jarvis-Owner-Token"))
        if path == "/command":
            client = str((self.client_address or [""])[0]).lower()
            local_execute = (
                not bool(os.environ.get("VERCEL"))
                and os.environ.get("JARVIS_WEB_LOCAL_EXEC", "1") != "0"
                and client in {"127.0.0.1", "::1", "localhost"}
            )
            payload, status = command_payload(
                body,
                origin=origin,
                local_execute=local_execute,
                owner_authenticated=owner_authenticated,
            )
            return self.send_json(status, payload)
        if path in {"/assistant", "/chat"}:
            payload, status = assistant_response(
                body,
                origin=origin,
                owner_authenticated=owner_authenticated,
            )
            payload.setdefault("endpoint", f"POST {path}")
            return self.send_json(status, payload)
        if path == "/speech":
            payload, status = elevenlabs_speech(body)
            if isinstance(payload, bytes):
                return self.send_bytes(status, payload, "audio/mpeg", "no-store")
            return self.send_json(status, payload)
        if path in {"/owner-dev/on", "/owner-dev/off", "/owner-dev/toggle"}:
            payload = owner_mode_payload()
            payload["message"] = "O modo web pessoal já está ativo; funções serverless não mantêm toggles locais."
            return self.send_json(200, payload)
        if path == "/self-test":
            checks = [
                {"name": "cockpit", "ok": UI_FILE.is_file()},
                {"name": "model_asset", "ok": (UI_ASSET_DIR / "models" / "jarvis-humanoid.glb").is_file()},
                {"name": "stateless_gateway", "ok": True},
                {"name": "assistant_configured", "ok": bool(os.environ.get("OPENROUTER_API_KEY")), "required": False},
                {"name": "elevenlabs_configured", "ok": bool(os.environ.get("ELEVENLABS_API_KEY")), "required": False},
                {"name": "supabase_memory_configured", "ok": supabase_configured(), "required": False},
                {"name": "owner_pairing_configured", "ok": owner_pairing_required(), "required": False},
                {"name": "device_bridge_configured", "ok": bool(supabase_configured() and owner_pairing_required()), "required": False},
                {"name": "n8n_configured", "ok": bool(os.environ.get("N8N_WEBHOOK_URL")), "required": False},
            ]
            return self.send_json(200, {
                "ok": all(row["ok"] for row in checks if row.get("required", True)),
                "endpoint": "POST /self-test",
                "status_real": "web_self_test",
                "checks": checks,
            })
        if path in {"/validate", "/safety-gate"}:
            return self.send_json(200, {
                "ok": True,
                "endpoint": f"POST {path}",
                "status_real": "web_gateway_contract_valid",
                "checks": [
                    "request size limited",
                    "secret-like prompts refused",
                    "asset paths confined",
                    "no arbitrary shell",
                    "device actions require local worker",
                ],
            })
        if path in PLANNING_PATHS or path.startswith(("/feature-", "/context-", "/jarvis-brief")):
            payload, status = planning_payload(path, body)
            return self.send_json(status, payload)
        return self.send_json(404, {
            "ok": False,
            "endpoint": f"POST {path}",
            "error": "Ação não disponível no runtime web.",
            "next_action": "Descreva o objetivo na barra principal para gerar conversa, plano ou handoff local.",
        })

    def log_message(self, fmt, *args):
        print("[jarvis-web]", fmt % args)


def main():
    parser = argparse.ArgumentParser(description="JARVIS web gateway preview")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    required = [UI_FILE, WEB_DIR / "jarvis.css", WEB_DIR / "jarvis.js", WEB_DIR / "jarvis-3d.js", UI_ASSET_DIR / "models" / "jarvis-humanoid.glb"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if args.check:
        print("JARVIS Web Check")
        print("Status real: arquivos locais do cockpit verificados.")
        if missing:
            print("FALHA: " + ", ".join(missing))
            print("Produção: nada alterado.")
            return 1
        print(f"OK — {len(required)} componentes presentes.")
        print("Produção: nada alterado.")
        return 0
    if missing:
        print("FALHA: cockpit incompleto: " + ", ".join(missing))
        print("Produção: nada alterado.")
        return 1
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}"
    print("JARVIS web gateway")
    print(f"Status real: local preview at {url}")
    print("Produção: nada alterado.")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
