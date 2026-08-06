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
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen
import argparse
import json
import mimetypes
import os
import re
import shlex


ROOT = Path(__file__).resolve().parents[1]
UI_FILE = ROOT / "web" / "index.html"
UI_ASSET_DIR = ROOT / "11_SCRIPTS" / "jarvis_ui_assets"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
MAX_BODY_BYTES = 32_768
MAX_PROMPT_CHARS = 8_000

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

WEB_CAPABILITIES = [
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
        "name": "feature_planning",
        "status": "available",
        "what": "Planos, briefs, checklists e triagem sem escrita persistente.",
    },
    {
        "name": "local_worker_handoff",
        "status": "available",
        "what": "Transforma pedidos de dispositivo em comandos explícitos para o worker local.",
    },
]

LOCAL_INTENTS = (
    (re.compile(r"\b(print|screenshot|captur(?:a|ar)|tela)\b", re.I), "screen_capture"),
    (re.compile(r"\b(falar|fala|voz|audio|áudio|ler em voz alta)\b", re.I), "speak"),
    (re.compile(r"\b(converter|imagem|foto|png|jpe?g|heic|tiff)\b", re.I), "image_convert"),
    (re.compile(r"\b(whatsapp|mensagem|mandar msg|enviar msg)\b", re.I), "message_draft"),
    (re.compile(r"\b(armazenamento|arquivos grandes|limpar disco|espaço em disco)\b", re.I), "storage_scan"),
    (re.compile(r"\b(organizar arquivos|arrumar arquivos|triagem de arquivos)\b", re.I), "files_triage"),
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
    "/forge-batch",
    "/forge-plan",
    "/forge-run",
    "/forge-workshop",
    "/operator-brief",
    "/spec-to-tasks",
}


def has_secret_like_text(value):
    text = str(value or "")
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def clean_text(value, limit=MAX_PROMPT_CHARS):
    return str(value or "").replace("\x00", "").strip()[:limit]


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


def status_payload():
    ai_ready = bool(os.environ.get("OPENROUTER_API_KEY"))
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
        "capabilities": WEB_CAPABILITIES,
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


def local_handoff(command, intent):
    safe_command = "./jarvis do " + shlex.quote(command)
    return {
        "ok": True,
        "endpoint": "POST /command",
        "status_real": "web_to_local_handoff",
        "message": "Esse pedido precisa rodar no Mac. O handoff está pronto para o worker local.",
        "intent": intent,
        "requires_local_worker": True,
        "local_command": safe_command,
        "copy_command": safe_command,
        "why": "Uma função na Vercel não tem acesso à tela, voz, WhatsApp ou arquivos do seu computador.",
    }


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


def assistant_response(body, origin=""):
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
            return local_handoff(latest, intent), 200

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        payload, status = planning_payload("/assistant", {"goal": latest})
        payload.update({
            "message": "O cérebro web ainda não tem OPENROUTER_API_KEY configurada; gerei um plano local como fallback.",
            "ai_configured": False,
            "setup_variable": "OPENROUTER_API_KEY",
        })
        return payload, status

    system = {
        "role": "system",
        "content": (
            "Você é JARVIS, assistente pessoal de Theo. Responda em português claro, direto e útil. "
            "Ajude a pensar, planejar, escrever e decidir. Não alegue ter executado ações no computador "
            "ou em serviços externos. Nunca peça, repita ou exponha credenciais. Quando algo exigir o Mac, "
            "explique que o worker local deve executar."
        ),
    }
    request_body = json.dumps(
        {
            "model": os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
            "messages": [system, *messages],
            "temperature": 0.4,
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
        return {
            "ok": True,
            "endpoint": "POST /assistant",
            "status_real": "assistant_response_from_openrouter",
            "message": content,
            "content": content,
            "model": clean_text(result.get("model") or DEFAULT_MODEL, 200),
            "provider": "openrouter",
            "external_processing": True,
        }, 200
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


def command_payload(body, origin=""):
    command = clean_text(body.get("command") or body.get("prompt"))
    if not command:
        return {"ok": False, "error": "Comando vazio."}, 400
    if has_secret_like_text(command):
        return {
            "ok": False,
            "endpoint": "POST /command",
            "error": "O comando parece conter uma credencial. Remova o segredo e tente novamente.",
        }, 400

    for pattern, intent in LOCAL_INTENTS:
        if pattern.search(command):
            return local_handoff(command, intent), 200

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

    return assistant_response({"command": command}, origin=origin)


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

    def send_bytes(self, status, body, content_type, cache="public, max-age=3600"):
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

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self._security_headers()
        self.end_headers()

    def do_GET(self):
        path, query = request_route(self.path)
        if path == "/":
            return self.serve_ui()
        if path == "/favicon.ico":
            return self.send_bytes(200, b"", "image/x-icon", "public, max-age=86400")
        if path.startswith("/asset/"):
            return self.serve_asset(path[len("/asset/"):])
        if path in {"/health", "/status", "/runtime"}:
            payload = status_payload()
            payload["endpoint"] = f"GET {path}"
            return self.send_json(200, payload)
        if path == "/owner-dev":
            return self.send_json(200, owner_mode_payload())
        if path in {"/capabilities", "/capability-matrix"}:
            return self.send_json(200, {
                "ok": True,
                "endpoint": f"GET {path}",
                "status_real": "web_capabilities",
                "capabilities": WEB_CAPABILITIES,
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
        if path in {"/next", "/latest", "/feature-backlog", "/forge-dashboard", "/autopilot-dashboard"}:
            return self.send_json(200, {
                "ok": True,
                "endpoint": f"GET {path}",
                "status_real": "web_runtime_stateless",
                "message": "Digite um objetivo no cockpit; o JARVIS conversa, planeja ou encaminha ao worker local.",
                "next_action": "Use a barra central com um pedido em linguagem natural.",
                "persistent_history": False,
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
        if path == "/command":
            payload, status = command_payload(body, origin=origin)
            return self.send_json(status, payload)
        if path in {"/assistant", "/chat"}:
            payload, status = assistant_response(body, origin=origin)
            payload.setdefault("endpoint", f"POST {path}")
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
        if path in PLANNING_PATHS or path.startswith(("/forge-", "/feature-", "/context-", "/jarvis-brief")):
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
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print("JARVIS web gateway")
    print(f"Status real: local preview at http://{args.host}:{args.port}")
    print("Produção: nada alterado.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
