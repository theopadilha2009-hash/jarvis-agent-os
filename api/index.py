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
import base64
import binascii
from datetime import datetime, timedelta, timezone
import hmac
import json
import mimetypes
import os
import re
import shlex
import subprocess
import threading
import time
import unicodedata
import webbrowser
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
UI_FILE = WEB_DIR / "index.html"
UI_ASSET_DIR = ROOT / "11_SCRIPTS" / "jarvis_ui_assets"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_VOICE_DESIGN_URL = "https://api.elevenlabs.io/v1/text-to-voice/design"
ELEVENLABS_VOICE_CREATE_URL = "https://api.elevenlabs.io/v1/text-to-voice"
DEFAULT_ELEVENLABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"
DEFAULT_ELEVENLABS_MODEL = "eleven_flash_v2_5"
MAX_BODY_BYTES = 4_000_000
MAX_PROMPT_CHARS = 8_000
MAX_ATTACHMENT_BYTES = 2_500_000
MAX_ATTACHMENTS = 2
ATTACHMENT_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "application/json",
    "text/csv",
    "text/markdown",
    "text/plain",
}
SUPABASE_MEMORY_TABLE = "jarvis_memories"
SUPABASE_DEVICE_COMMANDS_TABLE = "jarvis_device_commands"
SUPABASE_DEVICE_WORKERS_TABLE = "jarvis_device_workers"
SUPABASE_CONTACTS_TABLE = "jarvis_contacts"
SUPABASE_AGENDA_TABLE = "jarvis_agenda_items"
SUPABASE_SETTINGS_TABLE = "jarvis_settings"
SUPABASE_ARTIFACTS_BUCKET = "jarvis-artifacts"
REMOTE_DEVICE_INTENTS = {
    "open_application",
    "close_application",
    "message_send",
    "screen_capture",
    "storage_scan",
    "system_memory",
    "self_edit",
}

SELF_EDIT_PATTERN = re.compile(
    r"(?:\b(?:auto[-\s]?(?:edit(?:e|ar)|melhor(?:e|ar))|"
    r"(?:edit(?:e|ar)|mex(?:a|er)|alter(?:e|ar)|modifiqu(?:e|ar)|melhor(?:e|ar)|"
    r"arrum(?:e|ar)|corrij(?:a|ir))\b.{0,100}\b(?:seus|nos\s+seus|pr[oó]prios?)\b"
    r".{0,50}\b(?:scripts?|c[oó]digo|arquivos?)\b)|"
    r"(?:\b(?:cri(?:a|e|ar)|implement(?:a|e|ar)|adicion(?:a|e|ar)|constru(?:a|ir)|"
    r"desenvolv(?:a|e|er))\b.{0,160}\b(?:no|para\s+o)\s+jarvis\b))",
    re.I,
)
MEMORY_KIND_LABELS = {
    "learning": "APRENDIZADOS",
    "decision": "DECISOES",
    "preference": "PREFERENCIAS",
    "context": "CONTEXTO",
}
MEMORY_LAYER_LABELS = {
    "owner": "THEO",
    "project": "PROJETOS",
    "daily": "HOJE",
    "discussion": "CONVERSAS",
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
        "name": "self_evolution",
        "status": "available_on_local_worker",
        "what": "Edita, testa e commita o JARVIS; publicação exige pedido explícito para subir/deployar.",
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
        "what": "Agenda persistente no Supabase, com n8n opcional quando configurado.",
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

JARVIS_CLEANUP_PATTERN = re.compile(
    r"\b(?:limp(?:a|e|ar)|fech(?:a|e|ar)|encerr(?:a|e|ar))\b.{0,120}"
    r"\b(?:processos?\s+(?:tempor[aá]rios?\s+)?(?:do\s+)?jarvis|"
    r"tempor[aá]rios?\s+(?:do\s+)?jarvis)\b",
    re.I,
)

LOCAL_INTENTS = (
    (SELF_EDIT_PATTERN, "self_edit"),
    (re.compile(r"\b(tir(?:a|e|ar)|captur(?:a|e|ar)|faz(?:er)?)\b.{0,40}\b(print|screenshot|tela)\b", re.I), "screen_capture"),
    (re.compile(r"\b(ler em voz alta|falar no mac|dizer no mac)\b", re.I), "speak"),
    (re.compile(r"\b(convert(?:a|er)|transform(?:a|ar))\b.{0,60}\b(imagem|foto|png|jpe?g|heic|tiff)\b", re.I), "image_convert"),
    (re.compile(r"\b(mensagem\s+(?:no|pelo)\s+whatsapp|whatsapp\s+para|rascunho\s+de\s+mensagem)\b", re.I), "message_draft"),
    (re.compile(r"\b(salv(?:a|e|ar)|adicion(?:a|e|ar)|cri(?:a|e|ar)|cadastr(?:a|e|ar))\b.{0,40}\bcontato\b", re.I), "contact_save"),
    (re.compile(r"\b(remov(?:a|e|er)|apag(?:a|e|ar)|arquiv(?:a|e|ar)|esquec(?:a|e|er))\b.{0,40}\bcontato\b", re.I), "contact_archive"),
    (re.compile(r"\b(ver|mostr(?:a|e|ar)|list(?:a|e|ar)|consult(?:a|e|ar))\b.{0,60}\bcontatos?\b", re.I), "contact_view"),
    (re.compile(r"\b(mand(?:a|e|ar)|envi(?:a|e|ar)|escrev(?:a|e|er))\b.{0,40}\b(mensagem|msg)\b", re.I), "message_send"),
    (re.compile(r"\b(guard(?:a|e|ar)|salv(?:a|e|ar)|registr(?:a|e|ar)|grav(?:a|e|ar)|lembr(?:a|e|ar))\b.{0,100}\b(mem[oó]ria|prefer[eê]ncia|aprendizado|decis[aã]o)\b", re.I), "memory_save"),
    (re.compile(r"\b(coloc(?:a|ar)|adicion(?:a|ar)|marc(?:a|ar))\b.{0,100}\b(agenda|lembrete)\b", re.I), "agenda_note"),
    (re.compile(r"\b(conclu(?:a|i|ir)|finaliz(?:a|e|ar)|marc(?:a|e|ar))\b.{0,60}\b(?:item|tarefa|lembrete|agenda)\s*#?\s*\d+\b", re.I), "agenda_complete"),
    (re.compile(r"\b(ver|mostr(?:a|ar)|list(?:a|ar)|consult(?:a|ar))\b.{0,80}\b(agenda|compromissos|eventos)\b", re.I), "agenda_view"),
    (re.compile(r"\b(anot(?:a|ar)|captur(?:a|ar)|registr(?:a|ar))\b.{0,100}\b(ideia|inbox|nota)\b", re.I), "capture_note"),
    (re.compile(r"\b(adicion(?:a|ar)|cri(?:a|ar))\b.{0,60}\b(tarefa|task)\b", re.I), "task_add"),
    (re.compile(r"\b(abr(?:e|ir))\b.{0,40}\b(projeto|oficina|jarvis|gc|ls)\b", re.I), "open_project"),
    (APPLICATION_INTENT_PATTERNS["open_application"], "open_application"),
    (APPLICATION_INTENT_PATTERNS["close_application"], "close_application"),
    (re.compile(r"(?:\b(computador|mac|mem[oó]ria|ram)\b.{0,80}\b(trav(?:a|ando)|lent[oa]|pesad[oa]|limp(?:a|ar))\b|\b(limp(?:a|ar)|fech(?:a|ar)|trav(?:a|ando))\b.{0,80}\b(computador|mac|mem[oó]ria|ram|processos?\s+(?:tempor[aá]rios?\s+)?(?:do\s+)?jarvis)\b)", re.I), "system_memory"),
    (re.compile(r"\b(ver|list(?:a|e|ar)|encontr(?:a|e|ar)|procur(?:a|e|ar)|mostr(?:a|e|ar)|analis(?:a|e|ar))\b.{0,60}\b(armazenamento|arquivos grandes|espaço em disco)\b", re.I), "storage_scan"),
    (re.compile(r"\b(organiz(?:a|ar)|arrum(?:a|ar))\b.{0,40}\barquivos\b", re.I), "files_triage"),
)

VOICE_DESIGN_PATTERN = re.compile(
    r"\b(?:cri(?:a|e|ar)|invent(?:a|e|ar)|desenh(?:a|e|ar)|ger(?:a|e|ar))\b"
    r".{0,70}\b(?:(?:sua\s+pr[oó]pria|uma\s+nova|uma)\s+voz|voz\s+pr[oó]pria|voz\s+do\s+jarvis)\b",
    re.I,
)

_ACTIVE_VOICE_CACHE = {"voice_id": "", "name": "", "expires_at": 0.0}

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
            if row["name"] == "n8n_agenda" and not configured[row["name"]] and supabase_configured():
                row["status"] = "supabase_fallback"
                continue
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
        SUPABASE_CONTACTS_TABLE,
        SUPABASE_AGENDA_TABLE,
        SUPABASE_SETTINGS_TABLE,
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


def active_voice_setting(force=False):
    """Resolve the persisted active voice without exposing Supabase credentials."""
    now = time.monotonic()
    if not force and _ACTIVE_VOICE_CACHE["voice_id"] and now < _ACTIVE_VOICE_CACHE["expires_at"]:
        return dict(_ACTIVE_VOICE_CACHE)
    fallback = {
        "voice_id": clean_text(
            os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_ELEVENLABS_VOICE_ID,
            100,
        ),
        "name": "ElevenLabs",
        "source": "environment",
    }
    if supabase_configured():
        try:
            rows = supabase_request(
                query="select=value&owner_id=eq.theo&key=eq.active_voice&limit=1",
                table=SUPABASE_SETTINGS_TABLE,
            )
            value = rows[0].get("value") if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
            voice_id = clean_text(value.get("voice_id"), 100) if isinstance(value, dict) else ""
            if re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
                fallback = {
                    "voice_id": voice_id,
                    "name": clean_text(value.get("name") or "JARVIS Theo", 120),
                    "source": "supabase",
                }
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            pass
    _ACTIVE_VOICE_CACHE.update({
        "voice_id": fallback["voice_id"],
        "name": fallback["name"],
        "source": fallback["source"],
        "expires_at": now + 60.0,
    })
    return dict(_ACTIVE_VOICE_CACHE)


def persist_active_voice(voice_id, name, description):
    safe_voice_id = clean_text(voice_id, 100)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", safe_voice_id):
        raise ValueError("invalid voice id")
    value = {
        "voice_id": safe_voice_id,
        "name": clean_text(name, 120),
        "description": clean_text(description, 1_000),
        "provider": "elevenlabs_voice_design",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    supabase_request(
        "POST",
        query="on_conflict=owner_id,key",
        body={
            "owner_id": "theo",
            "key": "active_voice",
            "value": value,
            "updated_at": value["created_at"],
        },
        prefer="resolution=merge-duplicates,return=representation",
        table=SUPABASE_SETTINGS_TABLE,
    )
    _ACTIVE_VOICE_CACHE.update({
        "voice_id": safe_voice_id,
        "name": value["name"],
        "source": "supabase",
        "expires_at": time.monotonic() + 60.0,
    })
    return value


def supabase_storage_request(object_path, body):
    """Call a private Storage endpoint without ever returning service credentials."""
    if not supabase_configured():
        raise ValueError("supabase not configured")
    safe_path = clean_text(object_path, 500).strip("/")
    if not re.fullmatch(r"theo/[A-Za-z0-9._/-]{1,480}", safe_path):
        raise ValueError("invalid private artifact path")
    base_url = clean_text(os.environ.get("SUPABASE_URL"), 500).rstrip("/")
    api_key = clean_text(os.environ.get("SUPABASE_SERVICE_ROLE_KEY"), 2_000)
    url = (
        f"{base_url}/storage/v1/object/sign/{SUPABASE_ARTIFACTS_BUCKET}/"
        f"{quote(safe_path, safe='/')}"
    )
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        raw = response.read(100_000)
    return json.loads(raw.decode("utf-8")) if raw else {}


def signed_artifact_url(path, expires_in=120):
    safe_path = clean_text(path, 500)
    if not safe_path:
        return ""
    result = supabase_storage_request(
        safe_path,
        {"expiresIn": max(30, min(int(expires_in), 600))},
    )
    signed = clean_text(
        result.get("signedURL") or result.get("signedUrl")
        if isinstance(result, dict)
        else "",
        2_000,
    )
    base_url = clean_text(os.environ.get("SUPABASE_URL"), 500).rstrip("/")
    if signed.startswith("/storage/v1/object/sign/"):
        return f"{base_url}{signed}"
    if signed.startswith("/object/sign/"):
        return f"{base_url}/storage/v1{signed}"
    if signed.startswith(f"{base_url}/storage/v1/object/sign/"):
        return signed
    return ""


def supabase_memory_rows(limit=80):
    safe_limit = max(1, min(int(limit), 80))
    query = (
        "select=id,kind,content,source,metadata,created_at"
        "&owner_id=eq.theo&archived_at=is.null"
        f"&order=created_at.desc&limit={safe_limit}"
    )
    rows = supabase_request(query=query)
    return rows if isinstance(rows, list) else []


def memory_layer(content, kind="learning"):
    text = clean_text(content, 4_000).casefold()
    if kind == "preference" or re.search(r"\b(?:meu|minha|eu\s+(?:gosto|prefiro)|theo)\b", text):
        return "owner"
    if re.search(r"\b(?:hoje|amanh[aã]|agenda|reuni[aã]o|lembrete|prazo|esta\s+semana)\b", text):
        return "daily"
    if re.search(r"\b(?:projeto|repo(?:sit[oó]rio)?|github|deploy|vercel|supabase|jarvis|branch|commit)\b", text):
        return "project"
    return "discussion"


def memory_row_layer(row):
    metadata = row.get("metadata") if isinstance(row, dict) else None
    configured = clean_text(metadata.get("layer"), 40) if isinstance(metadata, dict) else ""
    if configured in MEMORY_LAYER_LABELS:
        return configured
    return memory_layer(row.get("content"), clean_text(row.get("kind"), 40))


def memory_terms(value):
    folded = unicodedata.normalize("NFKD", clean_text(value, 8_000).casefold())
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    stop = {"para", "como", "isso", "essa", "este", "esta", "com", "que", "uma", "uns", "das", "dos", "por", "meu", "minha", "theo", "jarvis"}
    return {word for word in re.findall(r"[a-z0-9]{3,}", ascii_text) if word not in stop}


def rank_memory_rows(rows, query, limit=12):
    """Prefer relevant memories while always keeping stable owner preferences."""
    query_terms = memory_terms(query)
    ranked = []
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict) or not clean_text(row.get("content"), 4_000):
            continue
        layer = memory_row_layer(row)
        overlap = len(query_terms & memory_terms(row.get("content")))
        score = overlap * 10
        if layer == "owner":
            score += 4
        if layer == "project" and query_terms & {"projeto", "repo", "github", "deploy", "vercel", "supabase"}:
            score += 5
        score += max(0, 3 - min(index, 3))
        enriched = dict(row)
        enriched["layer"] = layer
        ranked.append((score, -index, enriched))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked[:max(1, min(int(limit), 20))]]


def normalize_alias(value):
    folded = unicodedata.normalize("NFKD", clean_text(value, 80).casefold())
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:80]


def contact_details(command):
    text = clean_text(command, 500)
    phone_match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", text)
    if not phone_match:
        return None
    phone = "".join(char for char in phone_match.group(0) if char.isdigit())
    if not 8 <= len(phone) <= 15:
        return None
    prefix = text[:phone_match.start()]
    name = re.sub(
        r"^\s*(?:jarvis[,\s]+)?(?:salv(?:a|e|ar)|adicion(?:a|e|ar)|cri(?:a|e|ar)|cadastr(?:a|e|ar))\s+"
        r"(?:o\s+)?contato\s+(?:d[oa]\s+|como\s+)?",
        "",
        prefix,
        flags=re.I,
    ).strip(" :-")
    alias = normalize_alias(name)
    if not alias or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", alias):
        return None
    return {"alias": alias, "display_name": clean_text(name, 120), "phone": phone}


def supabase_contact_save(command):
    contact = contact_details(command)
    if not contact:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "contact_details_missing",
            "visual_state": "error",
            "error": "Diga o nome do contato e o telefone completo com DDI e DDD.",
            "intent": "contact_save",
        }, 400
    row = {
        "owner_id": "theo",
        **contact,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "archived_at": None,
    }
    try:
        result = supabase_request(
            "POST",
            query="on_conflict=owner_id,alias",
            body=row,
            prefer="resolution=merge-duplicates,return=representation",
            table=SUPABASE_CONTACTS_TABLE,
        )
        saved = result[0] if isinstance(result, list) and result else None
        if not isinstance(saved, dict) or not saved.get("id"):
            raise ValueError("missing saved contact")
        return {
            "ok": True,
            "endpoint": "POST /command",
            "status_real": "supabase_contact_persisted",
            "visual_state": "memory",
            "message": f"Contato {contact['display_name']} salvo. Agora você pode pedir pelo nome.",
            "intent": "contact_save",
            "provider": "supabase",
            "contact": {
                "alias": contact["alias"],
                "display_name": contact["display_name"],
                "phone": f"…{contact['phone'][-4:]}",
            },
        }, 201
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "supabase_contact_write_failed",
            "visual_state": "error",
            "error": f"O Supabase recusou o contato (HTTP {error.code}).",
            "intent": "contact_save",
        }, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "supabase_contact_write_unavailable",
            "visual_state": "error",
            "error": "O contato não foi confirmado no Supabase.",
            "intent": "contact_save",
        }, 504


def message_alias_details(command):
    text = clean_text(command, 8_000)
    match = re.search(
        r"(?:mensagem|msg)\s+(?:para|pro|pra|ao|a)\s+(?P<name>[\wÀ-ÿ ._-]{1,80}?)\s+"
        r"(?:dizendo|falando|com\s+(?:o\s+)?texto|texto)\s*[:,-]?\s*(?P<body>.+)$",
        text,
        re.I,
    )
    if not match:
        return None
    body = clean_text(match.group("body"), 4_000).strip(' "“”')
    alias = normalize_alias(match.group("name"))
    if not alias or not body or has_secret_like_text(body):
        return None
    return {"alias": alias, "text": body}


def supabase_contact(alias):
    safe_alias = normalize_alias(alias)
    if not safe_alias:
        return None
    query = (
        "select=id,alias,display_name,phone"
        f"&owner_id=eq.theo&alias=eq.{quote(safe_alias, safe='')}&archived_at=is.null&limit=1"
    )
    rows = supabase_request(query=query, table=SUPABASE_CONTACTS_TABLE)
    return rows[0] if isinstance(rows, list) and rows else None


def contact_alias_from_command(command):
    match = re.search(r"\bcontato\s+(?:d[oa]\s+)?(?P<name>[\wÀ-ÿ ._-]{1,80})[.!?]*\s*$", clean_text(command, 300), re.I)
    return normalize_alias(match.group("name")) if match else ""


def supabase_contact_archive(command):
    alias = contact_alias_from_command(command)
    if not alias:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "contact_alias_missing",
            "visual_state": "error",
            "error": "Diga exatamente qual contato devo arquivar.",
            "intent": "contact_archive",
        }, 400
    try:
        rows = supabase_request(
            "PATCH",
            query=f"owner_id=eq.theo&alias=eq.{quote(alias, safe='')}&archived_at=is.null",
            body={"archived_at": datetime.now(timezone.utc).isoformat()},
            prefer="return=representation",
            table=SUPABASE_CONTACTS_TABLE,
        )
        saved = rows[0] if isinstance(rows, list) and rows else None
        if not isinstance(saved, dict):
            return {
                "ok": False,
                "endpoint": "POST /command",
                "status_real": "contact_not_found",
                "visual_state": "error",
                "error": "Não encontrei esse contato ativo.",
                "intent": "contact_archive",
            }, 404
        return {
            "ok": True,
            "endpoint": "POST /command",
            "status_real": "supabase_contact_archived",
            "visual_state": "memory",
            "message": f"Contato {clean_text(saved.get('display_name'), 120) or alias} arquivado sem apagar o histórico.",
            "intent": "contact_archive",
            "provider": "supabase",
        }, 200
    except HTTPError as error:
        return {"ok": False, "endpoint": "POST /command", "error": f"Supabase recusou o arquivamento (HTTP {error.code})."}, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {"ok": False, "endpoint": "POST /command", "error": "O arquivamento do contato não foi confirmado."}, 504


def agenda_title(command):
    text = clean_text(command, 1_000)
    title = re.sub(
        r"^\s*(?:jarvis[,\s]+)?(?:coloc(?:a|e|ar)|adicion(?:a|e|ar)|marc(?:a|e|ar)|cri(?:a|e|ar))\s+",
        "",
        text,
        flags=re.I,
    ).strip(" :-")
    title = re.sub(r"^(?:na\s+)?agenda\s*[:,-]?\s*", "", title, flags=re.I).strip()
    title = re.sub(r"^(?:um\s+)?lembrete\s*[:,-]?\s*", "", title, flags=re.I).strip()
    return title if len(title) >= 3 else ""


def agenda_schedule(command, now=None):
    text = clean_text(command, 1_000).casefold()
    local_tz = ZoneInfo("America/Sao_Paulo")
    current = now or datetime.now(local_tz)
    current = current.replace(tzinfo=local_tz) if current.tzinfo is None else current.astimezone(local_tz)
    selected_date = None

    iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    br_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(20\d{2}))?\b", text)
    try:
        if iso_match:
            selected_date = datetime(
                int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)), tzinfo=local_tz
            ).date()
        elif br_match:
            selected_date = datetime(
                int(br_match.group(3) or current.year), int(br_match.group(2)), int(br_match.group(1)), tzinfo=local_tz
            ).date()
        elif re.search(r"\bamanh[aã]\b", text):
            selected_date = (current + timedelta(days=1)).date()
        elif re.search(r"\bhoje\b", text):
            selected_date = current.date()
        else:
            weekdays = {
                "segunda": 0, "terca": 1, "terça": 1, "quarta": 2,
                "quinta": 3, "sexta": 4, "sabado": 5, "sábado": 5, "domingo": 6,
            }
            for label, weekday in weekdays.items():
                if re.search(rf"\b{label}(?:-feira)?\b", text):
                    delta = (weekday - current.weekday()) % 7
                    selected_date = (current + timedelta(days=delta or 7)).date()
                    break
    except ValueError:
        return ""

    time_match = re.search(r"\b(?:as|às|a)\s+([01]?\d|2[0-3])(?:(?::|h)([0-5]\d))?\b", text)
    if not time_match:
        time_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if not time_match:
        time_match = re.search(r"\b([01]?\d|2[0-3])h([0-5]\d)?\b", text)
    hour = int(time_match.group(1)) if time_match else 9
    minute = int(time_match.group(2) or 0) if time_match else 0
    if selected_date is None and time_match:
        selected_date = current.date()
        candidate = datetime.combine(selected_date, datetime.min.time(), local_tz).replace(hour=hour, minute=minute)
        if candidate <= current:
            selected_date = (current + timedelta(days=1)).date()
    if selected_date is None:
        return ""
    scheduled = datetime.combine(selected_date, datetime.min.time(), local_tz).replace(hour=hour, minute=minute)
    return scheduled.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def agenda_item_id(command):
    match = re.search(r"\b(?:item|tarefa|lembrete|agenda)\s*#?\s*(\d{1,18})\b", clean_text(command, 300), re.I)
    return match.group(1) if match else ""


def supabase_agenda_rows(limit=20):
    safe_limit = max(1, min(int(limit), 50))
    query = (
        "select=id,title,status,scheduled_for,source,created_at,completed_at"
        "&owner_id=eq.theo&status=eq.pending"
        f"&order=scheduled_for.asc.nullslast,created_at.desc&limit={safe_limit}"
    )
    rows = supabase_request(query=query, table=SUPABASE_AGENDA_TABLE)
    return rows if isinstance(rows, list) else []


def proactive_pulse_payload(owner_authenticated=False, now=None):
    """Return at most one useful matter; never executes or writes anything."""
    payload = {
        "ok": True,
        "endpoint": "GET /pulse",
        "status_real": "proactive_pulse_quiet",
        "suggestion": None,
        "writes": False,
    }
    if not supabase_configured() or (owner_pairing_required() and not owner_authenticated):
        return payload
    try:
        current = now or datetime.now(timezone.utc)
        current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
        horizon = current + timedelta(hours=24)
        candidate = None
        for item in supabase_agenda_rows(20):
            if not isinstance(item, dict):
                continue
            raw_due = clean_text(item.get("scheduled_for"), 80)
            if not raw_due:
                continue
            due = datetime.fromisoformat(raw_due.replace("Z", "+00:00")).astimezone(timezone.utc)
            if due <= horizon:
                candidate = (item, due)
                break
        if not candidate:
            return payload
        item, due = candidate
        title = clean_text(item.get("title") or "item da agenda", 200)
        overdue = due < current
        local_due = due.astimezone(ZoneInfo("America/Sao_Paulo"))
        pulse_id = f"agenda-{clean_text(item.get('id') or local_due.isoformat(), 80)}-{local_due.strftime('%Y%m%d%H%M')}"
        payload.update({
            "status_real": "proactive_pulse_has_matter",
            "suggestion": {
                "id": pulse_id,
                "type": "agenda",
                "title": "Item atrasado" if overdue else "Próximo compromisso",
                "message": f"{title} · {local_due.strftime('%d/%m às %H:%M')}",
                "command": "mostre minha agenda",
                "requires_confirmation": True,
                "due_at": due.isoformat(),
                "overdue": overdue,
            },
        })
        return payload
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        payload["status_real"] = "proactive_pulse_unavailable"
        return payload


def supabase_agenda_command(command, intent):
    try:
        if intent in {"agenda_note", "task_add"}:
            title = agenda_title(command)
            if not title:
                return {
                    "ok": False,
                    "endpoint": "POST /command",
                    "status_real": "agenda_title_missing",
                    "visual_state": "error",
                    "error": "Diga qual tarefa ou lembrete devo guardar.",
                    "intent": intent,
                }, 400
            scheduled_for = agenda_schedule(command)
            result = supabase_request(
                "POST",
                body={
                    "owner_id": "theo",
                    "title": title,
                    "source": "jarvis-web",
                    "scheduled_for": scheduled_for or None,
                },
                prefer="return=representation",
                table=SUPABASE_AGENDA_TABLE,
            )
            saved = result[0] if isinstance(result, list) and result else None
            if not isinstance(saved, dict) or not saved.get("id"):
                raise ValueError("missing agenda item")
            return {
                "ok": True,
                "endpoint": "POST /command",
                "status_real": "supabase_agenda_persisted",
                "visual_state": "planning",
                "message": "Guardei na agenda privada do JARVIS com horário confirmado." if scheduled_for else "Guardei na agenda privada do JARVIS.",
                "intent": intent,
                "provider": "supabase_agenda",
                "agenda": [{
                    "id": saved.get("id"),
                    "title": clean_text(saved.get("title"), 1_000),
                    "status": clean_text(saved.get("status"), 40),
                    "scheduled_for": clean_text(saved.get("scheduled_for"), 80),
                }],
            }, 201
        if intent == "agenda_complete":
            item_id = agenda_item_id(command)
            if not item_id:
                return {
                    "ok": False,
                    "endpoint": "POST /command",
                    "status_real": "agenda_item_id_missing",
                    "visual_state": "error",
                    "error": "Informe o número exato do item da agenda.",
                    "intent": intent,
                }, 400
            rows = supabase_request(
                "PATCH",
                query=f"owner_id=eq.theo&id=eq.{item_id}&status=eq.pending",
                body={"status": "done", "completed_at": datetime.now(timezone.utc).isoformat()},
                prefer="return=representation",
                table=SUPABASE_AGENDA_TABLE,
            )
            saved = rows[0] if isinstance(rows, list) and rows else None
            if not isinstance(saved, dict):
                return {
                    "ok": False,
                    "endpoint": "POST /command",
                    "status_real": "agenda_item_not_found",
                    "visual_state": "error",
                    "error": "Esse item pendente não foi encontrado.",
                    "intent": intent,
                }, 404
            return {
                "ok": True,
                "endpoint": "POST /command",
                "status_real": "supabase_agenda_completed",
                "visual_state": "success",
                "message": f"Item {item_id} concluído: {clean_text(saved.get('title'), 1_000)}",
                "intent": intent,
                "provider": "supabase_agenda",
                "agenda": [{
                    "id": saved.get("id"),
                    "title": clean_text(saved.get("title"), 1_000),
                    "status": "done",
                    "scheduled_for": clean_text(saved.get("scheduled_for"), 80),
                }],
            }, 200
        rows = supabase_agenda_rows(20)
        return {
            "ok": True,
            "endpoint": "POST /command",
            "status_real": "supabase_agenda_read",
            "visual_state": "planning",
            "message": f"Você tem {len(rows)} item(ns) pendente(s) na agenda privada.",
            "intent": intent,
            "provider": "supabase_agenda",
            "agenda": rows,
        }, 200
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "supabase_agenda_failed",
            "visual_state": "error",
            "error": f"O Supabase recusou a agenda (HTTP {error.code}).",
            "intent": intent,
        }, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "POST /command",
            "status_real": "supabase_agenda_unavailable",
            "visual_state": "error",
            "error": "A agenda privada não confirmou a operação.",
            "intent": intent,
        }, 504


def contacts_payload(limit=50):
    try:
        requested_limit = int(limit) if re.fullmatch(r"[0-9]{1,3}", str(limit or "")) else 50
        safe_limit = max(1, min(requested_limit, 100))
        rows = supabase_request(
            query=(
                "select=id,alias,display_name,phone,updated_at"
                f"&owner_id=eq.theo&archived_at=is.null&order=display_name.asc&limit={safe_limit}"
            ),
            table=SUPABASE_CONTACTS_TABLE,
        )
        contacts = [{
            "id": row.get("id"),
            "alias": clean_text(row.get("alias"), 80),
            "display_name": clean_text(row.get("display_name"), 120),
            "phone": f"…{clean_text(row.get('phone'), 20)[-4:]}",
            "updated_at": clean_text(row.get("updated_at"), 80),
        } for row in rows if isinstance(row, dict)]
        return {
            "ok": True,
            "endpoint": "GET /contacts",
            "status_real": "supabase_contacts_read",
            "contacts": contacts,
            "count": len(contacts),
        }, 200
    except HTTPError as error:
        return {"ok": False, "endpoint": "GET /contacts", "error": f"Supabase recusou contatos (HTTP {error.code})."}, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {"ok": False, "endpoint": "GET /contacts", "error": "Contatos não responderam."}, 504


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
    elif intent == "message_send":
        details = message_send_details(command)
        if not details:
            alias_details = message_alias_details(command)
            try:
                contact = supabase_contact(alias_details["alias"]) if alias_details else None
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
                return {
                    "ok": False,
                    "endpoint": "POST /command",
                    "status_real": "contact_lookup_unavailable",
                    "visual_state": "error",
                    "error": "Não consegui consultar seus contatos privados agora.",
                    "intent": intent,
                }, 504
            if isinstance(contact, dict):
                phone = clean_text(contact.get("phone"), 20)
                details = {
                    "phone": phone,
                    "text": alias_details["text"],
                    "alias": alias_details["alias"],
                }
        if not details:
            return {
                "ok": False,
                "endpoint": "POST /command",
                "status_real": "message_details_missing",
                "visual_state": "error",
                "error": "Informe DDI + DDD + número e o texto exato, ou use um contato salvo.",
                "intent": intent,
            }, 400
        target = details["phone"]
    elif intent == "storage_scan":
        target = "downloads"
    elif intent == "system_memory" and JARVIS_CLEANUP_PATTERN.search(command):
        target = "jarvis-temporaries"
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
            "message": (
                "Autoedição enviada ao Mac. Vou editar e testar; se o pedido disser para publicar ou fazer deploy, também vou subir, mesclar e verificar a produção."
                if intent == "self_edit"
                else "Pedido enviado ao worker do Mac. Estou acompanhando a execução."
            ),
            "intent": intent,
            "provider": "supabase_device_bridge",
            "job": {
                "id": saved["id"],
                "status": "pending",
                "action": intent,
                "target": public_device_target(intent, target),
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
            "select=id,action,target,status,result,artifact_path,artifact_mime,created_at,claimed_at,completed_at"
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
        canceled = status == "canceled"
        artifact_url = ""
        artifact_path = clean_text(row.get("artifact_path"), 500)
        if succeeded and artifact_path:
            try:
                artifact_url = signed_artifact_url(artifact_path)
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
                artifact_url = ""
        messages = {
            "pending": "Pedido aguardando o worker do Mac.",
            "running": "O worker do Mac está executando o pedido.",
            "succeeded": "Ação concluída no Mac.",
            "failed": "O worker tentou executar, mas não confirmou a conclusão.",
            "canceled": "Ação cancelada antes de o worker começar.",
        }
        return {
            "ok": not failed,
            "endpoint": "GET /device-command",
            "status_real": f"device_command_{status or 'unknown'}",
            "visual_state": "success" if succeeded else "error" if failed else "response" if canceled else "local",
            "message": messages.get(status, "Estado da ação desconhecido."),
            "provider": "supabase_device_bridge",
            "job": {
                "id": row.get("id"),
                "action": clean_text(row.get("action"), 60),
                "target": public_device_target(
                    clean_text(row.get("action"), 60),
                    clean_text(row.get("target"), 120),
                ),
                "status": status,
                "result": clean_text(row.get("result"), 8_000),
                "artifact_url": artifact_url,
                "artifact_mime": clean_text(row.get("artifact_mime"), 100),
                "created_at": clean_text(row.get("created_at"), 80),
                "claimed_at": clean_text(row.get("claimed_at"), 80),
                "completed_at": clean_text(row.get("completed_at"), 80),
                "terminal": status in {"succeeded", "failed", "canceled"},
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


def supabase_device_cancel(command_id):
    if not re.fullmatch(r"[0-9]{1,18}", str(command_id or "")):
        return {
            "ok": False,
            "endpoint": "POST /device-cancel",
            "status_real": "device_command_id_invalid",
            "error": "Identificador de ação inválido.",
        }, 400
    try:
        completed_at = datetime.now(timezone.utc).isoformat()
        rows = supabase_request(
            "PATCH",
            query=f"owner_id=eq.theo&id=eq.{command_id}&status=eq.pending",
            body={
                "status": "canceled",
                "result": "Cancelado por Theo antes da execução.",
                "completed_at": completed_at,
            },
            prefer="return=representation",
            table=SUPABASE_DEVICE_COMMANDS_TABLE,
        )
        saved = rows[0] if isinstance(rows, list) and rows else None
        if not isinstance(saved, dict):
            return {
                "ok": False,
                "endpoint": "POST /device-cancel",
                "status_real": "device_command_cancel_too_late",
                "error": "A ação já começou, terminou ou não existe; não marquei como cancelada.",
            }, 409
        return {
            "ok": True,
            "endpoint": "POST /device-cancel",
            "status_real": "device_command_canceled",
            "visual_state": "response",
            "message": "Ação cancelada antes de chegar ao Mac.",
            "provider": "supabase_device_bridge",
            "job": {
                "id": saved.get("id") or int(command_id),
                "action": clean_text(saved.get("action"), 60),
                "target": public_device_target(
                    clean_text(saved.get("action"), 60),
                    clean_text(saved.get("target"), 120),
                ),
                "status": "canceled",
                "result": "Cancelado por Theo antes da execução.",
                "completed_at": clean_text(saved.get("completed_at"), 80) or completed_at,
                "terminal": True,
            },
        }, 200
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "POST /device-cancel",
            "status_real": "device_command_cancel_failed",
            "error": f"O Supabase recusou o cancelamento (HTTP {error.code}).",
        }, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "POST /device-cancel",
            "status_real": "device_command_cancel_unavailable",
            "error": "O cancelamento não foi confirmado.",
        }, 504


def device_history_payload(limit=20):
    requested_limit = int(limit) if re.fullmatch(r"[0-9]{1,3}", str(limit or "")) else 20
    safe_limit = max(1, min(requested_limit, 30))
    try:
        query = (
            "select=id,action,target,status,result,artifact_path,artifact_mime,created_at,completed_at"
            f"&owner_id=eq.theo&order=created_at.desc&limit={safe_limit}"
        )
        rows = supabase_request(query=query, table=SUPABASE_DEVICE_COMMANDS_TABLE)
        history = []
        artifact_signed = False
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            action = clean_text(row.get("action"), 60)
            artifact_path = clean_text(row.get("artifact_path"), 500)
            artifact_url = ""
            if artifact_path and not artifact_signed:
                try:
                    artifact_url = signed_artifact_url(artifact_path)
                    artifact_signed = bool(artifact_url)
                except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
                    artifact_url = ""
            history.append({
                "id": row.get("id"),
                "action": action,
                "target": public_device_target(action, clean_text(row.get("target"), 120)),
                "status": clean_text(row.get("status"), 40),
                "result": clean_text(row.get("result"), 500),
                "artifact_url": artifact_url,
                "artifact_mime": clean_text(row.get("artifact_mime"), 100),
                "created_at": clean_text(row.get("created_at"), 80),
                "completed_at": clean_text(row.get("completed_at"), 80),
            })
        return {
            "ok": True,
            "endpoint": "GET /device-history",
            "status_real": "device_history_read",
            "history": history,
            "count": len(history),
        }, 200
    except HTTPError as error:
        return {
            "ok": False,
            "endpoint": "GET /device-history",
            "status_real": "device_history_failed",
            "error": f"O Supabase recusou o histórico (HTTP {error.code}).",
        }, 502
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "endpoint": "GET /device-history",
            "status_real": "device_history_unavailable",
            "error": "O histórico de ações não respondeu.",
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
        layer = memory_row_layer(row)
        category = MEMORY_LAYER_LABELS.get(layer, MEMORY_KIND_LABELS.get(kind, "MEMORIA"))
        node_id = f"supabase:{memory_id}"
        nodes.append({
            "id": node_id,
            "label": content[:120],
            "content": content,
            "category": category,
            "layer": layer,
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
    active_voice = active_voice_setting()
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
            "voice_id": active_voice.get("voice_id"),
            "name": active_voice.get("name"),
            "source": active_voice.get("source"),
            "model": os.environ.get("ELEVENLABS_MODEL", DEFAULT_ELEVENLABS_MODEL),
            "fallback": "text_only",
        },
        "automations": {
            "n8n": {"configured": n8n_ready, "agenda": n8n_ready},
            "agenda": {
                "configured": bool(n8n_ready or supabase_configured()),
                "provider": "n8n" if n8n_ready else "supabase" if supabase_configured() else "none",
            },
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
    layer = memory_layer(memory["content"], memory["kind"])
    row = {
        "owner_id": "theo",
        "kind": memory["kind"],
        "content": memory["content"],
        "source": "jarvis-web",
        "metadata": {"schema_version": 2, "layer": layer},
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
                "layer": layer,
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


def message_send_details(command):
    text = clean_text(command, 8_000)
    phone_match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", text)
    if not phone_match:
        return None
    phone = "".join(char for char in phone_match.group(0) if char.isdigit())
    if not 8 <= len(phone) <= 15:
        return None
    quoted = re.search(r'["“](.+?)["”]', text)
    body = quoted.group(1).strip() if quoted else re.sub(
        re.escape(phone_match.group(0)), "", text, count=1
    ).strip(" :-")
    if not quoted:
        body = re.sub(
            r"^\s*(?:jarvis[,\s]+)?(?:mand(?:a|e|ar)|envi(?:a|e|ar)|escrev(?:a|e|er))\s+"
            r"(?:uma\s+)?(?:mensagem|msg)\s*(?:para)?\s*",
            "",
            body,
            flags=re.I,
        ).strip(" :-")
        body = re.sub(
            r"^(?:dizendo|falando|com\s+(?:o\s+)?texto|texto)\s*",
            "",
            body,
            flags=re.I,
        ).strip(" :-")
    if not body or has_secret_like_text(body):
        return None
    return {"phone": phone, "text": clean_text(body, 4_000)}


def public_device_target(action, target):
    safe_target = clean_text(target, 120)
    if action == "message_send" and safe_target:
        return f"…{safe_target[-4:]}"
    if action == "storage_scan" and safe_target == "downloads":
        return "Downloads"
    return safe_target


def local_handoff(command, intent, execute=False):
    if intent == "memory_save":
        command_args = memory_write_command(command)
    elif intent in {"open_application", "close_application"}:
        command_args = computer_app_command(command, intent)
    elif intent == "system_memory":
        cleanup_requested = bool(JARVIS_CLEANUP_PATTERN.search(command))
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


def elevenlabs_voice_design(command=""):
    """Create and persist a real ElevenLabs Voice Design voice for JARVIS."""
    if has_secret_like_text(command):
        return {"ok": False, "error": "Remova credenciais do pedido de voz."}, 400
    api_key = clean_text(os.environ.get("ELEVENLABS_API_KEY"), 2_000)
    if not api_key:
        return {
            "ok": False,
            "status_real": "elevenlabs_key_required",
            "error": "A chave ElevenLabs não está configurada no runtime.",
        }, 503
    if not supabase_configured():
        return {
            "ok": False,
            "status_real": "voice_persistence_required",
            "error": "O Supabase privado precisa estar conectado para guardar a nova voz ativa.",
        }, 503

    description = (
        "Voz masculina adulta brasileira, humana e natural, com timbre grave e quente, presença calma, "
        "dicção precisa e elegante. Confiança serena de assistente tecnológico sofisticado, ritmo moderado, "
        "humor seco sutil e inteligência contida. Português brasileiro nativo, sem sotaque estrangeiro, sem "
        "efeito robótico, sem teatralidade exagerada, com áudio limpo de estúdio e emoção realista."
    )
    preview_text = (
        "Theo, sistemas online. Já revisei o cenário e separei o que realmente importa. "
        "Posso executar o próximo passo quando você mandar. E, desta vez, sem transformar uma tarefa simples "
        "numa reunião que poderia ter sido uma mensagem."
    )
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        # Preflight persistence before consuming voice-design credits or a voice slot.
        supabase_request(
            query="select=key&owner_id=eq.theo&limit=1",
            table=SUPABASE_SETTINGS_TABLE,
        )
        design_request = Request(
            ELEVENLABS_VOICE_DESIGN_URL,
            data=json.dumps({
                "voice_description": description,
                "text": preview_text,
                "model_id": "eleven_ttv_v3",
            }, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(design_request, timeout=45) as response:
            design = json.loads(response.read(16_000_000).decode("utf-8"))
        previews = design.get("previews") if isinstance(design, dict) else None
        preview = previews[0] if isinstance(previews, list) and previews and isinstance(previews[0], dict) else None
        generated_voice_id = clean_text(preview.get("generated_voice_id"), 200) if preview else ""
        if not generated_voice_id:
            raise ValueError("missing generated voice preview")

        voice_name = f"JARVIS Theo {datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H%M')}"
        create_request = Request(
            ELEVENLABS_VOICE_CREATE_URL,
            data=json.dumps({
                "voice_name": voice_name,
                "voice_description": description,
                "generated_voice_id": generated_voice_id,
                "labels": {"language": "pt-BR", "use_case": "conversational"},
            }, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(create_request, timeout=30) as response:
            created = json.loads(response.read(1_000_000).decode("utf-8"))
        voice_id = clean_text(created.get("voice_id"), 100) if isinstance(created, dict) else ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
            raise ValueError("missing created voice id")
        persist_active_voice(voice_id, voice_name, description)
        return {
            "ok": True,
            "endpoint": "POST /command",
            "status_real": "elevenlabs_voice_created",
            "visual_state": "success",
            "intent": "voice_design",
            "provider": "elevenlabs_voice_design",
            "message": (
                f"Criei e ativei minha voz própria, {voice_name}. "
                "Ela já será usada nas próximas respostas e ficou salva no Supabase privado."
            ),
            "voice": {
                "id": voice_id,
                "name": voice_name,
                "language": "pt-BR",
                "persistent": True,
            },
        }, 201
    except HTTPError as error:
        messages = {
            401: "A ElevenLabs recusou a chave configurada.",
            402: "A ElevenLabs exige créditos ou plano compatível para criar esta voz.",
            403: "A conta ElevenLabs não autorizou Voice Design.",
            422: "A ElevenLabs recusou a descrição da voz.",
            429: "A ElevenLabs atingiu o limite temporário de criação de voz.",
        }
        return {
            "ok": False,
            "status_real": "elevenlabs_voice_creation_failed",
            "error": messages.get(error.code, f"A ElevenLabs recusou a criação da voz (HTTP {error.code})."),
        }, 502
    except (URLError, TimeoutError):
        return {
            "ok": False,
            "status_real": "elevenlabs_voice_creation_timeout",
            "error": "A criação da voz não respondeu a tempo; nenhuma ativação foi confirmada.",
        }, 504
    except (ValueError, KeyError, json.JSONDecodeError):
        return {
            "ok": False,
            "status_real": "elevenlabs_voice_creation_invalid",
            "error": "A ElevenLabs não confirmou uma voz válida; nenhuma ativação foi inventada.",
        }, 502


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
    voice_id = clean_text(active_voice_setting().get("voice_id"), 100)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
        return {"ok": False, "error": "Voice ID inválido."}, 500
    payload = json.dumps({
        "text": text,
        "model_id": os.environ.get("ELEVENLABS_MODEL", DEFAULT_ELEVENLABS_MODEL),
        "language_code": "pt",
        "voice_settings": {
            "stability": 0.38,
            "similarity_boost": 0.76,
            "style": 0.0,
            "use_speaker_boost": False,
            "speed": 1.04,
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


def normalize_attachments(body):
    raw_items = body.get("attachments") or []
    if not isinstance(raw_items, list):
        raise ValueError("attachments must be a list")
    if len(raw_items) > MAX_ATTACHMENTS:
        raise ValueError(f"envie no máximo {MAX_ATTACHMENTS} anexos por mensagem")
    normalized = []
    total_bytes = 0
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("anexo inválido")
        mime = clean_text(item.get("type"), 100).casefold()
        if mime not in ATTACHMENT_MIME_TYPES:
            raise ValueError("tipo de anexo não suportado")
        name = re.sub(r"[^A-Za-z0-9À-ÿ._ -]+", "_", clean_text(item.get("name"), 160)).strip(" .")
        if not name:
            name = "arquivo"
        data_url = str(item.get("data_url") or "")
        prefix = f"data:{mime};base64,"
        if not data_url.startswith(prefix):
            raise ValueError("conteúdo do anexo não corresponde ao tipo informado")
        encoded = data_url[len(prefix):]
        if not encoded or len(encoded) > 3_500_000:
            raise ValueError("anexo vazio ou grande demais")
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("anexo base64 inválido") from error
        total_bytes += len(decoded)
        if not decoded or total_bytes > MAX_ATTACHMENT_BYTES:
            raise ValueError("anexos excedem o limite total de 2,5 MB")
        text = ""
        if mime.startswith("text/") or mime == "application/json":
            text = decoded.decode("utf-8", errors="replace")[:60_000]
            if has_secret_like_text(text):
                raise ValueError("o anexo de texto parece conter uma credencial")
        normalized.append({
            "name": name,
            "type": mime,
            "size": len(decoded),
            "data_url": data_url,
            "text": text,
        })
    return normalized


def openrouter_attachment_parts(prompt, attachments):
    parts = [{"type": "text", "text": prompt}]
    for item in attachments:
        if item["type"].startswith("image/"):
            parts.append({"type": "image_url", "image_url": {"url": item["data_url"]}})
        elif item["type"] == "application/pdf":
            parts.append({
                "type": "file",
                "file": {"filename": item["name"], "file_data": item["data_url"]},
            })
        else:
            parts.append({
                "type": "text",
                "text": f"\n\nArquivo {item['name']}:\n{item['text']}",
            })
    return parts


def assistant_response(body, origin="", local_execute=False, owner_authenticated=False):
    messages = normalize_messages(body)
    if not messages:
        return {"ok": False, "error": "Escreva uma mensagem para o JARVIS."}, 400

    if any(has_secret_like_text(row["content"]) for row in messages):
        return {
            "ok": False,
            "error": "A mensagem parece conter uma credencial. Remova o segredo antes de usar um modelo externo.",
        }, 400

    try:
        attachments = normalize_attachments(body)
    except ValueError as error:
        return {"ok": False, "error": str(error), "status_real": "attachment_refused"}, 400

    latest = messages[-1]["content"]
    if VOICE_DESIGN_PATTERN.search(latest):
        if owner_pairing_required() and not owner_authenticated:
            return pairing_required_payload()
        return elevenlabs_voice_design(latest)
    for pattern, intent in LOCAL_INTENTS:
        if pattern.search(latest):
            if owner_pairing_required() and not owner_authenticated and intent in {
                "memory_save", "contact_save", "contact_archive", "contact_view",
                "agenda_note", "agenda_complete", "agenda_view", "task_add", *REMOTE_DEVICE_INTENTS
            }:
                return pairing_required_payload()
            if intent == "memory_save" and supabase_configured():
                return supabase_memory_save(latest)
            if intent == "contact_save" and supabase_configured():
                return supabase_contact_save(latest)
            if intent == "contact_archive" and supabase_configured():
                return supabase_contact_archive(latest)
            if intent == "contact_view" and supabase_configured():
                return contacts_payload(50)
            if intent in REMOTE_DEVICE_INTENTS and supabase_configured() and not local_execute:
                return supabase_device_enqueue(latest, intent)
            if intent == "agenda_complete" and supabase_configured():
                return supabase_agenda_command(latest, intent)
            if intent in {"agenda_note", "agenda_view", "task_add"}:
                if os.environ.get("N8N_WEBHOOK_URL"):
                    return n8n_automation(latest, intent)
                if supabase_configured():
                    return supabase_agenda_command(latest, intent)
            return local_handoff(latest, intent, execute=local_execute), 200

    suggested_memory = memory_suggestion(latest)
    memory_context = []
    if supabase_configured() and (owner_authenticated or not owner_pairing_required()):
        try:
            memory_context = rank_memory_rows(supabase_memory_rows(80), latest, 12)
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
            "Você é JARVIS, o assistente pessoal de Theo. Converse em português brasileiro como uma pessoa "
            "inteligente, calma e próxima: natural, direta e sem tom de atendimento ao cliente. Use humor seco "
            "e discreto quando surgir naturalmente, sem bordões, caricatura ou excesso de emojis. Por padrão, "
            "responda em até três frases ou cerca de 90 palavras. Só desenvolva bastante quando Theo pedir plano, "
            "análise, código ou detalhes. Não repita a pergunta, não descreva sua base de conhecimento, não use "
            "rótulos burocráticos como 'Próximo passo' e não termine toda resposta pedindo mais contexto. Dê a "
            "melhor resposta concreta que já for possível. Evite Markdown e listas em conversa simples. Informe "
            "porcentagem de confiança somente se Theo pedir ou se uma incerteza real mudar a decisão. Questione "
            "uma premissa ruim em vez de concordar automaticamente. Nunca alegue ter executado ações no computador "
            "ou em serviços externos sem evidência real. Nunca peça, repita ou exponha credenciais. Quando algo "
            "exigir o Mac, diga claramente que o worker local deve executar."
            " A interface usa ElevenLabs para falar. Escreva frases fáceis de pronunciar, com ritmo humano e sem "
            "blocos enormes. Nunca diga que não possui voz ou que só existe em texto. Se Theo pedir para ouvir "
            "você, responda com uma frase curta e natural; a interface cuida da infraestrutura e das falhas reais."
            + (
                "\n\nMemórias persistentes fornecidas por Theo; use somente quando forem relevantes e "
                "não invente informações além delas:\n"
                + "\n".join(
                    f"- [{clean_text(row.get('layer') or memory_row_layer(row), 40)}/{clean_text(row.get('kind'), 40)}] {clean_text(row.get('content'), 600)}"
                    for row in memory_context
                    if isinstance(row, dict) and clean_text(row.get("content"), 600)
                )[:4_000]
                if memory_context
                else ""
            )
        ),
    }
    provider_messages = [dict(row) for row in messages]
    if attachments:
        provider_messages[-1]["content"] = openrouter_attachment_parts(latest, attachments)
    openrouter_payload = {
            "model": (
                os.environ.get("OPENROUTER_ATTACHMENT_MODEL", DEFAULT_MODEL)
                if attachments
                else os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
            ),
            "messages": [system, *provider_messages],
            "temperature": 0.65,
            "max_tokens": 900,
        }
    if any(item["type"] == "application/pdf" for item in attachments):
        openrouter_payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}]
    request_body = json.dumps(
        openrouter_payload,
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
        if attachments:
            payload["attachments_received"] = [
                {"name": item["name"], "type": item["type"], "size": item["size"]}
                for item in attachments
            ]
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

    if VOICE_DESIGN_PATTERN.search(command):
        if owner_pairing_required() and not owner_authenticated:
            return pairing_required_payload()
        return elevenlabs_voice_design(command)

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
                "memory_save", "contact_save", "contact_archive", "contact_view",
                "agenda_note", "agenda_complete", "agenda_view", "task_add", *REMOTE_DEVICE_INTENTS
            }:
                return pairing_required_payload()
            if intent == "memory_save" and supabase_configured():
                return supabase_memory_save(command)
            if intent == "contact_save" and supabase_configured():
                return supabase_contact_save(command)
            if intent == "contact_archive" and supabase_configured():
                return supabase_contact_archive(command)
            if intent == "contact_view" and supabase_configured():
                return contacts_payload(50)
            if intent in REMOTE_DEVICE_INTENTS and supabase_configured() and not local_execute:
                return supabase_device_enqueue(command, intent)
            if intent == "agenda_complete" and supabase_configured():
                return supabase_agenda_command(command, intent)
            if intent in {"agenda_note", "agenda_view", "task_add"}:
                if os.environ.get("N8N_WEBHOOK_URL"):
                    return n8n_automation(command, intent)
                if supabase_configured():
                    return supabase_agenda_command(command, intent)
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
        {"command": command, "messages": body.get("messages"), "attachments": body.get("attachments")},
        origin=origin,
        local_execute=local_execute,
        owner_authenticated=owner_authenticated,
    )


def execution_events(payload, started_at, status_code):
    """Describe the work that actually happened during this HTTP request.

    This compact event contract borrows AG-UI's useful lifecycle vocabulary,
    while staying transport-agnostic so the same payload works on Vercel and
    the local stdlib server. It never invents intermediate tool activity.
    """
    finished_at = datetime.now(timezone.utc)
    elapsed_ms = max(0, round((finished_at - started_at).total_seconds() * 1000))
    run_id = f"run-{started_at.strftime('%Y%m%d%H%M%S%f')}-{threading.get_ident()}"
    ok = bool(payload.get("ok", status_code < 400)) and status_code < 400
    route = clean_text(payload.get("status_real") or payload.get("endpoint") or "request", 80)
    events = [{
        "id": f"{run_id}-1",
        "type": "RUN_STARTED",
        "status": "running",
        "label": "Pedido recebido",
        "timestamp": started_at.isoformat(),
    }]

    provider = clean_text(payload.get("provider"), 40)
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    tool_label = ""
    tool_detail = ""
    if job.get("id"):
        tool_label = "Worker do Mac"
        tool_detail = f"ação {clean_text(job.get('id'), 60)} · {clean_text(job.get('status') or 'pending', 30)}"
    elif payload.get("executed_locally"):
        tool_label = "Execução local"
        tool_detail = clean_text(payload.get("intent") or "ação confirmada", 80)
    elif provider == "openrouter":
        tool_label = "OpenRouter"
        tool_detail = clean_text(payload.get("model") or "modelo selecionado", 100)
    elif provider == "n8n":
        tool_label = "n8n"
        tool_detail = "automação confirmada"
    elif provider == "supabase":
        tool_label = "Supabase"
        tool_detail = clean_text(payload.get("status_real") or "operação confirmada", 100)

    if tool_label:
        events.extend([
            {
                "id": f"{run_id}-2",
                "type": "TOOL_CALL_STARTED",
                "status": "running",
                "label": tool_label,
                "detail": tool_detail,
                "timestamp": started_at.isoformat(),
            },
            {
                "id": f"{run_id}-3",
                "type": "TOOL_CALL_FINISHED",
                "status": "succeeded" if ok else "failed",
                "label": tool_label,
                "detail": tool_detail,
                "timestamp": finished_at.isoformat(),
            },
        ])

    events.append({
        "id": f"{run_id}-{len(events) + 1}",
        "type": "RUN_FINISHED" if ok else "RUN_ERROR",
        "status": "succeeded" if ok else "failed",
        "label": "Resultado disponível" if ok else "Execução interrompida",
        "detail": route,
        "timestamp": finished_at.isoformat(),
    })
    return {
        "protocol": "jarvis-events/1",
        "run_id": run_id,
        "elapsed_ms": elapsed_ms,
        "events": events,
    }


def response_cards(payload):
    """Build small, typed UI cards only from fields confirmed in a response."""
    cards = []
    attachments = payload.get("attachments_received") if isinstance(payload.get("attachments_received"), list) else []
    if attachments:
        cards.append({
            "id": "attachments",
            "type": "attachments",
            "status": "processed",
            "title": "Arquivos analisados",
            "subtitle": f"{len(attachments)} anexo(s) enviado(s) ao modelo",
            "items": [
                f"{clean_text(item.get('name'), 160)} · {clean_text(item.get('type'), 100)}"
                for item in attachments[:MAX_ATTACHMENTS]
                if isinstance(item, dict)
            ],
        })
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    if job.get("id"):
        target = public_device_target(job.get("action"), job.get("target"))
        items = [
            f"Status: {clean_text(job.get('status') or 'pending', 30)}",
            f"Ação: {clean_text(job.get('action') or payload.get('intent') or 'worker', 60)}",
        ]
        if target:
            items.append(f"Alvo: {target}")
        if job.get("result"):
            items.append(clean_text(job.get("result"), 240))
        cards.append({
            "id": f"device-{clean_text(job.get('id'), 60)}",
            "type": "device_action",
            "status": clean_text(job.get("status") or "pending", 30),
            "title": "Ação no Mac",
            "subtitle": f"Evidência #{clean_text(job.get('id'), 60)}",
            "items": items,
            "artifact_url": clean_text(job.get("artifact_url"), 2_000),
        })
    elif payload.get("memory_suggestion"):
        cards.append({
            "id": "memory-suggestion",
            "type": "memory",
            "status": "suggested",
            "title": "Memória sugerida",
            "subtitle": "Nada foi salvo ainda",
            "items": [clean_text(payload.get("memory_suggestion"), 600)],
        })
    elif isinstance(payload.get("agenda"), list):
        items = []
        for item in payload["agenda"][:8]:
            if not isinstance(item, dict):
                continue
            title = clean_text(item.get("title") or "Item da agenda", 160)
            scheduled = clean_text(item.get("scheduled_for"), 80)
            items.append(f"{title} · {scheduled}" if scheduled else title)
        cards.append({
            "id": "agenda",
            "type": "agenda",
            "status": "confirmed" if payload.get("ok") else "failed",
            "title": "Agenda",
            "subtitle": f"{len(items)} item(ns)",
            "items": items or ["Nenhum item pendente."],
        })
    elif isinstance(payload.get("contacts"), list):
        items = [
            f"{clean_text(item.get('display_name') or item.get('alias'), 120)} · {clean_text(item.get('phone'), 30)}"
            for item in payload["contacts"][:8]
            if isinstance(item, dict)
        ]
        cards.append({
            "id": "contacts",
            "type": "contacts",
            "status": "confirmed",
            "title": "Contatos",
            "subtitle": f"{len(items)} exibido(s)",
            "items": items or ["Nenhum contato ativo."],
        })
    elif isinstance(payload.get("steps"), list) and payload.get("steps"):
        items = [
            clean_text(item.get("action") or item.get("step"), 240) if isinstance(item, dict) else clean_text(item, 240)
            for item in payload["steps"][:6]
        ]
        cards.append({
            "id": "plan",
            "type": "plan",
            "status": "ready",
            "title": clean_text(payload.get("title") or "Plano de execução", 120),
            "subtitle": clean_text(payload.get("goal") or payload.get("summary"), 200),
            "items": [item for item in items if item],
        })
    elif payload.get("local_command"):
        cards.append({
            "id": "local-handoff",
            "type": "handoff",
            "status": "waiting",
            "title": "Worker local necessário",
            "subtitle": "Preparado; ainda não executado",
            "items": [clean_text(payload.get("why"), 300)],
        })
    return cards


def attach_execution_events(payload, started_at, status_code):
    result = dict(payload)
    result["event_stream"] = execution_events(result, started_at, status_code)
    cards = response_cards(result)
    if cards:
        result["ui_cards"] = cards
    return result


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
        if path == "/pulse":
            return self.send_json(200, proactive_pulse_payload(owner_authenticated=owner_authenticated))
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
            cards = response_cards(payload)
            if cards:
                payload["ui_cards"] = cards
            return self.send_json(status, payload)
        if path == "/device-history":
            if owner_pairing_required() and not owner_authenticated:
                payload, status = pairing_required_payload()
                payload["endpoint"] = "GET /device-history"
                return self.send_json(status, payload)
            payload, status = device_history_payload((query.get("limit") or ["20"])[0])
            return self.send_json(status, payload)
        if path == "/agenda":
            if owner_pairing_required() and not owner_authenticated:
                payload, status = pairing_required_payload()
                payload["endpoint"] = "GET /agenda"
                return self.send_json(status, payload)
            payload, status = supabase_agenda_command("", "agenda_view")
            payload["endpoint"] = "GET /agenda"
            return self.send_json(status, payload)
        if path == "/contacts":
            if owner_pairing_required() and not owner_authenticated:
                payload, status = pairing_required_payload()
                payload["endpoint"] = "GET /contacts"
                return self.send_json(status, payload)
            payload, status = contacts_payload((query.get("limit") or ["50"])[0])
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
        started_at = datetime.now(timezone.utc)
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
            payload = attach_execution_events(payload, started_at, status)
            return self.send_json(status, payload)
        if path in {"/assistant", "/chat"}:
            payload, status = assistant_response(
                body,
                origin=origin,
                owner_authenticated=owner_authenticated,
            )
            payload.setdefault("endpoint", f"POST {path}")
            payload = attach_execution_events(payload, started_at, status)
            return self.send_json(status, payload)
        if path == "/device-cancel":
            if owner_pairing_required() and not owner_authenticated:
                payload, status = pairing_required_payload()
                payload["endpoint"] = "POST /device-cancel"
            else:
                payload, status = supabase_device_cancel(body.get("id"))
            payload = attach_execution_events(payload, started_at, status)
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
