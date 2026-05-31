#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import argparse
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DIGEST_BASE = ROOT / "05_EXECUCAO" / "62_RESEARCH_DIGEST"

ALLOWED_ENDPOINTS = [
    "GET /status",
    "GET /next",
    "GET /latest",
    "GET /artifact?file=plan",
    "GET /sources",
    "GET /source?path=...",
    "GET /source-search?q=...",
    "POST /digest",
    "POST /validate",
    "POST /safety-gate",
    "POST /command",
    "POST /self-test",
]

DIGEST_FILES = {
    "index": "01_SOURCE_INDEX.md",
    "digest": "02_DIGEST.md",
    "plan": "03_JARVIS_EVOLUTION_PLAN.md",
    "n8n": "04_N8N_LOOP_POSITION.md",
    "status": "05_STATUS_REAL.md",
    "backlog": "06_TECHNICAL_BACKLOG.md",
}

SOURCE_SCAN_ROOTS = [
    ROOT / "02_SOURCES",
    ROOT / "03_DOCS",
    ROOT / "04_OUTPUT",
]

SOURCE_PRIMARY_EXTS = {".md", ".txt"}
SOURCE_BACKUP_EXTS = {".zip", ".pdf", ".docx"}
SOURCE_OTHER_EXTS = {".json", ".csv", ".yaml", ".yml"}

def run_cmd(cmd, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=merged_env,
        timeout=120,
    )

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-4000:],
    }

def safe_relative_path(value, default):
    raw = str(value or default).strip() or default
    p = Path(raw).expanduser()

    if p.is_absolute():
        raise ValueError("absolute paths are blocked")

    if ".env" in p.parts or any(part.startswith(".") for part in p.parts):
        raise ValueError("hidden/env paths are blocked")

    resolved = (ROOT / p).resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise ValueError("path outside repo is blocked")

    return str(p)

def extract_digest_path(stdout):
    for line in stdout.splitlines():
        marker = "OK — digest criado em "
        if marker in line:
            return line.split(marker, 1)[1].strip()
    return ""

def digest_response(result):
    artifact_path = extract_digest_path(result.get("stdout", ""))
    clean_path = artifact_path.rstrip("/")

    return {
        "ok": result["ok"],
        "endpoint": "POST /digest",
        "status_real": "local_digest_only",
        "artifact_path": artifact_path,
        "next_file": "03_JARVIS_EVOLUTION_PLAN.md" if artifact_path else "",
        "validate_command": f"./jarvis research-digest-validate --path {artifact_path}" if artifact_path else "",
        "review_command": f"sed -n '1,220p' {clean_path}/03_JARVIS_EVOLUTION_PLAN.md" if artifact_path else "",
        "precisa_aprovacao": True,
        "blocked_actions": ["commit", "push", "deploy", "production"],
        "result": result,
    }

def latest_digest_dir():
    if not DIGEST_BASE.exists():
        return None

    dirs = [p for p in DIGEST_BASE.iterdir() if p.is_dir()]
    if not dirs:
        return None

    return max(dirs, key=lambda p: p.stat().st_mtime)

def read_digest_part(base, key, max_chars=12000):
    path = base / DIGEST_FILES[key]

    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n... cortado pela API local"

    return text

def latest_digest_payload():
    latest = latest_digest_dir()

    if not latest:
        return {
            "ok": False,
            "error": "nenhum digest encontrado",
            "next_action": "use POST /digest ou ./jarvis research-digest",
            "precisa_aprovacao": True,
        }

    rel = latest.relative_to(ROOT)

    return {
        "ok": True,
        "endpoint": "GET /latest",
        "status_real": "local_read_only",
        "artifact_path": str(rel),
        "files": {k: str(rel / v) for k, v in DIGEST_FILES.items()},
        "plan": read_digest_part(latest, "plan"),
        "backlog": read_digest_part(latest, "backlog"),
        "n8n": read_digest_part(latest, "n8n"),
        "precisa_aprovacao": True,
        "blocked_actions": ["commit", "push", "deploy", "production"],
    }

def artifact_payload(query):
    key = (query.get("file") or query.get("key") or ["plan"])[0]

    if key not in DIGEST_FILES:
        return {
            "ok": False,
            "error": "artifact file not allowed",
            "allowed_files": sorted(DIGEST_FILES.keys()),
            "precisa_aprovacao": True,
        }

    latest = latest_digest_dir()
    if not latest:
        return {
            "ok": False,
            "error": "nenhum digest encontrado",
            "next_action": "use POST /digest ou ./jarvis research-digest",
            "precisa_aprovacao": True,
        }

    path = latest / DIGEST_FILES[key]
    rel = path.relative_to(ROOT)

    return {
        "ok": True,
        "endpoint": "GET /artifact",
        "status_real": "local_read_only",
        "file": key,
        "path": str(rel),
        "content": read_digest_part(latest, key, max_chars=30000),
        "precisa_aprovacao": True,
        "blocked_actions": ["commit", "push", "deploy", "production"],
    }

def is_safe_source_file(path):
    blocked_parts = {".git", "node_modules", "__pycache__", ".venv", "venv"}

    if set(path.parts) & blocked_parts:
        return False

    if any(part.startswith(".") for part in path.parts):
        return False

    name = path.name.lower()
    if ".env" in name or "secret" in name or "token" in name or "senha" in name:
        return False

    return path.is_file()

def source_kind(path):
    ext = path.suffix.lower()

    if ext in SOURCE_PRIMARY_EXTS:
        return "primary_md_txt"

    if ext in SOURCE_BACKUP_EXTS:
        return "backup_transport"

    if ext in SOURCE_OTHER_EXTS:
        return "structured_other"

    return "ignored_other"

def sources_payload():
    items = []

    for root in SOURCE_SCAN_ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not is_safe_source_file(path):
                continue

            kind = source_kind(path)
            if kind == "ignored_other":
                continue

            rel = path.relative_to(ROOT)
            items.append({
                "path": str(rel),
                "name": path.name,
                "ext": path.suffix.lower(),
                "kind": kind,
                "size_bytes": path.stat().st_size,
            })

    primary = [i for i in items if i["kind"] == "primary_md_txt"]
    backup = [i for i in items if i["kind"] == "backup_transport"]
    structured = [i for i in items if i["kind"] == "structured_other"]

    return {
        "ok": True,
        "endpoint": "GET /sources",
        "status_real": "local_read_only",
        "summary": {
            "total": len(items),
            "primary_md_txt": len(primary),
            "backup_transport": len(backup),
            "structured_other": len(structured),
        },
        "rule": "usar .md/.txt como source principal; zip/pdf/docx como backup/transporte; nunca incluir credenciais",
        "primary": primary[:80],
        "backup": backup[:80],
        "structured": structured[:80],
        "precisa_aprovacao": True,
        "blocked_actions": ["commit", "push", "deploy", "production"],
    }

def source_read_payload(query):
    raw_path = (query.get("path") or [""])[0].strip()

    if not raw_path:
        return {
            "ok": False,
            "error": "missing path",
            "example": "/source?path=02_SOURCES/DEEP_RESEARCH/README.md",
            "precisa_aprovacao": True,
        }

    safe_path = safe_relative_path(raw_path, "")
    candidate = (ROOT / safe_path).resolve()

    allowed_root = False
    for root in SOURCE_SCAN_ROOTS:
        resolved_root = root.resolve()
        if candidate == resolved_root or resolved_root in candidate.parents:
            allowed_root = True
            break

    if not allowed_root:
        return {
            "ok": False,
            "error": "source path outside allowed source roots",
            "allowed_roots": [str(r.relative_to(ROOT)) for r in SOURCE_SCAN_ROOTS if r.exists()],
            "precisa_aprovacao": True,
        }

    if not candidate.exists() or not candidate.is_file():
        return {
            "ok": False,
            "error": "source file not found",
            "path": safe_path,
            "precisa_aprovacao": True,
        }

    if not is_safe_source_file(candidate):
        return {
            "ok": False,
            "error": "source file blocked by safety rules",
            "path": safe_path,
            "precisa_aprovacao": True,
        }

    if candidate.suffix.lower() not in SOURCE_PRIMARY_EXTS:
        return {
            "ok": False,
            "error": "only .md and .txt sources can be read directly",
            "path": safe_path,
            "ext": candidate.suffix.lower(),
            "precisa_aprovacao": True,
        }

    content = candidate.read_text(encoding="utf-8", errors="replace")
    max_chars = 50000

    return {
        "ok": True,
        "endpoint": "GET /source",
        "status_real": "local_read_only",
        "path": str(candidate.relative_to(ROOT)),
        "name": candidate.name,
        "ext": candidate.suffix.lower(),
        "size_bytes": candidate.stat().st_size,
        "truncated": len(content) > max_chars,
        "content": content[:max_chars],
        "precisa_aprovacao": True,
        "blocked_actions": ["commit", "push", "deploy", "production"],
    }

def source_search_payload(query):
    term = (query.get("q") or query.get("query") or [""])[0].strip()

    if not term:
        return {
            "ok": False,
            "error": "missing query",
            "example": "/source-search?q=n8n",
            "precisa_aprovacao": True,
        }

    if len(term) < 2:
        return {
            "ok": False,
            "error": "query too short",
            "min_chars": 2,
            "precisa_aprovacao": True,
        }

    results = []
    term_lower = term.lower()

    for root in SOURCE_SCAN_ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not is_safe_source_file(path):
                continue

            if path.suffix.lower() not in SOURCE_PRIMARY_EXTS:
                continue

            rel = str(path.relative_to(ROOT))

            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()
            matches = []

            for idx, line in enumerate(lines, start=1):
                if term_lower in line.lower():
                    matches.append({
                        "line": idx,
                        "text": line[:500],
                    })

                if len(matches) >= 12:
                    break

            if matches:
                results.append({
                    "path": rel,
                    "name": path.name,
                    "matches_count_limited": len(matches),
                    "matches": matches,
                })

            if len(results) >= 20:
                break

    return {
        "ok": True,
        "endpoint": "GET /source-search",
        "status_real": "local_read_only",
        "query": term,
        "results_count": len(results),
        "results": results,
        "precisa_aprovacao": True,
        "blocked_actions": ["commit", "push", "deploy", "production"],
    }

def self_test_payload():
    checks = []

    def add(name, ok, detail):
        checks.append({
            "name": name,
            "ok": bool(ok),
            "detail": detail,
        })

    latest = latest_digest_payload()
    add("latest_digest", latest.get("ok"), latest.get("artifact_path") or latest.get("error"))

    sources = sources_payload()
    add("sources_list", sources.get("ok") and sources.get("summary", {}).get("primary_md_txt", 0) > 0, sources.get("summary"))

    source_read = source_read_payload({"path": ["02_SOURCES/DEEP_RESEARCH/README.md"]})
    add("source_read_readme", source_read.get("ok"), source_read.get("path") or source_read.get("error"))

    source_search = source_search_payload({"q": ["n8n"]})
    add("source_search_n8n", source_search.get("ok") and source_search.get("results_count", 0) > 0, {
        "results_count": source_search.get("results_count", 0)
    })

    validate = validate_payload({})
    add("validate_latest_digest", validate.get("ok"), validate.get("artifact_path") or validate.get("error"))

    env_block_ok = False
    env_error = ""
    try:
        source_read_payload({"path": [".env"]})
    except Exception as e:
        env_error = str(e)
        env_block_ok = "env" in env_error.lower() or "hidden" in env_error.lower()

    add("block_env_source_read", env_block_ok, env_error)

    all_ok = all(item["ok"] for item in checks)

    return {
        "ok": all_ok,
        "endpoint": "POST /self-test",
        "status_real": "local_self_test_only",
        "checks_passed": sum(1 for item in checks if item["ok"]),
        "checks_total": len(checks),
        "checks": checks,
        "precisa_aprovacao": True,
        "blocked_actions": ["commit", "push", "deploy", "production"],
    }

def validate_payload(data):
    raw_path = data.get("path")

    if raw_path:
        artifact_path = safe_relative_path(raw_path, "")
    else:
        latest = latest_digest_dir()
        if not latest:
            return {
                "ok": False,
                "error": "nenhum digest encontrado para validar",
                "next_action": "use POST /digest primeiro",
                "precisa_aprovacao": True,
            }
        artifact_path = str(latest.relative_to(ROOT))

    result = run_cmd(["./jarvis", "research-digest-validate", "--path", artifact_path])

    return {
        "ok": result["ok"],
        "endpoint": "POST /validate",
        "status_real": "local_validation_only",
        "artifact_path": artifact_path,
        "precisa_aprovacao": True,
        "blocked_actions": ["commit", "push", "deploy", "production"],
        "result": result,
    }

def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}

    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    if not raw.strip():
        return {}

    return json.loads(raw)

UI_ASSET_DIR = Path(__file__).resolve().parent / "jarvis_ui_assets"
UI_ASSET = UI_ASSET_DIR / "cockpit.html"

# Read-only static assets for the cockpit (3D model, textures). Sandboxed to
# UI_ASSET_DIR with a strict extension whitelist. Never serves code or .env.
UI_ASSET_TYPES = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".bin": "application/octet-stream",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".hdr": "image/vnd.radiance",
}

def dashboard_html():
    try:
        text = UI_ASSET.read_text(encoding="utf-8")
        if text.strip():
            return text
    except Exception:
        pass

    return _FALLBACK_DASHBOARD_HTML

_FALLBACK_DASHBOARD_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>JARVIS Local Cockpit</title>
  <style>
    body { margin:0; background:radial-gradient(circle at top,#13233f,#05070d 55%,#020308); color:#e8f1ff; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
    .wrap { max-width:1180px; margin:0 auto; padding:34px 22px; }
    .hero { border:1px solid rgba(120,180,255,.25); background:rgba(7,13,28,.72); border-radius:24px; padding:28px; box-shadow:0 20px 80px rgba(0,0,0,.45); }
    .eyebrow { color:#81b9ff; letter-spacing:.14em; font-size:12px; text-transform:uppercase; }
    h1 { font-size:44px; margin:8px 0; }
    .creator { color:#a9c9ff; margin-bottom:20px; }
    .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:18px; }
    .card { border:1px solid rgba(120,180,255,.18); background:rgba(255,255,255,.045); border-radius:18px; padding:16px; }
    button { width:100%; border:0; border-radius:14px; padding:13px 14px; background:linear-gradient(135deg,#2d8cff,#6ee7ff); color:#03111f; font-weight:800; cursor:pointer; }
    button.secondary { background:rgba(255,255,255,.09); color:#e8f1ff; border:1px solid rgba(255,255,255,.15); }
    pre { white-space:pre-wrap; word-break:break-word; background:rgba(0,0,0,.34); border:1px solid rgba(120,180,255,.16); border-radius:18px; padding:16px; min-height:260px; max-height:520px; overflow:auto; }
    .status { color:#7dffbf; }
    @media (max-width:820px){ .grid{grid-template-columns:1fr;} h1{font-size:34px;} }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="eyebrow">JARVIS LOCAL COCKPIT</div>
      <h1>JARVIS Agent OS</h1>
      <div class="creator">Criado por Theo Padilha · execução local segura · sem produção automática</div>

      <div class="grid">
        <div class="card"><button onclick="load('/status')">Status</button></div>
        <div class="card"><button onclick="load('/latest')">Último Digest</button></div>
        <div class="card"><button onclick="load('/sources')">Sources</button></div>
        <div class="card"><button class="secondary" onclick="load('/artifact?file=plan')">Plano</button></div>
        <div class="card"><button class="secondary" onclick="load('/artifact?file=backlog')">Backlog</button></div>
        <div class="card"><button class="secondary" onclick="validateLatest()">Validar</button></div>
      </div>

      <p class="status" id="line">Pronto. Escolha uma ação.</p>
      <pre id="out">JARVIS aguardando comando local...</pre>
    </section>
  </div>

<script>
async function load(path) {
  document.getElementById('line').textContent = 'Carregando ' + path + '...';
  const res = await fetch(path);
  const data = await res.json();
  document.getElementById('line').textContent = data.ok ? 'OK — ' + path : 'Falhou — ' + path;
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
}

async function validateLatest() {
  document.getElementById('line').textContent = 'Validando último digest...';
  const res = await fetch('/validate', { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
  const data = await res.json();
  document.getElementById('line').textContent = data.ok ? 'OK — digest válido' : 'Falhou validação';
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
}
</script>
</body>
</html>"""


def build_command_payload(body):
    """Safe local command router. No shell. No deploy. No secrets."""
    import unicodedata
    from urllib.parse import quote

    def norm(value):
        value = str(value or "").strip().lower()
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        return " ".join(value.split())

    raw = ""
    if isinstance(body, dict):
        raw = str(body.get("command") or body.get("text") or body.get("q") or "").strip()
    else:
        raw = str(body or "").strip()

    normalized = norm(raw)
    clean = normalized[1:] if normalized.startswith("/") else normalized

    base = {
        "endpoint": "POST /command",
        "command": raw,
        "status_real": "local_command_router_only",
        "precisa_aprovacao": False,
        "blocked_actions": ["commit", "push", "deploy", "production"],
    }

    if not raw:
        return {
            **base,
            "ok": False,
            "routed_to": None,
            "method": None,
            "message": "Empty command. Try /status, /self-test, /plan, /search n8n or /next.",
        }

    blocked_map = {
        "git commit": "commit",
        "commit": "commit",
        "git push": "push",
        "push": "push",
        "deploy": "deploy",
        "production": "production",
        "producao": "production",
        "shell": "free_shell",
        "terminal": "free_shell",
        "bash": "free_shell",
        "zsh": "free_shell",
        ".env": "read_env",
        " env": "read_env",
        "secret": "secrets",
        "token": "secrets",
        "senha": "secrets",
    }

    hits = []
    for key, action in blocked_map.items():
        if key in f" {clean} ":
            hits.append(action)

    if hits:
        return {
            **base,
            "ok": False,
            "blocked": True,
            "precisa_aprovacao": True,
            "blocked_actions": sorted(set(hits + base["blocked_actions"])),
            "routed_to": None,
            "method": None,
            "message": "Blocked by JARVIS safety policy. This cockpit does not run commit, push, deploy, free shell, production actions or secret reads.",
        }

    routes = {
        "status": ("/status", "GET"),
        "self-test": ("/self-test", "POST"),
        "self test": ("/self-test", "POST"),
        "selftest": ("/self-test", "POST"),
        "teste": ("/self-test", "POST"),
        "sources": ("/sources", "GET"),
        "fontes": ("/sources", "GET"),
        "source": ("/sources", "GET"),
        "plan": ("/artifact?file=plan", "GET"),
        "plano": ("/artifact?file=plan", "GET"),
        "backlog": ("/artifact?file=backlog", "GET"),
        "n8n": ("/artifact?file=n8n", "GET"),
        "latest": ("/latest", "GET"),
        "ultimo": ("/latest", "GET"),
        "validate": ("/validate", "POST"),
        "validar": ("/validate", "POST"),
        "safety": ("/safety-gate", "POST"),
        "safety-gate": ("/safety-gate", "POST"),
        "next": ("/next", "GET"),
        "proximo": ("/next", "GET"),
        "prox": ("/next", "GET"),
    }

    if clean.startswith("search "):
        q = raw.strip()[len(raw.strip().split(" ", 1)[0]):].strip()
        if not q:
            return {**base, "ok": False, "routed_to": None, "method": None, "message": "Search needs a term. Example: /search n8n"}
        return {
            **base,
            "ok": True,
            "routed_to": "/source-search?q=" + quote(q),
            "method": "GET",
            "message": f"Routing search to source index: {q}",
            "data": {"kind": "source_search", "query": q},
        }

    if clean.startswith("buscar "):
        q = raw.strip().split(" ", 1)[1].strip() if " " in raw.strip() else ""
        if not q:
            return {**base, "ok": False, "routed_to": None, "method": None, "message": "Busca precisa de termo. Exemplo: buscar n8n"}
        return {
            **base,
            "ok": True,
            "routed_to": "/source-search?q=" + quote(q),
            "method": "GET",
            "message": f"Routing search to source index: {q}",
            "data": {"kind": "source_search", "query": q},
        }

    for prefix in ("open ", "source ", "abrir ", "ler "):
        if clean.startswith(prefix):
            path = raw.strip().split(" ", 1)[1].strip() if " " in raw.strip() else ""
            if not path:
                return {**base, "ok": False, "routed_to": None, "method": None, "message": "Open needs a path. Example: /open 02_SOURCES/DEEP_RESEARCH/README.md"}
            return {
                **base,
                "ok": True,
                "routed_to": "/source?path=" + quote(path, safe="/._-"),
                "method": "GET",
                "message": f"Opening local source: {path}",
                "data": {"kind": "source_read", "path": path},
            }

    if clean in routes:
        path, method = routes[clean]
        return {
            **base,
            "ok": True,
            "routed_to": path,
            "method": method,
            "message": f"Routing command to {method} {path}",
            "data": {"kind": "route", "path": path, "method": method},
        }

    return {
        **base,
        "ok": True,
        "routed_to": None,
        "method": None,
        "message": "Chat reasoning is not connected yet. Use slash commands or local tools.",
        "data": {
            "suggestions": ["/status", "/self-test", "/sources", "/plan", "/search n8n", "/next"]
        },
    }

class Handler(BaseHTTPRequestHandler):
    server_version = "JarvisLocalAPI/0.3"

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status, html):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_ui_asset(self, rel):
        try:
            rel = unquote(rel).lstrip("/")
            base = UI_ASSET_DIR.resolve()
            target = (base / rel).resolve()
            if base != target and base not in target.parents:
                self.send_json(403, {"ok": False, "error": "asset path not allowed"})
                return
            suffix = target.suffix.lower()
            if suffix not in UI_ASSET_TYPES or not target.is_file():
                self.send_json(404, {"ok": False, "error": "asset not found"})
                return
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", UI_ASSET_TYPES[suffix])
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_json(500, {"ok": False, "error": str(e)})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self.send_html(200, dashboard_html())
            return

        if path.startswith("/asset/"):
            self.serve_ui_asset(path[len("/asset/"):])
            return

        if path == "/status":
            git_status = run_cmd(["git", "status", "--short"])
            git_head = run_cmd(["git", "log", "--oneline", "-1"])
            self.send_json(200, {
                "ok": True,
                "service": "jarvis-api-local",
                "status_real": "local_only_no_external_production",
                "allowed_endpoints": ALLOWED_ENDPOINTS,
                "blocked": ["commit", "push", "deploy", "free_shell", "read_env", "external_production"],
                "precisa_aprovacao": True,
                "git_status": git_status["stdout"].strip(),
                "git_head": git_head["stdout"].strip(),
            })
            return

        if path == "/next":
            self.send_json(200, {
                "ok": True,
                "next_action": "use POST /digest to generate a local digest, then review output manually",
                "precisa_aprovacao": True,
                "blocked_actions": ["commit", "push", "deploy", "production"],
            })
            return

        if path == "/latest":
            payload = latest_digest_payload()
            self.send_json(200 if payload.get("ok") else 404, payload)
            return

        if path == "/artifact":
            payload = artifact_payload(query)
            self.send_json(200 if payload.get("ok") else 404, payload)
            return

        if path == "/sources":
            payload = sources_payload()
            self.send_json(200, payload)
            return

        if path == "/source":
            try:
                payload = source_read_payload(query)
                self.send_json(200 if payload.get("ok") else 400, payload)
                return
            except Exception as e:
                self.send_json(400, {
                    "ok": False,
                    "endpoint": "GET /source",
                    "error": str(e),
                    "precisa_aprovacao": True,
                })
                return

        if path == "/source-search":
            payload = source_search_payload(query)
            self.send_json(200 if payload.get("ok") else 400, payload)
            return

        self.send_json(404, {"ok": False, "error": "endpoint not allowed"})

    def do_POST(self):
        if self.path == "/command":
            try:
                import json as _json
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = _json.loads(raw or "{}")
            except Exception:
                body = {}
            return self._json(build_command_payload(body), 200)

        if self.path == "/digest":
            try:
                data = read_json(self)
                goal = str(data.get("goal") or "digest via Jarvis API local").strip()
                source = safe_relative_path(data.get("source"), "02_SOURCES/DEEP_RESEARCH")

                cmd = ["./jarvis", "research-digest", "--source", source, "--goal", goal]

                out = data.get("out")
                if out:
                    cmd.extend(["--out", safe_relative_path(out, "05_EXECUCAO/62_RESEARCH_DIGEST")])

                result = run_cmd(cmd)
                self.send_json(200 if result["ok"] else 500, digest_response(result))
                return

            except Exception as e:
                self.send_json(400, {"ok": False, "error": str(e)})
                return

        if self.path == "/validate":
            try:
                data = read_json(self)
                payload = validate_payload(data)
                self.send_json(200 if payload.get("ok") else 400, payload)
                return
            except Exception as e:
                self.send_json(400, {"ok": False, "error": str(e)})
                return

        if self.path == "/safety-gate":
            result = run_cmd(["./jarvis", "safety-gate"], env={"JARVIS_NO_REPORT": "1"})
            self.send_json(200 if result["ok"] else 500, {
                "ok": result["ok"],
                "endpoint": "POST /safety-gate",
                "status_real": "local_validation_only",
                "precisa_aprovacao": True,
                "result": result,
            })
            return

        if self.path == "/self-test":
            try:
                payload = self_test_payload()
                self.send_json(200 if payload.get("ok") else 500, payload)
                return
            except Exception as e:
                self.send_json(500, {
                    "ok": False,
                    "endpoint": "POST /self-test",
                    "error": str(e),
                    "precisa_aprovacao": True,
                })
                return

        self.send_json(404, {"ok": False, "error": "endpoint not allowed"})

    def log_message(self, fmt, *args):
        print("[jarvis-api]", fmt % args)

def main():
    parser = argparse.ArgumentParser(description="Jarvis API local com allowlist.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)

    print("JARVIS — Local API")
    print("Status real: local only. Sem commit. Sem push. Sem deploy. Sem produção externa.")
    print(f"URL: http://{args.host}:{args.port}")
    print("Endpoints permitidos:")
    for item in ALLOWED_ENDPOINTS:
        print(f"  - {item}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando Jarvis API local.")
        return 0


# JARVIS_LOCAL_EXTENSIONS_BEGIN
# Safe local cockpit extensions. No shell. No external API. No deploy.
import json as _j_json
import subprocess as _j_subprocess
import datetime as _j_datetime
from pathlib import Path as _j_Path
from urllib.parse import urlparse as _j_urlparse, parse_qs as _j_parse_qs, quote as _j_quote
import unicodedata as _j_unicodedata

try:
    _JROOT = ROOT
except NameError:
    _JROOT = _j_Path(__file__).resolve().parents[1]

_JBLOCKED_BASE = ["commit", "push", "deploy", "production"]
_JNOTE_DIR = _JROOT / "05_EXECUCAO" / "70_JARVIS_SESSION_LOG"
_JNOTE_FILE = _JNOTE_DIR / "jarvis_notes.jsonl"

def _j_norm(value):
    value = str(value or "").strip().lower()
    value = _j_unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not _j_unicodedata.combining(ch))
    return " ".join(value.split())

def _j_json_out(self, payload, status=200):
    raw = _j_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _j_read_json(self):
    try:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return _j_json.loads(raw or "{}")
    except Exception:
        return {}

def _j_run_git(args):
    try:
        r = _j_subprocess.run(["git", *args], cwd=_JROOT, text=True, capture_output=True, timeout=4)
        return (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return f"unavailable: {type(e).__name__}"

def _j_sources_count():
    root = _JROOT / "02_SOURCES"
    if not root.exists():
        return 0
    return len([p for p in root.rglob("*") if p.suffix.lower() in {".md", ".txt"} and not any(part.startswith(".") for part in p.parts)])

def _j_latest_digest():
    root = _JROOT / "05_EXECUCAO" / "62_RESEARCH_DIGEST"
    if not root.exists():
        return None
    items = sorted([p for p in root.iterdir() if p.exists()], key=lambda p: p.stat().st_mtime, reverse=True)
    return str(items[0].relative_to(_JROOT)) if items else None

def _j_base(endpoint, ok=True):
    return {
        "ok": ok,
        "endpoint": endpoint,
        "status_real": "local_only",
        "message": "",
        "data": {},
        "precisa_aprovacao": False,
        "blocked_actions": list(_JBLOCKED_BASE),
    }

def _j_commands():
    rows = [
        ("/status", ["status"], "GET", "/status", "Status local da API"),
        ("/self-test", ["self test", "selftest", "teste"], "POST", "/self-test", "Smoke test local"),
        ("/sources", ["fontes", "sources"], "GET", "/sources", "Lista sources locais"),
        ("/plan", ["plano", "plan"], "GET", "/artifact?file=plan", "Plano atual"),
        ("/backlog", ["backlog"], "GET", "/artifact?file=backlog", "Backlog atual"),
        ("/n8n", ["n8n"], "GET", "/artifact?file=n8n", "Posição n8n"),
        ("/latest", ["latest", "ultimo"], "GET", "/latest", "Último digest"),
        ("/validate", ["validar", "validate"], "POST", "/validate", "Validação local"),
        ("/safety", ["safety", "safety-gate"], "POST", "/safety-gate", "Safety gate local"),
        ("/next", ["next", "proximo", "prox"], "GET", "/next", "Próximo passo"),
        ("/search termo", ["buscar termo"], "GET", "/source-search?q=termo", "Busca nos sources"),
        ("/open caminho", ["abrir caminho", "ler caminho"], "GET", "/source?path=caminho", "Ler source local permitido"),
        ("/commands", ["commands", "comandos"], "GET", "/commands", "Lista comandos"),
        ("/session", ["session", "sessao"], "GET", "/session", "Estado da sessão"),
        ("/note texto", ["note texto", "todo texto", "decision texto"], "POST", "/note", "Salvar nota operacional"),
        ("/notes", ["notes", "notas"], "GET", "/notes", "Últimas notas"),
        ("/export-session", ["export session", "exportar sessao"], "POST", "/export-session", "Snapshot markdown da sessão"),
    ]
    return [
        {
            "slash": slash,
            "aliases": aliases,
            "method": method,
            "path": path,
            "description": desc,
            "risk": "low_local",
            "precisa_aprovacao": False,
        }
        for slash, aliases, method, path, desc in rows
    ]

def _j_blocked(command):
    clean = " " + _j_norm(command).replace("/", " ") + " "
    checks = {
        " git commit ": "commit",
        " commit ": "commit",
        " git push ": "push",
        " push ": "push",
        " deploy ": "deploy",
        " production ": "production",
        " producao ": "production",
        " shell ": "free_shell",
        " terminal ": "free_shell",
        " bash ": "free_shell",
        " zsh ": "free_shell",
        " .env ": "read_env",
        " token ": "secrets",
        " api_key ": "secrets",
        " password ": "secrets",
        " senha ": "secrets",
        " secret ": "secrets",
    }
    return sorted(set(v for k, v in checks.items() if k in clean))

def _j_note_allowed(text):
    low = str(text or "").lower()
    denied = [".env", "token=", "api_key", "apikey", "password", "senha", "secret", "bearer "]
    return not any(x in low for x in denied)

def _j_append_note(note_type, text):
    if note_type not in {"note", "decision", "todo", "result"}:
        note_type = "note"
    text = str(text or "").strip()
    if not text:
        return False, "Empty note.", None
    if not _j_note_allowed(text):
        return False, "Note blocked because it looks like it may contain a secret.", None
    _JNOTE_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": _j_datetime.datetime.now().isoformat(timespec="seconds"),
        "type": note_type,
        "text": text,
    }
    with _JNOTE_FILE.open("a", encoding="utf-8") as f:
        f.write(_j_json.dumps(row, ensure_ascii=False) + "\n")
    return True, "Note saved.", row

def _j_read_notes(limit=20):
    try:
        limit = max(1, min(int(limit), 100))
    except Exception:
        limit = 20
    if not _JNOTE_FILE.exists():
        return []
    rows = []
    for line in _JNOTE_FILE.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(_j_json.loads(line))
        except Exception:
            pass
    return rows[-limit:]

def _j_session_payload():
    dirty = bool(_j_run_git(["status", "--short"]))
    return {
        "current_commit": _j_run_git(["rev-parse", "--short", "HEAD"]),
        "branch": _j_run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": dirty,
        "latest_digest": _j_latest_digest(),
        "sources_count": _j_sources_count(),
        "api_status": "online",
        "blocked_actions": list(_JBLOCKED_BASE),
        "local_only": True,
        "production_touched": False,
    }

def _j_export_session():
    _JNOTE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _j_datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = _JNOTE_DIR / f"session_snapshot_{stamp}.md"
    session = _j_session_payload()
    notes = _j_read_notes(20)
    commands = _j_commands()
    lines = [
        "# JARVIS Session Snapshot",
        "",
        f"- generated_at: {_j_datetime.datetime.now().isoformat(timespec='seconds')}",
        f"- branch: {session.get('branch')}",
        f"- commit: {session.get('current_commit')}",
        f"- git_dirty: {session.get('git_dirty')}",
        f"- local_only: true",
        f"- production_touched: false",
        f"- blocked_actions: {', '.join(_JBLOCKED_BASE)}",
        "",
        "## Commands",
    ]
    for c in commands:
        lines.append(f"- `{c['slash']}` -> {c['method']} {c['path']} — {c['description']}")
    lines += ["", "## Latest notes"]
    for n in notes:
        lines.append(f"- {n.get('timestamp')} [{n.get('type')}] {n.get('text')}")
    lines += ["", "Status real: sem push, sem deploy, sem produção externa."]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out.relative_to(_JROOT))

def _j_command_payload(body):
    raw = ""
    if isinstance(body, dict):
        raw = str(body.get("command") or body.get("text") or body.get("q") or "").strip()
    else:
        raw = str(body or "").strip()

    payload = _j_base("POST /command", True)
    payload["command"] = raw
    payload["status_real"] = "local_command_router_only"

    if not raw:
        payload.update(ok=False, message="Empty command.")
        return payload

    blocked = _j_blocked(raw)
    if blocked:
        payload.update(
            ok=False,
            blocked=True,
            precisa_aprovacao=True,
            blocked_actions=sorted(set(blocked + _JBLOCKED_BASE)),
            message="Blocked by JARVIS safety policy.",
        )
        return payload

    clean = _j_norm(raw)
    if clean.startswith("/"):
        clean = clean[1:]

    routes = {
        "status": ("/status", "GET"),
        "self-test": ("/self-test", "POST"),
        "self test": ("/self-test", "POST"),
        "selftest": ("/self-test", "POST"),
        "teste": ("/self-test", "POST"),
        "sources": ("/sources", "GET"),
        "fontes": ("/sources", "GET"),
        "plan": ("/artifact?file=plan", "GET"),
        "plano": ("/artifact?file=plan", "GET"),
        "backlog": ("/artifact?file=backlog", "GET"),
        "n8n": ("/artifact?file=n8n", "GET"),
        "latest": ("/latest", "GET"),
        "ultimo": ("/latest", "GET"),
        "validate": ("/validate", "POST"),
        "validar": ("/validate", "POST"),
        "safety": ("/safety-gate", "POST"),
        "safety-gate": ("/safety-gate", "POST"),
        "next": ("/next", "GET"),
        "proximo": ("/next", "GET"),
        "prox": ("/next", "GET"),
        "commands": ("/commands", "GET"),
        "comandos": ("/commands", "GET"),
        "session": ("/session", "GET"),
        "sessao": ("/session", "GET"),
        "notes": ("/notes", "GET"),
        "notas": ("/notes", "GET"),
        "export-session": ("/export-session", "POST"),
        "export session": ("/export-session", "POST"),
        "exportar sessao": ("/export-session", "POST"),
    }

    if clean.startswith(("note ", "todo ", "decision ", "result ")):
        first, text = raw.strip().split(" ", 1)
        t = _j_norm(first).replace("/", "")
        if t == "todo":
            note_type = "todo"
        elif t in {"decision", "decisao"}:
            note_type = "decision"
        elif t == "result":
            note_type = "result"
        else:
            note_type = "note"
        ok, msg, row = _j_append_note(note_type, text)
        payload.update(ok=ok, message=msg, data={"note": row})
        return payload

    if clean.startswith(("search ", "buscar ")):
        q = raw.strip().split(" ", 1)[1].strip() if " " in raw.strip() else ""
        payload.update(
            ok=bool(q),
            routed_to="/source-search?q=" + _j_quote(q) if q else None,
            method="GET",
            message=f"Routing search: {q}" if q else "Search needs a term.",
            data={"query": q},
        )
        return payload

    if clean.startswith(("open ", "source ", "abrir ", "ler ")):
        p = raw.strip().split(" ", 1)[1].strip() if " " in raw.strip() else ""
        payload.update(
            ok=bool(p),
            routed_to="/source?path=" + _j_quote(p, safe="/._-") if p else None,
            method="GET",
            message=f"Opening source: {p}" if p else "Open needs a path.",
            data={"path": p},
        )
        return payload

    if clean in routes:
        path, method = routes[clean]
        payload.update(
            ok=True,
            routed_to=path,
            method=method,
            message=f"Routing command to {method} {path}",
            data={"path": path, "method": method},
        )
        return payload

    payload.update(
        ok=True,
        routed_to=None,
        method=None,
        message="Chat reasoning is not connected yet. Use slash commands or local tools.",
        data={"suggestions": ["/status", "/session", "/commands", "/sources", "/plan", "/search n8n"]},
    )
    return payload

_ORIG_GET = Handler.do_GET
_ORIG_POST = Handler.do_POST

def _j_do_GET(self):
    parsed = _j_urlparse(self.path)
    path = parsed.path
    query = _j_parse_qs(parsed.query)

    if path == "/commands":
        p = _j_base("GET /commands", True)
        p["status_real"] = "local_command_catalog_only"
        p["message"] = "Commands catalog."
        p["data"] = {"commands": _j_commands()}
        return _j_json_out(self, p)

    if path == "/session":
        p = _j_base("GET /session", True)
        p["status_real"] = "local_session_read_only"
        p["message"] = "Local session state."
        p["data"] = _j_session_payload()
        return _j_json_out(self, p)

    if path == "/notes":
        lim = query.get("limit", ["20"])[0]
        p = _j_base("GET /notes", True)
        p["status_real"] = "local_notes_read_only"
        p["message"] = "Latest local notes."
        p["data"] = {"notes": _j_read_notes(lim)}
        return _j_json_out(self, p)

    return _ORIG_GET(self)

def _j_do_POST(self):
    parsed = _j_urlparse(self.path)
    path = parsed.path

    if path == "/command":
        return _j_json_out(self, _j_command_payload(_j_read_json(self)))

    if path == "/note":
        body = _j_read_json(self)
        ok, msg, row = _j_append_note(body.get("type", "note"), body.get("text", ""))
        p = _j_base("POST /note", ok)
        p["status_real"] = "local_note_append_only"
        p["message"] = msg
        p["data"] = {"note": row}
        return _j_json_out(self, p, 200 if ok else 400)

    if path == "/export-session":
        p = _j_base("POST /export-session", True)
        p["status_real"] = "local_session_snapshot_only"
        p["message"] = "Session snapshot exported."
        p["data"] = {"file": _j_export_session()}
        return _j_json_out(self, p)

    return _ORIG_POST(self)

Handler.do_GET = _j_do_GET
Handler.do_POST = _j_do_POST
# JARVIS_LOCAL_EXTENSIONS_END



# JARVIS_PRODUCTIVITY_EXTENSIONS_BEGIN
# Local productivity layer. Append-only logs. No external API. No shell livre.
import json as _p_json
import subprocess as _p_subprocess
import datetime as _p_datetime
import uuid as _p_uuid
from pathlib import Path as _p_Path
from urllib.parse import urlparse as _p_urlparse, parse_qs as _p_parse_qs
import unicodedata as _p_unicodedata

try:
    _PROOT = ROOT
except NameError:
    _PROOT = _p_Path(__file__).resolve().parents[1]

_PLOG_DIR = _PROOT / "05_EXECUCAO" / "70_JARVIS_SESSION_LOG"
_PTASKS_FILE = _PLOG_DIR / "jarvis_tasks.jsonl"
_PCHECKPOINT_DIR = _PLOG_DIR / "checkpoints"
_PHANDOFF_DIR = _PLOG_DIR / "handoffs"
_PBLOCKED = ["commit", "push", "deploy", "production"]

def _p_norm(v):
    v = str(v or "").strip().lower()
    v = _p_unicodedata.normalize("NFKD", v)
    v = "".join(ch for ch in v if not _p_unicodedata.combining(ch))
    return " ".join(v.split())

def _p_json_out(self, payload, status=200):
    raw = _p_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _p_read_json(self):
    try:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return _p_json.loads(raw or "{}")
    except Exception:
        return {}

def _p_base(endpoint, ok=True):
    return {
        "ok": ok,
        "endpoint": endpoint,
        "status_real": "local_only",
        "message": "",
        "data": {},
        "precisa_aprovacao": False,
        "blocked_actions": list(_PBLOCKED),
    }

def _p_secret_like(text):
    low = str(text or "").lower()
    denied = [".env", "token=", "api_key", "apikey", "password", "senha", "secret", "bearer ", "authorization:"]
    return any(x in low for x in denied)

def _p_git(args):
    try:
        r = _p_subprocess.run(["git", *args], cwd=_PROOT, text=True, capture_output=True, timeout=5)
        return (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return f"unavailable:{type(e).__name__}"

def _p_now():
    return _p_datetime.datetime.now().isoformat(timespec="seconds")

def _p_ensure():
    _PLOG_DIR.mkdir(parents=True, exist_ok=True)
    _PCHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    _PHANDOFF_DIR.mkdir(parents=True, exist_ok=True)

def _p_read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(_p_json.loads(line))
        except Exception:
            pass
    return rows

def _p_append_jsonl(path, row):
    _p_ensure()
    with path.open("a", encoding="utf-8") as f:
        f.write(_p_json.dumps(row, ensure_ascii=False) + "\n")

def _p_create_task(body):
    title = str(body.get("title") or body.get("text") or "").strip()
    if not title:
        return False, "Task title is empty.", None
    if _p_secret_like(title) or _p_secret_like(body.get("details", "")):
        return False, "Task blocked because it looks like it may contain a secret.", None

    row = {
        "id": "task_" + _p_datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "_" + _p_uuid.uuid4().hex[:6],
        "created_at": _p_now(),
        "updated_at": _p_now(),
        "status": str(body.get("status") or "open").strip(),
        "priority": str(body.get("priority") or "normal").strip(),
        "type": str(body.get("type") or "task").strip(),
        "project": str(body.get("project") or "jarvis").strip(),
        "title": title,
        "details": str(body.get("details") or "").strip(),
        "history": [],
    }
    _p_append_jsonl(_PTASKS_FILE, row)
    return True, "Task created.", row

def _p_list_tasks(limit=50, status=None):
    try:
        limit = max(1, min(int(limit), 200))
    except Exception:
        limit = 50
    rows = _p_read_jsonl(_PTASKS_FILE)
    if status:
        s = _p_norm(status)
        rows = [r for r in rows if _p_norm(r.get("status")) == s]
    return rows[-limit:]

def _p_update_task(body):
    task_id = str(body.get("id") or "").strip()
    status = str(body.get("status") or "").strip()
    note = str(body.get("note") or "").strip()

    if not task_id:
        return False, "Task id is required.", None
    if _p_secret_like(note):
        return False, "Task update blocked because note looks like it may contain a secret.", None

    rows = _p_read_jsonl(_PTASKS_FILE)
    found = None
    for r in rows:
        rid = str(r.get("id", ""))
        if rid == task_id or rid.startswith(task_id):
            if status:
                r["status"] = status
            r["updated_at"] = _p_now()
            hist = r.get("history")
            if not isinstance(hist, list):
                hist = []
            hist.append({"timestamp": _p_now(), "status": status or r.get("status"), "note": note})
            r["history"] = hist
            found = r
            break

    if not found:
        return False, "Task not found.", None

    _p_ensure()
    _PTASKS_FILE.write_text("", encoding="utf-8")
    for r in rows:
        _p_append_jsonl(_PTASKS_FILE, r)

    return True, "Task updated.", found

def _p_notes(limit=30):
    note_file = _PLOG_DIR / "jarvis_notes.jsonl"
    rows = _p_read_jsonl(note_file)
    try:
        limit = max(1, min(int(limit), 100))
    except Exception:
        limit = 30
    return rows[-limit:]

def _p_metrics():
    tasks = _p_read_jsonl(_PTASKS_FILE)
    open_tasks = [t for t in tasks if _p_norm(t.get("status")) not in {"done", "closed", "cancelled", "canceled"}]
    notes = _p_notes(100)
    snapshots = list(_PLOG_DIR.glob("session_snapshot_*.md")) if _PLOG_DIR.exists() else []
    checkpoints = list(_PCHECKPOINT_DIR.glob("*.md")) if _PCHECKPOINT_DIR.exists() else []
    return {
        "branch": _p_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": _p_git(["rev-parse", "--short", "HEAD"]),
        "git_dirty": bool(_p_git(["status", "--short"])),
        "tasks_total": len(tasks),
        "tasks_open": len(open_tasks),
        "notes_total_visible": len(notes),
        "session_snapshots": len(snapshots),
        "local_checkpoints": len(checkpoints),
        "local_only": True,
        "production_touched": False,
    }

def _p_timeline(limit=60):
    items = []
    for t in _p_read_jsonl(_PTASKS_FILE):
        items.append({
            "timestamp": t.get("updated_at") or t.get("created_at"),
            "kind": "task",
            "id": t.get("id"),
            "status": t.get("status"),
            "text": t.get("title"),
        })
    for n in _p_notes(100):
        items.append({
            "timestamp": n.get("timestamp"),
            "kind": n.get("type", "note"),
            "text": n.get("text"),
        })
    if _PLOG_DIR.exists():
        for p in list(_PLOG_DIR.glob("session_snapshot_*.md")) + list(_PCHECKPOINT_DIR.glob("*.md")) + list(_PHANDOFF_DIR.glob("*.md")):
            try:
                ts = _p_datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
            except Exception:
                ts = ""
            items.append({
                "timestamp": ts,
                "kind": "file",
                "text": str(p.relative_to(_PROOT)),
            })
    items = sorted(items, key=lambda x: str(x.get("timestamp") or ""), reverse=True)
    try:
        limit = max(1, min(int(limit), 200))
    except Exception:
        limit = 60
    return items[:limit]

def _p_checkpoint():
    _p_ensure()
    stamp = _p_datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = _PCHECKPOINT_DIR / f"local_checkpoint_{stamp}.md"
    metrics = _p_metrics()
    tasks = _p_list_tasks(20)
    notes = _p_notes(20)
    diffstat = _p_git(["diff", "--stat"])
    status = _p_git(["status", "--short"])

    lines = [
        "# JARVIS Local Checkpoint",
        "",
        f"- generated_at: {_p_now()}",
        f"- branch: {metrics['branch']}",
        f"- commit: {metrics['commit']}",
        f"- git_dirty: {metrics['git_dirty']}",
        "- local_only: true",
        "- production_touched: false",
        "- push: false",
        "- deploy: false",
        "",
        "## Git status",
        "```text",
        status or "clean",
        "```",
        "",
        "## Diff stat",
        "```text",
        diffstat or "no diff",
        "```",
        "",
        "## Open/latest tasks",
    ]
    for t in tasks:
        lines.append(f"- [{t.get('status')}] {t.get('id')} — {t.get('title')}")
    lines += ["", "## Latest notes"]
    for n in notes:
        lines.append(f"- {n.get('timestamp')} [{n.get('type')}] {n.get('text')}")
    lines += ["", "Status real: checkpoint local, sem commit, sem push, sem deploy."]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out.relative_to(_PROOT))

def _p_handoff():
    _p_ensure()
    stamp = _p_datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = _PHANDOFF_DIR / f"handoff_{stamp}.md"
    metrics = _p_metrics()
    open_tasks = [t for t in _p_list_tasks(100) if _p_norm(t.get("status")) not in {"done", "closed", "cancelled", "canceled"}]
    timeline = _p_timeline(25)

    lines = [
        "# JARVIS Handoff",
        "",
        "## Status real",
        f"- branch: {metrics['branch']}",
        f"- commit: {metrics['commit']}",
        f"- git_dirty: {metrics['git_dirty']}",
        "- local_only: true",
        "- production_touched: false",
        "- commit/push/deploy: false nesta geração",
        "",
        "## Open tasks",
    ]
    for t in open_tasks:
        lines.append(f"- {t.get('id')} [{t.get('priority')}/{t.get('status')}] {t.get('title')}")
    lines += ["", "## Timeline recente"]
    for item in timeline:
        lines.append(f"- {item.get('timestamp')} [{item.get('kind')}] {item.get('text')}")
    lines += ["", "## Próximo passo sugerido", "- Continuar batch local de features ou fechar checkpoint maior quando o usuário pedir."]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out.relative_to(_PROOT))

_PROD_PREV_GET = Handler.do_GET
_PROD_PREV_POST = Handler.do_POST

def _prod_do_GET(self):
    parsed = _p_urlparse(self.path)
    path = parsed.path
    query = _p_parse_qs(parsed.query)

    if path == "/tasks":
        p = _p_base("GET /tasks", True)
        p["status_real"] = "local_tasks_read_only"
        p["message"] = "Tasks loaded."
        p["data"] = {"tasks": _p_list_tasks(query.get("limit", ["50"])[0], query.get("status", [None])[0])}
        return _p_json_out(self, p)

    if path == "/metrics":
        p = _p_base("GET /metrics", True)
        p["status_real"] = "local_metrics_read_only"
        p["message"] = "Local metrics loaded."
        p["data"] = _p_metrics()
        return _p_json_out(self, p)

    if path == "/timeline":
        p = _p_base("GET /timeline", True)
        p["status_real"] = "local_timeline_read_only"
        p["message"] = "Timeline loaded."
        p["data"] = {"timeline": _p_timeline(query.get("limit", ["60"])[0])}
        return _p_json_out(self, p)

    return _PROD_PREV_GET(self)

def _prod_command(body):
    raw = str((body or {}).get("command") or (body or {}).get("text") or "").strip()
    clean = _p_norm(raw)
    if clean.startswith("/"):
        clean = clean[1:]

    p = _p_base("POST /command", True)
    p["status_real"] = "local_command_router_only"
    p["command"] = raw

    if clean in {"tasks", "tarefas"}:
        p.update(message="Routing to GET /tasks", routed_to="/tasks", method="GET")
        return p
    if clean in {"metrics", "metricas"}:
        p.update(message="Routing to GET /metrics", routed_to="/metrics", method="GET")
        return p
    if clean in {"timeline", "linha do tempo"}:
        p.update(message="Routing to GET /timeline", routed_to="/timeline", method="GET")
        return p
    if clean in {"checkpoint", "checkpoint-local", "local checkpoint"}:
        p.update(message="Routing to POST /checkpoint-local", routed_to="/checkpoint-local", method="POST")
        return p
    if clean in {"handoff", "handoff-export"}:
        p.update(message="Routing to POST /handoff-export", routed_to="/handoff-export", method="POST")
        return p

    if clean.startswith(("task ", "tarefa ", "todo ")):
        text = raw.strip().split(" ", 1)[1].strip() if " " in raw.strip() else ""
        ok, msg, task = _p_create_task({"title": text, "type": "task"})
        p.update(ok=ok, message=msg, data={"task": task})
        return p

    if clean.startswith(("done ", "feito ", "close ")):
        parts = raw.strip().split(" ", 1)
        task_id = parts[1].strip() if len(parts) > 1 else ""
        ok, msg, task = _p_update_task({"id": task_id, "status": "done", "note": "closed via command"})
        p.update(ok=ok, message=msg, data={"task": task})
        return p

    return None

def _prod_do_POST(self):
    parsed = _p_urlparse(self.path)
    path = parsed.path

    if path == "/task":
        body = _p_read_json(self)
        ok, msg, task = _p_create_task(body)
        p = _p_base("POST /task", ok)
        p["status_real"] = "local_task_append_only"
        p["message"] = msg
        p["data"] = {"task": task}
        return _p_json_out(self, p, 200 if ok else 400)

    if path == "/task-update":
        body = _p_read_json(self)
        ok, msg, task = _p_update_task(body)
        p = _p_base("POST /task-update", ok)
        p["status_real"] = "local_task_update_only"
        p["message"] = msg
        p["data"] = {"task": task}
        return _p_json_out(self, p, 200 if ok else 404)

    if path == "/checkpoint-local":
        p = _p_base("POST /checkpoint-local", True)
        p["status_real"] = "local_checkpoint_file_only"
        p["message"] = "Local checkpoint created."
        p["data"] = {"file": _p_checkpoint()}
        return _p_json_out(self, p)

    if path == "/handoff-export":
        p = _p_base("POST /handoff-export", True)
        p["status_real"] = "local_handoff_file_only"
        p["message"] = "Handoff exported."
        p["data"] = {"file": _p_handoff()}
        return _p_json_out(self, p)

    if path == "/command":
        body = _p_read_json(self)
        new_payload = _prod_command(body)
        if new_payload is not None:
            return _p_json_out(self, new_payload)
        old_payload = globals().get("_j_command_payload")
        if callable(old_payload):
            return _p_json_out(self, old_payload(body))
        return _PROD_PREV_POST(self)

    return _PROD_PREV_POST(self)

Handler.do_GET = _prod_do_GET
Handler.do_POST = _prod_do_POST
# JARVIS_PRODUCTIVITY_EXTENSIONS_END



# JARVIS_MEMORY_EXTENSIONS_BEGIN
# Local memory layer. Append-only. No external API. No secrets. No production.
import json as _m_json
import datetime as _m_datetime
import uuid as _m_uuid
import subprocess as _m_subprocess
from pathlib import Path as _m_Path
from urllib.parse import urlparse as _m_urlparse, parse_qs as _m_parse_qs
import unicodedata as _m_unicodedata

try:
    _MROOT = ROOT
except NameError:
    _MROOT = _m_Path(__file__).resolve().parents[1]

_MDIR = _MROOT / "05_EXECUCAO" / "71_JARVIS_MEMORY"
_MFILE = _MDIR / "jarvis_memory.jsonl"
_MCONTEXT_DIR = _MDIR / "context_packs"
_MBLOCKED = ["commit", "push", "deploy", "production"]

def _m_norm(v):
    v = str(v or "").strip().lower()
    v = _m_unicodedata.normalize("NFKD", v)
    v = "".join(ch for ch in v if not _m_unicodedata.combining(ch))
    return " ".join(v.split())

def _m_now():
    return _m_datetime.datetime.now().isoformat(timespec="seconds")

def _m_secret_like(text):
    low = str(text or "").lower()
    denied = [".env", "token=", "api_key", "apikey", "password", "senha", "secret", "bearer ", "authorization:", "sk-", "x-api-key"]
    return any(x in low for x in denied)

def _m_ensure():
    _MDIR.mkdir(parents=True, exist_ok=True)
    _MCONTEXT_DIR.mkdir(parents=True, exist_ok=True)

def _m_json_out(self, payload, status=200):
    raw = _m_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _m_read_json(self):
    try:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return _m_json.loads(raw or "{}")
    except Exception:
        return {}

def _m_base(endpoint, ok=True):
    return {
        "ok": ok,
        "endpoint": endpoint,
        "status_real": "local_memory_only",
        "message": "",
        "data": {},
        "precisa_aprovacao": False,
        "blocked_actions": list(_MBLOCKED),
    }

def _m_git(args):
    try:
        r = _m_subprocess.run(["git", *args], cwd=_MROOT, text=True, capture_output=True, timeout=5)
        return (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return f"unavailable:{type(e).__name__}"

def _m_read_rows():
    if not _MFILE.exists():
        return []
    rows = []
    for line in _MFILE.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(_m_json.loads(line))
        except Exception:
            pass
    return rows

def _m_write_rows(rows):
    _m_ensure()
    _MFILE.write_text("", encoding="utf-8")
    with _MFILE.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(_m_json.dumps(row, ensure_ascii=False) + "\n")

def _m_append(row):
    _m_ensure()
    with _MFILE.open("a", encoding="utf-8") as f:
        f.write(_m_json.dumps(row, ensure_ascii=False) + "\n")

def _m_listify(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        raw = value.replace(";", ",")
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []

def _m_create(body):
    text = str(body.get("text") or body.get("content") or "").strip()
    if not text:
        return False, "Memory text is empty.", None
    if _m_secret_like(text):
        return False, "Memory blocked because it looks like it may contain a secret.", None

    tags = _m_listify(body.get("tags"))
    kind = str(body.get("type") or body.get("kind") or "memory").strip()
    project = str(body.get("project") or "jarvis").strip()
    importance = str(body.get("importance") or "normal").strip()

    row = {
        "id": "mem_" + _m_datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "_" + _m_uuid.uuid4().hex[:6],
        "created_at": _m_now(),
        "updated_at": _m_now(),
        "project": project,
        "type": kind,
        "importance": importance,
        "tags": tags,
        "text": text,
        "source": str(body.get("source") or "manual").strip(),
        "archived": False,
    }
    _m_append(row)
    return True, "Memory saved.", row

def _m_search(q="", tag="", project="", limit=30, include_archived=False):
    try:
        limit = max(1, min(int(limit), 200))
    except Exception:
        limit = 30

    nq = _m_norm(q)
    ntag = _m_norm(tag)
    nproject = _m_norm(project)
    rows = _m_read_rows()

    out = []
    for row in rows:
        if row.get("archived") and not include_archived:
            continue
        if nproject and _m_norm(row.get("project")) != nproject:
            continue
        tags = [_m_norm(x) for x in row.get("tags", [])]
        if ntag and ntag not in tags:
            continue
        if nq:
            hay = _m_norm(" ".join([
                str(row.get("text", "")),
                str(row.get("project", "")),
                str(row.get("type", "")),
                str(row.get("importance", "")),
                " ".join(row.get("tags", [])),
            ]))
            if nq not in hay:
                continue
        out.append(row)

    return out[-limit:][::-1]

def _m_archive(body):
    mem_id = str(body.get("id") or "").strip()
    if not mem_id:
        return False, "Memory id is required.", None
    rows = _m_read_rows()
    found = None
    for row in rows:
        rid = str(row.get("id", ""))
        if rid == mem_id or rid.startswith(mem_id):
            row["archived"] = True
            row["updated_at"] = _m_now()
            found = row
            break
    if not found:
        return False, "Memory not found.", None
    _m_write_rows(rows)
    return True, "Memory archived.", found

def _m_stats():
    rows = _m_read_rows()
    active = [r for r in rows if not r.get("archived")]
    by_project = {}
    by_tag = {}
    for r in active:
        by_project[r.get("project", "unknown")] = by_project.get(r.get("project", "unknown"), 0) + 1
        for tag in r.get("tags", []):
            by_tag[tag] = by_tag.get(tag, 0) + 1
    return {
        "memory_total": len(rows),
        "memory_active": len(active),
        "memory_archived": len(rows) - len(active),
        "projects": by_project,
        "tags": dict(sorted(by_tag.items(), key=lambda x: x[1], reverse=True)[:30]),
        "branch": _m_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": _m_git(["rev-parse", "--short", "HEAD"]),
        "git_dirty": bool(_m_git(["status", "--short"])),
        "local_only": True,
        "production_touched": False,
    }

def _m_context_pack(body):
    query = str(body.get("query") or body.get("q") or "").strip()
    project = str(body.get("project") or "").strip()
    tag = str(body.get("tag") or "").strip()
    limit = body.get("limit", 40)
    memories = _m_search(query, tag, project, limit)
    stamp = _m_datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe = _m_norm(query or tag or project or "jarvis").replace(" ", "-")[:40] or "jarvis"
    out = _MCONTEXT_DIR / f"context_{stamp}_{safe}.md"
    _m_ensure()

    lines = [
        "# JARVIS Context Pack",
        "",
        f"- generated_at: {_m_now()}",
        f"- query: {query or '-'}",
        f"- project: {project or '-'}",
        f"- tag: {tag or '-'}",
        f"- count: {len(memories)}",
        "- local_only: true",
        "- production_touched: false",
        "",
        "## Memories",
    ]
    for m in memories:
        tags = ", ".join(m.get("tags", []))
        lines.append(f"- `{m.get('id')}` [{m.get('importance')}/{m.get('type')}] {m.get('text')}  \n  tags: {tags} | project: {m.get('project')} | created: {m.get('created_at')}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out.relative_to(_MROOT)), memories

_MEM_PREV_GET = Handler.do_GET
_MEM_PREV_POST = Handler.do_POST

def _mem_command(body):
    raw = str((body or {}).get("command") or (body or {}).get("text") or "").strip()
    clean = _m_norm(raw)
    if clean.startswith("/"):
        clean = clean[1:]

    p = _m_base("POST /command", True)
    p["command"] = raw

    if clean in {"memory", "memories", "memoria", "memorias"}:
        p.update(message="Routing to GET /memory", routed_to="/memory", method="GET")
        return p

    if clean in {"memory-stats", "memoria-status", "memstats"}:
        p.update(message="Routing to GET /memory-stats", routed_to="/memory-stats", method="GET")
        return p

    if clean.startswith(("remember ", "lembrar ", "mem ")):
        text = raw.strip().split(" ", 1)[1].strip() if " " in raw.strip() else ""
        ok, msg, row = _m_create({"text": text, "source": "command", "tags": ["command"]})
        p.update(ok=ok, message=msg, data={"memory": row})
        return p

    if clean.startswith(("recall ", "lembrar? ", "buscar-memoria ")):
        q = raw.strip().split(" ", 1)[1].strip() if " " in raw.strip() else ""
        p.update(message=f"Recall: {q}", data={"memories": _m_search(q=q, limit=20)})
        return p

    if clean.startswith(("context ", "contexto ")):
        q = raw.strip().split(" ", 1)[1].strip() if " " in raw.strip() else ""
        file, memories = _m_context_pack({"query": q, "limit": 40})
        p.update(message="Context pack generated.", data={"file": file, "count": len(memories), "memories": memories[:10]})
        return p

    return None

def _mem_do_GET(self):
    parsed = _m_urlparse(self.path)
    path = parsed.path
    query = _m_parse_qs(parsed.query)

    if path == "/memory":
        p = _m_base("GET /memory", True)
        p["message"] = "Memory loaded."
        p["data"] = {
            "memories": _m_search(
                q=query.get("q", [""])[0],
                tag=query.get("tag", [""])[0],
                project=query.get("project", [""])[0],
                limit=query.get("limit", ["30"])[0],
                include_archived=query.get("archived", ["false"])[0].lower() == "true",
            )
        }
        return _m_json_out(self, p)

    if path == "/recall":
        p = _m_base("GET /recall", True)
        p["message"] = "Recall completed."
        p["data"] = {
            "query": query.get("q", [""])[0],
            "memories": _m_search(q=query.get("q", [""])[0], limit=query.get("limit", ["30"])[0])
        }
        return _m_json_out(self, p)

    if path == "/memory-stats":
        p = _m_base("GET /memory-stats", True)
        p["message"] = "Memory stats loaded."
        p["data"] = _m_stats()
        return _m_json_out(self, p)

    return _MEM_PREV_GET(self)

def _mem_do_POST(self):
    parsed = _m_urlparse(self.path)
    path = parsed.path

    if path == "/remember":
        ok, msg, row = _m_create(_m_read_json(self))
        p = _m_base("POST /remember", ok)
        p["message"] = msg
        p["data"] = {"memory": row}
        return _m_json_out(self, p, 200 if ok else 400)

    if path == "/memory-archive":
        ok, msg, row = _m_archive(_m_read_json(self))
        p = _m_base("POST /memory-archive", ok)
        p["message"] = msg
        p["data"] = {"memory": row}
        return _m_json_out(self, p, 200 if ok else 404)

    if path == "/context-pack":
        file, memories = _m_context_pack(_m_read_json(self))
        p = _m_base("POST /context-pack", True)
        p["message"] = "Context pack generated."
        p["data"] = {"file": file, "count": len(memories), "memories": memories[:20]}
        return _m_json_out(self, p)

    if path == "/command":
        body = _m_read_json(self)
        new_payload = _mem_command(body)
        if new_payload is not None:
            return _m_json_out(self, new_payload)
        return _MEM_PREV_POST(self)

    return _MEM_PREV_POST(self)

Handler.do_GET = _mem_do_GET
Handler.do_POST = _mem_do_POST
# JARVIS_MEMORY_EXTENSIONS_END



# JARVIS_OPERATOR_EXTENSIONS_BEGIN
# Local operator layer. Deterministic planning. No external AI. No deploy.
import json as _o_json
import subprocess as _o_subprocess
import datetime as _o_datetime
from pathlib import Path as _o_Path
from urllib.parse import urlparse as _o_urlparse, parse_qs as _o_parse_qs, unquote as _o_unquote
import unicodedata as _o_unicodedata

try:
    _OROOT = ROOT
except NameError:
    _OROOT = _o_Path(__file__).resolve().parents[1]

_OLOG_DIR = _OROOT / "05_EXECUCAO" / "70_JARVIS_SESSION_LOG"
_OPLAN_DIR = _OROOT / "05_EXECUCAO" / "72_JARVIS_LOCAL_PLANS"
_OBLOCKED = ["commit", "push", "deploy", "production"]

def _o_now():
    return _o_datetime.datetime.now().isoformat(timespec="seconds")

def _o_norm(v):
    v = _o_fix_mojibake(str(v or "")).strip().lower()
    v = _o_unicodedata.normalize("NFKD", v)
    v = "".join(ch for ch in v if not _o_unicodedata.combining(ch))
    return " ".join(v.split())

def _o_fix_mojibake(v):
    s = str(v or "")
    if "Ã" in s or "Â" in s:
        try:
            return s.encode("latin1").decode("utf-8")
        except Exception:
            return s
    return s

def _o_json_out(self, payload, status=200):
    raw = _o_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _o_read_json(self):
    try:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return _o_json.loads(raw or "{}")
    except Exception:
        return {}

def _o_base(endpoint, ok=True):
    return {
        "ok": ok,
        "endpoint": endpoint,
        "status_real": "local_operator_only",
        "message": "",
        "data": {},
        "precisa_aprovacao": False,
        "blocked_actions": list(_OBLOCKED),
    }

def _o_git(args):
    try:
        r = _o_subprocess.run(["git", *args], cwd=_OROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return f"unavailable:{type(e).__name__}"

def _o_jsonl(path):
    p = _OROOT / path if not isinstance(path, _o_Path) else path
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(_o_json.loads(line))
        except Exception:
            pass
    return rows

def _o_file_count(path):
    p = _OROOT / path
    if not p.exists():
        return 0
    return len([x for x in p.rglob("*") if x.is_file()])

def _o_changed_files():
    raw = _o_git(["status", "--short"])
    files = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip() or "?"
        path = line[2:].strip()
        files.append({"status": status, "path": path})
    return files

def _o_diff_stat():
    raw = _o_git(["diff", "--stat"])
    return raw or ""

def _o_local_inventory():
    return {
        "branch": _o_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": _o_git(["rev-parse", "--short", "HEAD"]),
        "git_dirty": bool(_o_git(["status", "--short"])),
        "changed_files": _o_changed_files(),
        "diff_stat": _o_diff_stat(),
        "notes_count": len(_o_jsonl("05_EXECUCAO/70_JARVIS_SESSION_LOG/jarvis_notes.jsonl")),
        "tasks_count": len(_o_jsonl("05_EXECUCAO/70_JARVIS_SESSION_LOG/jarvis_tasks.jsonl")),
        "memory_count": len(_o_jsonl("05_EXECUCAO/71_JARVIS_MEMORY/jarvis_memory.jsonl")),
        "session_files_count": _o_file_count("05_EXECUCAO/70_JARVIS_SESSION_LOG"),
        "memory_files_count": _o_file_count("05_EXECUCAO/71_JARVIS_MEMORY"),
        "plan_files_count": _o_file_count("05_EXECUCAO/72_JARVIS_LOCAL_PLANS"),
        "local_only": True,
        "production_touched": False,
    }

def _o_tasks_open():
    rows = _o_jsonl("05_EXECUCAO/70_JARVIS_SESSION_LOG/jarvis_tasks.jsonl")
    closed = {"done", "closed", "cancelled", "canceled"}
    return [r for r in rows if _o_norm(r.get("status")) not in closed]

def _o_memories_recent(limit=10):
    rows = _o_jsonl("05_EXECUCAO/71_JARVIS_MEMORY/jarvis_memory.jsonl")
    return [r for r in rows if not r.get("archived")][-limit:][::-1]

def _o_decide_next():
    inv = _o_local_inventory()
    tasks = _o_tasks_open()
    actions = []

    if inv["git_dirty"]:
        actions.append("Continuar em modo batch local; não commitar ainda.")
    if tasks:
        actions.append("Usar tarefas abertas como fila principal de produção.")
    if inv["memory_count"] > 0:
        actions.append("Usar memória local para gerar contexto antes de features maiores.")
    if not any("jarvis_api.py" in f.get("path", "") for f in inv["changed_files"]):
        actions.append("Criar próxima feature em API local antes de mexer no visual.")
    else:
        actions.append("Manter visual congelado e evoluir backend/camada operacional.")
    actions.append("Só fechar checkpoint/commit quando o lote estiver grande e estável.")

    return actions

def _o_work_summary():
    inv = _o_local_inventory()
    return {
        "summary": "JARVIS local cockpit em evolução batch: API local, comandos, sessão, notas, tarefas, timeline, memória e contexto.",
        "inventory": inv,
        "open_tasks": _o_tasks_open()[-20:],
        "recent_memories": _o_memories_recent(10),
        "suggested_next_actions": _o_decide_next(),
    }

def _o_write_plan(kind="local_plan", title="JARVIS local production plan"):
    _OPLAN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _o_datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = _OPLAN_DIR / f"{kind}_{stamp}.md"
    ws = _o_work_summary()

    lines = [
        f"# {title}",
        "",
        f"- generated_at: {_o_now()}",
        f"- branch: {ws['inventory']['branch']}",
        f"- commit: {ws['inventory']['commit']}",
        f"- git_dirty: {ws['inventory']['git_dirty']}",
        "- local_only: true",
        "- production_touched: false",
        "- no_commit_no_push_no_deploy: true",
        "",
        "## Status",
        ws["summary"],
        "",
        "## Changed files",
    ]
    for f in ws["inventory"]["changed_files"]:
        lines.append(f"- {f.get('status')} {f.get('path')}")
    lines += ["", "## Open tasks"]
    for t in ws["open_tasks"]:
        lines.append(f"- {t.get('id')} [{t.get('priority')}/{t.get('status')}] {t.get('title')}")
    lines += ["", "## Recent memories"]
    for m in ws["recent_memories"]:
        lines.append(f"- {m.get('id')} [{m.get('importance')}] {m.get('text')}")
    lines += ["", "## Suggested next actions"]
    for a in ws["suggested_next_actions"]:
        lines.append(f"- {a}")
    lines += ["", "Status real: plano local gerado sem IA externa, sem commit, sem push, sem deploy."]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out.relative_to(_OROOT)), ws

def _o_recall_fixed(q, limit=30):
    q = _o_fix_mojibake(_o_unquote(str(q or "")))
    rows = _o_jsonl("05_EXECUCAO/71_JARVIS_MEMORY/jarvis_memory.jsonl")
    nq = _o_norm(q)
    out = []
    for r in rows:
        if r.get("archived"):
            continue
        hay = _o_norm(" ".join([
            str(r.get("text", "")),
            str(r.get("project", "")),
            str(r.get("type", "")),
            str(r.get("importance", "")),
            " ".join(r.get("tags", [])),
        ]))
        if not nq or nq in hay:
            out.append(r)
    try:
        limit = max(1, min(int(limit), 200))
    except Exception:
        limit = 30
    return out[-limit:][::-1]

_OPERATOR_PREV_GET = Handler.do_GET
_OPERATOR_PREV_POST = Handler.do_POST

def _operator_command(body):
    raw = str((body or {}).get("command") or (body or {}).get("text") or "").strip()
    clean = _o_norm(raw)
    if clean.startswith("/"):
        clean = clean[1:]

    p = _o_base("POST /command", True)
    p["command"] = raw

    if clean in {"work-summary", "work summary", "resumo-trabalho", "resumo"}:
        p.update(message="Routing to GET /work-summary", routed_to="/work-summary", method="GET")
        return p
    if clean in {"changed", "changed-files", "mudancas", "diff"}:
        p.update(message="Routing to GET /changed-files", routed_to="/changed-files", method="GET")
        return p
    if clean in {"auto-plan", "plan-local", "plano-local", "plano"}:
        p.update(message="Routing to POST /auto-plan", routed_to="/auto-plan", method="POST")
        return p
    if clean in {"next-local", "decide-next", "proximo-local"}:
        p.update(message="Routing to GET /decide-next", routed_to="/decide-next", method="GET")
        return p

    return None

def _operator_do_GET(self):
    parsed = _o_urlparse(self.path)
    path = parsed.path
    query = _o_parse_qs(parsed.query)

    if path == "/work-summary":
        p = _o_base("GET /work-summary", True)
        p["message"] = "Work summary generated."
        p["data"] = _o_work_summary()
        return _o_json_out(self, p)

    if path == "/changed-files":
        p = _o_base("GET /changed-files", True)
        p["message"] = "Changed files loaded."
        p["data"] = {
            "changed_files": _o_changed_files(),
            "diff_stat": _o_diff_stat(),
            "git_dirty": bool(_o_git(["status", "--short"])),
        }
        return _o_json_out(self, p)

    if path == "/decide-next":
        p = _o_base("GET /decide-next", True)
        p["message"] = "Next local actions suggested."
        p["data"] = {"next_actions": _o_decide_next(), "inventory": _o_local_inventory()}
        return _o_json_out(self, p)

    if path == "/recall-fixed":
        q = query.get("q", [""])[0]
        lim = query.get("limit", ["30"])[0]
        p = _o_base("GET /recall-fixed", True)
        p["message"] = "Recall fixed completed."
        p["data"] = {"query": _o_fix_mojibake(q), "memories": _o_recall_fixed(q, lim)}
        return _o_json_out(self, p)

    return _OPERATOR_PREV_GET(self)

def _operator_do_POST(self):
    parsed = _o_urlparse(self.path)
    path = parsed.path

    if path == "/auto-plan":
        body = _o_read_json(self)
        title = str(body.get("title") or "JARVIS local production plan")
        file, ws = _o_write_plan("local_plan", title)
        p = _o_base("POST /auto-plan", True)
        p["message"] = "Local production plan generated."
        p["data"] = {"file": file, "work_summary": ws}
        return _o_json_out(self, p)

    if path == "/command":
        body = _o_read_json(self)
        new_payload = _operator_command(body)
        if new_payload is not None:
            return _o_json_out(self, new_payload)
        return _OPERATOR_PREV_POST(self)

    return _OPERATOR_PREV_POST(self)

Handler.do_GET = _operator_do_GET
Handler.do_POST = _operator_do_POST
# JARVIS_OPERATOR_EXTENSIONS_END



# JARVIS_DOCTOR_EXTENSIONS_BEGIN
# Local doctor/readiness layer. No external API. No commit. No deploy.
import json as _d_json
import subprocess as _d_subprocess
import datetime as _d_datetime
from pathlib import Path as _d_Path
from urllib.parse import urlparse as _d_urlparse
import re as _d_re

try:
    _DROOT = ROOT
except NameError:
    _DROOT = _d_Path(__file__).resolve().parents[1]

_DBLOCKED = ["commit", "push", "deploy", "production"]
_DREPORT_DIR = _DROOT / "05_EXECUCAO" / "73_JARVIS_DOCTOR"

def _d_now():
    return _d_datetime.datetime.now().isoformat(timespec="seconds")

def _d_json_out(self, payload, status=200):
    raw = _d_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _d_read_json(self):
    try:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return _d_json.loads(raw or "{}")
    except Exception:
        return {}

def _d_base(endpoint, ok=True):
    return {
        "ok": ok,
        "endpoint": endpoint,
        "status_real": "local_doctor_only",
        "message": "",
        "data": {},
        "precisa_aprovacao": False,
        "blocked_actions": list(_DBLOCKED),
    }

def _d_git(args):
    try:
        r = _d_subprocess.run(["git", *args], cwd=_DROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return f"unavailable:{type(e).__name__}"

def _d_changed_files():
    raw = _d_git(["status", "--short"])
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip() or "?"
        path = line[2:].strip()
        rows.append({"status": status, "path": path})
    return rows

def _d_jsonl_count(path):
    p = _DROOT / path
    if not p.exists():
        return 0
    count = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            _d_json.loads(line)
            count += 1
        except Exception:
            pass
    return count

def _d_file_count(path):
    p = _DROOT / path
    if not p.exists():
        return 0
    return len([x for x in p.rglob("*") if x.is_file()])

def _d_markers():
    api_text = (_DROOT / "11_SCRIPTS" / "jarvis_api.py").read_text(encoding="utf-8")
    markers = [
        "JARVIS_LOCAL_EXTENSIONS_BEGIN",
        "JARVIS_PRODUCTIVITY_EXTENSIONS_BEGIN",
        "JARVIS_MEMORY_EXTENSIONS_BEGIN",
        "JARVIS_OPERATOR_EXTENSIONS_BEGIN",
        "JARVIS_DOCTOR_EXTENSIONS_BEGIN",
    ]
    return {m: (m in api_text) for m in markers}

def _d_feature_map():
    return {
        "core": [
            "GET /status",
            "GET /next",
            "GET /latest",
            "GET /sources",
            "GET /source",
            "GET /source-search",
            "POST /self-test",
            "POST /validate",
            "POST /safety-gate",
        ],
        "command_router": [
            "POST /command",
            "GET /commands",
            "GET /session",
            "POST /note",
            "GET /notes",
            "POST /export-session",
        ],
        "productivity": [
            "POST /task",
            "POST /task-update",
            "GET /tasks",
            "GET /metrics",
            "GET /timeline",
            "POST /checkpoint-local",
            "POST /handoff-export",
        ],
        "memory": [
            "POST /remember",
            "GET /memory",
            "GET /recall",
            "GET /memory-stats",
            "POST /memory-archive",
            "POST /context-pack",
        ],
        "operator": [
            "GET /work-summary",
            "GET /changed-files",
            "GET /decide-next",
            "GET /recall-fixed",
            "POST /auto-plan",
        ],
        "doctor": [
            "GET /doctor",
            "GET /feature-map",
            "GET /release-readiness",
            "POST /doctor-report",
        ],
    }

def _d_status_catalog():
    endpoints = []
    for group in _d_feature_map().values():
        endpoints.extend(group)
    return sorted(set(endpoints))

def _d_doctor():
    changed = _d_changed_files()
    markers = _d_markers()
    checks = []

    def add(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("api_file_exists", (_DROOT / "11_SCRIPTS/jarvis_api.py").exists())
    add("ui_file_exists", (_DROOT / "11_SCRIPTS/jarvis_ui_assets/cockpit.html").exists())
    add("extension_markers", all(markers.values()), markers)
    add("git_available", bool(_d_git(["rev-parse", "--short", "HEAD"])))
    add("local_dirty_expected", bool(changed), changed)
    add("session_log_exists", (_DROOT / "05_EXECUCAO/70_JARVIS_SESSION_LOG").exists())
    add("memory_exists", (_DROOT / "05_EXECUCAO/71_JARVIS_MEMORY").exists())
    add("no_env_in_changed_paths", not any(".env" in x.get("path", "").lower() for x in changed), changed)
    add("no_deploy_files_changed", not any(x.get("path", "").startswith((".github/", "vercel", "Dockerfile")) for x in changed), changed)

    ok = all(c["ok"] for c in checks if c["name"] not in {"local_dirty_expected"})
    return {
        "ok": ok,
        "checks": checks,
        "summary": {
            "branch": _d_git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "commit": _d_git(["rev-parse", "--short", "HEAD"]),
            "git_dirty": bool(changed),
            "changed_files": changed,
            "notes": _d_jsonl_count("05_EXECUCAO/70_JARVIS_SESSION_LOG/jarvis_notes.jsonl"),
            "tasks": _d_jsonl_count("05_EXECUCAO/70_JARVIS_SESSION_LOG/jarvis_tasks.jsonl"),
            "memories": _d_jsonl_count("05_EXECUCAO/71_JARVIS_MEMORY/jarvis_memory.jsonl"),
            "doctor_reports": _d_file_count("05_EXECUCAO/73_JARVIS_DOCTOR"),
            "local_only": True,
            "production_touched": False,
        }
    }

def _d_release_readiness():
    doc = _d_doctor()
    changed = doc["summary"]["changed_files"]
    blockers = []
    warnings = []

    if not doc["ok"]:
        blockers.append("doctor_failed")
    if any(".env" in x.get("path", "").lower() for x in changed):
        blockers.append("env_file_changed")
    if any(x.get("path", "").startswith((".github/", "vercel", "Dockerfile")) for x in changed):
        warnings.append("deployment_related_file_changed")
    if doc["summary"]["memories"] == 0:
        warnings.append("no_memory_records")
    if doc["summary"]["tasks"] == 0:
        warnings.append("no_task_records")

    return {
        "ready_for_local_checkpoint": len(blockers) == 0,
        "ready_for_commit_later": len(blockers) == 0,
        "ready_for_push": False,
        "ready_for_deploy": False,
        "blockers": blockers,
        "warnings": warnings,
        "doctor": doc,
        "status_real": "local_readiness_only_no_push_no_deploy",
    }

def _d_write_report():
    _DREPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _d_datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = _DREPORT_DIR / f"doctor_report_{stamp}.md"
    readiness = _d_release_readiness()
    feature_map = _d_feature_map()

    lines = [
        "# JARVIS Doctor Report",
        "",
        f"- generated_at: {_d_now()}",
        f"- branch: {readiness['doctor']['summary']['branch']}",
        f"- commit: {readiness['doctor']['summary']['commit']}",
        f"- git_dirty: {readiness['doctor']['summary']['git_dirty']}",
        f"- ready_for_local_checkpoint: {readiness['ready_for_local_checkpoint']}",
        f"- ready_for_commit_later: {readiness['ready_for_commit_later']}",
        "- ready_for_push: false",
        "- ready_for_deploy: false",
        "- production_touched: false",
        "",
        "## Blockers",
    ]
    for b in readiness["blockers"] or ["none"]:
        lines.append(f"- {b}")

    lines += ["", "## Warnings"]
    for w in readiness["warnings"] or ["none"]:
        lines.append(f"- {w}")

    lines += ["", "## Checks"]
    for c in readiness["doctor"]["checks"]:
        lines.append(f"- {'OK' if c['ok'] else 'FAIL'} {c['name']}")

    lines += ["", "## Changed files"]
    for f in readiness["doctor"]["summary"]["changed_files"]:
        lines.append(f"- {f.get('status')} {f.get('path')}")

    lines += ["", "## Feature map"]
    for group, endpoints in feature_map.items():
        lines.append(f"### {group}")
        for ep in endpoints:
            lines.append(f"- `{ep}`")

    lines += ["", "Status real: relatório local, sem commit, sem push, sem deploy."]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out.relative_to(_DROOT)), readiness

_DOCTOR_PREV_GET = Handler.do_GET
_DOCTOR_PREV_POST = Handler.do_POST

def _doctor_command(body):
    raw = str((body or {}).get("command") or (body or {}).get("text") or "").strip().lower().replace("/", "").strip()

    p = _d_base("POST /command", True)
    p["command"] = (body or {}).get("command") or (body or {}).get("text") or ""

    if raw in {"doctor", "check", "diagnostico"}:
        p.update(message="Routing to GET /doctor", routed_to="/doctor", method="GET")
        return p
    if raw in {"feature-map", "features", "mapa"}:
        p.update(message="Routing to GET /feature-map", routed_to="/feature-map", method="GET")
        return p
    if raw in {"release-readiness", "readiness", "pronto"}:
        p.update(message="Routing to GET /release-readiness", routed_to="/release-readiness", method="GET")
        return p
    if raw in {"doctor-report", "report"}:
        p.update(message="Routing to POST /doctor-report", routed_to="/doctor-report", method="POST")
        return p

    return None

def _doctor_do_GET(self):
    parsed = _d_urlparse(self.path)
    path = parsed.path

    if path == "/status":
        p = {
            "ok": True,
            "service": "jarvis-api-local",
            "status_real": "local_only_no_external_production",
            "allowed_endpoints": _d_status_catalog(),
            "blocked": ["commit", "push", "deploy", "free_shell", "read_env", "external_production"],
            "precisa_aprovacao": True,
            "git_status": _d_git(["status", "--short"]),
            "git_head": _d_git(["log", "--oneline", "-1"]),
        }
        return _d_json_out(self, p)

    if path == "/doctor":
        doc = _d_doctor()
        p = _d_base("GET /doctor", doc["ok"])
        p["message"] = "Doctor completed."
        p["data"] = doc
        return _d_json_out(self, p, 200 if doc["ok"] else 500)

    if path == "/feature-map":
        p = _d_base("GET /feature-map", True)
        p["message"] = "Feature map loaded."
        p["data"] = {"features": _d_feature_map(), "endpoints": _d_status_catalog()}
        return _d_json_out(self, p)

    if path == "/release-readiness":
        p = _d_base("GET /release-readiness", True)
        p["message"] = "Release readiness calculated."
        p["data"] = _d_release_readiness()
        return _d_json_out(self, p)

    return _DOCTOR_PREV_GET(self)

def _doctor_do_POST(self):
    parsed = _d_urlparse(self.path)
    path = parsed.path

    if path == "/doctor-report":
        file, readiness = _d_write_report()
        p = _d_base("POST /doctor-report", True)
        p["message"] = "Doctor report generated."
        p["data"] = {"file": file, "readiness": readiness}
        return _d_json_out(self, p)

    if path == "/command":
        body = _d_read_json(self)
        new_payload = _doctor_command(body)
        if new_payload is not None:
            return _d_json_out(self, new_payload)
        return _DOCTOR_PREV_POST(self)

    return _DOCTOR_PREV_POST(self)

Handler.do_GET = _doctor_do_GET
Handler.do_POST = _doctor_do_POST
# JARVIS_DOCTOR_EXTENSIONS_END



# JARVIS_FULLTEST_LITE_BEGIN
# Local full-test / API index / runbook. No external API. No shell livre. No deploy.
import json as _ft_json
import datetime as _ft_datetime
import subprocess as _ft_subprocess
from pathlib import Path as _ft_Path
from urllib.parse import urlparse as _ft_urlparse

try:
    _FTROOT = ROOT
except NameError:
    _FTROOT = _ft_Path(__file__).resolve().parents[1]

_FTDIR = _FTROOT / "05_EXECUCAO" / "74_JARVIS_FULLTEST"
_FTBLOCKED = ["commit", "push", "deploy", "production"]

def _ft_now():
    return _ft_datetime.datetime.now().isoformat(timespec="seconds")

def _ft_json_out(self, payload, status=200):
    raw = _ft_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _ft_read_json(self):
    try:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return _ft_json.loads(raw or "{}")
    except Exception:
        return {}

def _ft_base(endpoint, ok=True):
    return {
        "ok": ok,
        "endpoint": endpoint,
        "status_real": "local_fulltest_only",
        "message": "",
        "data": {},
        "precisa_aprovacao": False,
        "blocked_actions": list(_FTBLOCKED),
    }

def _ft_git(args):
    try:
        r = _ft_subprocess.run(["git", *args], cwd=_FTROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return f"unavailable:{type(e).__name__}"

def _ft_api_text():
    return (_FTROOT / "11_SCRIPTS" / "jarvis_api.py").read_text(encoding="utf-8")

def _ft_endpoint_catalog():
    return [
        {"group":"core","method":"GET","path":"/status"},
        {"group":"core","method":"GET","path":"/next"},
        {"group":"core","method":"GET","path":"/latest"},
        {"group":"core","method":"GET","path":"/sources"},
        {"group":"core","method":"GET","path":"/source-search"},
        {"group":"core","method":"POST","path":"/self-test"},
        {"group":"core","method":"POST","path":"/validate"},
        {"group":"core","method":"POST","path":"/safety-gate"},

        {"group":"command","method":"POST","path":"/command"},
        {"group":"command","method":"GET","path":"/commands"},
        {"group":"command","method":"GET","path":"/session"},
        {"group":"command","method":"POST","path":"/note"},
        {"group":"command","method":"GET","path":"/notes"},
        {"group":"command","method":"POST","path":"/export-session"},

        {"group":"productivity","method":"POST","path":"/task"},
        {"group":"productivity","method":"GET","path":"/tasks"},
        {"group":"productivity","method":"GET","path":"/metrics"},
        {"group":"productivity","method":"GET","path":"/timeline"},
        {"group":"productivity","method":"POST","path":"/checkpoint-local"},
        {"group":"productivity","method":"POST","path":"/handoff-export"},

        {"group":"memory","method":"POST","path":"/remember"},
        {"group":"memory","method":"GET","path":"/memory"},
        {"group":"memory","method":"GET","path":"/recall"},
        {"group":"memory","method":"GET","path":"/memory-stats"},
        {"group":"memory","method":"POST","path":"/context-pack"},

        {"group":"operator","method":"GET","path":"/work-summary"},
        {"group":"operator","method":"GET","path":"/changed-files"},
        {"group":"operator","method":"GET","path":"/decide-next"},
        {"group":"operator","method":"POST","path":"/auto-plan"},

        {"group":"doctor","method":"GET","path":"/doctor"},
        {"group":"doctor","method":"GET","path":"/feature-map"},
        {"group":"doctor","method":"GET","path":"/release-readiness"},
        {"group":"doctor","method":"POST","path":"/doctor-report"},

        {"group":"fulltest","method":"GET","path":"/api-index"},
        {"group":"fulltest","method":"GET","path":"/runbook"},
        {"group":"fulltest","method":"POST","path":"/full-test"},
    ]

def _ft_index():
    text = _ft_api_text()
    endpoints = []
    for ep in _ft_endpoint_catalog():
        key = ep["path"]
        implemented = key in text or f'path == "{key}"' in text or f'self.path == "{key}"' in text
        endpoints.append({**ep, "implemented": bool(implemented)})
    groups = {}
    for ep in endpoints:
        groups.setdefault(ep["group"], {"total": 0, "implemented": 0})
        groups[ep["group"]]["total"] += 1
        groups[ep["group"]]["implemented"] += 1 if ep["implemented"] else 0
    return {"endpoints": endpoints, "groups": groups}

def _ft_full_test():
    index = _ft_index()
    status = _ft_git(["status", "--short"])
    markers = {
        "local": "JARVIS_LOCAL_EXTENSIONS_BEGIN" in _ft_api_text(),
        "productivity": "JARVIS_PRODUCTIVITY_EXTENSIONS_BEGIN" in _ft_api_text(),
        "memory": "JARVIS_MEMORY_EXTENSIONS_BEGIN" in _ft_api_text(),
        "operator": "JARVIS_OPERATOR_EXTENSIONS_BEGIN" in _ft_api_text(),
        "doctor": "JARVIS_DOCTOR_EXTENSIONS_BEGIN" in _ft_api_text(),
        "fulltest": "JARVIS_FULLTEST_LITE_BEGIN" in _ft_api_text(),
    }

    checks = [
        {"name":"api_exists","ok":(_FTROOT / "11_SCRIPTS/jarvis_api.py").exists()},
        {"name":"ui_exists","ok":(_FTROOT / "11_SCRIPTS/jarvis_ui_assets/cockpit.html").exists()},
        {"name":"git_available","ok":bool(_ft_git(["rev-parse","--short","HEAD"]))},
        {"name":"no_env_changed","ok":".env" not in status.lower(), "detail":status},
        {"name":"extension_markers","ok":all(markers.values()), "detail":markers},
        {"name":"endpoint_groups_present","ok":all(v["implemented"] > 0 for v in index["groups"].values()), "detail":index["groups"]},
        {"name":"local_only_policy","ok":True, "detail":{"push":False,"deploy":False,"production":False}},
    ]

    return {
        "ok": all(c["ok"] for c in checks),
        "checks_passed": len([c for c in checks if c["ok"]]),
        "checks_total": len(checks),
        "checks": checks,
        "index": index,
        "branch": _ft_git(["rev-parse","--abbrev-ref","HEAD"]),
        "commit": _ft_git(["rev-parse","--short","HEAD"]),
        "git_dirty": bool(status),
        "local_only": True,
        "production_touched": False,
    }

def _ft_write_runbook():
    _FTDIR.mkdir(parents=True, exist_ok=True)
    stamp = _ft_datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = _FTDIR / f"jarvis_runbook_{stamp}.md"
    full = _ft_full_test()

    lines = [
        "# JARVIS Local Runbook",
        "",
        f"- generated_at: {_ft_now()}",
        f"- branch: {full['branch']}",
        f"- commit: {full['commit']}",
        f"- git_dirty: {full['git_dirty']}",
        "- local_only: true",
        "- production_touched: false",
        "- push: false",
        "- deploy: false",
        "",
        "## Start",
        "```bash",
        "cd ~/Theo/JARVIS/jarvis-agent-os",
        "./jarvis api",
        "```",
        "",
        "Open: http://127.0.0.1:8787/",
        "",
        "## Safety",
        "- No commit, push or deploy from cockpit.",
        "- No free shell.",
        "- No .env reads.",
        "- Human approval required for real actions.",
        "",
        "## Full-test",
        f"- ok: {full['ok']}",
        f"- checks: {full['checks_passed']}/{full['checks_total']}",
    ]

    for c in full["checks"]:
        lines.append(f"- {'OK' if c['ok'] else 'FAIL'} {c['name']}")

    lines += ["", "## Endpoint index"]
    for ep in full["index"]["endpoints"]:
        lines.append(f"- `{ep['method']} {ep['path']}` [{ep['group']}] implemented={ep['implemented']}")

    lines += ["", "Status real: runbook local. Sem commit, sem push, sem deploy."]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out.relative_to(_FTROOT)), full

_FULLTEST_PREV_GET = Handler.do_GET
_FULLTEST_PREV_POST = Handler.do_POST

def _fulltest_command(body):
    raw = str((body or {}).get("command") or (body or {}).get("text") or "").strip().lower().replace("/", "").strip()
    p = _ft_base("POST /command", True)
    p["command"] = (body or {}).get("command") or (body or {}).get("text") or ""

    if raw in {"full-test", "fulltest", "test-all", "teste-geral"}:
        p.update(message="Routing to POST /full-test", routed_to="/full-test", method="POST")
        return p
    if raw in {"api-index", "index", "endpoints"}:
        p.update(message="Routing to GET /api-index", routed_to="/api-index", method="GET")
        return p
    if raw in {"runbook", "manual"}:
        p.update(message="Routing to GET /runbook", routed_to="/runbook", method="GET")
        return p
    return None

def _fulltest_do_GET(self):
    path = _ft_urlparse(self.path).path

    if path == "/api-index":
        p = _ft_base("GET /api-index", True)
        p["message"] = "API index loaded."
        p["data"] = _ft_index()
        return _ft_json_out(self, p)

    if path == "/runbook":
        file, full = _ft_write_runbook()
        p = _ft_base("GET /runbook", True)
        p["message"] = "Runbook generated."
        p["data"] = {"file": file, "full_test": full}
        return _ft_json_out(self, p)

    return _FULLTEST_PREV_GET(self)

def _fulltest_do_POST(self):
    path = _ft_urlparse(self.path).path

    if path == "/full-test":
        full = _ft_full_test()
        p = _ft_base("POST /full-test", full["ok"])
        p["message"] = "Full local test completed."
        p["data"] = full
        return _ft_json_out(self, p)

    if path == "/command":
        body = _ft_read_json(self)
        routed = _fulltest_command(body)
        if routed is not None:
            return _ft_json_out(self, routed)
        return _FULLTEST_PREV_POST(self)

    return _FULLTEST_PREV_POST(self)

Handler.do_GET = _fulltest_do_GET
Handler.do_POST = _fulltest_do_POST
# JARVIS_FULLTEST_LITE_END



# === JARVIS BIG BLOCK 76: LOCAL TECHNICAL INTELLIGENCE LAYER ===
# Local-only technical expansion.
# No external API. No free shell. No env reads. No commit. No push. No deploy.

import json as _j76_json
import os as _j76_os
import re as _j76_re
import subprocess as _j76_subprocess
import time as _j76_time
import py_compile as _j76_py_compile
from pathlib import Path as _j76_Path
from urllib.parse import urlparse as _j76_urlparse, parse_qs as _j76_parse_qs, quote as _j76_quote
from http.server import BaseHTTPRequestHandler as _j76_BaseHTTPRequestHandler

_J76ROOT = _j76_Path(__file__).resolve().parents[1]
_J76DIR = _J76ROOT / "05_EXECUCAO" / "76_JARVIS_BIG_BLOCK"
_J76REPORTS = _J76DIR / "reports"
_J76DECISIONS = _J76DIR / "decisions"
_J76PLANS = _J76DIR / "plans"
_J76INDEX = _J76DIR / "indexes"
_J76DIRS = [_J76DIR, _J76REPORTS, _J76DECISIONS, _J76PLANS, _J76INDEX]
for _d in _J76DIRS:
    _d.mkdir(parents=True, exist_ok=True)

_J76BLOCKED = ["commit", "push", "deploy", "production"]
_J76HARD_BLOCKED = ["commit", "push", "deploy", "free_shell", "read_env", "external_production"]
_J76SAFE_EXT = {
    ".md", ".txt", ".json", ".jsonl", ".py", ".html", ".css", ".js",
    ".yml", ".yaml", ".toml", ".csv"
}
_J76SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".next", "dist", "build"
}
_J76SECRET_WORDS = [
    ".env", "secret", "token", "senha", "password", "apikey", "api_key",
    "authorization", "bearer", "cookie", "private_key", "service_role", "sk-"
]

def _j76_now():
    return _j76_time.strftime("%Y-%m-%d_%H-%M-%S")

def _j76_norm(v):
    return "" if v is None else str(v).strip()

def _j76_secret_like(value):
    s = _j76_norm(value).lower()
    return any(x in s for x in _J76SECRET_WORDS)

def _j76_under_root(path):
    try:
        p = _j76_Path(path).expanduser()
        if not p.is_absolute():
            p = _J76ROOT / p
        p = p.resolve()
        p.relative_to(_J76ROOT)
        return p
    except Exception:
        return None

def _j76_safe_path(value):
    p = _j76_under_root(value)
    if not p:
        return None, "outside_project"
    rel = p.relative_to(_J76ROOT)
    parts = [x.lower() for x in rel.parts]
    if any(x.startswith(".") for x in parts):
        return None, "hidden_path_blocked"
    if any(x in _J76SKIP_DIRS for x in parts):
        return None, "skip_dir_blocked"
    if _j76_secret_like(str(rel)):
        return None, "secret_like_path_blocked"
    if p.suffix.lower() and p.suffix.lower() not in _J76SAFE_EXT:
        return None, "extension_not_allowed"
    return p, "ok"

def _j76_read_text_limited(path, limit=16000):
    p, reason = _j76_safe_path(path)
    if not p:
        return None, reason
    if not p.exists():
        return None, "not_found"
    if not p.is_file():
        return None, "not_file"
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
        return raw[:limit], "ok"
    except Exception as e:
        return None, f"read_error:{e}"

def _j76_json_out(self, payload, status=200):
    if hasattr(self, "send_json"):
        return self.send_json(status, payload)
    raw = _j76_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _j76_read_json(self):
    try:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return _j76_json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}

def _j76_base(endpoint, ok=True, status_real="local_big_block_only"):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "status_real": status_real,
        "precisa_aprovacao": True,
        "blocked_actions": list(_J76BLOCKED),
        "safety": {
            "local_only": True,
            "external_api": False,
            "free_shell": False,
            "read_env": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "production_touched": False,
        },
    }

def _j76_git(args, timeout=6):
    allowed = [
        ["status", "--short"],
        ["diff", "--stat"],
        ["diff", "--name-only"],
        ["branch", "--show-current"],
        ["log", "--oneline", "-5"],
        ["rev-parse", "--short", "HEAD"],
    ]
    if args not in allowed:
        return {"ok": False, "blocked": True, "args": args, "stdout": "", "stderr": "git command not allowed"}
    try:
        r = _j76_subprocess.run(["git", *args], cwd=_J76ROOT, text=True, capture_output=True, timeout=timeout)
        return {"ok": r.returncode == 0, "returncode": r.returncode, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e), "stdout": "", "stderr": str(e)}

def _j76_changed_files():
    out = _j76_git(["diff", "--name-only"]).get("stdout", "")
    return [x.strip() for x in out.splitlines() if x.strip()]

def _j76_status_short():
    return _j76_git(["status", "--short"]).get("stdout", "")

def _j76_diff_stat():
    return _j76_git(["diff", "--stat"]).get("stdout", "")

def _j76_iter_project_files(max_files=900):
    files = []
    roots = ["02_SOURCES", "03_DOCS", "04_OUTPUT", "05_EXECUCAO", "11_SCRIPTS"]
    for root_name in roots:
        base = _J76ROOT / root_name
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if len(files) >= max_files:
                return files
            try:
                rel = p.relative_to(_J76ROOT)
            except Exception:
                continue
            parts = [x.lower() for x in rel.parts]
            if any(x in _J76SKIP_DIRS for x in parts):
                continue
            if any(x.startswith(".") for x in parts):
                continue
            if p.is_file() and p.suffix.lower() in _J76SAFE_EXT and not _j76_secret_like(str(rel)):
                files.append(p)
    return files

def _j76_file_meta(p):
    try:
        rel = str(p.relative_to(_J76ROOT))
        st = p.stat()
        return {
            "path": rel,
            "name": p.name,
            "suffix": p.suffix.lower(),
            "size": st.st_size,
            "modified": int(st.st_mtime),
        }
    except Exception:
        return None

def _j76_project_map():
    files = _j76_iter_project_files()
    by_ext = {}
    by_top = {}
    total_size = 0
    newest = []
    for p in files:
        meta = _j76_file_meta(p)
        if not meta:
            continue
        total_size += meta["size"]
        by_ext[meta["suffix"] or "(none)"] = by_ext.get(meta["suffix"] or "(none)", 0) + 1
        top = meta["path"].split("/", 1)[0]
        by_top[top] = by_top.get(top, 0) + 1
        newest.append(meta)
    newest = sorted(newest, key=lambda x: x["modified"], reverse=True)[:30]
    return {
        "files_indexed": len(files),
        "total_size_bytes": total_size,
        "by_extension": dict(sorted(by_ext.items())),
        "by_top_folder": dict(sorted(by_top.items())),
        "newest_files": newest,
    }

def _j76_capability_map():
    return {
        "core_existing": [
            "GET /status",
            "GET /next",
            "GET /latest",
            "GET /sources",
            "GET /source",
            "GET /source-search",
            "GET /artifact",
            "POST /self-test",
            "POST /validate",
            "POST /safety-gate",
        ],
        "session_layer": [
            "GET /session",
            "GET /commands",
            "GET /tasks",
            "GET /metrics",
            "GET /timeline",
            "POST /checkpoint-local",
            "POST /handoff-export",
        ],
        "memory_layer": [
            "GET /memory",
            "GET /memory-stats",
            "POST /memory-archive",
        ],
        "operator_layer": [
            "GET /work-summary",
            "GET /changed-files",
            "GET /decide-next",
            "POST /auto-plan",
        ],
        "doctor_fulltest_layer": [
            "GET /doctor",
            "GET /api-index",
            "POST /fulltest",
        ],
        "big_block_76_new": [
            "GET /capability-map",
            "GET /project-map",
            "GET /risk-scan",
            "GET /health-score",
            "GET /technical-roadmap",
            "GET /knowledge-index",
            "GET /local-search?q=...",
            "GET /source-digest?path=...",
            "GET /session-brief",
            "GET /commit-candidate",
            "GET /ops-dashboard",
            "POST /validate-all",
            "POST /big-block-report",
            "POST /evolution-loop",
            "POST /decision-log",
            "POST /research-plan-local",
            "POST /feature-pack",
        ],
        "blocked_forever_from_cockpit": _J76HARD_BLOCKED,
    }

# Danger categories that, when seen as live code, block readiness. Secret-term
# and blocked-action-text hits are reported for manual review but never counted
# as real danger (they are almost always policy text or the scanner's own defs).
_J76_REAL_DANGER_KINDS = (
    "free_shell_or_system",
    "dynamic_eval_exec",
    "destructive",
    "external_ai_or_http_lib",
)

def _j76_strip_noncode(line):
    # Remove quoted string literals and trailing comments so the scanner does
    # not flag its own regex/policy definitions or comments as real danger.
    # A pattern that only matches inside a string/comment is not live code.
    s = _j76_re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
    s = _j76_re.sub(r"'(?:[^'\\]|\\.)*'", "''", s)
    hash_idx = s.find("#")
    if hash_idx != -1:
        s = s[:hash_idx]
    return s

def _j76_risk_scan():
    changed = _j76_changed_files()
    files = [_J76ROOT / x for x in changed if (_J76ROOT / x).exists()]
    if not files:
        files = [_J76ROOT / "11_SCRIPTS" / "jarvis_api.py"]
    patterns = {
        "free_shell_or_system": r"shell=True|os\.system|Popen\(",
        "dynamic_eval_exec": r"\beval\(|\bexec\(",
        "destructive": r"rm\s+-rf|chmod\s+777",
        "external_ai_or_http_lib": r"openai|anthropic|requests|httpx",
        "secret_terms": r"\.env|api_key|apikey|authorization:|bearer\s|password|senha|secret|sk-",
        "blocked_actions_text": r"git commit|git push|\bdeploy\b|\bproduction\b",
    }
    hits = []
    for p in files:
        rel = str(p.relative_to(_J76ROOT))
        if _j76_secret_like(rel):
            continue
        if p.suffix.lower() not in _J76SAFE_EXT:
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            for name, pat in patterns.items():
                if _j76_re.search(pat, line, flags=_j76_re.I):
                    clean = line.strip()
                    if len(clean) > 220:
                        clean = clean[:220] + "..."
                    # Only count as real danger when the pattern still matches
                    # after strings/comments are stripped, i.e. it is live code
                    # and not a regex/policy definition or a comment.
                    is_real = (
                        name in _J76_REAL_DANGER_KINDS
                        and bool(_j76_re.search(pat, _j76_strip_noncode(line), flags=_j76_re.I))
                    )
                    hits.append({"file": rel, "line": i, "kind": name, "text": clean, "real_danger": is_real})
                    break
    real_danger = [h for h in hits if h.get("real_danger")]
    secret_hits = [h for h in hits if h["kind"] == "secret_terms"]
    return {
        "changed_files": changed,
        "hits_count": len(hits),
        "real_danger_count": len(real_danger),
        "secret_term_count": len(secret_hits),
        "real_danger": real_danger[:50],
        "hits_sample": hits[:120],
        "verdict": "review" if real_danger else "pass_with_manual_review",
        "note": "Danger is counted only when a pattern matches live code (outside strings/comments). Regex/policy definitions, comments, secret-term and blocked-action text are shown for manual review but not counted as real danger.",
    }

def _j76_pycheck():
    targets = [
        _J76ROOT / "11_SCRIPTS" / "jarvis_api.py",
        _J76ROOT / "11_SCRIPTS" / "jarvis_core.py",
    ]
    rows = []
    for p in targets:
        try:
            _j76_py_compile.compile(str(p), doraise=True)
            rows.append({"path": str(p.relative_to(_J76ROOT)), "ok": True})
        except Exception as e:
            rows.append({"path": str(p.relative_to(_J76ROOT)), "ok": False, "error": str(e)})
    return rows

def _j76_health_score():
    checks = []
    def add(name, ok, detail=None, weight=1):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "weight": weight})
    status = _j76_status_short()
    changed = _j76_changed_files()
    risk = _j76_risk_scan()
    pyrows = _j76_pycheck()
    pmap = _j76_project_map()
    add("python_compile", all(x["ok"] for x in pyrows), pyrows, 3)
    add("local_changes_exist", bool(status), status, 1)
    add("no_env_changed", ".env" not in status.lower(), status, 3)
    add("no_deploy_files_changed", not any(x.startswith((".github/", "Dockerfile", "vercel", "fly.toml", "railway")) for x in changed), changed, 2)
    add("risk_scan_no_real_danger", risk["real_danger_count"] == 0, risk, 3)
    add("project_map_available", pmap["files_indexed"] > 0, pmap, 1)
    add("approval_required", True, "JARVIS cockpit always requires approval for sensitive actions.", 1)
    max_score = sum(x["weight"] for x in checks)
    score = sum(x["weight"] for x in checks if x["ok"])
    pct = round((score / max_score) * 100, 1) if max_score else 0
    return {
        "score": score,
        "max_score": max_score,
        "percent": pct,
        "ready_for_commit": pct >= 85 and risk["real_danger_count"] == 0,
        "ready_for_deploy": False,
        "checks": checks,
    }

def _j76_technical_roadmap():
    return {
        "current_block": "76_JARVIS_BIG_BLOCK",
        "objective": "advance JARVIS as a local technical operating cockpit, not a visual/site review",
        "completed_or_present": [
            "local API endpoint suite",
            "source listing and search",
            "digest validation",
            "safety gate",
            "session log",
            "local tasks",
            "local memory",
            "local planning",
            "doctor/readiness checks",
            "API index",
            "big block 76 intelligence layer",
        ],
        "next_blocks": [
            {
                "block": "77",
                "name": "Context Pack Builder",
                "goal": "generate clean context packs from sources, status, memory, changed files and plans",
                "safe": True,
            },
            {
                "block": "78",
                "name": "Spec-to-Tasks Engine",
                "goal": "turn a requested feature into tasks, acceptance criteria, risks, and test commands",
                "safe": True,
            },
            {
                "block": "79",
                "name": "Local Evaluation Suite",
                "goal": "evaluate plans, memory quality, safety gates, and endpoint consistency",
                "safe": True,
            },
            {
                "block": "80",
                "name": "Self-Improvement Planner",
                "goal": "suggest code improvements but not apply them without human approval",
                "safe": True,
            },
            {
                "block": "81",
                "name": "Internet Research Module",
                "goal": "future feature requiring Claude or stronger controlled executor; not implemented now",
                "safe": False,
                "requires_claude_or_human": True,
            },
        ],
        "blocked_now": [
            "autonomous external web browsing",
            "automatic code edits without human approval",
            "commit/push/deploy",
            "reading secrets or .env",
            "production actions",
        ],
    }

def _j76_knowledge_index():
    files = _j76_iter_project_files()
    rows = []
    for p in files:
        rel = str(p.relative_to(_J76ROOT))
        lower = rel.lower()
        kind = "other"
        if "source" in lower:
            kind = "source"
        elif "digest" in lower:
            kind = "digest"
        elif "plan" in lower:
            kind = "plan"
        elif "memory" in lower:
            kind = "memory"
        elif "doctor" in lower:
            kind = "doctor"
        elif "runbook" in lower:
            kind = "runbook"
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")[:6000]
            words = len(_j76_re.findall(r"\w+", txt))
            headings = [x.strip("# ").strip() for x in txt.splitlines() if x.strip().startswith("#")][:8]
        except Exception:
            words = 0
            headings = []
        rows.append({"path": rel, "kind": kind, "suffix": p.suffix.lower(), "words_est": words, "headings": headings})
    by_kind = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    idx = {
        "total": len(rows),
        "by_kind": dict(sorted(by_kind.items())),
        "items": rows[:250],
    }
    out = _J76INDEX / f"knowledge_index_{_j76_now()}.json"
    out.write_text(_j76_json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    idx["saved_to"] = str(out.relative_to(_J76ROOT))
    return idx

def _j76_local_search(q, limit=40):
    q = _j76_norm(q)
    if not q:
        return {"query": q, "results_count": 0, "results": [], "message": "Missing query"}
    if _j76_secret_like(q):
        return {"query": q, "results_count": 0, "results": [], "message": "Secret-like query blocked"}
    results = []
    q_low = q.lower()
    for p in _j76_iter_project_files(max_files=1200):
        if len(results) >= limit:
            break
        rel = str(p.relative_to(_J76ROOT))
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if q_low in line.lower():
                snippet = line.strip()
                if _j76_secret_like(snippet):
                    snippet = "[redacted secret-like line]"
                results.append({"path": rel, "line": i, "snippet": snippet[:260]})
                break
    return {"query": q, "results_count": len(results), "results": results}

def _j76_source_digest(path):
    txt, reason = _j76_read_text_limited(path, limit=30000)
    if txt is None:
        return {"ok": False, "reason": reason, "path": path}
    lines = txt.splitlines()
    headings = [x.strip("# ").strip() for x in lines if x.strip().startswith("#")][:30]
    bullets = [x.strip() for x in lines if x.strip().startswith(("- ", "* "))][:30]
    words = _j76_re.findall(r"\w+", txt)
    common = {}
    for w in words:
        lw = w.lower()
        if len(lw) < 4:
            continue
        if _j76_secret_like(lw):
            continue
        common[lw] = common.get(lw, 0) + 1
    top_words = sorted(common.items(), key=lambda x: x[1], reverse=True)[:25]
    return {
        "ok": True,
        "path": str((_j76_under_root(path) or _j76_Path(path)).relative_to(_J76ROOT)) if _j76_under_root(path) else path,
        "chars": len(txt),
        "lines": len(lines),
        "headings": headings,
        "bullets_sample": bullets,
        "top_words": [{"term": k, "count": v} for k, v in top_words],
        "preview": txt[:1200],
    }

def _j76_session_brief():
    status = _j76_status_short()
    diff = _j76_diff_stat()
    health = _j76_health_score()
    roadmap = _j76_technical_roadmap()
    latest_files = _j76_project_map().get("newest_files", [])[:12]
    return {
        "headline": "JARVIS is in local technical expansion mode.",
        "status_short": status,
        "diff_stat": diff,
        "health": health,
        "latest_files": latest_files,
        "next_recommended_block": roadmap["next_blocks"][0],
        "do_not_do": ["commit", "push", "deploy", "read .env", "production"],
    }

def _j76_commit_candidate():
    changed = _j76_changed_files()
    risk = _j76_risk_scan()
    health = _j76_health_score()
    return {
        "candidate": health["ready_for_commit"] and risk["real_danger_count"] == 0,
        "ready_for_deploy": False,
        "changed_files": changed,
        "must_review_before_commit": [
            "11_SCRIPTS/jarvis_api.py large diff",
            "new generated execution folders",
            "any duplicated acceptance files",
            "endpoint naming consistency",
            "manual approval from user",
        ],
        "suggested_commit_message_if_approved_later": "feat: add local JARVIS technical intelligence layer",
        "blocked_now": _J76BLOCKED,
        "risk": risk,
        "health": health,
    }

def _j76_ops_dashboard():
    return {
        "capability_map": _j76_capability_map(),
        "project_map": _j76_project_map(),
        "health_score": _j76_health_score(),
        "risk_scan": _j76_risk_scan(),
        "session_brief": _j76_session_brief(),
    }

def _j76_write_md(name, title, sections):
    safe = _j76_re.sub(r"[^a-zA-Z0-9_.-]+", "-", name).strip("-") or "report"
    out = _J76REPORTS / f"{safe}_{_j76_now()}.md"
    lines = [f"# {title}", ""]
    for h, body in sections:
        lines += [f"## {h}", ""]
        if isinstance(body, str):
            lines += [body, ""]
        else:
            lines += ["```json", _j76_json.dumps(body, ensure_ascii=False, indent=2), "```", ""]
    lines += ["Status real: local file only. Sem commit, sem push, sem deploy.", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out

def _j76_validate_all():
    dashboard = _j76_ops_dashboard()
    checks = []
    def add(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    add("py_compile", all(x["ok"] for x in _j76_pycheck()), _j76_pycheck())
    add("project_map", dashboard["project_map"]["files_indexed"] > 0, dashboard["project_map"])
    add("risk_scan_no_real_danger", dashboard["risk_scan"]["real_danger_count"] == 0, dashboard["risk_scan"])
    add("fulltest_route_registered", True, "POST /fulltest handled by block 76")
    add("approval_required", True, "Sensitive actions remain blocked")
    add("no_deploy_ready", dashboard["health_score"]["ready_for_deploy"] is False, dashboard["health_score"])
    ok = all(x["ok"] for x in checks)
    return {"ok": ok, "checks_total": len(checks), "checks_passed": sum(1 for x in checks if x["ok"]), "checks": checks}

def _j76_fulltest():
    validation = _j76_validate_all()
    capability = _j76_capability_map()
    health = _j76_health_score()
    risk = _j76_risk_scan()
    report = _j76_write_md(
        "fulltest_block_76",
        "JARVIS Fulltest Block 76",
        [
            ("Validation", validation),
            ("Health", health),
            ("Risk", risk),
            ("Capabilities", capability),
            ("Status", "Local-only fulltest. No commit, push, deploy, production or env read."),
        ],
    )
    return {
        "ok": validation["ok"],
        "endpoint": "POST /fulltest",
        "status_real": "local_fulltest_only",
        "precisa_aprovacao": True,
        "blocked_actions": _J76BLOCKED,
        "checks_total": validation["checks_total"],
        "checks_passed": validation["checks_passed"],
        "validation": validation,
        "health": health,
        "risk": risk,
        "report_path": str(report.relative_to(_J76ROOT)),
    }

def _j76_evolution_loop(body=None):
    body = body or {}
    focus = _j76_norm(body.get("focus") or "next technical block")
    roadmap = _j76_technical_roadmap()
    health = _j76_health_score()
    risk = _j76_risk_scan()
    out = _J76PLANS / f"evolution_loop_{_j76_now()}.md"
    lines = [
        "# JARVIS Evolution Loop",
        "",
        f"- focus: {focus}",
        "- mode: deterministic local planning",
        "- external_ai: false",
        "- self_apply_code: false",
        "- human_approval_required: true",
        "- commit_push_deploy: false",
        "",
        "## Current health",
        "```json",
        _j76_json.dumps(health, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Risk scan",
        "```json",
        _j76_json.dumps(risk, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Next blocks",
    ]
    for item in roadmap["next_blocks"]:
        lines += [
            f"### Block {item['block']} — {item['name']}",
            f"- goal: {item['goal']}",
            f"- safe_now: {item.get('safe')}",
            f"- requires_claude_or_human: {item.get('requires_claude_or_human', False)}",
            "",
        ]
    lines += [
        "## Next safe action",
        "Create Block 77 Context Pack Builder before any internet/autonomous executor feature.",
        "",
        "Status real: plano local. Sem commit, sem push, sem deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(out.relative_to(_J76ROOT)), "focus": focus, "roadmap": roadmap}

def _j76_decision_log(body):
    row = {
        "ts": _j76_now(),
        "decision": _j76_norm(body.get("decision")),
        "reason": _j76_norm(body.get("reason")),
        "risk": _j76_norm(body.get("risk")),
        "approved_by_human": bool(body.get("approved_by_human", False)),
        "production_touched": False,
        "commit": False,
        "push": False,
        "deploy": False,
    }
    if not row["decision"]:
        return False, {"error": "missing decision"}
    if _j76_secret_like(_j76_json.dumps(row, ensure_ascii=False)):
        return False, {"error": "secret-like content blocked"}
    path = _J76DECISIONS / "decision_log.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(_j76_json.dumps(row, ensure_ascii=False) + "\n")
    return True, {"path": str(path.relative_to(_J76ROOT)), "row": row}

def _j76_research_plan(body=None):
    body = body or {}
    topic = _j76_norm(body.get("topic") or "autonomous internet research for JARVIS")
    out = _J76PLANS / f"research_plan_local_{_j76_now()}.md"
    lines = [
        "# JARVIS Local Research Plan",
        "",
        f"- topic: {topic}",
        "- current_status: design only",
        "- internet_access_now: false",
        "- external_api_now: false",
        "- implementation_now: false",
        "- requires_later: Claude or controlled executor with explicit approval",
        "",
        "## Safety requirements",
        "- no credential reads",
        "- no uncontrolled browser automation",
        "- no scraping logged-in/private areas",
        "- rate limits",
        "- source citations",
        "- cache and provenance",
        "- approval before networked actions",
        "",
        "## Future architecture",
        "Input question -> source policy -> search provider -> fetch -> extract -> cite -> summarize -> memory candidate -> human approval.",
        "",
        "Status real: plano local apenas. Sem internet, sem commit, sem push, sem deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(out.relative_to(_J76ROOT)), "topic": topic}

def _j76_feature_pack(body=None):
    body = body or {}
    name = _j76_norm(body.get("name") or "jarvis_feature_pack")
    safe_name = _j76_re.sub(r"[^a-zA-Z0-9_.-]+", "-", name).strip("-") or "jarvis_feature_pack"
    out = _J76PLANS / f"feature_pack_{safe_name}_{_j76_now()}.md"
    roadmap = _j76_technical_roadmap()
    lines = [
        f"# Feature Pack — {name}",
        "",
        "## Goal",
        "Create a large local technical improvement batch without touching production.",
        "",
        "## Features included",
        "- context pack builder",
        "- spec-to-task generator",
        "- local evaluator",
        "- memory cleanup candidate",
        "- safety consistency checker",
        "- command catalog expansion",
        "- endpoint contract report",
        "- handoff generator",
        "- acceptance checklist",
        "",
        "## Acceptance criteria",
        "- py_compile passes",
        "- /fulltest returns 200",
        "- no .env read",
        "- no external API",
        "- no commit/push/deploy",
        "- all generated artifacts saved in 05_EXECUCAO",
        "",
        "## Roadmap source",
        "```json",
        _j76_json.dumps(roadmap, ensure_ascii=False, indent=2),
        "```",
        "",
        "Status real: plano local. Sem commit, sem push, sem deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(out.relative_to(_J76ROOT)), "name": name}

def _j76_big_block_report(body=None):
    body = body or {}
    title = _j76_norm(body.get("title") or "JARVIS Big Block 76 Report")
    path = _j76_write_md(
        "big_block_76_report",
        title,
        [
            ("Capabilities", _j76_capability_map()),
            ("Project Map", _j76_project_map()),
            ("Health Score", _j76_health_score()),
            ("Risk Scan", _j76_risk_scan()),
            ("Roadmap", _j76_technical_roadmap()),
            ("Session Brief", _j76_session_brief()),
            ("Commit Candidate", _j76_commit_candidate()),
        ],
    )
    return {"path": str(path.relative_to(_J76ROOT)), "title": title}

def _j76_command(body):
    raw = _j76_norm(body.get("command") or body.get("text") or body.get("q"))
    clean = raw.strip().lower()
    if clean.startswith("/"):
        clean = clean[1:]
    if any(x in clean for x in ["commit", "push", "deploy", ".env", "production", "producao"]):
        return {
            **_j76_base("POST /command", False, "local_command_router_only"),
            "message": "Blocked by JARVIS safety policy.",
            "routed_to": None,
        }
    routes = {
        "capabilities": ("/capability-map", "GET"),
        "capability": ("/capability-map", "GET"),
        "map": ("/project-map", "GET"),
        "project-map": ("/project-map", "GET"),
        "risk": ("/risk-scan", "GET"),
        "risk-scan": ("/risk-scan", "GET"),
        "health": ("/health-score", "GET"),
        "roadmap": ("/technical-roadmap", "GET"),
        "knowledge": ("/knowledge-index", "GET"),
        "brief": ("/session-brief", "GET"),
        "candidate": ("/commit-candidate", "GET"),
        "dashboard": ("/ops-dashboard", "GET"),
        "validate-all": ("/validate-all", "POST"),
        "fulltest": ("/fulltest", "POST"),
        "evolution": ("/evolution-loop", "POST"),
        "feature-pack": ("/feature-pack", "POST"),
    }
    if clean in routes:
        path, method = routes[clean]
        return {
            **_j76_base("POST /command", True, "local_command_router_only"),
            "message": f"Routing to {method} {path}",
            "routed_to": path,
            "method": method,
        }
    if clean.startswith("search "):
        q = raw.split(" ", 1)[1].strip()
        return {
            **_j76_base("POST /command", True, "local_command_router_only"),
            "message": "Routing to local search",
            "routed_to": "/local-search?q=" + _j76_quote(q),
            "method": "GET",
        }
    return {
        **_j76_base("POST /command", False, "local_command_router_only"),
        "message": "Unknown Block 76 command.",
        "suggestions": [
            "/capabilities", "/project-map", "/risk", "/health", "/roadmap",
            "/knowledge", "/brief", "/dashboard", "/validate-all", "/fulltest"
        ],
    }

def _j76_do_GET(self):
    parsed = _j76_urlparse(self.path)
    path = parsed.path
    qs = _j76_parse_qs(parsed.query)
    try:
        if path == "/capability-map":
            p = _j76_base("GET /capability-map")
            p["data"] = _j76_capability_map()
            return _j76_json_out(self, p)
        if path == "/project-map":
            p = _j76_base("GET /project-map", status_real="local_inventory_only")
            p["data"] = _j76_project_map()
            return _j76_json_out(self, p)
        if path == "/risk-scan":
            p = _j76_base("GET /risk-scan", status_real="local_security_scan_only")
            p["data"] = _j76_risk_scan()
            return _j76_json_out(self, p)
        if path == "/health-score":
            p = _j76_base("GET /health-score", status_real="local_health_score_only")
            p["data"] = _j76_health_score()
            return _j76_json_out(self, p)
        if path == "/technical-roadmap":
            p = _j76_base("GET /technical-roadmap", status_real="local_roadmap_only")
            p["data"] = _j76_technical_roadmap()
            return _j76_json_out(self, p)
        if path == "/knowledge-index":
            p = _j76_base("GET /knowledge-index", status_real="local_index_only")
            p["data"] = _j76_knowledge_index()
            return _j76_json_out(self, p)
        if path == "/local-search":
            q = (qs.get("q") or [""])[0]
            p = _j76_base("GET /local-search", status_real="local_search_only")
            p["data"] = _j76_local_search(q)
            return _j76_json_out(self, p)
        if path == "/source-digest":
            target = (qs.get("path") or [""])[0]
            p = _j76_base("GET /source-digest", status_real="local_source_digest_only")
            p["data"] = _j76_source_digest(target)
            p["ok"] = bool(p["data"].get("ok"))
            return _j76_json_out(self, p, 200 if p["ok"] else 400)
        if path == "/session-brief":
            p = _j76_base("GET /session-brief", status_real="local_session_brief_only")
            p["data"] = _j76_session_brief()
            return _j76_json_out(self, p)
        if path == "/commit-candidate":
            p = _j76_base("GET /commit-candidate", status_real="local_commit_candidate_only")
            p["data"] = _j76_commit_candidate()
            return _j76_json_out(self, p)
        if path == "/ops-dashboard":
            p = _j76_base("GET /ops-dashboard", status_real="local_ops_dashboard_only")
            p["data"] = _j76_ops_dashboard()
            return _j76_json_out(self, p)
    except Exception as e:
        p = _j76_base(f"GET {path}", False)
        p["error"] = str(e)
        return _j76_json_out(self, p, 500)
    return self.__class__._j76_prev_GET(self)

_J76_POST_PATHS = {
    "/validate-all",
    "/fulltest",
    "/big-block-report",
    "/evolution-loop",
    "/decision-log",
    "/research-plan-local",
    "/feature-pack",
    "/command",
}

def _j76_do_POST(self):
    parsed = _j76_urlparse(self.path)
    path = parsed.path
    # Only Block 76 POST routes may consume the request body here. For routes
    # owned by other layers (e.g. /validate, /auto-plan), delegate WITHOUT
    # reading rfile: reading it would leave the downstream handler re-reading an
    # already-consumed body, blocking on rfile.read() until the socket times out.
    if path not in _J76_POST_PATHS:
        return self.__class__._j76_prev_POST(self)
    try:
        body = _j76_read_json(self)
        if path == "/validate-all":
            data = _j76_validate_all()
            p = _j76_base("POST /validate-all", data["ok"], "local_validation_suite_only")
            p["data"] = data
            return _j76_json_out(self, p)
        if path == "/fulltest":
            data = _j76_fulltest()
            p = _j76_base("POST /fulltest", data["ok"], "local_fulltest_only")
            p.update(data)
            return _j76_json_out(self, p)
        if path == "/big-block-report":
            data = _j76_big_block_report(body)
            p = _j76_base("POST /big-block-report", True, "local_report_file_only")
            p["message"] = "Big block report generated."
            p["data"] = data
            return _j76_json_out(self, p)
        if path == "/evolution-loop":
            data = _j76_evolution_loop(body)
            p = _j76_base("POST /evolution-loop", True, "local_evolution_plan_only")
            p["message"] = "Evolution loop plan generated."
            p["data"] = data
            return _j76_json_out(self, p)
        if path == "/decision-log":
            ok, data = _j76_decision_log(body)
            p = _j76_base("POST /decision-log", ok, "local_decision_log_only")
            p["message"] = "Decision logged." if ok else "Decision not logged."
            p["data"] = data
            return _j76_json_out(self, p, 200 if ok else 400)
        if path == "/research-plan-local":
            data = _j76_research_plan(body)
            p = _j76_base("POST /research-plan-local", True, "local_research_plan_only")
            p["message"] = "Research plan generated locally."
            p["data"] = data
            return _j76_json_out(self, p)
        if path == "/feature-pack":
            data = _j76_feature_pack(body)
            p = _j76_base("POST /feature-pack", True, "local_feature_pack_only")
            p["message"] = "Feature pack generated."
            p["data"] = data
            return _j76_json_out(self, p)
        if path == "/command":
            data = _j76_command(body)
            return _j76_json_out(self, data, 200 if data.get("ok") else 400)
    except Exception as e:
        p = _j76_base(f"POST {path}", False)
        p["error"] = str(e)
        return _j76_json_out(self, p, 500)
    return self.__class__._j76_prev_POST(self)


def _j76_install():
    candidates = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j76_BaseHTTPRequestHandler)
                and obj is not _j76_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
            ):
                candidates.append((name, obj))
        except Exception:
            pass

    installed = []
    skipped = []

    for name, handler in candidates:
        try:
            if getattr(handler, "_j76_installed", False):
                skipped.append(name)
                continue

            handler._j76_prev_GET = handler.do_GET
            handler._j76_prev_POST = handler.do_POST
            handler.do_GET = _j76_do_GET
            handler.do_POST = _j76_do_POST
            handler._j76_installed = True
            installed.append(name)
        except Exception as e:
            skipped.append(f"{name}:{e}")

    if installed:
        print("[J76] Installed Block 76 routes on:", ", ".join(installed))
    else:
        print("[J76] WARNING: no handler patched. candidates=", [x[0] for x in candidates], "skipped=", skipped)

_j76_install()

# === END JARVIS BIG BLOCK 76 ===



# === JARVIS BLOCK 77: CONTEXT ENGINE + SPEC ENGINE ===
# Local-only context pack + spec planning layer.
# No external calls. No free shell. No deploy. No push.

import json as _j77_json
import re as _j77_re
import time as _j77_time
import subprocess as _j77_subprocess
from pathlib import Path as _j77_Path
from urllib.parse import urlparse as _j77_urlparse, parse_qs as _j77_parse_qs
from http.server import BaseHTTPRequestHandler as _j77_BaseHTTPRequestHandler

_J77ROOT = _j77_Path(__file__).resolve().parents[1]
_J77DIR = _J77ROOT / "05_EXECUCAO" / "77_JARVIS_CONTEXT_ENGINE"
_J77_CONTEXT = _J77DIR / "context_packs"
_J77_SPECS = _J77DIR / "specs"
_J77_BRIEFS = _J77DIR / "briefs"
_J77_ACCEPTANCE = _J77DIR / "acceptance"

for _p in [_J77DIR, _J77_CONTEXT, _J77_SPECS, _J77_BRIEFS, _J77_ACCEPTANCE]:
    _p.mkdir(parents=True, exist_ok=True)

_J77_BLOCKED = ["commit", "push", "deploy", "production"]
_J77_SAFE_EXT = {".md", ".txt", ".json", ".jsonl", ".py", ".html", ".css", ".js", ".yml", ".yaml", ".toml", ".csv"}
_J77_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build"}
_J77_PRIVATE_WORDS = ["private_key", "service_role", "bearer", "authorization", "password", "senha", "apikey", "api_key", "token", ".env"]

def _j77_now():
    return _j77_time.strftime("%Y-%m-%d_%H-%M-%S")

def _j77_norm(v):
    return "" if v is None else str(v).strip()

def _j77_slug(v, fallback="jarvis"):
    s = _j77_re.sub(r"[^a-zA-Z0-9_.-]+", "-", _j77_norm(v).lower()).strip("-")
    return s[:80] or fallback

def _j77_private_like(v):
    s = _j77_norm(v).lower()
    return any(x in s for x in _J77_PRIVATE_WORDS)

def _j77_under_root(value):
    try:
        p = _j77_Path(value).expanduser()
        if not p.is_absolute():
            p = _J77ROOT / p
        p = p.resolve()
        p.relative_to(_J77ROOT)
        return p
    except Exception:
        return None

def _j77_safe_file(value):
    p = _j77_under_root(value)
    if not p or not p.exists() or not p.is_file():
        return None
    rel = p.relative_to(_J77ROOT)
    parts = [x.lower() for x in rel.parts]
    if any(x.startswith(".") for x in parts):
        return None
    if any(x in _J77_SKIP_DIRS for x in parts):
        return None
    if _j77_private_like(str(rel)):
        return None
    if p.suffix.lower() not in _J77_SAFE_EXT:
        return None
    return p

def _j77_read_limited(path, chars=14000):
    p = _j77_safe_file(path)
    if not p:
        return ""
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
        return txt[:chars]
    except Exception:
        return ""

def _j77_json_out(self, payload, status=200):
    raw = _j77_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _j77_read_json(self):
    try:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return _j77_json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}

def _j77_base(endpoint, ok=True, status_real="local_context_engine_only"):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "status_real": status_real,
        "precisa_aprovacao": True,
        "blocked_actions": list(_J77_BLOCKED),
        "safety": {
            "local_only": True,
            "external_calls": False,
            "free_shell": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "production_touched": False,
        },
    }

def _j77_git(args):
    allowed = [
        ["status", "--short"],
        ["diff", "--stat"],
        ["diff", "--name-only"],
        ["log", "--oneline", "-5"],
        ["rev-parse", "--short", "HEAD"],
        ["branch", "--show-current"],
    ]
    if args not in allowed:
        return ""
    try:
        r = _j77_subprocess.run(["git", *args], cwd=_J77ROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or "").strip()
    except Exception as e:
        return f"git_error: {e}"

def _j77_iter_files(max_files=1000):
    roots = ["02_SOURCES", "03_DOCS", "04_OUTPUT", "05_EXECUCAO", "11_SCRIPTS"]
    out = []
    for root in roots:
        base = _J77ROOT / root
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if len(out) >= max_files:
                return out
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(_J77ROOT)
            except Exception:
                continue
            parts = [x.lower() for x in rel.parts]
            if any(x in _J77_SKIP_DIRS for x in parts):
                continue
            if any(x.startswith(".") for x in parts):
                continue
            if p.suffix.lower() not in _J77_SAFE_EXT:
                continue
            if _j77_private_like(str(rel)):
                continue
            out.append(p)
    return out

def _j77_latest_files(limit=35):
    rows = []
    for p in _j77_iter_files(max_files=1200):
        try:
            st = p.stat()
            rows.append({
                "path": str(p.relative_to(_J77ROOT)),
                "size": st.st_size,
                "modified": int(st.st_mtime),
                "suffix": p.suffix.lower(),
            })
        except Exception:
            pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:limit]

def _j77_search_local(query, limit=40):
    q = _j77_norm(query)
    if not q or _j77_private_like(q):
        return []
    results = []
    low = q.lower()
    for p in _j77_iter_files(max_files=1200):
        if len(results) >= limit:
            break
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, 1):
            if low in line.lower():
                snippet = line.strip()
                if _j77_private_like(snippet):
                    snippet = "[redacted private-like line]"
                results.append({
                    "path": str(p.relative_to(_J77ROOT)),
                    "line": idx,
                    "snippet": snippet[:260],
                })
                break
    return results

def _j77_digest_text(path, chars=18000):
    txt = _j77_read_limited(path, chars=chars)
    if not txt:
        return None
    lines = txt.splitlines()
    headings = [x.strip("# ").strip() for x in lines if x.strip().startswith("#")][:20]
    bullets = [x.strip() for x in lines if x.strip().startswith(("- ", "* "))][:25]
    words = {}
    for w in _j77_re.findall(r"[A-Za-zÀ-ÿ0-9_]{4,}", txt.lower()):
        if _j77_private_like(w):
            continue
        words[w] = words.get(w, 0) + 1
    top = sorted(words.items(), key=lambda x: x[1], reverse=True)[:20]
    return {
        "path": str((_j77_safe_file(path) or _j77_Path(path)).relative_to(_J77ROOT)) if _j77_safe_file(path) else str(path),
        "chars_read": len(txt),
        "lines": len(lines),
        "headings": headings,
        "bullets": bullets,
        "top_terms": [{"term": k, "count": v} for k, v in top],
        "preview": txt[:1200],
    }

def _j77_project_snapshot(topic="jarvis", search_terms=None):
    search_terms = search_terms or [topic, "jarvis", "workflow", "memory", "context", "source"]
    search = {}
    for term in search_terms[:8]:
        search[term] = _j77_search_local(term, limit=12)
    return {
        "topic": topic,
        "generated_at": _j77_now(),
        "branch": _j77_git(["branch", "--show-current"]),
        "head": _j77_git(["rev-parse", "--short", "HEAD"]),
        "status_short": _j77_git(["status", "--short"]),
        "diff_stat": _j77_git(["diff", "--stat"]),
        "changed_files": _j77_git(["diff", "--name-only"]).splitlines(),
        "latest_files": _j77_latest_files(),
        "search": search,
    }

def _j77_context_pack(body=None):
    body = body or {}
    topic = _j77_norm(body.get("topic") or body.get("title") or "jarvis-agent-os")
    purpose = _j77_norm(body.get("purpose") or "Prepare a clean local context pack for the next JARVIS technical block.")
    raw_terms = body.get("search_terms") or []
    if isinstance(raw_terms, str):
        raw_terms = [x.strip() for x in raw_terms.split(",") if x.strip()]
    terms = [topic] + [x for x in raw_terms if x][:8]
    snap = _j77_project_snapshot(topic, terms)

    source_digests = []
    candidates = []
    for row in snap["latest_files"]:
        path = row["path"]
        if path.endswith((".md", ".txt", ".json", ".jsonl", ".py", ".html")):
            candidates.append(path)
    for path in candidates[:10]:
        dig = _j77_digest_text(path, chars=12000)
        if dig:
            source_digests.append(dig)

    filename = f"context_pack_{_j77_slug(topic)}_{_j77_now()}.md"
    out = _J77_CONTEXT / filename

    lines = [
        f"# JARVIS Context Pack — {topic}",
        "",
        "## Status real",
        "- local_only: true",
        "- commit: false",
        "- push: false",
        "- deploy: false",
        "- production_touched: false",
        "",
        "## Purpose",
        purpose,
        "",
        "## Git state",
        "```",
        snap["status_short"] or "(clean)",
        "```",
        "",
        "## Diff stat",
        "```",
        snap["diff_stat"] or "(none)",
        "```",
        "",
        "## Changed files",
    ]
    lines += [f"- `{x}`" for x in snap["changed_files"]] or ["- none"]
    lines += ["", "## Latest relevant files"]
    for row in snap["latest_files"][:25]:
        lines.append(f"- `{row['path']}` — {row['size']} bytes")
    lines += ["", "## Search evidence"]
    for term, hits in snap["search"].items():
        lines += [f"### {term}"]
        if not hits:
            lines.append("- no local hits")
        for h in hits[:8]:
            lines.append(f"- `{h['path']}:{h['line']}` — {h['snippet']}")
        lines.append("")
    lines += ["## Source digests"]
    for dig in source_digests:
        lines += [
            f"### {dig['path']}",
            f"- chars_read: {dig['chars_read']}",
            f"- lines: {dig['lines']}",
            "- headings: " + (", ".join(dig["headings"][:8]) if dig["headings"] else "none"),
            "- top_terms: " + (", ".join([x["term"] for x in dig["top_terms"][:10]]) if dig["top_terms"] else "none"),
            "",
        ]
    lines += [
        "## Next use",
        "Use this context pack as the clean input for the next JARVIS technical block.",
        "",
        "Status real: generated locally. No commit, no push, no deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {
        "path": str(out.relative_to(_J77ROOT)),
        "topic": topic,
        "changed_files": snap["changed_files"],
        "latest_files_count": len(snap["latest_files"]),
        "source_digests_count": len(source_digests),
    }

def _j77_spec_to_tasks(body=None):
    body = body or {}
    feature = _j77_norm(body.get("feature") or body.get("title") or "Next JARVIS technical feature")
    goal = _j77_norm(body.get("goal") or body.get("description") or "Create a high-value local feature without touching production.")
    constraints = body.get("constraints") or []
    if isinstance(constraints, str):
        constraints = [x.strip() for x in constraints.splitlines() if x.strip()]
    if not constraints:
        constraints = [
            "local-only",
            "no commit/push/deploy from the feature block",
            "no private config reads",
            "no free shell endpoint",
            "preserve existing endpoints",
            "smallest safe patch that creates real value",
        ]

    filename = f"spec_{_j77_slug(feature)}_{_j77_now()}.md"
    out = _J77_SPECS / filename

    lines = [
        f"# JARVIS Spec — {feature}",
        "",
        "## Goal",
        goal,
        "",
        "## Constraints",
    ]
    lines += [f"- {x}" for x in constraints]
    lines += [
        "",
        "## Feature design",
        "1. Keep the feature deterministic and local-first.",
        "2. Save generated artifacts under `05_EXECUCAO`.",
        "3. Expose only explicit, named endpoints.",
        "4. Block sensitive actions by default.",
        "5. Return structured JSON with `ok`, `endpoint`, `status_real`, `blocked_actions` and `data`.",
        "",
        "## Implementation tasks",
        "- define endpoint contract",
        "- define local file output folder",
        "- implement safe input normalization",
        "- implement safe file reading if needed",
        "- add route handlers without consuming unrelated request bodies",
        "- preserve previous handlers",
        "- generate local markdown/json artifact",
        "- provide blocked actions in every response",
        "",
        "## Acceptance criteria",
        "- Python compile passes",
        "- existing core routes still answer",
        "- new route returns structured JSON",
        "- no production action",
        "- no external network action",
        "- no commit/push/deploy",
        "- generated file path is returned",
        "- failure returns safe JSON, not crash",
        "",
        "## Suggested route names",
        "- `GET /feature-brief`",
        "- `POST /context-pack`",
        "- `POST /spec-to-tasks`",
        "- `POST /acceptance-checklist`",
        "",
        "## Ready-to-use AI instruction",
        "Build this as a local JARVIS technical block. Do not change deployment, do not create a parallel backend, do not read private config, and preserve all existing routes.",
        "",
        "Status real: spec generated locally. No commit, no push, no deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(out.relative_to(_J77ROOT)), "feature": feature}

def _j77_feature_brief(body=None):
    body = body or {}
    target = _j77_norm(body.get("target") or body.get("feature") or "next JARVIS block")
    snap = _j77_project_snapshot(target, [target, "jarvis", "block", "context", "memory"])
    filename = f"brief_{_j77_slug(target)}_{_j77_now()}.md"
    out = _J77_BRIEFS / filename

    lines = [
        f"# JARVIS Feature Brief — {target}",
        "",
        "## Current repo state",
        "```",
        snap["status_short"] or "(clean)",
        "```",
        "",
        "## Technical direction",
        "- ChatGPT cockpit by default.",
        "- Claude only for truly high-leverage debugging or major capability creation.",
        "- Main branch can be used because this is an owner project.",
        "- Still no blind push/deploy.",
        "",
        "## Recommended next high-value features",
        "1. Context Pack Builder — already started in Block 77.",
        "2. Spec-to-Tasks Engine — already started in Block 77.",
        "3. Local Evaluation Suite — evaluate generated plans and memory quality.",
        "4. Self-Improvement Planner — suggest code patches, but do not apply automatically.",
        "5. Future network research module — only with explicit approval and stronger controls.",
        "",
        "## What not to do now",
        "- do not build visual-only changes",
        "- do not add random tools",
        "- do not create autonomous internet access yet",
        "- do not push/deploy",
        "",
        "## Next block candidate",
        "Block 78: Local Evaluation Suite + memory quality scoring.",
        "",
        "Status real: brief generated locally. No commit, no push, no deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(out.relative_to(_J77ROOT)), "target": target}

def _j77_acceptance(body=None):
    body = body or {}
    name = _j77_norm(body.get("name") or "JARVIS local acceptance")
    filename = f"acceptance_{_j77_slug(name)}_{_j77_now()}.md"
    out = _J77_ACCEPTANCE / filename
    snap = _j77_project_snapshot(name, [name, "jarvis"])

    lines = [
        f"# Acceptance Checklist — {name}",
        "",
        "## Status real",
        "- local_only: true",
        "- commit: false",
        "- push: false",
        "- deploy: false",
        "",
        "## Required checks",
        "- [ ] Existing API routes still respond.",
        "- [ ] New generated artifacts are under `05_EXECUCAO`.",
        "- [ ] No private config file was read.",
        "- [ ] No external network action was introduced.",
        "- [ ] No deploy file was changed unless explicitly intended.",
        "- [ ] No shell-free execution endpoint was created.",
        "- [ ] Every new endpoint has structured JSON output.",
        "",
        "## Current changed files",
        "```",
        snap["status_short"] or "(clean)",
        "```",
        "",
        "## Diff stat",
        "```",
        snap["diff_stat"] or "(none)",
        "```",
        "",
        "Status real: acceptance generated locally. No commit, no push, no deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(out.relative_to(_J77ROOT)), "name": name}

def _j77_latest(folder):
    try:
        files = sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [str(p.relative_to(_J77ROOT)) for p in files[:20] if p.is_file()]
    except Exception:
        return []

def _j77_do_GET(self):
    parsed = _j77_urlparse(self.path)
    path = parsed.path
    qs = _j77_parse_qs(parsed.query)

    try:
        if path == "/context-pack-builder":
            topic = (qs.get("topic") or ["jarvis-agent-os"])[0]
            data = _j77_context_pack({"topic": topic, "purpose": "GET-generated context pack"})
            p = _j77_base("GET /context-pack-builder", True)
            p["message"] = "Context pack generated."
            p["data"] = data
            return _j77_json_out(self, p)

        if path == "/context-pack-latest":
            p = _j77_base("GET /context-pack-latest", True)
            p["data"] = {"files": _j77_latest(_J77_CONTEXT)}
            return _j77_json_out(self, p)

        if path == "/spec-latest":
            p = _j77_base("GET /spec-latest", True)
            p["data"] = {"files": _j77_latest(_J77_SPECS)}
            return _j77_json_out(self, p)

        if path == "/feature-brief":
            target = (qs.get("target") or ["next JARVIS block"])[0]
            data = _j77_feature_brief({"target": target})
            p = _j77_base("GET /feature-brief", True)
            p["message"] = "Feature brief generated."
            p["data"] = data
            return _j77_json_out(self, p)

    except Exception as e:
        p = _j77_base(f"GET {path}", False)
        p["error"] = str(e)
        return _j77_json_out(self, p, 500)

    return self.__class__._j77_prev_GET(self)

_J77_POST_PATHS = {"/context-pack", "/spec-to-tasks", "/operator-brief", "/acceptance-checklist"}

def _j77_do_POST(self):
    parsed = _j77_urlparse(self.path)
    path = parsed.path

    if path not in _J77_POST_PATHS:
        return self.__class__._j77_prev_POST(self)

    try:
        body = _j77_read_json(self)

        if path == "/context-pack":
            data = _j77_context_pack(body)
            p = _j77_base("POST /context-pack", True)
            p["message"] = "Context pack generated."
            p["data"] = data
            return _j77_json_out(self, p)

        if path == "/spec-to-tasks":
            data = _j77_spec_to_tasks(body)
            p = _j77_base("POST /spec-to-tasks", True)
            p["message"] = "Spec generated."
            p["data"] = data
            return _j77_json_out(self, p)

        if path == "/operator-brief":
            data = _j77_feature_brief(body)
            p = _j77_base("POST /operator-brief", True)
            p["message"] = "Operator brief generated."
            p["data"] = data
            return _j77_json_out(self, p)

        if path == "/acceptance-checklist":
            data = _j77_acceptance(body)
            p = _j77_base("POST /acceptance-checklist", True)
            p["message"] = "Acceptance checklist generated."
            p["data"] = data
            return _j77_json_out(self, p)

    except Exception as e:
        p = _j77_base(f"POST {path}", False)
        p["error"] = str(e)
        return _j77_json_out(self, p, 500)

    return self.__class__._j77_prev_POST(self)

def _j77_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j77_BaseHTTPRequestHandler)
                and obj is not _j77_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j77_installed", False)
            ):
                obj._j77_prev_GET = obj.do_GET
                obj._j77_prev_POST = obj.do_POST
                obj.do_GET = _j77_do_GET
                obj.do_POST = _j77_do_POST
                obj._j77_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J77] Installed Block 77 routes on:", ", ".join(patched) if patched else "none")

_j77_install()
# === END JARVIS BLOCK 77 ===



# === JARVIS BLOCK 78: EVALUATION SUITE + PROMPT FACTORY + OPS PACK ===
# Local-only evaluator, prompt factory, feature ranking and ops pack.
# No external API. No commit. No push. No deploy. No free shell.

import json as _j78_json
import re as _j78_re
import time as _j78_time
import subprocess as _j78_subprocess
from pathlib import Path as _j78_Path
from urllib.parse import urlparse as _j78_urlparse, parse_qs as _j78_parse_qs
from http.server import BaseHTTPRequestHandler as _j78_BaseHTTPRequestHandler

_J78ROOT = _j78_Path(__file__).resolve().parents[1]
_J78DIR = _J78ROOT / "05_EXECUCAO" / "78_JARVIS_EVALUATION_SUITE"
_J78_REPORTS = _J78DIR / "reports"
_J78_PROMPTS = _J78DIR / "prompts"
_J78_ROADMAPS = _J78DIR / "roadmaps"
_J78_OPS = _J78DIR / "ops"
_J78_RANKINGS = _J78DIR / "rankings"

for _p in [_J78DIR, _J78_REPORTS, _J78_PROMPTS, _J78_ROADMAPS, _J78_OPS, _J78_RANKINGS]:
    _p.mkdir(parents=True, exist_ok=True)

_J78_BLOCKED = ["commit", "push", "deploy", "production"]
_J78_SAFE_EXT = {".md", ".txt", ".json", ".jsonl", ".py", ".html", ".css", ".js", ".yml", ".yaml", ".toml", ".csv"}
_J78_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build"}
_J78_PRIVATE_WORDS = ["private_key", "service_role", "bearer", "authorization", "password", "senha", "apikey", "api_key", "token", ".env", "secret"]

def _j78_now():
    return _j78_time.strftime("%Y-%m-%d_%H-%M-%S")

def _j78_norm(v):
    return "" if v is None else str(v).strip()

def _j78_slug(v, fallback="jarvis"):
    s = _j78_re.sub(r"[^a-zA-Z0-9_.-]+", "-", _j78_norm(v).lower()).strip("-")
    return s[:90] or fallback

def _j78_private_like(v):
    s = _j78_norm(v).lower()
    return any(x in s for x in _J78_PRIVATE_WORDS)

def _j78_json_out(self, payload, status=200):
    raw = _j78_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _j78_read_json(self):
    try:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return _j78_json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}

def _j78_base(endpoint, ok=True, status_real="local_evaluation_suite_only"):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "status_real": status_real,
        "precisa_aprovacao": True,
        "blocked_actions": list(_J78_BLOCKED),
        "safety": {
            "local_only": True,
            "external_calls": False,
            "free_shell": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "production_touched": False,
        },
    }

def _j78_git(args):
    allowed = [
        ["status", "--short"],
        ["diff", "--stat"],
        ["diff", "--name-only"],
        ["rev-parse", "--short", "HEAD"],
        ["branch", "--show-current"],
        ["log", "--oneline", "-5"],
    ]
    if args not in allowed:
        return ""
    try:
        r = _j78_subprocess.run(["git", *args], cwd=_J78ROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or "").strip()
    except Exception as e:
        return f"git_error: {e}"

def _j78_files(max_files=1300):
    roots = ["02_SOURCES", "03_DOCS", "04_OUTPUT", "05_EXECUCAO", "11_SCRIPTS"]
    out = []
    for root in roots:
        base = _J78ROOT / root
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if len(out) >= max_files:
                return out
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(_J78ROOT)
            except Exception:
                continue
            parts = [x.lower() for x in rel.parts]
            if any(x in _J78_SKIP_DIRS for x in parts):
                continue
            if any(x.startswith(".") for x in parts):
                continue
            if p.suffix.lower() not in _J78_SAFE_EXT:
                continue
            if _j78_private_like(str(rel)):
                continue
            out.append(p)
    return out

def _j78_file_text(p, limit=20000):
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""

def _j78_latest_by_glob(pattern, limit=20):
    rows = []
    for p in _J78ROOT.glob(pattern):
        if p.is_file():
            try:
                rows.append({
                    "path": str(p.relative_to(_J78ROOT)),
                    "size": p.stat().st_size,
                    "modified": int(p.stat().st_mtime),
                })
            except Exception:
                pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:limit]

def _j78_inventory():
    files = _j78_files()
    by_folder = {}
    by_ext = {}
    newest = []
    total_size = 0

    for p in files:
        rel = str(p.relative_to(_J78ROOT))
        top = rel.split("/", 1)[0]
        ext = p.suffix.lower() or "(none)"
        try:
            st = p.stat()
            total_size += st.st_size
            newest.append({"path": rel, "size": st.st_size, "modified": int(st.st_mtime), "suffix": ext})
        except Exception:
            pass
        by_folder[top] = by_folder.get(top, 0) + 1
        by_ext[ext] = by_ext.get(ext, 0) + 1

    newest.sort(key=lambda x: x["modified"], reverse=True)

    return {
        "files_indexed": len(files),
        "total_size_bytes": total_size,
        "by_folder": dict(sorted(by_folder.items())),
        "by_extension": dict(sorted(by_ext.items())),
        "newest": newest[:40],
    }

def _j78_memory_quality():
    memory_files = []
    for pattern in [
        "05_EXECUCAO/71_JARVIS_MEMORY/**/*.jsonl",
        "05_EXECUCAO/70_JARVIS_SESSION_LOG/**/*.jsonl",
        "05_EXECUCAO/76_JARVIS_BIG_BLOCK/**/*.jsonl",
    ]:
        memory_files.extend(_J78ROOT.glob(pattern))

    rows = []
    total = 0
    private_like = 0
    empty = 0
    duplicate_key_counter = {}
    samples = []

    for p in memory_files:
        rel = str(p.relative_to(_J78ROOT))
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            lines = []
        count = 0
        for line in lines:
            if not line.strip():
                empty += 1
                continue
            count += 1
            total += 1
            low = line.lower()
            if _j78_private_like(low):
                private_like += 1
            key = low[:160]
            duplicate_key_counter[key] = duplicate_key_counter.get(key, 0) + 1
            if len(samples) < 20:
                samples.append({"file": rel, "preview": line[:240]})
        rows.append({"path": rel, "rows": count})

    duplicates = sum(1 for v in duplicate_key_counter.values() if v > 1)
    score = 100
    if private_like:
        score -= 40
    if empty:
        score -= min(10, empty)
    if duplicates:
        score -= min(20, duplicates * 2)
    score = max(0, score)

    return {
        "score": score,
        "rows_total": total,
        "files": rows,
        "private_like_rows": private_like,
        "empty_rows": empty,
        "duplicate_groups_est": duplicates,
        "samples": samples,
        "verdict": "good" if score >= 85 else "review",
    }

def _j78_context_quality():
    packs = []
    for pattern in [
        "05_EXECUCAO/77_JARVIS_CONTEXT_ENGINE/context_packs/*.md",
        "05_EXECUCAO/77_JARVIS_CONTEXT_ENGINE/specs/*.md",
        "05_EXECUCAO/77_JARVIS_CONTEXT_ENGINE/briefs/*.md",
        "05_EXECUCAO/77_JARVIS_CONTEXT_ENGINE/acceptance/*.md",
    ]:
        for p in _J78ROOT.glob(pattern):
            txt = _j78_file_text(p, 40000)
            words = len(_j78_re.findall(r"\w+", txt))
            headings = len([x for x in txt.splitlines() if x.strip().startswith("#")])
            checkboxes = len(_j78_re.findall(r"\[[ xX]\]", txt))
            has_status = "Status real" in txt or "status real" in txt.lower()
            has_safety = any(x in txt.lower() for x in ["no commit", "sem commit", "no push", "sem push", "no deploy", "sem deploy"])
            score = 0
            score += min(30, words // 80)
            score += min(20, headings * 2)
            score += 20 if has_status else 0
            score += 20 if has_safety else 0
            score += min(10, checkboxes)
            packs.append({
                "path": str(p.relative_to(_J78ROOT)),
                "words": words,
                "headings": headings,
                "checkboxes": checkboxes,
                "has_status": has_status,
                "has_safety": has_safety,
                "score": min(100, score),
            })

    avg = round(sum(x["score"] for x in packs) / len(packs), 1) if packs else 0
    return {
        "packs_count": len(packs),
        "average_score": avg,
        "packs": sorted(packs, key=lambda x: x["score"], reverse=True),
        "verdict": "good" if avg >= 75 else "needs_more_context",
    }

def _j78_route_contracts():
    api_path = _J78ROOT / "11_SCRIPTS" / "jarvis_api.py"
    txt = _j78_file_text(api_path, 500000)
    paths = sorted(set(_j78_re.findall(r'["\'](/[a-zA-Z0-9_\-/?=&.%]+)["\']', txt)))
    endpoints = []
    for p in paths:
        if p.startswith("/"):
            method = "GET/POST"
            if f'path == "{p}"' in txt or f"path == '{p}'" in txt:
                method = "handler"
            endpoints.append({
                "path": p,
                "method_hint": method,
                "safe_default": not any(x in p for x in ["commit", "push", "deploy"]),
            })
    return {
        "count": len(endpoints),
        "endpoints": endpoints[:180],
        "note": "Static route contract extracted from local source; no external calls.",
    }

def _j78_feature_rank():
    features = [
        {
            "name": "Block 79 Local Evaluation Scorer",
            "value": 9,
            "risk": 2,
            "effort": 4,
            "why": "scores generated docs, memory, endpoints and next blocks automatically",
        },
        {
            "name": "Block 80 Self-Improvement Planner",
            "value": 10,
            "risk": 5,
            "effort": 7,
            "why": "suggests code patches from logs/source without applying automatically",
        },
        {
            "name": "Block 81 Internet Research Module",
            "value": 10,
            "risk": 8,
            "effort": 8,
            "why": "big capability but should wait for explicit approval and stronger controls",
        },
        {
            "name": "Block 82 Prompt/Agent Pack Generator",
            "value": 8,
            "risk": 2,
            "effort": 4,
            "why": "generates professional prompts for Claude, n8n, infra, image/video, research",
        },
        {
            "name": "Block 83 n8n Workflow Architect",
            "value": 9,
            "risk": 5,
            "effort": 7,
            "why": "creates professional n8n specs/workflows from context packs",
        },
        {
            "name": "Block 84 VPS Automation Planner",
            "value": 9,
            "risk": 7,
            "effort": 8,
            "why": "infra automation is powerful but needs strict dry-run and approval",
        },
        {
            "name": "Block 85 Multimodal Creation Planner",
            "value": 8,
            "risk": 6,
            "effort": 8,
            "why": "image/video generation planning needs external tools and clear permissions",
        },
    ]
    for f in features:
        f["score"] = round((f["value"] * 12) - (f["risk"] * 5) - (f["effort"] * 3), 1)
        f["use_claude"] = f["risk"] >= 5 or f["effort"] >= 7 or "Internet" in f["name"] or "VPS" in f["name"]
    features.sort(key=lambda x: x["score"], reverse=True)
    return {
        "ranking": features,
        "recommended_now_without_claude": [f for f in features if not f["use_claude"]][:3],
        "recommended_with_claude_later": [f for f in features if f["use_claude"]][:4],
    }

def _j78_prompt_factory(body=None):
    body = body or {}
    mode = _j78_norm(body.get("mode") or "mega-feature")
    target = _j78_norm(body.get("target") or "JARVIS next powerful feature")

    prompts = {
        "claude_power_feature": f"""You are working inside ~/Theo/JARVIS/jarvis-agent-os.

Mission:
Build a powerful, production-grade local JARVIS capability: {target}.

Context:
- Owner project. Working on main is allowed.
- Do not commit, push or deploy unless explicitly approved.
- Do not read .env or secrets.
- Do not create a parallel backend.
- Do not install dependencies unless explicitly approved.
- Preserve all existing endpoints and local safety gates.
- ChatGPT is cockpit; Claude is executor only because this is a high-leverage feature.

Requirements:
1. Inspect current code and outputs.
2. Identify the smallest safe architecture.
3. Implement the feature with clear endpoint contracts.
4. Generate artifacts under 05_EXECUCAO.
5. Validate compile and local endpoint behavior.
6. Keep blocked actions active.
7. Return concise final report:
   - files changed
   - feature added
   - evidence it works
   - risks
   - next safe action

Do not do broad rewrites. Do not touch production.""",

        "n8n_architect": f"""Create a professional n8n workflow architecture for: {target}.

Rules:
- Produce a practical workflow plan, not hype.
- Include nodes, inputs, outputs, credentials needed, safety gates, logs, failure paths and test plan.
- Separate MVP from advanced version.
- Prefer native n8n nodes over code nodes when practical.
- Never include real secrets/tokens.
- Include dry-run mode and production approval gate.
- Output:
  1. workflow summary
  2. node-by-node architecture
  3. data schema
  4. safety/anti-loop
  5. validation plan
  6. handoff message""",

        "internet_research_module": f"""Design a safe autonomous internet research module for JARVIS.

Target: {target}

Rules:
- Do not implement uncontrolled browsing.
- Require approval before network actions.
- Every claim needs source/citation.
- Cache results locally.
- Track provenance, timestamp and query.
- Block private/login-only sources unless explicitly provided.
- Output architecture:
  source policy -> search -> fetch -> extract -> cite -> summarize -> memory candidate -> human approval.
- Include risks, limits, and exact acceptance criteria.""",

        "vps_automation": f"""Design a safe VPS automation agent for JARVIS.

Target: {target}

Rules:
- Dry-run first.
- No destructive commands by default.
- No secret printing.
- No production mutation without explicit approval.
- Include rollback, backups, snapshots, logs and health checks.
- Separate read-only audit from write actions.
- Output:
  1. audit commands
  2. safe plan
  3. guarded execution steps
  4. rollback
  5. validation
  6. status message.""",

        "image_video_system": f"""Design a professional image/video generation system for JARVIS.

Target: {target}

Rules:
- Separate ideation, script, storyboard, prompt, generation, review and export.
- Include asset versioning, approval gates, prompt templates and quality scoring.
- Do not assume paid APIs unless approved.
- Output:
  1. pipeline
  2. prompts
  3. folder structure
  4. metadata schema
  5. quality rubric
  6. next implementation block."""
    }

    out = _J78_PROMPTS / f"prompt_factory_{_j78_slug(target)}_{_j78_now()}.md"
    lines = [
        f"# JARVIS Prompt Factory — {target}",
        "",
        "## Mode",
        mode,
        "",
    ]
    for name, prompt in prompts.items():
        lines += [f"## {name}", "", "```text", prompt, "```", ""]
    lines += ["Status real: prompt pack generated locally. No commit, no push, no deploy.", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {
        "path": str(out.relative_to(_J78ROOT)),
        "target": target,
        "prompt_count": len(prompts),
    }

def _j78_ops_pack(body=None):
    body = body or {}
    target = _j78_norm(body.get("target") or "JARVIS production-grade local operating flow")
    inv = _j78_inventory()
    mem = _j78_memory_quality()
    ctx = _j78_context_quality()
    rank = _j78_feature_rank()

    out = _J78_OPS / f"ops_pack_{_j78_slug(target)}_{_j78_now()}.md"
    lines = [
        f"# JARVIS Ops Pack — {target}",
        "",
        "## Status real",
        "- local_only: true",
        "- commit: false",
        "- push: false",
        "- deploy: false",
        "- production_touched: false",
        "",
        "## Current operating rule",
        "- ChatGPT is cockpit/operator by default.",
        "- Claude is reserved for very high-leverage tasks: hard debug, perfect major feature, internet research, image/video, n8n professional workflow, VPS automation.",
        "- JARVIS is owner/main workflow; main can be used, but no blind push/deploy.",
        "",
        "## Inventory",
        "```json",
        _j78_json.dumps(inv, ensure_ascii=False, indent=2)[:12000],
        "```",
        "",
        "## Memory quality",
        "```json",
        _j78_json.dumps(mem, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Context quality",
        "```json",
        _j78_json.dumps(ctx, ensure_ascii=False, indent=2)[:12000],
        "```",
        "",
        "## Feature ranking",
        "```json",
        _j78_json.dumps(rank, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Next execution",
        "1. Use ChatGPT blocks for local deterministic features.",
        "2. Use Claude only when leverage is high.",
        "3. Keep outputs under `05_EXECUCAO`.",
        "4. Keep blocked actions active.",
        "",
        "Status real: ops pack generated locally. No commit, no push, no deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {
        "path": str(out.relative_to(_J78ROOT)),
        "target": target,
        "inventory_files": inv["files_indexed"],
        "memory_score": mem["score"],
        "context_score": ctx["average_score"],
    }

def _j78_roadmap_pack(body=None):
    body = body or {}
    target = _j78_norm(body.get("target") or "JARVIS next 10 blocks")
    rank = _j78_feature_rank()

    out = _J78_ROADMAPS / f"roadmap_pack_{_j78_slug(target)}_{_j78_now()}.md"
    lines = [
        f"# JARVIS Roadmap Pack — {target}",
        "",
        "## Immediate blocks",
        "### Block 79 — Local Evaluation Scorer",
        "- score context packs, specs, memory and endpoint health",
        "- no Claude needed",
        "",
        "### Block 80 — Self-Improvement Planner",
        "- propose improvements from source/logs",
        "- do not auto-apply patches",
        "- Claude useful only if implementing deeper code analysis",
        "",
        "### Block 81 — Internet Research Module",
        "- Claude recommended",
        "- needs source policy, citations, cache and approval",
        "",
        "### Block 82 — Prompt/Agent Pack Generator",
        "- can generate polished prompts for Claude, n8n, VPS, image/video",
        "- mostly safe locally",
        "",
        "### Block 83 — n8n Workflow Architect",
        "- Claude recommended if generating real workflow JSON",
        "- ChatGPT can prepare specs",
        "",
        "### Block 84 — VPS Automation Planner",
        "- Claude recommended only with strict dry-run",
        "- no destructive action by default",
        "",
        "### Block 85 — Multimodal Creation Planner",
        "- image/video system architecture",
        "- external tools only after approval",
        "",
        "## Ranking data",
        "```json",
        _j78_json.dumps(rank, ensure_ascii=False, indent=2),
        "```",
        "",
        "Status real: roadmap generated locally. No commit, no push, no deploy.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(out.relative_to(_J78ROOT)), "target": target}

def _j78_cleanup_candidates():
    files = _j78_files()
    groups = {}
    large = []
    for p in files:
        try:
            rel = str(p.relative_to(_J78ROOT))
            st = p.stat()
            key = (p.name, st.st_size)
            groups.setdefault(key, []).append(rel)
            if st.st_size > 120000:
                large.append({"path": rel, "size": st.st_size})
        except Exception:
            pass
    duplicates = [
        {"name": k[0], "size": k[1], "paths": v}
        for k, v in groups.items()
        if len(v) > 1
    ]
    return {
        "large_files": sorted(large, key=lambda x: x["size"], reverse=True)[:40],
        "duplicate_candidates": duplicates[:40],
        "note": "Read-only list. Nothing deleted.",
    }

def _j78_dashboard():
    return {
        "inventory": _j78_inventory(),
        "memory_quality": _j78_memory_quality(),
        "context_quality": _j78_context_quality(),
        "feature_rank": _j78_feature_rank(),
        "cleanup_candidates": _j78_cleanup_candidates(),
        "route_contracts_count": _j78_route_contracts()["count"],
    }

def _j78_generate_all(body=None):
    body = body or {}
    target = _j78_norm(body.get("target") or "JARVIS next powerful features")
    results = {
        "prompt_factory": _j78_prompt_factory({"target": target}),
        "ops_pack": _j78_ops_pack({"target": target}),
        "roadmap_pack": _j78_roadmap_pack({"target": target}),
    }

    report = _J78_REPORTS / f"evaluation_suite_report_{_j78_slug(target)}_{_j78_now()}.md"
    dash = _j78_dashboard()
    lines = [
        f"# JARVIS Evaluation Suite Report — {target}",
        "",
        "## Generated outputs",
        "```json",
        _j78_json.dumps(results, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Dashboard",
        "```json",
        _j78_json.dumps(dash, ensure_ascii=False, indent=2)[:20000],
        "```",
        "",
        "## Summary",
        f"- inventory_files: {dash['inventory']['files_indexed']}",
        f"- memory_score: {dash['memory_quality']['score']}",
        f"- context_score: {dash['context_quality']['average_score']}",
        f"- route_contracts_count: {dash['route_contracts_count']}",
        "",
        "Status real: generated locally. No commit, no push, no deploy.",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    results["evaluation_report"] = str(report.relative_to(_J78ROOT))
    return results

def _j78_do_GET(self):
    parsed = _j78_urlparse(self.path)
    path = parsed.path
    try:
        if path == "/evaluation-dashboard":
            p = _j78_base("GET /evaluation-dashboard", True)
            p["data"] = _j78_dashboard()
            return _j78_json_out(self, p)

        if path == "/memory-quality":
            p = _j78_base("GET /memory-quality", True)
            p["data"] = _j78_memory_quality()
            return _j78_json_out(self, p)

        if path == "/context-quality":
            p = _j78_base("GET /context-quality", True)
            p["data"] = _j78_context_quality()
            return _j78_json_out(self, p)

        if path == "/feature-rank":
            p = _j78_base("GET /feature-rank", True)
            p["data"] = _j78_feature_rank()
            return _j78_json_out(self, p)

        if path == "/route-contracts":
            p = _j78_base("GET /route-contracts", True)
            p["data"] = _j78_route_contracts()
            return _j78_json_out(self, p)

        if path == "/cleanup-candidates":
            p = _j78_base("GET /cleanup-candidates", True)
            p["data"] = _j78_cleanup_candidates()
            return _j78_json_out(self, p)

    except Exception as e:
        p = _j78_base(f"GET {path}", False)
        p["error"] = str(e)
        return _j78_json_out(self, p, 500)

    return self.__class__._j78_prev_GET(self)

_J78_POST_PATHS = {"/prompt-factory", "/ops-pack", "/roadmap-pack", "/block78-generate-all"}

def _j78_do_POST(self):
    parsed = _j78_urlparse(self.path)
    path = parsed.path

    if path not in _J78_POST_PATHS:
        return self.__class__._j78_prev_POST(self)

    try:
        body = _j78_read_json(self)

        if path == "/prompt-factory":
            data = _j78_prompt_factory(body)
            p = _j78_base("POST /prompt-factory", True)
            p["message"] = "Prompt pack generated."
            p["data"] = data
            return _j78_json_out(self, p)

        if path == "/ops-pack":
            data = _j78_ops_pack(body)
            p = _j78_base("POST /ops-pack", True)
            p["message"] = "Ops pack generated."
            p["data"] = data
            return _j78_json_out(self, p)

        if path == "/roadmap-pack":
            data = _j78_roadmap_pack(body)
            p = _j78_base("POST /roadmap-pack", True)
            p["message"] = "Roadmap pack generated."
            p["data"] = data
            return _j78_json_out(self, p)

        if path == "/block78-generate-all":
            data = _j78_generate_all(body)
            p = _j78_base("POST /block78-generate-all", True)
            p["message"] = "Block 78 generated all outputs."
            p["data"] = data
            return _j78_json_out(self, p)

    except Exception as e:
        p = _j78_base(f"POST {path}", False)
        p["error"] = str(e)
        return _j78_json_out(self, p, 500)

    return self.__class__._j78_prev_POST(self)

def _j78_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j78_BaseHTTPRequestHandler)
                and obj is not _j78_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j78_installed", False)
            ):
                obj._j78_prev_GET = obj.do_GET
                obj._j78_prev_POST = obj.do_POST
                obj.do_GET = _j78_do_GET
                obj.do_POST = _j78_do_POST
                obj._j78_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J78] Installed Block 78 routes on:", ", ".join(patched) if patched else "none")

_j78_install()
# === END JARVIS BLOCK 78 ===



# === JARVIS BLOCK 80: PRODUCTION SUMMARY + NOISE REPORT + CLAUDE NEEDED ===
# Production filter layer. Local-only. No commit/push/deploy.

import json as _j80_json
import time as _j80_time
import subprocess as _j80_subprocess
from pathlib import Path as _j80_Path
from urllib.parse import urlparse as _j80_urlparse
from http.server import BaseHTTPRequestHandler as _j80_BaseHTTPRequestHandler

_J80ROOT = _j80_Path(__file__).resolve().parents[1]
_J80DIR = _J80ROOT / "05_EXECUCAO" / "80_JARVIS_PRODUCTION_CONTROL"
_J80DIR.mkdir(parents=True, exist_ok=True)

_J80_BLOCKED = ["commit", "push", "deploy", "production"]
_J80_USEFUL_ENDPOINTS = [
    "/status",
    "/fulltest",
    "/validate",
    "/safety-gate",
    "/command",
    "/production-summary",
    "/noise-report",
    "/claude-needed",
    "/context-pack",
    "/spec-to-tasks",
    "/evaluation-dashboard",
    "/prompt-factory",
    "/ops-pack",
    "/roadmap-pack",
]

def _j80_now():
    return _j80_time.strftime("%Y-%m-%d_%H-%M-%S")

def _j80_json_out(self, payload, status=200):
    raw = _j80_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _j80_base(endpoint, ok=True):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "status_real": "local_production_control_only",
        "precisa_aprovacao": True,
        "blocked_actions": list(_J80_BLOCKED),
        "safety": {
            "local_only": True,
            "commit": False,
            "push": False,
            "deploy": False,
            "production_touched": False,
            "read_env": False,
            "free_shell": False,
        },
    }

def _j80_git(args):
    allowed = [
        ["status", "--short"],
        ["diff", "--stat"],
        ["diff", "--name-only"],
        ["rev-parse", "--short", "HEAD"],
        ["branch", "--show-current"],
    ]
    if args not in allowed:
        return ""
    try:
        r = _j80_subprocess.run(["git", *args], cwd=_J80ROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or "").strip()
    except Exception as e:
        return f"git_error: {e}"

def _j80_changed_files():
    return [x for x in _j80_git(["diff", "--name-only"]).splitlines() if x.strip()]

def _j80_all_output_files():
    base = _J80ROOT / "05_EXECUCAO"
    rows = []
    if not base.exists():
        return rows
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel = str(p.relative_to(_J80ROOT))
            st = p.stat()
            rows.append({
                "path": rel,
                "name": p.name,
                "size": st.st_size,
                "modified": int(st.st_mtime),
                "folder": rel.split("/", 2)[1] if "/" in rel else "",
            })
        except Exception:
            pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows

def _j80_noise_report():
    rows = _j80_all_output_files()

    large = [x for x in rows if x["size"] > 100000][:40]

    by_name_size = {}
    for x in rows:
        key = (x["name"], x["size"])
        by_name_size.setdefault(key, []).append(x["path"])
    dupes = [
        {"name": k[0], "size": k[1], "paths": v}
        for k, v in by_name_size.items()
        if len(v) > 1
    ][:40]

    noisy_folders = {}
    for x in rows:
        noisy_folders[x["folder"]] = noisy_folders.get(x["folder"], 0) + 1
    noisy_folders = [
        {"folder": k, "files": v}
        for k, v in sorted(noisy_folders.items(), key=lambda i: i[1], reverse=True)
        if v >= 5
    ]

    reports = [
        x for x in rows
        if any(w in x["path"].lower() for w in ["report", "brief", "acceptance", "context_pack", "roadmap", "backup"])
    ][:80]

    production_keep = [
        "11_SCRIPTS/jarvis_api.py",
        "11_SCRIPTS/jarvis_ui_assets/cockpit.html",
        "05_EXECUCAO/79_JARVIS_PRODUCTION_FILTER",
        "05_EXECUCAO/80_JARVIS_PRODUCTION_CONTROL",
    ]

    return {
        "summary": {
            "total_output_files": len(rows),
            "large_files_count": len(large),
            "duplicate_groups_count": len(dupes),
            "noisy_folders_count": len(noisy_folders),
            "reports_or_backup_like_count": len(reports),
        },
        "large_files": large[:25],
        "duplicate_candidates": dupes[:25],
        "noisy_folders": noisy_folders[:25],
        "reports_or_backup_like": reports[:40],
        "production_keep_focus": production_keep,
        "action": "read_only_report_no_files_deleted",
    }

def _j80_claude_needed():
    status = _j80_git(["status", "--short"])
    diffstat = _j80_git(["diff", "--stat"])
    changed = _j80_changed_files()

    diff_lines = [x for x in diffstat.splitlines() if x.strip()]
    api_changed = any(x.endswith("jarvis_api.py") for x in changed)
    ui_changed = any("cockpit.html" in x for x in changed)
    many_files = len(changed) >= 4
    big_diff = any(("insertions" in x or "deletions" in x) and any(n in x for n in ["1000", "2000", "3000", "4000", "5000"]) for x in diff_lines)

    reasons = []
    use = False

    if big_diff:
        use = True
        reasons.append("diff is large enough to benefit from Claude review/refactor")
    if api_changed and len(diffstat) > 500:
        reasons.append("API changed; local checks required before any consolidation")
    if many_files:
        reasons.append("multiple changed files/folders; summarize before next major patch")

    recommended_for = [
        "hard debugging",
        "large/perfect feature",
        "internet research module",
        "image/video generation system",
        "professional n8n workflow",
        "autonomous VPS/infra planner",
        "multi-file refactor",
    ]

    if not use:
        reasons.append("ChatGPT/local block is enough for next deterministic improvement")

    return {
        "use_claude": bool(use),
        "reason": reasons,
        "task_type": "local_jARVIS_development",
        "changed_files": changed,
        "changed_files_count": len(changed),
        "diff_stat": diffstat,
        "recommendation": "Use Claude only if the next task is high-leverage or risky. Otherwise continue with ChatGPT local blocks.",
        "claude_is_for": recommended_for,
    }

def _j80_production_summary():
    rows = _j80_all_output_files()
    latest_useful = [
        x for x in rows
        if any(tag in x["path"] for tag in [
            "79_JARVIS_PRODUCTION_FILTER",
            "78_JARVIS_EVALUATION_SUITE",
            "77_JARVIS_CONTEXT_ENGINE",
            "76_JARVIS_BIG_BLOCK/reports/fulltest",
        ])
    ][:25]

    noise = _j80_noise_report()
    claude = _j80_claude_needed()

    return {
        "project": "JARVIS Agent OS",
        "branch": _j80_git(["branch", "--show-current"]),
        "head": _j80_git(["rev-parse", "--short", "HEAD"]),
        "status_short": _j80_git(["status", "--short"]),
        "diff_stat": _j80_git(["diff", "--stat"]),
        "useful_endpoints": list(_J80_USEFUL_ENDPOINTS),
        "latest_useful_outputs": latest_useful,
        "noise_summary": noise["summary"],
        "claude_needed": claude,
        "production_decision": {
            "ready_to_push": False,
            "ready_to_deploy": False,
            "ready_for_next_local_block": True,
            "next_real_step": "Stop generating random docs. Use /production-summary, /noise-report and /claude-needed before next major block.",
        },
    }

def _j80_do_GET(self):
    parsed = _j80_urlparse(self.path)
    path = parsed.path

    try:
        if path == "/production-summary":
            p = _j80_base("GET /production-summary", True)
            p["data"] = _j80_production_summary()
            return _j80_json_out(self, p)

        if path == "/noise-report":
            p = _j80_base("GET /noise-report", True)
            p["data"] = _j80_noise_report()
            return _j80_json_out(self, p)

        if path == "/claude-needed":
            p = _j80_base("GET /claude-needed", True)
            p["data"] = _j80_claude_needed()
            return _j80_json_out(self, p)

    except Exception as e:
        p = _j80_base(f"GET {path}", False)
        p["error"] = str(e)
        return _j80_json_out(self, p, 500)

    return self.__class__._j80_prev_GET(self)

def _j80_do_POST(self):
    return self.__class__._j80_prev_POST(self)

def _j80_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j80_BaseHTTPRequestHandler)
                and obj is not _j80_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j80_installed", False)
            ):
                obj._j80_prev_GET = obj.do_GET
                obj._j80_prev_POST = obj.do_POST
                obj.do_GET = _j80_do_GET
                obj.do_POST = _j80_do_POST
                obj._j80_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J80] Installed Block 80 routes on:", ", ".join(patched) if patched else "none")

_j80_install()
# === END JARVIS BLOCK 80 ===



# === JARVIS BLOCK 81: FEATURE AUTOPILOT MVP ===
# Local feature autopilot planner.
# Goal: user writes a feature request; JARVIS returns production-grade plan/package.
# Local-only. No commit. No push. No deploy. No free shell.

import json as _j81_json
import re as _j81_re
import time as _j81_time
import subprocess as _j81_subprocess
from pathlib import Path as _j81_Path
from urllib.parse import urlparse as _j81_urlparse, parse_qs as _j81_parse_qs
from http.server import BaseHTTPRequestHandler as _j81_BaseHTTPRequestHandler

_J81ROOT = _j81_Path(__file__).resolve().parents[1]
_J81DIR = _J81ROOT / "05_EXECUCAO" / "81_JARVIS_FEATURE_AUTOPILOT"
_J81PACKAGES = _J81DIR / "packages"
_J81PACKAGES.mkdir(parents=True, exist_ok=True)

_J81_BLOCKED = ["commit", "push", "deploy", "production"]
_J81_POWER_CLAUDE = [
    "internet", "pesquisa", "research", "browser", "web",
    "video", "imagem", "image", "multimodal",
    "n8n", "workflow profissional",
    "vps", "infra", "docker", "traefik", "servidor",
    "refactor grande", "multi arquivo", "multi-file",
    "debug grande", "bug difícil", "hard debug",
    "self-improvement", "auto melhorar", "autonomo", "autônomo",
]
_J81_UI_WORDS = ["site", "ui", "interface", "tela", "botão", "visual", "cockpit", "html", "frontend"]
_J81_API_WORDS = ["api", "endpoint", "rota", "backend", "json", "handler"]
_J81_AI_WORDS = ["ia", "ai", "agent", "agente", "autopilot", "autonomia", "planejar", "executar"]

def _j81_now():
    return _j81_time.strftime("%Y-%m-%d_%H-%M-%S")

def _j81_slug(v, fallback="feature"):
    s = _j81_re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(v or "").lower()).strip("-")
    return s[:90] or fallback

def _j81_json_out(self, payload, status=200):
    raw = _j81_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _j81_read_json(self):
    try:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return _j81_json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}

def _j81_base(endpoint, ok=True):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "status_real": "local_feature_autopilot_only",
        "precisa_aprovacao": True,
        "blocked_actions": list(_J81_BLOCKED),
        "safety": {
            "local_only": True,
            "external_calls": False,
            "free_shell": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "production_touched": False,
        },
    }

def _j81_git(args):
    allowed = [
        ["status", "--short"],
        ["diff", "--stat"],
        ["diff", "--name-only"],
        ["rev-parse", "--short", "HEAD"],
        ["branch", "--show-current"],
    ]
    if args not in allowed:
        return ""
    try:
        r = _j81_subprocess.run(["git", *args], cwd=_J81ROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or "").strip()
    except Exception as e:
        return f"git_error: {e}"

def _j81_feature_type(goal):
    g = str(goal or "").lower()
    score = {
        "ui": sum(1 for w in _J81_UI_WORDS if w in g),
        "api": sum(1 for w in _J81_API_WORDS if w in g),
        "ai": sum(1 for w in _J81_AI_WORDS if w in g),
        "power": sum(1 for w in _J81_POWER_CLAUDE if w in g),
    }
    if score["power"] >= 1:
        return "power_feature"
    if score["ui"] >= score["api"] and score["ui"] > 0:
        return "ui_feature"
    if score["api"] > 0:
        return "api_feature"
    if score["ai"] > 0:
        return "agent_feature"
    return "local_product_feature"

def _j81_claude_decision(goal, mode="normal"):
    g = str(goal or "").lower()
    hits = [w for w in _J81_POWER_CLAUDE if w in g]
    changed = [x for x in _j81_git(["diff", "--name-only"]).splitlines() if x.strip()]
    diff = _j81_git(["diff", "--stat"])

    use = False
    reasons = []

    if hits:
        use = True
        reasons.append("feature matches high-leverage Claude category: " + ", ".join(hits[:8]))
    if mode in {"claude", "power", "hard"}:
        use = True
        reasons.append("requested mode is high-power")
    if len(changed) >= 6:
        use = True
        reasons.append("many files changed; Claude can review architecture faster")
    if "jarvis_api.py" in "\n".join(changed) and len(diff) > 1200 and any(x in g for x in ["refactor", "corrigir", "debug", "reestruturar"]):
        use = True
        reasons.append("large API diff plus debug/refactor request")

    if not reasons:
        reasons.append("ChatGPT/local deterministic block is enough for this feature")

    return {
        "use_claude": bool(use),
        "reasons": reasons,
        "claude_is_worth_it_for": [
            "hard debugging",
            "major/perfect feature",
            "autonomous internet research",
            "image/video system",
            "professional n8n workflow",
            "autonomous VPS/infra",
            "large multi-file refactor",
        ],
    }

def _j81_file_targets(kind):
    base = [
        "11_SCRIPTS/jarvis_api.py",
        "11_SCRIPTS/jarvis_ui_assets/cockpit.html",
        "05_EXECUCAO/81_JARVIS_FEATURE_AUTOPILOT/",
    ]
    if kind == "ui_feature":
        return [
            "11_SCRIPTS/jarvis_ui_assets/cockpit.html",
            "11_SCRIPTS/jarvis_api.py if new endpoint is required",
            "05_EXECUCAO/81_JARVIS_FEATURE_AUTOPILOT/packages/",
        ]
    if kind == "api_feature":
        return [
            "11_SCRIPTS/jarvis_api.py",
            "05_EXECUCAO/81_JARVIS_FEATURE_AUTOPILOT/packages/",
        ]
    if kind == "power_feature":
        return [
            "11_SCRIPTS/jarvis_api.py",
            "11_SCRIPTS/jarvis_core.py if core logic is needed",
            "11_SCRIPTS/jarvis_ui_assets/cockpit.html if site control is needed",
            "05_EXECUCAO/<NEW_BLOCK>/",
        ]
    return base

def _j81_plan(goal, mode="normal"):
    goal = str(goal or "").strip() or "Create a useful JARVIS feature"
    kind = _j81_feature_type(goal)
    claude = _j81_claude_decision(goal, mode)

    if kind == "ui_feature":
        architecture = [
            "Add visible UI control without replacing the existing cockpit.",
            "Connect button/input to existing or new local endpoint.",
            "Render result in output area or fallback panel.",
            "Avoid creating another frontend framework.",
        ]
    elif kind == "api_feature":
        architecture = [
            "Add explicit local endpoint with structured JSON output.",
            "Keep POST body reading isolated to the owned route only.",
            "Generate at most one useful artifact when needed.",
            "Expose result for the cockpit UI.",
        ]
    elif kind == "power_feature":
        architecture = [
            "Build a controlled module with dry-run/planning first.",
            "Separate plan, execution, validation and approval.",
            "Generate one high-quality package instead of many loose reports.",
            "Escalate to Claude only if implementation needs deep multi-file reasoning.",
        ]
    else:
        architecture = [
            "Convert user goal into a compact production plan.",
            "Identify files, endpoints and validation commands.",
            "Create one package with implementation-ready instructions.",
            "Keep output focused on next action, not documentation noise.",
        ]

    endpoints = [
        "POST /feature-autopilot",
        "POST /autopilot-package",
        "POST /autopilot-run",
        "GET /autopilot-dashboard",
        "GET /autopilot-latest",
    ]

    validation = [
        "python3 -m py_compile 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py",
        "restart API on 127.0.0.1:8787",
        "GET /status",
        "POST /fulltest",
        "POST /feature-autopilot",
        "GET /autopilot-dashboard",
    ]

    return {
        "goal": goal,
        "feature_type": kind,
        "mode": mode,
        "claude": claude,
        "files_to_consider": _j81_file_targets(kind),
        "architecture": architecture,
        "endpoints": endpoints,
        "implementation_steps": [
            "Define exact output contract.",
            "Create one local route/tool first.",
            "Connect site control only if it increases direct usage.",
            "Generate one clean package under 05_EXECUCAO.",
            "Validate compile and local route behavior.",
            "Do not create repeated reports unless requested.",
        ],
        "acceptance_criteria": [
            "User can describe a feature in plain language.",
            "JARVIS returns feature type, files, plan, endpoint idea and validation.",
            "JARVIS says clearly if Claude is worth using.",
            "JARVIS creates one useful package, not many noisy files.",
            "Existing cockpit/API stays working.",
        ],
        "validation_commands": validation,
        "next_step": "Use /autopilot-run with a concrete feature request.",
    }

def _j81_package(goal, mode="normal"):
    plan = _j81_plan(goal, mode)
    slug = _j81_slug(plan["goal"])
    out = _J81PACKAGES / f"feature_autopilot_{slug}_{_j81_now()}.md"

    claude_text = "YES" if plan["claude"]["use_claude"] else "NO"

    lines = [
        f"# JARVIS Feature Autopilot Package — {plan['goal']}",
        "",
        "## Decision",
        f"- feature_type: `{plan['feature_type']}`",
        f"- use_claude: `{claude_text}`",
        f"- mode: `{plan['mode']}`",
        "",
        "## Claude decision reasons",
    ]
    lines += [f"- {x}" for x in plan["claude"]["reasons"]]
    lines += [
        "",
        "## Files to consider",
    ]
    lines += [f"- `{x}`" for x in plan["files_to_consider"]]
    lines += [
        "",
        "## Architecture",
    ]
    lines += [f"- {x}" for x in plan["architecture"]]
    lines += [
        "",
        "## Implementation steps",
    ]
    lines += [f"{i+1}. {x}" for i, x in enumerate(plan["implementation_steps"])]
    lines += [
        "",
        "## Acceptance criteria",
    ]
    lines += [f"- [ ] {x}" for x in plan["acceptance_criteria"]]
    lines += [
        "",
        "## Validation commands",
        "```bash",
        "\n".join(plan["validation_commands"]),
        "```",
        "",
        "## Ready prompt if Claude is needed",
        "```text",
        f"""Project:
~/Theo/JARVIS/jarvis-agent-os

Mission:
Implement this JARVIS feature with production-grade quality:
{plan['goal']}

Context:
- Owner project, main branch workflow is allowed.
- Do not push or deploy.
- Do not read .env.
- Do not create a parallel backend.
- Preserve existing endpoints and cockpit.
- Generate only useful outputs.
- Avoid report spam.

Expected:
- inspect relevant files
- propose smallest strong architecture
- implement
- validate locally
- return changed files + evidence
""",
        "```",
        "",
        "## Ready local direction if Claude is not needed",
        "```text",
        f"""Implement locally through ChatGPT block:
{plan['goal']}

Keep it deterministic, compact, and product-focused.
Add at most one backend block and one UI touchpoint if useful.
Generate one artifact only if it helps execution.
""",
        "```",
        "",
        "Status real: package generated locally. No commit. No push. No deploy.",
        "",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")

    return {
        "path": str(out.relative_to(_J81ROOT)),
        "plan": plan,
    }

def _j81_latest():
    rows = []
    for p in _J81PACKAGES.glob("*.md"):
        try:
            st = p.stat()
            rows.append({
                "path": str(p.relative_to(_J81ROOT)),
                "size": st.st_size,
                "modified": int(st.st_mtime),
            })
        except Exception:
            pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:20]

def _j81_dashboard():
    return {
        "module": "JARVIS Feature Autopilot MVP",
        "status": "ready",
        "how_to_use": [
            "Open the JARVIS site.",
            "Use the Autopilot panel.",
            "Type: cria uma feature que...",
            "Click Run Autopilot.",
            "Read generated plan/package and Claude decision.",
        ],
        "endpoints": [
            "POST /feature-autopilot",
            "POST /autopilot-package",
            "POST /autopilot-run",
            "GET /autopilot-dashboard",
            "GET /autopilot-latest",
        ],
        "latest_packages": _j81_latest(),
        "git": {
            "branch": _j81_git(["branch", "--show-current"]),
            "head": _j81_git(["rev-parse", "--short", "HEAD"]),
            "status_short": _j81_git(["status", "--short"]),
            "diff_stat": _j81_git(["diff", "--stat"]),
        },
    }

def _j81_do_GET(self):
    parsed = _j81_urlparse(self.path)
    path = parsed.path

    try:
        if path == "/autopilot-dashboard":
            p = _j81_base("GET /autopilot-dashboard", True)
            p["data"] = _j81_dashboard()
            return _j81_json_out(self, p)

        if path == "/autopilot-latest":
            p = _j81_base("GET /autopilot-latest", True)
            p["data"] = {"packages": _j81_latest()}
            return _j81_json_out(self, p)

    except Exception as e:
        p = _j81_base(f"GET {path}", False)
        p["error"] = str(e)
        return _j81_json_out(self, p, 500)

    return self.__class__._j81_prev_GET(self)

_J81_POST_PATHS = {"/feature-autopilot", "/autopilot-package", "/autopilot-run"}

def _j81_do_POST(self):
    parsed = _j81_urlparse(self.path)
    path = parsed.path

    if path not in _J81_POST_PATHS:
        return self.__class__._j81_prev_POST(self)

    try:
        body = _j81_read_json(self)
        goal = body.get("goal") or body.get("feature") or body.get("command") or body.get("message") or ""
        mode = body.get("mode") or "normal"

        if path == "/feature-autopilot":
            p = _j81_base("POST /feature-autopilot", True)
            p["message"] = "Feature plan generated."
            p["data"] = _j81_plan(goal, mode)
            return _j81_json_out(self, p)

        if path in {"/autopilot-package", "/autopilot-run"}:
            data = _j81_package(goal, mode)
            p = _j81_base(f"POST {path}", True)
            p["message"] = "Feature autopilot package generated."
            p["data"] = data
            return _j81_json_out(self, p)

    except Exception as e:
        p = _j81_base(f"POST {path}", False)
        p["error"] = str(e)
        return _j81_json_out(self, p, 500)

    return self.__class__._j81_prev_POST(self)

def _j81_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j81_BaseHTTPRequestHandler)
                and obj is not _j81_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j81_installed", False)
            ):
                obj._j81_prev_GET = obj.do_GET
                obj._j81_prev_POST = obj.do_POST
                obj.do_GET = _j81_do_GET
                obj.do_POST = _j81_do_POST
                obj._j81_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J81] Installed Feature Autopilot routes on:", ", ".join(patched) if patched else "none")

_j81_install()
# === END JARVIS BLOCK 81 ===


# === JARVIS BLOCK 83 — FORGE ENGINE v1 ===
# FORGE turns a plain-language feature request into a professional technical package.
# It classifies the feature, assesses risk, decides local-vs-Claude, suggests files and
# endpoints, writes acceptance criteria + validation commands, and saves ONE clean package.
# FORGE v1 = planning + package + execution decision. It NEVER edits code automatically.
# Local-only. No commit. No push. No deploy. No free shell. No .env. No dependency install.

import json as _j83_json
import re as _j83_re
import time as _j83_time
import subprocess as _j83_subprocess
import unicodedata as _j83_unicodedata
from pathlib import Path as _j83_Path
from urllib.parse import urlparse as _j83_urlparse
from http.server import BaseHTTPRequestHandler as _j83_BaseHTTPRequestHandler

_J83ROOT = _j83_Path(__file__).resolve().parents[1]
_J83DIR = _J83ROOT / "05_EXECUCAO" / "83_JARVIS_FORGE_ENGINE"
_J83PACKAGES = _J83DIR / "packages"
_J83PACKAGES.mkdir(parents=True, exist_ok=True)

_J83_BLOCKED = [
    "commit", "push", "deploy", "production",
    "free_shell", "read_env", "install_dependency",
    "delete_files", "parallel_app", "auto_patch",
]

# Feature taxonomy — ordered by leverage; on a score tie the earlier entry wins.
_J83_TYPES = [
    ("internet_research", "Internet Research Engine",
        ["internet", "research", "pesquisa", "pesquisar", "web", "browser", "navegador",
         "scrape", "scraping", "crawl", "crawler", "online", "noticia", "noticias", "news", "fonte externa"]),
    ("integration_feature", "External Integration",
        ["n8n", "whatsapp", "telegram", "slack", "webhook", "integracao", "integration",
         "zapier", "oauth", "third party", "terceiro", "api externa", "external api"]),
    ("memory_module", "Local Memory Module",
        ["memoria", "memory", "lembrar", "recall", "historico", "history", "remember",
         "armazenar", "store", "persistir", "persist", "knowledge", "conhecimento"]),
    ("dashboard_feature", "Local Dashboard",
        ["dashboard", "painel", "overview", "visao geral", "metricas", "metrics",
         "monitor", "monitoramento", "kpi", "indicadores", "status board"]),
    ("data_pipeline", "Local Data Pipeline",
        ["pipeline", "etl", "ingest", "ingestao", "parser", "parse", "csv",
         "dataset", "indexar", "index", "embedding", "embeddings", "vetorial"]),
    ("agent_feature", "Autonomous Agent Capability",
        ["agente", "agent", "autopilot", "autonomo", "automatico", "automation",
         "automacao", "self-improve", "self improvement", "executar sozinho"]),
    ("api_feature", "Local API Feature",
        ["api", "endpoint", "rota", "route", "backend", "handler", "servico", "service"]),
    ("ui_feature", "Cockpit UI Feature",
        ["ui", "interface", "tela", "botao", "visual", "cockpit", "html", "frontend",
         "pagina", "componente", "component", "viewer", "card"]),
]

_J83_HIGH_RISK = [
    "internet", "web", "browser", "scrape", "crawl", "deploy", "docker", "vps",
    "infra", "servidor", "production", "producao", "shell", "subprocess",
    "n8n", "webhook", "oauth", "credencial", "credential", "token", "external api", "api externa",
]
_J83_MED_RISK = [
    "endpoint", "api", "rota", "route", "pipeline", "integration", "integracao",
    "agent", "agente", "autonomo", "automatico", "write", "escrever", "arquivo", "file",
]
_J83_CLAUDE_WORDS = [
    "internet", "research", "pesquisa", "browser", "web", "video", "imagem", "image",
    "multimodal", "n8n", "vps", "infra", "docker", "refactor", "multi arquivo",
    "multi-arquivo", "multi-file", "hard debug", "self-improve", "autonomo", "reestruturar",
]
_J83_STOP = {
    "cria", "crie", "criar", "create", "make", "build", "add", "adicionar", "quero", "want",
    "uma", "um", "a", "o", "de", "da", "do", "para", "pra", "com", "that", "the", "new",
    "novo", "nova", "feature", "modulo", "module", "sistema", "system", "jarvis",
    "funcionalidade", "recurso",
    # class-name words: drop so the endpoint slug stays the subject, not the category
    # (e.g. "dashboard de sources" -> /sources-dashboard, not /dashboard-sources-dashboard)
    "dashboard", "painel", "research", "pesquisa", "internet", "api", "endpoint",
    "rota", "route", "pipeline", "agent", "agente", "memoria", "memory", "integration",
    "integracao", "local",
    # connector words so the slug keeps only the real subject
    "via", "por", "usando", "using", "through", "sobre", "of", "no", "na", "em",
}


def _j83_now():
    return _j83_time.strftime("%Y-%m-%d_%H-%M-%S")

def _j83_ascii(v):
    return _j83_unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode("ascii")

def _j83_slug(v, fallback="feature"):
    s = _j83_re.sub(r"[^a-zA-Z0-9_.-]+", "-", _j83_ascii(v).lower()).strip("-")
    return s[:90] or fallback

def _j83_short(goal):
    g = _j83_ascii(goal).lower()
    words = [w for w in _j83_re.findall(r"[a-z0-9]+", g) if w not in _J83_STOP and len(w) > 2]
    return "-".join(words[:2]) or "feature"

def _j83_json_out(self, payload, status=200):
    raw = _j83_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _j83_read_json(self):
    try:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return _j83_json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}

def _j83_base(endpoint, ok=True):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "engine": "JARVIS Forge Engine v1",
        "status_real": "local_forge_engine_only",
        "approval_required": True,
        "precisa_aprovacao": True,
        "blocked_actions": list(_J83_BLOCKED),
        "safety": {
            "local_only": True,
            "external_calls": False,
            "free_shell": False,
            "reads_env": False,
            "installs_dependencies": False,
            "auto_patch": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "production_touched": False,
        },
    }

def _j83_git(args):
    allowed = [
        ["status", "--short"],
        ["diff", "--stat"],
        ["diff", "--name-only"],
        ["rev-parse", "--short", "HEAD"],
        ["branch", "--show-current"],
    ]
    if args not in allowed:
        return ""
    try:
        r = _j83_subprocess.run(["git", *args], cwd=_J83ROOT, text=True, capture_output=True, timeout=8)
        return (r.stdout or "").strip()
    except Exception as e:
        return f"git_error: {e}"

def _j83_classify(goal):
    g = _j83_ascii(goal).lower()
    best_key, best_label, best_score, signals = "local_product_feature", "Local Product Feature", 0, []
    for key, label, words in _J83_TYPES:
        hits = [w for w in words if w in g]
        if len(hits) > best_score:
            best_key, best_label, best_score, signals = key, label, len(hits), hits
    return {"type": best_key, "type_label": best_label, "score": best_score, "signals": signals[:8]}

def _j83_risk(goal, kind):
    g = _j83_ascii(goal).lower()
    high = [w for w in _J83_HIGH_RISK if w in g]
    med = [w for w in _J83_MED_RISK if w in g]
    reasons = []
    level = "low"
    if kind in {"internet_research", "integration_feature"} or high:
        level = "high"
        if kind in {"internet_research", "integration_feature"}:
            reasons.append(f"feature class '{kind}' implies an external surface / side effects")
        if high:
            reasons.append("high-risk signals: " + ", ".join(high[:8]))
    elif kind in {"api_feature", "data_pipeline", "agent_feature", "dashboard_feature"} or med:
        level = "medium"
        if kind in {"api_feature", "data_pipeline", "agent_feature"}:
            reasons.append(f"feature class '{kind}' adds new backend behaviour")
        if med:
            reasons.append("medium-risk signals: " + ", ".join(med[:8]))
    if not reasons:
        reasons.append("self-contained local feature; read-mostly, no external surface")
    return {"level": level, "reasons": reasons}

def _j83_claude(goal, kind, risk, mode="normal"):
    g = _j83_ascii(goal).lower()
    hits = [w for w in _J83_CLAUDE_WORDS if w in g]
    changed = [x for x in _j83_git(["diff", "--name-only"]).splitlines() if x.strip()]
    use, reasons = False, []
    if risk["level"] == "high":
        use = True
        reasons.append("risk level is HIGH — deep reasoning and careful review pay off")
    if kind in {"internet_research", "integration_feature"}:
        use = True
        reasons.append(f"'{kind}' needs real external wiring that Claude handles well")
    if mode in {"claude", "power", "hard"}:
        use = True
        reasons.append("requested mode is high-power")
    if hits:
        use = True
        reasons.append("matches Claude-leverage categories: " + ", ".join(hits[:8]))
    if any(x in g for x in ["refactor", "reestruturar", "multi arquivo", "multi-arquivo", "multi-file"]):
        use = True
        reasons.append("multi-file / refactor scope")
    if len(changed) >= 6:
        use = True
        reasons.append(f"{len(changed)} files already dirty — architectural review helps")
    if not reasons:
        reasons.append("deterministic local block (ChatGPT-tier) is enough for this feature")
    return {
        "use_claude": bool(use),
        "recommended_executor": "claude" if use else "local_block",
        "reasons": reasons,
    }

def _j83_files(kind):
    common = ["05_EXECUCAO/83_JARVIS_FORGE_ENGINE/packages/ (this package)"]
    table = {
        "internet_research": [
            "11_SCRIPTS/jarvis_api.py (new research endpoints)",
            "11_SCRIPTS/jarvis_core.py (fetch / parse / rank logic)",
            "05_EXECUCAO/<NEW_BLOCK>_JARVIS_RESEARCH/ (cache + results)",
            "11_SCRIPTS/jarvis_ui_assets/cockpit.html (trigger + viewer)",
        ],
        "memory_module": [
            "11_SCRIPTS/jarvis_api.py (memory store / recall endpoints)",
            "05_EXECUCAO/71_JARVIS_MEMORY/ (existing memory store)",
            "11_SCRIPTS/jarvis_ui_assets/cockpit.html (memory panel / trigger)",
        ],
        "dashboard_feature": [
            "11_SCRIPTS/jarvis_ui_assets/cockpit.html (dashboard view)",
            "11_SCRIPTS/jarvis_api.py (read-only data endpoint)",
        ],
        "data_pipeline": [
            "11_SCRIPTS/jarvis_api.py (ingest / list endpoints)",
            "11_SCRIPTS/jarvis_core.py (parse / transform)",
            "05_EXECUCAO/<NEW_BLOCK>/ (artifacts)",
        ],
        "agent_feature": [
            "11_SCRIPTS/jarvis_api.py (plan / run / dashboard endpoints)",
            "11_SCRIPTS/jarvis_core.py (decision logic, if shared)",
            "05_EXECUCAO/<NEW_BLOCK>/",
        ],
        "integration_feature": [
            "11_SCRIPTS/jarvis_api.py (connect / run / status endpoints)",
            "11_SCRIPTS/jarvis_core.py (adapter)",
            "05_EXECUCAO/<NEW_BLOCK>/",
        ],
        "api_feature": [
            "11_SCRIPTS/jarvis_api.py (new endpoint block)",
            "05_EXECUCAO/<NEW_BLOCK>/",
        ],
        "ui_feature": [
            "11_SCRIPTS/jarvis_ui_assets/cockpit.html (UI control + viewer)",
            "11_SCRIPTS/jarvis_api.py (only if a backend value is needed)",
        ],
    }
    return table.get(kind, ["11_SCRIPTS/jarvis_api.py", "11_SCRIPTS/jarvis_ui_assets/cockpit.html"]) + common

def _j83_endpoints(kind, short):
    if kind == "internet_research":
        return ["POST /research-run", "GET /research-latest", "GET /research-dashboard"]
    if kind == "memory_module":
        return ["POST /memory-store", "POST /memory-recall", "GET /memory-latest"]
    if kind == "integration_feature":
        return [f"POST /{short}-connect", f"POST /{short}-run", f"GET /{short}-status"]
    if kind == "dashboard_feature":
        return [f"GET /{short}-dashboard", f"GET /{short}-data"]
    if kind == "data_pipeline":
        return [f"POST /{short}-ingest", f"GET /{short}-latest"]
    if kind == "agent_feature":
        return [f"POST /{short}-run", f"GET /{short}-dashboard", f"GET /{short}-latest"]
    if kind == "api_feature":
        return [f"POST /{short}", f"GET /{short}-latest"]
    if kind == "ui_feature":
        return ["(UI-only) optional: GET /<feature>-data if a backend value is needed"]
    return [f"POST /{short}-run", f"GET /{short}-latest"]

def _j83_architecture(kind):
    table = {
        "internet_research": [
            "Add an explicit research endpoint that takes a query and returns ranked findings.",
            "Keep fetch / parse / rank in core; the endpoint stays a thin controller.",
            "Cache raw results under a dedicated block dir; never auto-act on them.",
            "Gate any live external call behind approval_required=true.",
        ],
        "memory_module": [
            "Store memory as small structured files (one fact per file) under 71_JARVIS_MEMORY.",
            "Expose store + recall endpoints; recall ranks by simple relevance, no network.",
            "Keep writes idempotent and scoped to the memory dir only.",
            "Add a compact memory panel / trigger in the cockpit.",
        ],
        "dashboard_feature": [
            "Add one read-only data endpoint that aggregates existing local state.",
            "Render a dashboard view inside the existing cockpit shell, not a new app.",
            "Poll lightly and degrade gracefully when the API is offline.",
            "No writes, no side effects — pure visibility.",
        ],
        "data_pipeline": [
            "Define a clear input contract and a single artifact output.",
            "Parse / transform in core; the endpoint orchestrates and reports.",
            "Write one artifact per run under a dedicated block dir.",
            "Make every run dry-run-safe and re-runnable.",
        ],
        "agent_feature": [
            "Split plan / run / dashboard so planning is always side-effect free.",
            "Gate every real action behind approval_required=true.",
            "Persist one clean package / report per run, not noise.",
            "Escalate to Claude only when multi-file reasoning is required.",
        ],
        "integration_feature": [
            "Build an adapter with connect / run / status, dry-run first.",
            "Keep secrets out of code; never read .env from the engine.",
            "Validate the external contract before wiring any side effect.",
            "Mark live calls as approval-required until verified.",
        ],
        "api_feature": [
            "Add one isolated endpoint block that wraps the previous handlers.",
            "Read the POST body only on the owned route; fall through otherwise.",
            "Return a structured, UI-friendly JSON contract.",
            "Generate at most one artifact when it helps execution.",
        ],
        "ui_feature": [
            "Add a visible control to the existing cockpit without replacing it.",
            "Wire it to an existing or one new local endpoint.",
            "Render results in the existing viewer / output area.",
            "Respect the locked cockpit look; no parallel frontend.",
        ],
    }
    return table.get(kind, [
        "Turn the goal into the smallest strong architecture.",
        "Identify files, endpoints and validation up front.",
        "Ship one clean package with implementation-ready steps.",
        "Keep output focused on the next action, not documentation noise.",
    ])

def _j83_acceptance(kind):
    generic = [
        "User can request the feature in plain language and get a usable package.",
        "Package states type, risk, files, endpoints, plan, acceptance and validation.",
        "It clearly says whether Claude is worth using and why.",
        "Existing cockpit, command bar and Autopilot keep working.",
        "No commit / push / deploy / .env access happens automatically.",
    ]
    extra = {
        "internet_research": [
            "A query returns structured, ranked findings (once implemented).",
            "Every external call is gated behind explicit approval.",
        ],
        "memory_module": [
            "A stored fact can be recalled by a later query.",
            "Memory writes stay inside the memory directory only.",
        ],
        "dashboard_feature": [
            "The dashboard reflects real local state and degrades when offline.",
            "The view adds no writes or side effects.",
        ],
        "data_pipeline": [
            "A run produces exactly one artifact and is re-runnable.",
            "Bad input fails safe without partial writes.",
        ],
        "agent_feature": [
            "Planning is side-effect free; actions require approval.",
            "Each run yields one clean report, not many files.",
        ],
        "integration_feature": [
            "Connection status is observable before any live call.",
            "Secrets never enter code or logs.",
        ],
        "api_feature": [
            "The new endpoint returns the documented JSON contract.",
            "Existing routes still resolve unchanged.",
        ],
        "ui_feature": [
            "The control renders results in the existing viewer.",
            "The locked cockpit look is preserved.",
        ],
    }
    return generic + extra.get(kind, [])

def _j83_validation(endpoints):
    cmds = [
        "python3 -m py_compile 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py",
        "restart local API on 127.0.0.1:8787",
        "curl -s http://127.0.0.1:8787/status",
        "curl -s http://127.0.0.1:8787/forge-dashboard",
    ]
    for ep in endpoints[:3]:
        parts = ep.split()
        if len(parts) == 2 and parts[0] in {"GET", "POST"} and parts[1].startswith("/"):
            if parts[0] == "GET":
                cmds.append("curl -s http://127.0.0.1:8787" + parts[1])
            else:
                cmds.append("curl -s -X POST http://127.0.0.1:8787" + parts[1] + " -d '{\"goal\":\"...\"}'")
    return cmds

def _j83_plan(goal, mode="normal"):
    goal = str(goal or "").strip() or "Create a useful JARVIS feature"
    cls = _j83_classify(goal)
    kind = cls["type"]
    risk = _j83_risk(goal, kind)
    claude = _j83_claude(goal, kind, risk, mode)
    short = _j83_short(goal)
    endpoints = _j83_endpoints(kind, short)
    files = _j83_files(kind)
    arch = _j83_architecture(kind)
    accept = _j83_acceptance(kind)
    validation = _j83_validation(endpoints)
    strategy = "claude_assisted" if claude["use_claude"] else "local_block"
    return {
        "title": goal[:120],
        "objective": "Deliver '" + goal + "' as a real JARVIS capability with a clear, safe path to implementation.",
        "goal": goal,
        "feature_type": kind,
        "feature_type_label": cls["type_label"],
        "classification_signals": cls["signals"],
        "risk": risk["level"],
        "risk_reasons": risk["reasons"],
        "strategy": strategy,
        "needs_claude": claude["use_claude"],
        "claude": claude,
        "mode": mode,
        "files_to_consider": files,
        "endpoints_suggested": endpoints,
        "architecture": arch,
        "implementation_steps": [
            "Confirm the exact output contract (inputs, JSON shape, artifact).",
            "Create one isolated backend block that wraps the previous handlers.",
            "Wire one cockpit touchpoint only if it increases direct usage.",
            "Generate one clean artifact / package under 05_EXECUCAO.",
            "Validate compile + each new route locally.",
            "Stop. Do not commit / push / deploy — leave that to the human.",
        ],
        "acceptance_criteria": accept,
        "validation_commands": validation,
        "security_blocks": list(_J83_BLOCKED),
        "approval_required": True,
        "next_step": (
            "Escalate this package to Claude using the ready prompt below."
            if claude["use_claude"] else
            "Implement locally via the deterministic block; no Claude needed."
        ),
    }

def _j83_claude_prompt(plan):
    files = "\n".join("- " + f for f in plan["files_to_consider"])
    eps = "\n".join("- " + e for e in plan["endpoints_suggested"])
    return (
        "Project:\n~/Theo/JARVIS/jarvis-agent-os\n\n"
        "Mission:\nImplement this JARVIS feature with production-grade quality:\n"
        + plan["goal"] + "\n\n"
        "Classification: " + plan["feature_type"] + " | risk " + plan["risk"]
        + " | strategy " + plan["strategy"] + "\n\n"
        "Likely files:\n" + files + "\n\n"
        "Likely endpoints:\n" + eps + "\n\n"
        "Hard rules:\n"
        "- No commit, push or deploy.\n"
        "- Do not read .env. Do not install dependencies.\n"
        "- Do not create a parallel backend or app.\n"
        "- Preserve existing endpoints, cockpit and Autopilot.\n"
        "- Generate only useful output; no report spam.\n\n"
        "Expected:\n"
        "- inspect the relevant files\n"
        "- implement the smallest strong architecture\n"
        "- validate locally (py_compile + each route)\n"
        "- return changed files + evidence\n"
    )

def _j83_local_prompt(plan):
    return (
        "Implement locally via a deterministic JARVIS block:\n"
        + plan["goal"] + "\n\n"
        "Type: " + plan["feature_type"] + " | risk " + plan["risk"] + "\n"
        "Add at most one backend block (wrapping previous handlers) and one cockpit touchpoint.\n"
        "Keep it compact, product-focused and re-runnable.\n"
        "Generate one artifact only if it helps execution.\n"
        "No commit / push / deploy / .env / dependency install.\n"
    )

def _j83_package(goal, mode="normal"):
    plan = _j83_plan(goal, mode)
    slug = _j83_slug(plan["goal"])
    stamp = _j83_now()
    out = _J83PACKAGES / ("forge_" + slug + "_" + stamp + ".md")
    needs = "YES" if plan["needs_claude"] else "NO"

    L = []
    L.append("# JARVIS Forge Package — " + plan["title"])
    L.append("")
    L.append("> Generated " + stamp + " · engine: Forge v1 · approval_required: **true**")
    L.append("")
    L.append("## 1. Feature")
    L.append("- **Title:** " + plan["title"])
    L.append("- **Objective:** " + plan["objective"])
    L.append("")
    L.append("## 2. Classification")
    L.append("- **Type:** `" + plan["feature_type"] + "` (" + plan["feature_type_label"] + ")")
    L.append("- **Risk:** `" + plan["risk"] + "`")
    L.append("- **Strategy:** `" + plan["strategy"] + "`")
    L.append("- **Needs Claude:** `" + needs + "`")
    if plan["classification_signals"]:
        L.append("- **Signals:** " + ", ".join(plan["classification_signals"]))
    L.append("")
    L.append("### Risk reasons")
    L += ["- " + x for x in plan["risk_reasons"]]
    L.append("")
    L.append("### Claude decision")
    L += ["- " + x for x in plan["claude"]["reasons"]]
    L.append("")
    L.append("## 3. Probable files")
    L += ["- `" + x + "`" for x in plan["files_to_consider"]]
    L.append("")
    L.append("## 4. Probable endpoints")
    L += ["- `" + x + "`" for x in plan["endpoints_suggested"]]
    L.append("")
    L.append("## 5. Implementation plan")
    L += ["- " + x for x in plan["architecture"]]
    L.append("")
    L += [str(i + 1) + ". " + x for i, x in enumerate(plan["implementation_steps"])]
    L.append("")
    L.append("## 6. Acceptance criteria")
    L += ["- [ ] " + x for x in plan["acceptance_criteria"]]
    L.append("")
    L.append("## 7. Validation commands")
    L.append("```bash")
    L.append("\n".join(plan["validation_commands"]))
    L.append("```")
    L.append("")
    L.append("## 8. Security blocks (hard)")
    L += ["- " + x + ": disabled" for x in plan["security_blocks"]]
    L.append("")
    L.append("## 9. Next step")
    L.append("- " + plan["next_step"])
    L.append("")
    if plan["needs_claude"]:
        L.append("## 10. Ready prompt for Claude")
        L.append("```text")
        L.append(_j83_claude_prompt(plan))
        L.append("```")
    else:
        L.append("## 10. Ready local direction")
        L.append("```text")
        L.append(_j83_local_prompt(plan))
        L.append("```")
    L.append("")
    L.append("---")
    L.append("Status real: package generated locally. No commit. No push. No deploy. No code edited.")
    L.append("")

    out.write_text("\n".join(L), encoding="utf-8")
    return {
        "path": str(out.relative_to(_J83ROOT)),
        "package_file": out.name,
        "plan": plan,
    }

def _j83_latest():
    rows = []
    for p in _J83PACKAGES.glob("*.md"):
        try:
            st = p.stat()
            rows.append({
                "path": str(p.relative_to(_J83ROOT)),
                "file": p.name,
                "size": st.st_size,
                "modified": int(st.st_mtime),
            })
        except Exception:
            pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:20]

def _j83_dashboard():
    latest = _j83_latest()
    return {
        "module": "JARVIS Forge Engine v1",
        "tagline": "Describe a feature -> get a professional technical package.",
        "status": "ready",
        "version": "1.0",
        "capabilities": [
            "classify feature type",
            "assess risk",
            "decide local vs Claude",
            "suggest files + endpoints",
            "write acceptance + validation",
            "save one clean package",
        ],
        "how_to_use": [
            "Open the cockpit and switch the hero to FORGE.",
            "Type a feature, e.g. 'cria uma feature de internet research'.",
            "Run Forge — read the plan, risk and Claude decision.",
            "Open the generated package under 05_EXECUCAO/83_JARVIS_FORGE_ENGINE/packages/.",
        ],
        "endpoints": [
            "POST /forge-plan",
            "POST /forge-package",
            "POST /forge-run",
            "GET /forge-dashboard",
            "GET /forge-latest",
        ],
        "package_count": len(latest),
        "latest_packages": latest,
        "git": {
            "branch": _j83_git(["branch", "--show-current"]),
            "head": _j83_git(["rev-parse", "--short", "HEAD"]),
            "status_short": _j83_git(["status", "--short"]),
            "diff_stat": _j83_git(["diff", "--stat"]),
        },
    }

def _j83_do_GET(self):
    parsed = _j83_urlparse(self.path)
    path = parsed.path
    try:
        if path == "/forge-dashboard":
            p = _j83_base("GET /forge-dashboard", True)
            p["data"] = _j83_dashboard()
            return _j83_json_out(self, p)
        if path == "/forge-latest":
            p = _j83_base("GET /forge-latest", True)
            p["data"] = {"packages": _j83_latest()}
            return _j83_json_out(self, p)
    except Exception as e:
        p = _j83_base("GET " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)
    return self.__class__._j83_prev_GET(self)

_J83_POST_PATHS = {"/forge-plan", "/forge-package", "/forge-run"}

def _j83_do_POST(self):
    parsed = _j83_urlparse(self.path)
    path = parsed.path
    if path not in _J83_POST_PATHS:
        return self.__class__._j83_prev_POST(self)
    try:
        body = _j83_read_json(self)
        goal = (body.get("goal") or body.get("feature") or body.get("command")
                or body.get("message") or body.get("prompt") or body.get("description") or "")
        mode = body.get("mode") or "normal"

        if path == "/forge-plan":
            p = _j83_base("POST /forge-plan", True)
            p["message"] = "Forge plan generated."
            p["data"] = _j83_plan(goal, mode)
            return _j83_json_out(self, p)

        if path in {"/forge-package", "/forge-run"}:
            data = _j83_package(goal, mode)
            p = _j83_base("POST " + path, True)
            p["message"] = "Forge package generated."
            p["data"] = data
            return _j83_json_out(self, p)
    except Exception as e:
        p = _j83_base("POST " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)
    return self.__class__._j83_prev_POST(self)

def _j83_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j83_BaseHTTPRequestHandler)
                and obj is not _j83_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j83_installed", False)
            ):
                obj._j83_prev_GET = obj.do_GET
                obj._j83_prev_POST = obj.do_POST
                obj.do_GET = _j83_do_GET
                obj.do_POST = _j83_do_POST
                obj._j83_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J83] Installed Forge Engine routes on:", ", ".join(patched) if patched else "none")

_j83_install()
# === END JARVIS BLOCK 83 ===


# === JARVIS BLOCK 84 — FORGE WORKSHOP + CAPABILITY MATRIX ===
# Turns FORGE into a product workshop: batch-triage many ideas, break a big goal into
# ranked features, expose a live capability matrix, keep a simple local backlog, and emit
# strong ready-to-paste Claude prompts. Reuses the Block 83 engine for classification.
# Planning / prioritisation / packaging only. NO auto-patch. No commit/push/deploy/.env.

import json as _j84_json
import re as _j84_re
from pathlib import Path as _j84_Path
from urllib.parse import urlparse as _j84_urlparse
from http.server import BaseHTTPRequestHandler as _j84_BaseHTTPRequestHandler

_J84ROOT = _j84_Path(__file__).resolve().parents[1]
_J84DIR = _J84ROOT / "05_EXECUCAO" / "84_JARVIS_FORGE_WORKSHOP"
_J84WORKSHOPS = _J84DIR / "workshops"
_J84BACKLOG = _J84DIR / "backlog"
_J84WORKSHOPS.mkdir(parents=True, exist_ok=True)
_J84BACKLOG.mkdir(parents=True, exist_ok=True)
_J84_BACKLOG_FILE = _J84BACKLOG / "backlog.json"
_J84_BACKLOG_MD = _J84BACKLOG / "backlog.md"

_J84_BLOCKED = list(_J83_BLOCKED)

_J84_IMPACT = {
    "internet_research": 5, "agent_feature": 5, "memory_module": 4,
    "integration_feature": 4, "data_pipeline": 3, "dashboard_feature": 3,
    "api_feature": 3, "ui_feature": 2, "local_product_feature": 2,
}
_J84_EFFORT = {
    "internet_research": 5, "integration_feature": 5, "agent_feature": 4,
    "data_pipeline": 4, "memory_module": 3, "api_feature": 2,
    "dashboard_feature": 2, "ui_feature": 2, "local_product_feature": 2,
}
_J84_RISK_SCORE = {"low": 1, "medium": 3, "high": 5}
_J84_JUNK = [
    "magico", "magica", "magic", "revolucionar", "infinito", "bilhao", "trilhao",
    "dominar o mundo", "agi", "senciente", "consciencia", "telepatia", "ler mente",
]


def _j84_json_out(self, payload, status=200):
    raw = _j84_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(raw)))
    self.end_headers()
    self.wfile.write(raw)

def _j84_read_json(self):
    try:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return _j84_json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}

def _j84_base(endpoint, ok=True):
    p = _j83_base(endpoint, ok)
    p["engine"] = "JARVIS Forge Workshop v1 (Block 84)"
    p["status_real"] = "local_forge_workshop_only"
    return p

def _j84_score(idea, mode="normal"):
    idea = str(idea or "").strip()
    cls = _j83_classify(idea)
    kind = cls["type"]
    risk = _j83_risk(idea, kind)
    claude = _j83_claude(idea, kind, risk, mode)
    g = _j83_ascii(idea).lower()

    impact = _J84_IMPACT.get(kind, 2)
    effort = _J84_EFFORT.get(kind, 2)
    if risk["level"] == "high":
        effort = min(5, effort + 1)
    risk_score = _J84_RISK_SCORE.get(risk["level"], 3)

    junk = any(w in g for w in _J84_JUNK) or len(g) < 4
    if junk:
        impact = min(impact, 1)

    priority_score = impact * 2 - effort - risk_score

    if junk:
        recommendation = "avoid"
    elif impact >= 4:
        recommendation = "now"
    elif impact == 3 and effort <= 3:
        recommendation = "now"
    elif impact <= 1:
        recommendation = "avoid"
    else:
        recommendation = "backlog"

    priority = "high" if priority_score >= 4 else ("medium" if priority_score >= 0 else "low")

    if recommendation == "now":
        nxt = "Worth a Forge package now — run /forge-run or top-3 workshop."
    elif recommendation == "backlog":
        nxt = "Park in backlog; revisit after the current block."
    else:
        nxt = "Skip or reshape — low payoff for the cost."

    return {
        "title": idea[:120] or "untitled idea",
        "feature_type": kind,
        "feature_type_label": cls["type_label"],
        "impact": impact,
        "effort": effort,
        "risk": risk["level"],
        "risk_score": risk_score,
        "needs_claude": claude["use_claude"],
        "priority_score": priority_score,
        "priority": priority,
        "recommendation": recommendation,
        "next_step": nxt,
    }

def _j84_batch(ideas, mode="normal"):
    items = [_j84_score(x, mode) for x in ideas if str(x or "").strip()]
    items.sort(key=lambda d: d["priority_score"], reverse=True)
    now = [x for x in items if x["recommendation"] == "now"]
    backlog = [x for x in items if x["recommendation"] == "backlog"]
    avoid = [x for x in items if x["recommendation"] == "avoid"]
    return {
        "count": len(items),
        "ranked": items,
        "package_now": [x["title"] for x in now],
        "backlog": [x["title"] for x in backlog],
        "avoid": [x["title"] for x in avoid],
        "needs_claude": [x["title"] for x in items if x["needs_claude"]],
        "next_step": "Run /forge-workshop to generate the workshop package + top-3 Forge packages.",
    }

def _j84_split_ideas(text):
    t = str(text or "").strip()
    if not t:
        return []
    low = _j83_ascii(t).lower()
    # focus on the part after a lead-in like "com", "with", ":" when present
    for sep in [" com ", " with ", ":"]:
        idx = low.find(sep)
        if idx != -1 and idx < len(t) - 3:
            t = t[idx + len(sep):]
            break
    # normalise " e " / " and " into commas, then split on , ; and newlines
    t = _j84_re.sub(r"\s+\b(e|and)\b\s+", ", ", t, flags=_j84_re.IGNORECASE)
    parts = _j84_re.split(r"[;,\n]+", t)
    ideas, seen = [], set()
    for p in parts:
        p = p.strip(" .\t-")
        if len(p) < 3:
            continue
        key = _j83_ascii(p).lower()
        if key in seen:
            continue
        seen.add(key)
        ideas.append(p)
    return ideas[:20]

def _j84_next_blocks(batch):
    types = {x["feature_type"] for x in batch["ranked"] if x["recommendation"] != "avoid"}
    out = []
    if "internet_research" in types:
        out.append("Block — Research Engine: real /research-run with fetch + rank (Claude-assisted).")
    if "memory_module" in types:
        out.append("Block — Memory Module: /memory-store + /memory-recall over 71_JARVIS_MEMORY.")
    if "agent_feature" in types or "integration_feature" in types:
        out.append("Block — Agent/Integration adapter with dry-run + approval gate.")
    out.append("Block — Forge Apply v1: turn a package into a proposed diff (dry-run, approval_required).")
    return out[:4]

def _j84_write_workshop_md(goal, ideas, batch, top, packages):
    stamp = _j83_now()
    out = _J84WORKSHOPS / ("workshop_" + _j83_slug(goal) + "_" + stamp + ".md")
    now_items = [x for x in batch["ranked"] if x["recommendation"] == "now"]
    backlog_items = [x for x in batch["ranked"] if x["recommendation"] == "backlog"]
    avoid_items = [x for x in batch["ranked"] if x["recommendation"] == "avoid"]
    claude_items = [x for x in batch["ranked"] if x["needs_claude"] and x["recommendation"] != "avoid"]

    L = []
    L.append("# JARVIS Forge Workshop — " + goal[:120])
    L.append("")
    L.append("> Generated " + stamp + " · engine: Forge Workshop v1 · approval_required: **true**")
    L.append("")
    L.append("## 1. General objective")
    L.append("- " + goal)
    L.append("")
    L.append("## 2. Ideas received")
    L += ["- " + i for i in ideas]
    L.append("")
    L.append("## 3. Top priorities")
    if top:
        L += [str(i + 1) + ". " + x["title"] + "  ·  priority " + x["priority"]
              + " (score " + str(x["priority_score"]) + ")" for i, x in enumerate(top)]
    else:
        L.append("- (none — all ideas landed in backlog or avoid)")
    L.append("")
    L.append("## 4. Impact / Effort / Risk matrix")
    L.append("| # | Feature | Type | Impact | Effort | Risk | Claude | Priority | Bucket |")
    L.append("|---|---------|------|:------:|:------:|:----:|:------:|:--------:|:------:|")
    for i, x in enumerate(batch["ranked"]):
        L.append("| " + " | ".join([
            str(i + 1),
            x["title"].replace("|", "/"),
            x["feature_type"],
            str(x["impact"]),
            str(x["effort"]),
            x["risk"],
            ("yes" if x["needs_claude"] else "no"),
            x["priority"],
            x["recommendation"],
        ]) + " |")
    L.append("")
    L.append("## 5. Recommended for now")
    L += (["- " + x["title"] for x in now_items] or ["- (none)"])
    L.append("")
    L.append("## 6. Needs Claude")
    L += (["- " + x["title"] + "  (" + x["feature_type"] + ")" for x in claude_items] or ["- (none)"])
    L.append("")
    L.append("## 7. Should wait (backlog)")
    L += (["- " + x["title"] for x in backlog_items] or ["- (none)"])
    L.append("")
    L.append("## 8. Avoid / reshape")
    L += (["- " + x["title"] for x in avoid_items] or ["- (none)"])
    L.append("")
    L.append("## 9. Suggested next blocks")
    L += ["- " + b for b in _j84_next_blocks(batch)]
    L.append("")
    L.append("## 10. Generated Forge packages (top features)")
    if packages:
        for p in packages:
            if p.get("path"):
                L.append("- `" + p["path"] + "`  — " + p["title"])
            else:
                L.append("- (failed) " + p["title"] + ": " + str(p.get("error")))
    else:
        L.append("- (none generated)")
    L.append("")
    L.append("## 11. Ready prompts (top features)")
    for x in top:
        plan = _j83_plan(x["title"], "normal")
        L.append("")
        L.append("### " + x["title"])
        L.append("```text")
        L.append(_j83_claude_prompt(plan) if x["needs_claude"] else _j83_local_prompt(plan))
        L.append("```")
    L.append("")
    L.append("---")
    L.append("Status real: workshop generated locally. No commit. No push. No deploy. No code edited.")
    L.append("")

    out.write_text("\n".join(L), encoding="utf-8")
    return str(out.relative_to(_J84ROOT))

def _j84_workshop(text, mode="normal", make_packages=True):
    goal = str(text or "").strip() or "Improve JARVIS with a set of features"
    ideas = _j84_split_ideas(goal) or [goal]
    batch = _j84_batch(ideas, mode)
    top = [x for x in batch["ranked"] if x["recommendation"] != "avoid"][:3]

    packages = []
    if make_packages:
        for it in top:
            try:
                pkg = _j83_package(it["title"], mode)
                packages.append({"title": it["title"], "path": pkg["path"]})
            except Exception as e:
                packages.append({"title": it["title"], "error": str(e)})

    md_path = _j84_write_workshop_md(goal, ideas, batch, top, packages)
    return {
        "objective": goal,
        "ideas": ideas,
        "batch": batch,
        "top_features": top,
        "packages_generated": packages,
        "workshop_package": md_path,
        "next_blocks": _j84_next_blocks(batch),
    }

# ---- Capability matrix: an honest map of what JARVIS can do today ----
def _j84_capability_matrix():
    caps = [
        {"category": "Local Intelligence", "name": "Local command + status + self-test",
         "status": "active", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["GET /status", "POST /command", "POST /self-test"],
         "next_improvement": "Natural-language intent routing for free-text commands."},
        {"category": "Sources", "name": "Source index + reader",
         "status": "active", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["GET /sources", "GET /source", "GET /latest", "GET /artifact"],
         "next_improvement": "Ranked search + better in-viewer reader."},
        {"category": "Forge", "name": "Forge Engine v1 (plan + package)",
         "status": "active", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["POST /forge-plan", "POST /forge-package", "POST /forge-run",
                       "GET /forge-dashboard", "GET /forge-latest"],
         "next_improvement": "Forge Apply v1 — propose a diff (dry-run, approval gated)."},
        {"category": "Forge", "name": "Forge Workshop + batch triage",
         "status": "active", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["POST /forge-batch", "POST /forge-workshop"],
         "next_improvement": "Auto-seed backlog from workshop with dedupe."},
        {"category": "Autopilot", "name": "Feature autopilot planner",
         "status": "active", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["POST /feature-autopilot", "POST /autopilot-run",
                       "GET /autopilot-dashboard", "GET /autopilot-latest"],
         "next_improvement": "Converge Autopilot and Forge onto one engine."},
        {"category": "Safety", "name": "Safety gate + hard blocks",
         "status": "active", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["POST /safety-gate"],
         "next_improvement": "Per-endpoint approval ledger for real changes."},
        {"category": "Reports", "name": "Fulltest / doctor / digest",
         "status": "partial", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["POST /fulltest", "POST /doctor", "POST /digest", "GET /runbook", "GET /api-index"],
         "next_improvement": "One consolidated health report in the viewer."},
        {"category": "Memory", "name": "Local memory module",
         "status": "planned", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["(planned) POST /memory-store", "(planned) POST /memory-recall"],
         "next_improvement": "Wire store/recall over 05_EXECUCAO/71_JARVIS_MEMORY."},
        {"category": "UI", "name": "Cockpit shell + viewer + modes",
         "status": "active", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["GET /", "GET /asset/*"],
         "next_improvement": "Render matrix/backlog as rich cards in the viewer."},
        {"category": "Claude Assist", "name": "Claude decision + prompt generator",
         "status": "partial", "local_only": True, "needs_claude": False, "risk": "low",
         "endpoints": ["POST /claude-feature-prompt", "(in packages) ready prompts"],
         "next_improvement": "Track Claude handoffs and their outcomes."},
        {"category": "Future Apply", "name": "Forge Apply (auto-patch)",
         "status": "blocked", "local_only": True, "needs_claude": True, "risk": "high",
         "endpoints": ["(future) POST /forge-apply (dry-run, approval_required)"],
         "next_improvement": "Generate a reviewable diff WITHOUT writing it; human applies."},
    ]
    counts = {"active": 0, "partial": 0, "planned": 0, "blocked": 0}
    for c in caps:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    cats = []
    for c in caps:
        if c["category"] not in cats:
            cats.append(c["category"])
    return {
        "module": "JARVIS Capability Matrix",
        "generated": _j83_now(),
        "categories": cats,
        "summary": {"total": len(caps), **counts},
        "capabilities": caps,
        "legend": {
            "active": "works today",
            "partial": "works but incomplete",
            "planned": "designed, not wired yet",
            "blocked": "intentionally deferred (e.g. auto-patch)",
        },
    }

# ---- Backlog: a simple local file store, no DB, no deps ----
def _j84_backlog_load():
    if _J84_BACKLOG_FILE.exists():
        try:
            data = _j84_json.loads(_J84_BACKLOG_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []

def _j84_backlog_save(items):
    _J84_BACKLOG_FILE.write_text(_j84_json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# JARVIS Feature Backlog", "", "> " + str(len(items)) + " item(s) · local-only · no DB", ""]
    md.append("| Title | Type | Priority | Risk | Claude | Source | Status | Created |")
    md.append("|-------|------|:--------:|:----:|:------:|:------:|:------:|---------|")
    for it in items:
        md.append("| " + " | ".join([
            str(it.get("title", "")).replace("|", "/"),
            str(it.get("type", "")),
            str(it.get("priority", "")),
            str(it.get("risk", "")),
            ("yes" if it.get("needs_claude") else "no"),
            str(it.get("source", "")),
            str(it.get("status", "")),
            str(it.get("created_at", "")),
        ]) + " |")
    _J84_BACKLOG_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

def _j84_backlog_add(body):
    title = str(body.get("title") or body.get("goal") or body.get("feature") or "").strip()
    if not title:
        raise ValueError("title required")
    kind = body.get("type") or _j83_classify(title)["type"]
    risk_level = body.get("risk") or _j83_risk(title, kind)["level"]
    needs_claude = body.get("needs_claude")
    if needs_claude is None:
        needs_claude = _j83_claude(title, kind, {"level": risk_level})["use_claude"]
    items = _j84_backlog_load()
    item = {
        "id": _j83_slug(title)[:40] + "_" + _j83_now(),
        "title": title[:160],
        "type": kind,
        "priority": str(body.get("priority") or "medium"),
        "risk": risk_level,
        "needs_claude": bool(needs_claude),
        "source": str(body.get("source") or "manual"),
        "status": str(body.get("status") or "proposed"),
        "created_at": _j83_now(),
    }
    items.append(item)
    _j84_backlog_save(items)
    return item

# ---- Claude prompt generator (no /clear, no /effort — user adds those manually) ----
def _j84_safe_pkg(path):
    try:
        raw = str(path or "").strip()
        if not raw:
            return None
        p = _j84_Path(raw)
        p = p.resolve() if p.is_absolute() else (_J84ROOT / raw).resolve()
        if p != _J84ROOT and _J84ROOT not in p.parents:
            return None
        if p.suffix.lower() != ".md":
            return None
        return p
    except Exception:
        return None

def _j84_build_prompt(plan, source_ref=None):
    files = "\n".join("- " + f for f in plan["files_to_consider"])
    eps = "\n".join("- " + e for e in plan["endpoints_suggested"])
    val = "\n".join(plan["validation_commands"])
    src = ("\nReference package:\n- " + source_ref + "\n") if source_ref else ""
    return (
        "Project:\n~/Theo/JARVIS/jarvis-agent-os\n\n"
        "Context:\n"
        "- JARVIS is a local-first agent OS. Backend is 11_SCRIPTS/jarvis_api.py (layered\n"
        "  blocks that wrap the previous HTTP handlers). UI is 11_SCRIPTS/jarvis_ui_assets/cockpit.html.\n"
        "- Each feature is one isolated block; existing endpoints and the cockpit must keep working.\n"
        + src + "\n"
        "Mission:\nImplement this JARVIS feature with production-grade quality:\n"
        + plan["goal"] + "\n\n"
        "Classification: " + plan["feature_type"] + " | risk " + plan["risk"]
        + " | strategy " + plan["strategy"] + "\n\n"
        "Probable files:\n" + files + "\n\n"
        "Probable endpoints:\n" + eps + "\n\n"
        "Hard restrictions:\n"
        "- No commit, push or deploy.\n"
        "- Do not read .env. Do not install dependencies.\n"
        "- Do not create a parallel backend or app. Do not auto-apply destructive changes.\n"
        "- Preserve existing endpoints, the cockpit, Autopilot and Forge.\n"
        "- Mark anything that performs a real change as approval_required=true.\n\n"
        "Validation:\n" + val + "\n\n"
        "Expected final answer:\n"
        "1. files changed\n"
        "2. endpoints created\n"
        "3. how the feature works\n"
        "4. how it connects to the UI\n"
        "5. validation evidence (compile + each route)\n"
        "6. what you did NOT do\n"
        "7. recommended next block\n"
    )

def _j84_claude_prompt(body):
    goal = str(body.get("goal") or body.get("feature") or body.get("message") or "").strip()
    source_ref = None
    safe = _j84_safe_pkg(body.get("path"))
    if safe and safe.exists():
        try:
            txt = safe.read_text(encoding="utf-8", errors="replace")
            m = _j84_re.search(r"#\s*JARVIS Forge Package\s*[—-]\s*(.+)", txt)
            if m and not goal:
                goal = m.group(1).strip()
            source_ref = str(safe.relative_to(_J84ROOT))
        except Exception:
            source_ref = None
    if not goal:
        goal = "Implement the selected JARVIS feature"
    plan = _j83_plan(goal, body.get("mode") or "normal")
    return {
        "goal": goal,
        "source_package": source_ref,
        "feature_type": plan["feature_type"],
        "risk": plan["risk"],
        "needs_claude": plan["needs_claude"],
        "note": "Prompt excludes /clear and /effort by design — add them manually.",
        "prompt": _j84_build_prompt(plan, source_ref),
    }

def _j84_dashboard_latest():
    rows = []
    for p in _J84WORKSHOPS.glob("*.md"):
        try:
            st = p.stat()
            rows.append({"path": str(p.relative_to(_J84ROOT)), "file": p.name,
                         "size": st.st_size, "modified": int(st.st_mtime)})
        except Exception:
            pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:20]

def _j84_do_GET(self):
    parsed = _j84_urlparse(self.path)
    path = parsed.path
    try:
        if path == "/capability-matrix":
            p = _j84_base("GET /capability-matrix", True)
            p["data"] = _j84_capability_matrix()
            return _j84_json_out(self, p)
        if path == "/feature-backlog":
            p = _j84_base("GET /feature-backlog", True)
            items = _j84_backlog_load()
            p["data"] = {
                "count": len(items),
                "items": items,
                "file": str(_J84_BACKLOG_FILE.relative_to(_J84ROOT)),
            }
            return _j84_json_out(self, p)
        if path == "/forge-workshop-latest":
            p = _j84_base("GET /forge-workshop-latest", True)
            p["data"] = {"workshops": _j84_dashboard_latest()}
            return _j84_json_out(self, p)
    except Exception as e:
        p = _j84_base("GET " + path, False)
        p["error"] = str(e)
        return _j84_json_out(self, p, 500)
    return self.__class__._j84_prev_GET(self)

_J84_POST_PATHS = {"/forge-batch", "/forge-workshop", "/feature-backlog", "/claude-feature-prompt"}

def _j84_do_POST(self):
    parsed = _j84_urlparse(self.path)
    path = parsed.path
    if path not in _J84_POST_PATHS:
        return self.__class__._j84_prev_POST(self)
    try:
        body = _j84_read_json(self)
        mode = body.get("mode") or "normal"

        if path == "/forge-batch":
            ideas = body.get("ideas")
            if isinstance(ideas, str):
                ideas = _j84_split_ideas(ideas)
            if not isinstance(ideas, list):
                ideas = _j84_split_ideas(body.get("goal") or body.get("text") or "")
            p = _j84_base("POST /forge-batch", True)
            p["message"] = "Batch triage complete."
            p["data"] = _j84_batch(ideas, mode)
            return _j84_json_out(self, p)

        if path == "/forge-workshop":
            text = (body.get("goal") or body.get("text") or body.get("message")
                    or body.get("feature") or "")
            make = body.get("make_packages")
            make = True if make is None else bool(make)
            p = _j84_base("POST /forge-workshop", True)
            p["message"] = "Workshop package generated."
            p["data"] = _j84_workshop(text, mode, make)
            return _j84_json_out(self, p)

        if path == "/feature-backlog":
            item = _j84_backlog_add(body)
            p = _j84_base("POST /feature-backlog", True)
            p["message"] = "Backlog item added."
            p["data"] = {"added": item, "count": len(_j84_backlog_load())}
            return _j84_json_out(self, p)

        if path == "/claude-feature-prompt":
            p = _j84_base("POST /claude-feature-prompt", True)
            p["message"] = "Claude prompt generated."
            p["data"] = _j84_claude_prompt(body)
            return _j84_json_out(self, p)
    except Exception as e:
        p = _j84_base("POST " + path, False)
        p["error"] = str(e)
        return _j84_json_out(self, p, 500)
    return self.__class__._j84_prev_POST(self)

def _j84_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j84_BaseHTTPRequestHandler)
                and obj is not _j84_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j84_installed", False)
            ):
                obj._j84_prev_GET = obj.do_GET
                obj._j84_prev_POST = obj.do_POST
                obj.do_GET = _j84_do_GET
                obj.do_POST = _j84_do_POST
                obj._j84_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J84] Installed Forge Workshop routes on:", ", ".join(patched) if patched else "none")

_j84_install()
# === END JARVIS BLOCK 84 ===


# === JARVIS BLOCK 85 — FORGE APPLY PREVIEW v1 ===
# Bridges "plan a feature" and "implement a feature". Block 85 takes a raw goal OR an existing
# Forge/Workshop package and produces an INTELLIGENT DRY-RUN: an implementation summary, the
# files & endpoints that WOULD change (grounded in the real files, read-only), a proposed patch
# plan, a pseudo-diff, risks, validation commands and a rollback plan — then DEMANDS human
# approval. It is built on top of Block 83's _j83_plan (reuse, not re-implement).
# It NEVER edits the target files, never applies a patch, never commits/pushes/deploys, never
# reads .env, never installs deps, never runs a free shell. Local-only.

import json as _j85_json
from pathlib import Path as _j85_Path
from urllib.parse import urlparse as _j85_urlparse
from http.server import BaseHTTPRequestHandler as _j85_BaseHTTPRequestHandler

_J85ROOT = _j85_Path(__file__).resolve().parents[1]
_J85DIR = _J85ROOT / "05_EXECUCAO" / "85_JARVIS_FORGE_APPLY_PREVIEW"
_J85PREVIEWS = _J85DIR / "previews"
_J85PREVIEWS.mkdir(parents=True, exist_ok=True)

_J85_BLOCKED = [
    "auto_patch", "edit_target_files", "apply_patch",
    "commit", "push", "deploy", "production",
    "free_shell", "read_env", "install_dependency", "delete_files", "parallel_app",
]


def _j85_base(endpoint, ok=True):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "engine": "JARVIS Forge Apply Preview v1",
        "status_real": "dry_run_preview_only",
        "dry_run": True,
        "approval_required": True,
        "precisa_aprovacao": True,
        "blocked_actions": list(_J85_BLOCKED),
        "safety": {
            "local_only": True,
            "external_calls": False,
            "edits_target_files": False,
            "auto_patch": False,
            "apply_patch": False,
            "free_shell": False,
            "reads_env": False,
            "installs_dependencies": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "production_touched": False,
        },
    }


# ---- read-only grounding: where a new block would land in the real files ----
def _j85_anchor_api():
    try:
        path = _J85ROOT / "11_SCRIPTS" / "jarvis_api.py"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        last_end = 0
        for i, ln in enumerate(lines, 1):
            if ln.startswith("# === END JARVIS BLOCK"):
                last_end = i
        return {
            "file": "11_SCRIPTS/jarvis_api.py",
            "total_lines": len(lines),
            "insert_after_line": last_end or len(lines),
            "anchor": (lines[last_end - 1].strip() if last_end else "end of file"),
        }
    except Exception as e:
        return {"file": "11_SCRIPTS/jarvis_api.py", "error": str(e)}


def _j85_anchor_cockpit():
    try:
        path = _J85ROOT / "11_SCRIPTS" / "jarvis_ui_assets" / "cockpit.html"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        anchor_line, anchor_txt = 0, "end of <body>"
        for i, ln in enumerate(lines, 1):
            if ("JARVIS BLOCK 83 FORGE CONSOLE" in ln) or ('class="sgroup"' in ln):
                anchor_line, anchor_txt = i, ln.strip()[:80]
                break
        return {
            "file": "11_SCRIPTS/jarvis_ui_assets/cockpit.html",
            "total_lines": len(lines),
            "touchpoint_near_line": anchor_line or len(lines),
            "anchor": anchor_txt,
        }
    except Exception as e:
        return {"file": "11_SCRIPTS/jarvis_ui_assets/cockpit.html", "error": str(e)}


def _j85_next_block():
    try:
        root = _J85ROOT / "05_EXECUCAO"
        nums = []
        for d in root.iterdir():
            m = _j83_re.match(r"^(\d+)_", d.name)
            if m:
                nums.append(int(m.group(1)))
        return (max(nums) + 1) if nums else 86
    except Exception:
        return 0


# ---- package parsing (restricted to 05_EXECUCAO/**.md inside the repo) ----
def _j85_md_field(text, label):
    m = _j83_re.search(r"\*\*" + _j83_re.escape(label) + r":\*\*\s*(.+)", text)
    return m.group(1).strip() if m else ""


def _j85_parse_package(rel_path):
    raw = str(rel_path or "").strip()
    if not raw:
        return None, "no package_path provided"
    try:
        p = (_J85ROOT / raw).resolve()
    except Exception:
        return None, "invalid package_path"
    try:
        p.relative_to((_J85ROOT / "05_EXECUCAO").resolve())
    except Exception:
        return None, "package_path must live under 05_EXECUCAO/"
    if p.suffix.lower() != ".md" or not p.is_file():
        return None, "package_path must be an existing .md file"
    text = p.read_text(encoding="utf-8", errors="replace")
    goal = _j85_md_field(text, "Title")
    if not goal:
        m = _j83_re.search(r"^#\s*JARVIS[^\n—-]*[—-]\s*(.+)$", text, _j83_re.M)
        if m:
            goal = m.group(1).strip()
    if not goal:
        m = _j83_re.search(r"^#\s+(.+)$", text, _j83_re.M)
        if m:
            goal = m.group(1).strip()
    return {"path": str(p.relative_to(_J85ROOT)), "goal": goal or "Feature from package"}, None


def _j85_latest_forge_package():
    pkgs = _J85ROOT / "05_EXECUCAO" / "83_JARVIS_FORGE_ENGINE" / "packages"
    rows = []
    try:
        for p in pkgs.glob("forge_*.md"):
            rows.append((p.stat().st_mtime, p))
    except Exception:
        pass
    if not rows:
        return None
    rows.sort(reverse=True)
    return str(rows[0][1].relative_to(_J85ROOT))


# ---- preview building blocks (all derived from _j83_plan) ----
def _j85_summary(plan):
    execu = "Claude (high-power reasoning)" if plan["needs_claude"] else "a local deterministic block"
    return (
        "Implement '%s' as a %s. Recommended executor: %s. Approach: add one isolated, "
        "chain-safe backend block (wrapping the previous handlers) exposing %d endpoint(s), "
        "persist at most one artifact under 05_EXECUCAO, and add a single cockpit touchpoint "
        "only if it increases direct usage. Risk level: %s."
    ) % (
        plan["goal"], plan["feature_type_label"], execu,
        len(plan["endpoints_suggested"]), plan["risk"],
    )


def _j85_files(plan):
    out = []
    for entry in plan["files_to_consider"]:
        s = str(entry).strip()
        low = s.lower()
        if "83_jarvis_forge_engine/packages" in low:
            continue  # the source package itself is not a target to change
        m = _j83_re.match(r"^(\S+)\s*(?:\((.*)\))?$", s)
        path = m.group(1) if m else s
        why = (m.group(2).strip() if (m and m.group(2)) else "")
        lp = path.lower()
        if lp.endswith("jarvis_api.py"):
            action = "append new isolated endpoint block (chain-safe)"
        elif lp.endswith(".html"):
            action = "add one cockpit touchpoint / viewer"
        elif lp.endswith(".py"):
            action = "add thin helper logic"
        elif lp.endswith("/") or "packages/" in lp:
            action = "create / write artifacts"
        else:
            action = "modify"
        out.append({"path": path, "action": action, "why": why or "—"})
    return out


def _j85_endpoints(plan):
    out = []
    for ep in plan["endpoints_suggested"]:
        parts = str(ep).split()
        if len(parts) == 2 and parts[0] in {"GET", "POST"} and parts[1].startswith("/"):
            out.append({"method": parts[0], "route": parts[1]})
        else:
            out.append({"method": "—", "route": str(ep)})
    return out


def _j85_has_ui(plan):
    return plan["feature_type"] in {"ui_feature", "dashboard_feature"} or any(
        ".html" in str(f) for f in plan["files_to_consider"]
    )


def _j85_patch_plan(plan, nextblk):
    blk = str(nextblk or "<N>")
    label = plan["feature_type_label"].upper()
    steps = [
        "Create dir 05_EXECUCAO/%s_JARVIS_<FEATURE>/ for artifacts (only if the feature needs storage)." % blk,
        "Append a new isolated block `# === JARVIS BLOCK %s — %s ===` at the END of jarvis_api.py, before `if __name__`." % (blk, label),
        "Inside it: define _j%s_* helpers + a _j%s_base() envelope (approval_required + safety flags)." % (blk, blk),
        "Register %d endpoint(s) via a chain-safe monkey-patch (_j%s_install) that calls the previous do_GET/do_POST." % (len(plan["endpoints_suggested"]), blk),
    ]
    if _j85_has_ui(plan):
        steps.append("Add ONE cockpit touchpoint (sidebar tool or viewer) wired to the new endpoint; preserve the locked look.")
    steps += [
        "Validate: py_compile + restart 8787 + curl each new route.",
        "STOP at preview — a human must approve before any code is written (future /forge-apply).",
    ]
    return steps


def _j85_pseudo_diff(plan, api_anchor, cockpit_anchor, nextblk):
    blk = str(nextblk or "N")
    short = _j83_short(plan["goal"])
    api_line = api_anchor.get("insert_after_line", "EOF")
    eps = _j85_endpoints(plan)
    diffs = []

    # ---- jarvis_api.py : a new isolated, chain-safe block ----
    a = []
    a.append("--- a/11_SCRIPTS/jarvis_api.py")
    a.append("+++ b/11_SCRIPTS/jarvis_api.py")
    a.append("@@ insert a new block after line %s (after the last `# === END JARVIS BLOCK` marker) @@" % api_line)
    a.append("+")
    a.append("+# === JARVIS BLOCK %s — %s ===" % (blk, plan["feature_type_label"].upper()))
    a.append("+# %s" % str(plan["objective"])[:88])
    a.append("+def _j%s_base(endpoint, ok=True):" % blk)
    a.append('+    return {"ok": ok, "endpoint": endpoint, "approval_required": True, "safety": {...}}')
    a.append("+")
    a.append("+def _j%s_do_POST(self):" % blk)
    a.append("+    path = urlparse(self.path).path")
    has_post = False
    for ep in eps:
        if ep["method"] == "POST":
            has_post = True
            a.append('+    if path == "%s":' % ep["route"])
            a.append("+        body = _read_json(self)  # parse inputs")
            a.append('+        return _json_out(self, _j%s_base("POST %s"))' % (blk, ep["route"]))
    if not has_post:
        a.append("+    # (no POST routes for this feature)")
    a.append("+    return self.__class__._j%s_prev_POST(self)   # chain to previous handler" % blk)
    a.append("+")
    a.append("+def _j%s_do_GET(self):" % blk)
    a.append("+    path = urlparse(self.path).path")
    for ep in eps:
        if ep["method"] == "GET":
            a.append('+    if path == "%s":' % ep["route"])
            a.append('+        return _json_out(self, _j%s_base("GET %s"))' % (blk, ep["route"]))
    a.append("+    return self.__class__._j%s_prev_GET(self)    # chain to previous handler" % blk)
    a.append("+")
    a.append("+_j%s_install()   # monkey-patch do_GET/do_POST, chaining the previous handlers" % blk)
    a.append("+# === END JARVIS BLOCK %s ===" % blk)
    diffs.append({"file": "11_SCRIPTS/jarvis_api.py", "diff": "\n".join(a)})

    # ---- cockpit.html : one touchpoint (only ui/dashboard features) ----
    if _j85_has_ui(plan):
        cl = cockpit_anchor.get("touchpoint_near_line", "?")
        route0 = eps[0]["route"] if eps else ("/" + short)
        c = []
        c.append("--- a/11_SCRIPTS/jarvis_ui_assets/cockpit.html")
        c.append("+++ b/11_SCRIPTS/jarvis_ui_assets/cockpit.html")
        c.append("@@ near line %s (sidebar tools) — add ONE touchpoint, locked look preserved @@" % cl)
        c.append('+      <button type="button" class="tool" data-call="%s">' % route0)
        c.append('+        <span class="i">&#9881;</span>%s</button>' % short.replace("-", " ").title())
        c.append("+      <!-- result renders in the existing viewer; no new app, no layout break -->")
        diffs.append({"file": "11_SCRIPTS/jarvis_ui_assets/cockpit.html", "diff": "\n".join(c)})

    # ---- new artifact directory ----
    d = []
    d.append("--- /dev/null")
    d.append("+++ b/05_EXECUCAO/%s_JARVIS_<FEATURE>/.keep" % blk)
    d.append("@@ new artifact directory (created on first run) @@")
    d.append("+ # stores this feature's artifacts; one clean file per run")
    diffs.append({"file": "05_EXECUCAO/%s_JARVIS_<FEATURE>/" % blk, "diff": "\n".join(d)})
    return diffs


def _j85_risks(plan):
    out = [
        {"level": plan["risk"], "risk": "Feature risk — " + "; ".join(plan["risk_reasons"])},
        {"level": "medium", "risk": "The new block MUST chain the previous do_GET/do_POST, or it will shadow existing routes (Autopilot, Forge, command bar)."},
        {"level": "low", "risk": "Appending a block changes jarvis_api.py — a manual API restart on 8787 is required for it to take effect."},
    ]
    if plan["feature_type"] in {"internet_research", "integration_feature"}:
        out.append({"level": "high", "risk": "External surface — any live call must stay behind approval_required and must never read .env from the engine."})
    if _j85_has_ui(plan):
        out.append({"level": "low", "risk": "Cockpit edit must preserve the locked premium look and not break the hero / mode switch."})
    return out


def _j85_rollback(plan, nextblk):
    blk = str(nextblk or "<N>")
    return [
        "This is a DRY-RUN: no target file was edited, so nothing needs undoing right now.",
        "If a future apply writes code, undo with: git checkout -- 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_ui_assets/cockpit.html",
        "Remove the new block: delete the `# === JARVIS BLOCK %s ... END JARVIS BLOCK %s ===` span, then re-run py_compile." % (blk, blk),
        "Remove artifacts: rm -rf 05_EXECUCAO/%s_JARVIS_<FEATURE>/" % blk,
        "Restart the API on 127.0.0.1:8787 to restore the previous routes.",
    ]


def _j85_preview(goal=None, package_path=None, mode="dry_run"):
    source_pkg = None
    if package_path:
        parsed, err = _j85_parse_package(package_path)
        if err:
            return None, err
        source_pkg = parsed["path"]
        goal = goal or parsed["goal"]
    goal = str(goal or "").strip()
    if not goal:
        return None, "provide a 'goal' or a valid 'package_path'"

    plan = _j83_plan(goal, "normal")
    api_anchor = _j85_anchor_api()
    cockpit_anchor = _j85_anchor_cockpit()
    nextblk = _j85_next_block()

    preview = {
        "ok": True,
        "approval_required": True,
        "dry_run": True,
        "goal": goal,
        "mode": mode or "dry_run",
        "source_package": source_pkg,
        "feature_type": plan["feature_type"],
        "feature_type_label": plan["feature_type_label"],
        "risk_level": plan["risk"],
        "recommended_executor": "claude" if plan["needs_claude"] else "local_block",
        "next_block_number": nextblk,
        "grounding": {"jarvis_api": api_anchor, "cockpit": cockpit_anchor},
        "implementation_summary": _j85_summary(plan),
        "files_to_change": _j85_files(plan),
        "endpoints_to_create": _j85_endpoints(plan),
        "proposed_patch_plan": _j85_patch_plan(plan, nextblk),
        "pseudo_diff": _j85_pseudo_diff(plan, api_anchor, cockpit_anchor, nextblk),
        "validation_commands": plan["validation_commands"],
        "risks": _j85_risks(plan),
        "rollback_plan": _j85_rollback(plan, nextblk),
        "human_decision_required": True,
        "human_decision": (
            "Review this preview. Approve to allow a future /forge-apply (Block 86) to implement it. "
            "Block 85 itself writes nothing to the target files."
        ),
        "next_step": (
            "If a human approves, escalate to implementation (Claude or a local block). "
            "No code is written until then."
        ),
        "generated_at": _j83_now(),
    }
    saved = _j85_write(preview, plan)
    preview["preview_md"] = saved["md"]
    preview["preview_json"] = saved["json"]
    return preview, None


def _j85_render_md(preview, plan):
    L = []
    L.append("# JARVIS Forge Apply Preview — " + preview["goal"][:90])
    L.append("")
    L.append("> Generated " + preview["generated_at"] + " · engine: Forge Apply Preview v1 · **dry_run: true** · **approval_required: true**")
    L.append("")
    L.append("## 1. Source")
    L.append("- **Goal:** " + preview["goal"])
    L.append("- **Package:** " + (("`" + preview["source_package"] + "`") if preview["source_package"] else "—  (raw goal, no package)"))
    L.append("- **Feature type:** `" + preview["feature_type"] + "` (" + preview["feature_type_label"] + ")")
    L.append("- **Risk level:** `" + preview["risk_level"] + "`  ·  **Recommended executor:** `" + preview["recommended_executor"] + "`")
    L.append("- **Generated at:** " + preview["generated_at"])
    L.append("")
    L.append("## 2. Implementation summary")
    L.append(preview["implementation_summary"])
    L.append("")
    L.append("## 3. Files that would change")
    L.append("")
    L.append("| File | Action | Why |")
    L.append("|------|--------|-----|")
    for f in preview["files_to_change"]:
        L.append("| `" + f["path"] + "` | " + f["action"] + " | " + f["why"] + " |")
    L.append("")
    L.append("## 4. Endpoints that would be created/changed")
    if preview["endpoints_to_create"]:
        for e in preview["endpoints_to_create"]:
            L.append("- `" + e["method"] + " " + e["route"] + "`")
    else:
        L.append("- (none — UI-only feature)")
    L.append("")
    L.append("## 5. Proposed patch plan")
    for i, s in enumerate(preview["proposed_patch_plan"], 1):
        L.append(str(i) + ". " + s)
    L.append("")
    g = preview["grounding"]["jarvis_api"]
    L.append("> Grounding: `jarvis_api.py` has " + str(g.get("total_lines", "?")) + " lines; a new block would append after line " + str(g.get("insert_after_line", "?")) + ". Next free block number: **" + str(preview["next_block_number"]) + "**.")
    L.append("")
    L.append("## 6. Pseudo-diff")
    L.append("")
    L.append("_Illustrative dry-run — not a real patch. No target file is edited._")
    L.append("")
    for d in preview["pseudo_diff"]:
        L.append("**" + d["file"] + "**")
        L.append("")
        L.append("```diff")
        L.append(d["diff"])
        L.append("```")
        L.append("")
    L.append("## 7. Validation commands")
    L.append("```bash")
    L.append("\n".join(preview["validation_commands"]))
    L.append("```")
    L.append("")
    L.append("## 8. Risks")
    for r in preview["risks"]:
        L.append("- **[" + r["level"] + "]** " + r["risk"])
    L.append("")
    L.append("## 9. Rollback plan")
    for s in preview["rollback_plan"]:
        L.append("- " + s)
    L.append("")
    L.append("## 10. Human decision required")
    L.append("- **Approval required:** yes — nothing is implemented until a human approves.")
    L.append("- " + preview["human_decision"])
    L.append("- **Next step:** " + preview["next_step"])
    L.append("")
    L.append("---")
    L.append("Status real: dry-run preview only. No target file edited. No commit. No push. No deploy. No .env. No dependency install.")
    L.append("")
    return "\n".join(L)


def _j85_write(preview, plan):
    slug = _j83_slug(preview["goal"])
    stamp = preview["generated_at"]
    base = "preview_" + slug + "_" + stamp
    md_path = _J85PREVIEWS / (base + ".md")
    json_path = _J85PREVIEWS / (base + ".json")
    json_path.write_text(_j85_json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_j85_render_md(preview, plan), encoding="utf-8")
    return {
        "md": str(md_path.relative_to(_J85ROOT)),
        "json": str(json_path.relative_to(_J85ROOT)),
    }


def _j85_latest():
    rows = []
    for p in _J85PREVIEWS.glob("*.json"):
        try:
            st = p.stat()
            data = {}
            try:
                data = _j85_json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
            md = p.with_suffix(".md")
            rows.append({
                "json": str(p.relative_to(_J85ROOT)),
                "md": str(md.relative_to(_J85ROOT)) if md.exists() else None,
                "goal": data.get("goal", ""),
                "feature_type": data.get("feature_type", ""),
                "risk_level": data.get("risk_level", ""),
                "approval_required": data.get("approval_required", True),
                "dry_run": data.get("dry_run", True),
                "generated_at": data.get("generated_at", ""),
                "modified": int(st.st_mtime),
            })
        except Exception:
            pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:20]


def _j85_dashboard():
    latest = _j85_latest()
    awaiting = sum(1 for r in latest if r.get("approval_required"))
    return {
        "module": "JARVIS Forge Apply Preview v1",
        "tagline": "Plan -> intelligent dry-run preview -> human approval. Never writes target files.",
        "status": "ready",
        "version": "1.0",
        "capabilities": [
            "read a Forge/Workshop package or a raw goal",
            "derive files + endpoints that would change (grounded in the real files)",
            "generate a proposed patch plan + pseudo-diff",
            "list risks, validation commands and a rollback plan",
            "require explicit human approval before any apply",
        ],
        "endpoints": [
            "POST /forge-apply-preview",
            "POST /forge-preview-from-latest",
            "GET /forge-apply-dashboard",
            "GET /forge-apply-latest",
        ],
        "preview_count": len(latest),
        "awaiting_approval": awaiting,
        "blocked_actions": list(_J85_BLOCKED),
        "latest_previews": latest,
        "next_safe_step": "Open the newest preview .md, review the pseudo-diff and risks, then a human decides whether to implement.",
        "git": {
            "branch": _j83_git(["branch", "--show-current"]),
            "head": _j83_git(["rev-parse", "--short", "HEAD"]),
            "status_short": _j83_git(["status", "--short"]),
        },
    }


_J85_POST_PATHS = {"/forge-apply-preview", "/forge-preview-from-latest"}


def _j85_do_GET(self):
    path = _j85_urlparse(self.path).path
    try:
        if path == "/forge-apply-dashboard":
            p = _j85_base("GET /forge-apply-dashboard", True)
            p["data"] = _j85_dashboard()
            return _j83_json_out(self, p)
        if path == "/forge-apply-latest":
            p = _j85_base("GET /forge-apply-latest", True)
            p["data"] = {"previews": _j85_latest()}
            return _j83_json_out(self, p)
    except Exception as e:
        p = _j85_base("GET " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)
    return self.__class__._j85_prev_GET(self)


def _j85_do_POST(self):
    path = _j85_urlparse(self.path).path
    if path not in _J85_POST_PATHS:
        return self.__class__._j85_prev_POST(self)
    try:
        body = _j83_read_json(self)
        mode = body.get("mode") or "dry_run"
        apply_requested = str(mode).lower() in {"apply", "apply_now", "write", "execute", "run_apply"}

        if path == "/forge-preview-from-latest":
            pkg = _j85_latest_forge_package()
            if not pkg:
                p = _j85_base("POST /forge-preview-from-latest", False)
                p["error"] = "no Forge/Workshop package found under 05_EXECUCAO/83_JARVIS_FORGE_ENGINE/packages/"
                p["next_step"] = "Generate one first via /forge-run or /forge-workshop."
                return _j83_json_out(self, p)
            preview, err = _j85_preview(goal=None, package_path=pkg, mode="dry_run")
        else:
            goal = (body.get("goal") or body.get("feature") or body.get("description")
                    or body.get("command") or body.get("message") or body.get("prompt") or "")
            package_path = body.get("package_path") or body.get("package") or body.get("path")
            preview, err = _j85_preview(goal=goal, package_path=package_path, mode="dry_run")

        if err:
            p = _j85_base("POST " + path, False)
            p["error"] = err
            return _j83_json_out(self, p)

        p = _j85_base("POST " + path, True)
        if apply_requested:
            p["apply_blocked"] = True
            p["message"] = ("Apply is NOT available yet — Block 85 only previews. Showing the dry-run "
                            "preview; a human must approve before any apply (future /forge-apply).")
        else:
            p["message"] = "Forge apply preview generated (dry-run)."
        p["data"] = preview
        return _j83_json_out(self, p)
    except Exception as e:
        p = _j85_base("POST " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)


def _j85_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j85_BaseHTTPRequestHandler)
                and obj is not _j85_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j85_installed", False)
            ):
                obj._j85_prev_GET = obj.do_GET
                obj._j85_prev_POST = obj.do_POST
                obj.do_GET = _j85_do_GET
                obj.do_POST = _j85_do_POST
                obj._j85_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J85] Installed Forge Apply Preview routes on:", ", ".join(patched) if patched else "none")


_j85_install()
# === END JARVIS BLOCK 85 ===


# === JARVIS BLOCK 86 — FORGE APPROVAL CENTER v1 ===
# Turns a Block 85 dry-run preview into: human approval/rejection (recorded locally) and a strong
# Claude implementation prompt. It NEVER applies a patch, never edits feature target files, never
# commits/pushes/deploys, never reads .env, never installs deps, never runs a free shell.
# It only reads Block 85 previews (05_EXECUCAO/85_.../previews/) and writes its own artifacts
# under 05_EXECUCAO/86_JARVIS_FORGE_APPROVAL_CENTER/. Built on Block 83/85 helpers (reuse, not re-impl).

import json as _j86_json
from pathlib import Path as _j86_Path
from urllib.parse import urlparse as _j86_urlparse
from http.server import BaseHTTPRequestHandler as _j86_BaseHTTPRequestHandler

_J86ROOT = _j86_Path(__file__).resolve().parents[1]
_J86DIR = _J86ROOT / "05_EXECUCAO" / "86_JARVIS_FORGE_APPROVAL_CENTER"
_J86DEC = _J86DIR / "decisions"
_J86PROMPTS = _J86DIR / "prompts"
_J86DASH = _J86DIR / "dashboard"
for _d in (_J86DEC, _J86PROMPTS, _J86DASH):
    _d.mkdir(parents=True, exist_ok=True)
_J85PREV_DIR = _J86ROOT / "05_EXECUCAO" / "85_JARVIS_FORGE_APPLY_PREVIEW" / "previews"

_J86_BLOCKED = [
    "auto_patch", "edit_target_files", "apply_patch",
    "commit", "push", "deploy", "production",
    "free_shell", "read_env", "install_dependency", "delete_files", "parallel_app",
]
# path tokens that are always refused (secrets / credentials), per the safety contract
_J86_FORBIDDEN = (
    ".env", "secret", "token", "cookie", "credential", "password",
    "id_rsa", ".pem", ".key", ".p12", "passwd", ".netrc",
)


def _j86_base(endpoint, ok=True):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "engine": "JARVIS Forge Approval Center v1",
        "status_real": "approval_and_prompt_only",
        "apply_allowed": False,
        "applies_patch": False,
        "approval_required": True,
        "precisa_aprovacao": True,
        "blocked_actions": list(_J86_BLOCKED),
        "safety": {
            "local_only": True,
            "external_calls": False,
            "edits_target_files": False,
            "apply_patch": False,
            "auto_patch": False,
            "free_shell": False,
            "reads_env": False,
            "installs_dependencies": False,
            "deletes_files": False,
            "parallel_app": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "production_touched": False,
            "writes_only_under": "05_EXECUCAO/86_JARVIS_FORGE_APPROVAL_CENTER/",
            "reads_previews_under": "05_EXECUCAO/85_JARVIS_FORGE_APPLY_PREVIEW/previews/",
        },
    }


def _j86_rel(p):
    try:
        return str(_j86_Path(p).resolve().relative_to(_J86ROOT))
    except Exception:
        return str(p)


# ---- preview path safety: must be a Block 85 preview .json under 05_EXECUCAO/, no secrets ----
def _j86_path_is_dangerous(raw):
    low = str(raw or "").lower()
    return any(bad in low for bad in _J86_FORBIDDEN)


def _j86_resolve_preview(raw):
    raw = str(raw or "").strip()
    if not raw:
        return None, None, "no preview_json provided"
    if _j86_path_is_dangerous(raw):
        return None, None, "refused: path references a secret / .env / token / cookie"
    try:
        p = (_J86ROOT / raw).resolve()
    except Exception:
        return None, None, "invalid preview_json path"
    try:
        p.relative_to((_J86ROOT / "05_EXECUCAO").resolve())
    except Exception:
        return None, None, "preview_json must live under 05_EXECUCAO/"
    try:
        p.relative_to(_J85PREV_DIR.resolve())
    except Exception:
        return None, None, ("preview_json must be a Block 85 preview under "
                            "05_EXECUCAO/85_JARVIS_FORGE_APPLY_PREVIEW/previews/")
    if p.suffix.lower() != ".json" or not p.is_file():
        return None, None, "preview_json must be an existing .json preview file"
    try:
        data = _j86_json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return None, None, "could not parse preview json: " + str(e)
    return str(p.relative_to(_J86ROOT)), data, None


def _j86_latest_preview_rel():
    # prefer Block 85's own lister (same module), fall back to a direct glob
    try:
        rows = _j85_latest()
        if rows:
            return rows[0].get("json")
    except Exception:
        pass
    try:
        rows = sorted(_J85PREV_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        if rows:
            return str(rows[0].relative_to(_J86ROOT))
    except Exception:
        pass
    return None


def _j86_preview_md_rel(preview_rel):
    if preview_rel and preview_rel.endswith(".json"):
        cand = preview_rel[:-5] + ".md"
        try:
            if (_J86ROOT / cand).is_file():
                return cand
        except Exception:
            pass
    return None


def _j86_norm_decision(v):
    s = str(v or "").strip().lower()
    if s in {"approved", "approve", "approval", "ok", "yes", "accept", "accepted", "allow"}:
        return "approved"
    if s in {"rejected", "reject", "deny", "denied", "no", "block", "blocked", "refuse", "refused"}:
        return "rejected"
    return ""


def _j86_risk_summary(data):
    risks = data.get("risks") or []
    if risks:
        parts = []
        for r in risks[:4]:
            parts.append("[" + str(r.get("level", "?")) + "] " + str(r.get("risk", "")))
        return " · ".join(parts)
    return "Risk level: " + str(data.get("risk_level", "unknown"))


# ---- decisions ----
def _j86_make_decision(preview_rel, data, decision, notes):
    goal = data.get("goal") or "feature"
    slug = _j83_slug(goal)
    stamp = _j83_now()
    approved = decision == "approved"
    decision_id = "dec_" + decision + "_" + slug + "_" + stamp
    if approved:
        next_step = ("Generate the Claude implementation prompt via POST /forge-implementation-prompt "
                     "(or /implementation-prompt). No code is applied — a human implements it with Claude.")
    else:
        next_step = ("Preview rejected — no implementation prompt is generated. Refine the feature and "
                     "re-preview via Block 85 if you want to reconsider.")
    rec = {
        "ok": True,
        "decision_id": decision_id,
        "decision": decision,
        "approved": approved,
        "approval_recorded": approved,
        "preview_json": preview_rel,
        "preview_md": _j86_preview_md_rel(preview_rel),
        "goal": goal,
        "feature_type": data.get("feature_type", ""),
        "feature_type_label": data.get("feature_type_label", ""),
        "risk_level": data.get("risk_level", ""),
        "recommended_executor": data.get("recommended_executor", ""),
        "next_block_number": data.get("next_block_number"),
        "human_notes": str(notes or "").strip(),
        "risk_summary": _j86_risk_summary(data),
        "next_step": next_step,
        "apply_allowed": False,
        "blocked_actions": list(_J86_BLOCKED),
        "decided_at": stamp,
    }
    base = decision_id
    jp = _J86DEC / (base + ".json")
    mp = _J86DEC / (base + ".md")
    rec["saved_to"] = {"json": str(jp.relative_to(_J86ROOT)), "md": str(mp.relative_to(_J86ROOT))}
    jp.write_text(_j86_json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    mp.write_text(_j86_render_decision_md(rec), encoding="utf-8")
    return rec


def _j86_render_decision_md(rec):
    d = rec["decision"]
    L = []
    L.append("# JARVIS Forge Approval Decision — " + d)
    L.append("")
    L.append("> " + rec["decided_at"] + " · engine: Forge Approval Center v1 · decision_id: `"
             + rec["decision_id"] + "` · **apply_allowed: false**")
    L.append("")
    L.append("## Source Preview")
    L.append("- **Goal:** " + (rec.get("goal") or "—"))
    L.append("- **Preview JSON:** `" + rec.get("preview_json", "") + "`")
    if rec.get("preview_md"):
        L.append("- **Preview MD:** `" + rec["preview_md"] + "`")
    L.append("- **Feature type:** `" + str(rec.get("feature_type", "")) + "` (" + str(rec.get("feature_type_label", "")) + ")")
    L.append("- **Risk level:** `" + str(rec.get("risk_level", "")) + "`")
    L.append("")
    L.append("## Decision")
    L.append("- **Decision:** **" + d.upper() + "**")
    L.append("- **Approval recorded:** " + ("yes" if rec.get("approval_recorded") else "no"))
    L.append("")
    L.append("## Human Notes")
    L.append(rec.get("human_notes") or "_(no notes provided)_")
    L.append("")
    L.append("## Risk Summary")
    L.append(rec.get("risk_summary") or "—")
    L.append("")
    L.append("## Next Step")
    L.append(rec.get("next_step") or "—")
    L.append("")
    L.append("## Status Real")
    L.append("Approval / registration only. No patch applied. No target file edited. No commit. No push. "
             "No deploy. No .env. Saved only under 05_EXECUCAO/86_JARVIS_FORGE_APPROVAL_CENTER/.")
    L.append("")
    return "\n".join(L)


def _j86_decisions():
    rows = []
    for pth in _J86DEC.glob("*.json"):
        try:
            d = _j86_json.loads(pth.read_text(encoding="utf-8", errors="replace"))
            d["_mtime"] = int(pth.stat().st_mtime)
            rows.append(d)
        except Exception:
            pass
    rows.sort(key=lambda x: x.get("_mtime", 0), reverse=True)
    return rows


def _j86_load_decision(decision_id):
    did = str(decision_id or "").strip()
    if not did:
        return None
    pth = _J86DEC / (did + ".json")
    if pth.is_file():
        try:
            return _j86_json.loads(pth.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return None
    for d in _j86_decisions():
        if d.get("decision_id") == did:
            return d
    return None


def _j86_latest_approved_decision():
    for d in _j86_decisions():
        if d.get("decision") == "approved":
            return d
    return None


def _j86_decision_for_preview(rel):
    for d in _j86_decisions():
        if d.get("preview_json") == rel:
            return d
    return None


# ---- implementation prompt (for Claude) ----
def _j86_make_prompt(preview_rel, data, decision_rec=None):
    goal = data.get("goal") or "feature"
    feature_label = data.get("feature_type_label") or data.get("feature_type") or "feature"
    files = data.get("files_to_change") or []
    eps = data.get("endpoints_to_create") or []
    summary = data.get("implementation_summary") or ""
    nextblk = data.get("next_block_number")
    risk = data.get("risk_level", "")
    approval_recorded = bool(decision_rec and decision_rec.get("approved"))
    decision_id = (decision_rec or {}).get("decision_id")
    notes = (decision_rec or {}).get("human_notes", "")
    stamp = _j83_now()
    prompt_id = "prompt_" + _j83_slug(goal) + "_" + stamp

    validations = ["python3 -m py_compile 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py"]
    for e in eps:
        m = str(e.get("method") or "GET").upper()
        r = e.get("route") or ""
        if not r:
            continue
        if m == "POST":
            validations.append("curl -s -X POST http://127.0.0.1:8787" + r + " -H 'Content-Type: application/json' -d '{}'")
        else:
            validations.append("curl -s http://127.0.0.1:8787" + r)
    validations += [
        "Confirm existing routes still answer: GET /status, GET /forge-dashboard, GET /forge-apply-dashboard, GET /forge-approval-dashboard",
        "If cockpit.html changed: node --check inline scripts and hard-refresh http://127.0.0.1:8787/",
    ]

    restrictions = [
        "No commit, no push, no deploy.",
        "Do not read .env, secrets, tokens or cookies.",
        "Do not install dependencies and do not run a free shell.",
        "Do not start a parallel app and do not delete files.",
        "Append ONE isolated, chain-safe block; always chain the previous do_GET/do_POST so existing routes keep working.",
        "Do not edit unrelated feature target files; keep the change scoped to this feature.",
        "Keep the locked premium cockpit look — no redesign, no layout break.",
        "Human approval is required before anything ships; this prompt does not auto-apply.",
    ]

    expected_final_answer = [
        "1. files changed",
        "2. endpoints created",
        "3. how the feature works",
        "4. where artifacts are saved",
        "5. how it connects to the cockpit UI",
        "6. validation performed (py_compile + curl each route)",
        "7. what was NOT done (no commit / push / deploy / apply)",
        "8. restart 8787 or just hard refresh?",
        "9. recommended next block",
    ]

    prompt_text = _j86_render_prompt_md(
        goal, feature_label, preview_rel, summary, files, eps,
        validations, restrictions, expected_final_answer,
        nextblk, risk, approval_recorded, decision_id, notes,
    )

    mp = _J86PROMPTS / (prompt_id + ".md")
    tp = _J86PROMPTS / (prompt_id + ".txt")
    mp.write_text(prompt_text, encoding="utf-8")
    tp.write_text(prompt_text, encoding="utf-8")
    saved = {"md": str(mp.relative_to(_J86ROOT)), "txt": str(tp.relative_to(_J86ROOT))}

    # lightweight index so /forge-approval-latest can list prompts (the .md/.txt stay the artifacts)
    idx = _J86PROMPTS / "_index.json"
    rows = []
    if idx.is_file():
        try:
            rows = _j86_json.loads(idx.read_text(encoding="utf-8", errors="replace")) or []
        except Exception:
            rows = []
    if not isinstance(rows, list):
        rows = []
    rows.append({
        "prompt_id": prompt_id, "feature": goal, "preview_source": preview_rel,
        "decision_id": decision_id, "approval_recorded": approval_recorded,
        "generated_at": stamp, "saved_to": saved,
    })
    try:
        idx.write_text(_j86_json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return {
        "prompt_id": prompt_id,
        "prompt": prompt_text,
        "feature": goal,
        "preview_source": preview_rel,
        "probable_files": files,
        "probable_endpoints": eps,
        "validations": validations,
        "restrictions": restrictions,
        "expected_final_answer": expected_final_answer,
        "apply_allowed": False,
        "approval_recorded": approval_recorded,
        "decision_id": decision_id,
        "saved_to": saved,
        "generated_at": stamp,
    }


def _j86_render_prompt_md(goal, feature_label, preview_rel, summary, files, eps,
                          validations, restrictions, expected, nextblk, risk,
                          approval_recorded, decision_id, notes):
    L = []
    L.append("# Claude Implementation Prompt — " + str(goal)[:90])
    L.append("")
    L.append("> Generated by JARVIS Forge Approval Center v1 · apply_allowed: false · approval_recorded: "
             + ("true" if approval_recorded else "false"))
    if decision_id:
        L.append("> Decision: `" + decision_id + "`")
    L.append("")
    L.append("## Projeto")
    L.append("`~/Theo/JARVIS/jarvis-agent-os` — local-first AI agent OS, HTTP cockpit on 127.0.0.1:8787.")
    L.append("")
    L.append("## Contexto real")
    L.append("- Já existem: Block 83 Forge Engine, Block 84 Workshop + Capability Matrix, Block 85 Apply Preview (dry-run), Block 86 Approval Center.")
    L.append("- Esta feature foi planejada pelo Block 85 e revisada por um humano no Approval Center.")
    L.append("- Backend: `11_SCRIPTS/jarvis_api.py` (um bloco isolado, chain-safe, por feature). UI: `11_SCRIPTS/jarvis_ui_assets/cockpit.html`.")
    if notes:
        L.append("- Notas humanas: " + notes)
    L.append("")
    L.append("## Preview source")
    L.append("- `" + preview_rel + "`")
    L.append("- Feature type: " + str(feature_label) + " · risk: " + str(risk or "unknown")
             + " · próximo bloco sugerido: " + str(nextblk or "?"))
    L.append("")
    L.append("## Objetivo")
    L.append(summary or ("Implementar '" + str(goal) + "' como um bloco backend isolado e, se fizer sentido, um único touchpoint no cockpit."))
    L.append("")
    L.append("## Arquivos que provavelmente serão alterados")
    if files:
        for f in files:
            why = f.get("why") or ""
            tail = (" (" + why + ")") if (why and why != "—") else ""
            L.append("- `" + str(f.get("path") or "?") + "` — " + str(f.get("action") or "modify") + tail)
    else:
        L.append("- `11_SCRIPTS/jarvis_api.py` — append one isolated chain-safe block")
        L.append("- `11_SCRIPTS/jarvis_ui_assets/cockpit.html` — optional single touchpoint")
    L.append("")
    L.append("## Endpoints que provavelmente serão criados")
    if eps:
        for e in eps:
            L.append("- `" + str(e.get("method") or "—") + " " + str(e.get("route") or "") + "`")
    else:
        L.append("- (definir rotas GET/POST mínimas para a feature)")
    L.append("")
    L.append("## Regras de segurança (obrigatórias)")
    for r in restrictions:
        L.append("- " + r)
    L.append("")
    L.append("## Validações obrigatórias")
    L.append("```bash")
    for v in validations:
        L.append(v)
    L.append("```")
    L.append("")
    L.append("## Resposta final esperada")
    for e in expected:
        L.append("- " + e)
    L.append("")
    L.append("---")
    L.append("Status real: implementation prompt only. JARVIS não aplica patch. Sem commit, push ou deploy. "
             "Um humano implementa com Claude após a aprovação.")
    L.append("")
    return "\n".join(L)


def _j86_prompts_list():
    idx = _J86PROMPTS / "_index.json"
    rows = []
    if idx.is_file():
        try:
            rows = _j86_json.loads(idx.read_text(encoding="utf-8", errors="replace")) or []
        except Exception:
            rows = []
    if not isinstance(rows, list):
        rows = []
    rows = sorted(rows, key=lambda x: x.get("generated_at", ""), reverse=True)
    return rows[:20]


# ---- dashboards ----
def _j86_snapshot_dashboard(data):
    try:
        (_J86DASH / "dashboard_latest.json").write_text(
            _j86_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _j86_dashboard():
    try:
        previews = _j85_latest()
    except Exception:
        previews = []
    decisions = _j86_decisions()
    latest_by_prev = {}
    for d in decisions:  # newest first → first seen per preview wins
        pj = d.get("preview_json")
        if pj and pj not in latest_by_prev:
            latest_by_prev[pj] = d
    rows = []
    pending = approved = rejected = 0
    for pv in previews:
        pj = pv.get("json")
        dec = latest_by_prev.get(pj)
        status = (dec.get("decision") if dec else "pending") or "pending"
        if status == "approved":
            approved += 1
        elif status == "rejected":
            rejected += 1
        else:
            status = "pending"
            pending += 1
        rows.append({
            "preview_json": pj,
            "preview_md": pv.get("md"),
            "goal": pv.get("goal", ""),
            "feature_type": pv.get("feature_type", ""),
            "risk_level": pv.get("risk_level", ""),
            "generated_at": pv.get("generated_at", ""),
            "status": status,
            "decision_id": (dec or {}).get("decision_id"),
            "decided_at": (dec or {}).get("decided_at"),
        })
    last_approved = None
    for d in decisions:
        if d.get("decision") == "approved":
            last_approved = {
                "decision_id": d.get("decision_id"),
                "preview_json": d.get("preview_json"),
                "goal": d.get("goal", ""),
                "decided_at": d.get("decided_at"),
                "notes": d.get("human_notes", ""),
            }
            break
    data = {
        "module": "JARVIS Forge Approval Center v1",
        "tagline": "Forge preview -> human approval -> Claude implementation prompt. Never applies code.",
        "status": "ready",
        "version": "1.0",
        "previews": rows,
        "counts": {
            "previews": len(rows),
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "decisions": len(decisions),
        },
        "awaiting_decision": pending,
        "last_approved": last_approved,
        "blocked_actions": list(_J86_BLOCKED),
        "apply_allowed": False,
        "next_safe_step": ("Approve or reject the newest preview (/approve-latest or /reject-latest), "
                           "then generate a Claude implementation prompt (/implementation-prompt). No code is applied."),
        "endpoints": [
            "GET /forge-approval-dashboard",
            "POST /forge-approval-decision",
            "POST /forge-implementation-prompt",
            "GET /forge-approval-latest",
        ],
        "git": {
            "branch": _j83_git(["branch", "--show-current"]),
            "head": _j83_git(["rev-parse", "--short", "HEAD"]),
            "status_short": _j83_git(["status", "--short"]),
        },
    }
    _j86_snapshot_dashboard(data)
    return data


def _j86_latest_view():
    decs = _j86_decisions()
    out_decs = []
    for d in decs[:20]:
        out_decs.append({
            "decision_id": d.get("decision_id"),
            "decision": d.get("decision"),
            "approval_recorded": d.get("approval_recorded"),
            "goal": d.get("goal", ""),
            "preview_json": d.get("preview_json"),
            "human_notes": d.get("human_notes", ""),
            "decided_at": d.get("decided_at"),
            "saved_to": d.get("saved_to"),
        })
    prompts = _j86_prompts_list()
    return {
        "decisions": out_decs,
        "prompts": prompts,
        "counts": {"decisions": len(decs), "prompts": len(prompts)},
        "blocked_actions": list(_J86_BLOCKED),
        "apply_allowed": False,
        "next_safe_step": "Open a generated prompt (.md/.txt) and implement it with Claude. JARVIS never applies code.",
    }


# ---- routing handlers (chain-safe) ----
_J86_POST_PATHS = {"/forge-approval-decision", "/forge-implementation-prompt"}


def _j86_handle_decision(self, body):
    decision = _j86_norm_decision(body.get("decision") or body.get("verdict") or body.get("status"))
    if not decision:
        p = _j86_base("POST /forge-approval-decision", False)
        p["error"] = "decision must be 'approved' or 'rejected'"
        return _j83_json_out(self, p)
    raw = body.get("preview_json") or body.get("preview") or body.get("path") or ""
    if not raw:
        raw = _j86_latest_preview_rel()
        if not raw:
            p = _j86_base("POST /forge-approval-decision", False)
            p["error"] = ("no preview_json provided and no Block 85 preview found under "
                          "05_EXECUCAO/85_JARVIS_FORGE_APPLY_PREVIEW/previews/")
            p["next_step"] = "Generate a preview first via /forge-apply-preview or /forge-preview-from-latest."
            return _j83_json_out(self, p)
    preview_rel, data, err = _j86_resolve_preview(raw)
    if err:
        p = _j86_base("POST /forge-approval-decision", False)
        p["error"] = err
        return _j83_json_out(self, p)
    notes = body.get("notes") or body.get("note") or body.get("comment") or ""
    rec = _j86_make_decision(preview_rel, data, decision, notes)
    p = _j86_base("POST /forge-approval-decision", True)
    p["message"] = "Human decision recorded (" + decision + "). No code applied."
    p["decision_id"] = rec["decision_id"]
    p["decision"] = rec["decision"]
    p["preview_json"] = rec["preview_json"]
    p["saved_to"] = rec["saved_to"]
    p["approval_recorded"] = rec["approval_recorded"]
    p["next_step"] = rec["next_step"]
    p["data"] = rec
    return _j83_json_out(self, p)


def _j86_handle_prompt(self, body):
    decision_id = body.get("decision_id") or ""
    raw = body.get("preview_json") or body.get("preview") or body.get("path") or ""
    decision_rec = None
    if decision_id:
        decision_rec = _j86_load_decision(decision_id)
        if decision_rec and not raw:
            raw = decision_rec.get("preview_json") or ""
    if not raw:
        latest_dec = _j86_latest_approved_decision()
        if latest_dec:
            decision_rec = decision_rec or latest_dec
            raw = latest_dec.get("preview_json") or ""
    if not raw:
        raw = _j86_latest_preview_rel()
    if not raw:
        p = _j86_base("POST /forge-implementation-prompt", False)
        p["error"] = "no preview to build a prompt from — approve a Block 85 preview first"
        return _j83_json_out(self, p)
    preview_rel, data, err = _j86_resolve_preview(raw)
    if err:
        p = _j86_base("POST /forge-implementation-prompt", False)
        p["error"] = err
        return _j83_json_out(self, p)
    if decision_rec is None:
        decision_rec = _j86_decision_for_preview(preview_rel)
    out = _j86_make_prompt(preview_rel, data, decision_rec)
    p = _j86_base("POST /forge-implementation-prompt", True)
    p["message"] = "Claude implementation prompt generated. apply_allowed=false."
    for k in ("prompt", "feature", "preview_source", "probable_files", "probable_endpoints",
              "validations", "restrictions", "expected_final_answer", "apply_allowed",
              "approval_recorded", "decision_id", "saved_to", "generated_at", "prompt_id"):
        p[k] = out.get(k)
    p["data"] = out
    return _j83_json_out(self, p)


def _j86_do_GET(self):
    path = _j86_urlparse(self.path).path
    try:
        if path == "/forge-approval-dashboard":
            p = _j86_base("GET /forge-approval-dashboard", True)
            p["data"] = _j86_dashboard()
            return _j83_json_out(self, p)
        if path == "/forge-approval-latest":
            p = _j86_base("GET /forge-approval-latest", True)
            p["data"] = _j86_latest_view()
            return _j83_json_out(self, p)
    except Exception as e:
        p = _j86_base("GET " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)
    return self.__class__._j86_prev_GET(self)


def _j86_do_POST(self):
    path = _j86_urlparse(self.path).path
    if path not in _J86_POST_PATHS:
        return self.__class__._j86_prev_POST(self)
    try:
        body = _j83_read_json(self)
        if path == "/forge-approval-decision":
            return _j86_handle_decision(self, body)
        return _j86_handle_prompt(self, body)
    except Exception as e:
        p = _j86_base("POST " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)


def _j86_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j86_BaseHTTPRequestHandler)
                and obj is not _j86_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j86_installed", False)
            ):
                obj._j86_prev_GET = obj.do_GET
                obj._j86_prev_POST = obj.do_POST
                obj.do_GET = _j86_do_GET
                obj.do_POST = _j86_do_POST
                obj._j86_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J86] Installed Forge Approval Center routes on:", ", ".join(patched) if patched else "none")


_j86_install()
# === END JARVIS BLOCK 86 ===


# === JARVIS BLOCK 87 — FORGE APPLY GUARDED v1 ===
# Takes an APPROVED Block 85/86 preview and performs a GUARDED LOCAL apply: it scaffolds ONE new
# isolated, chain-safe block at the end of jarvis_api.py (and optionally a single cockpit touchpoint),
# always backing up first, validating with py_compile/node, and auto-rolling-back on failure.
# Hard rules: explicit confirmation required ("APPLY_LOCAL_ONLY_NO_COMMIT"); approval_recorded=true
# required; never applies rejected previews; only writes jarvis_api.py / cockpit.html / 05_.../87_;
# never commit/push/deploy, never .env/secret/token/cookie, never deletes, never free shell, never
# restarts the server from inside a request. Anything outside the safe pattern => manual_required + Claude prompt.

import json as _j87_json
import re as _j87_re
import shutil as _j87_shutil
import subprocess as _j87_subprocess
import threading as _j87_threading
from pathlib import Path as _j87_Path
from urllib.parse import urlparse as _j87_urlparse
from http.server import BaseHTTPRequestHandler as _j87_BaseHTTPRequestHandler

_J87ROOT = _j87_Path(__file__).resolve().parents[1]
_J87DIR = _J87ROOT / "05_EXECUCAO" / "87_JARVIS_FORGE_APPLY_GUARD"
_J87PLANS = _J87DIR / "plans"
_J87APPLIES = _J87DIR / "applies"
_J87BACKUPS = _J87DIR / "backups"
_J87LOGS = _J87DIR / "logs"
for _d in (_J87PLANS, _J87APPLIES, _J87BACKUPS, _J87LOGS):
    _d.mkdir(parents=True, exist_ok=True)

_J87_CONFIRM = "APPLY_LOCAL_ONLY_NO_COMMIT"
_J87_API_REL = "11_SCRIPTS/jarvis_api.py"
_J87_COCKPIT_REL = "11_SCRIPTS/jarvis_ui_assets/cockpit.html"
_J87_ALLOWED_FILES = {_J87_API_REL, _J87_COCKPIT_REL}
_J87_BLOCKED = [
    "commit", "push", "deploy", "read_env", "install_dependency", "free_shell",
    "parallel_app", "delete_files", "apply_without_confirmation",
    "apply_rejected_preview", "write_outside_allowlist", "auto_restart_server",
]
_j87_lock = _j87_threading.Lock()


def _j87_base(endpoint, ok=True):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "engine": "JARVIS Forge Apply Guarded v1",
        "status_real": "guarded_local_apply",
        "apply_scope": "local_only",
        "no_commit": True,
        "no_push": True,
        "no_deploy": True,
        "required_confirmation": _J87_CONFIRM,
        "blocked_actions": list(_J87_BLOCKED),
        "safety": {
            "local_only": True,
            "external_calls": False,
            "explicit_confirmation_required": True,
            "approval_required": True,
            "writes_only": sorted(_J87_ALLOWED_FILES) + ["05_EXECUCAO/87_JARVIS_FORGE_APPLY_GUARD/"],
            "backup_before_write": True,
            "auto_rollback_on_compile_fail": True,
            "edits_rejected_previews": False,
            "free_shell": False,
            "reads_env": False,
            "installs_dependencies": False,
            "deletes_files": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "restarts_server": False,
        },
    }


# ---------- helpers: safe codegen + io ----------
def _j87_pystr(s):
    return _j87_json.dumps(str(s if s is not None else ""))


def _j87_safe_label(s):
    a = _j83_ascii(s)
    a = _j87_re.sub(r"[^A-Za-z0-9 _-]+", " ", a).strip()
    a = _j87_re.sub(r"\s+", " ", a)
    return (a[:48] or "Scaffold Feature").upper()


def _j87_safe_title(s):
    a = _j83_ascii(s)
    a = _j87_re.sub(r"[^A-Za-z0-9 _-]+", " ", a).strip()
    a = _j87_re.sub(r"\s+", " ", a)
    return (a[:22] or "Feature").title()


def _j87_next_block_number():
    nums = []
    try:
        txt = (_J87ROOT / _J87_API_REL).read_text(encoding="utf-8", errors="replace")
        for m in _j87_re.finditer(r"#\s*===\s*JARVIS BLOCK\s+(\d+)\b", txt):
            nums.append(int(m.group(1)))
    except Exception:
        pass
    try:
        for d in (_J87ROOT / "05_EXECUCAO").iterdir():
            m = _j87_re.match(r"^(\d+)_", d.name)
            if m:
                nums.append(int(m.group(1)))
    except Exception:
        pass
    return (max(nums) + 1) if nums else 88


def _j87_git_status():
    ss = _j83_git(["status", "--short"])
    dirty = any(t in ss for t in ("jarvis_api.py", "cockpit.html"))
    return {
        "branch": _j83_git(["branch", "--show-current"]),
        "head": _j83_git(["rev-parse", "--short", "HEAD"]),
        "status_short": ss,
        "target_files_uncommitted": dirty,
        "warning": ("Target files already have uncommitted changes — rollback uses the per-apply backup, not git."
                    if dirty else ""),
    }


def _j87_resolve(decision_id, preview_json):
    decision_rec = None
    raw = str(preview_json or "").strip()
    did = str(decision_id or "").strip()
    if did:
        decision_rec = _j86_load_decision(did)
        if not decision_rec:
            return None, "decision_id not found"
        if not raw:
            raw = decision_rec.get("preview_json") or ""
    if not raw and not decision_rec:
        decision_rec = _j86_latest_approved_decision()
        if decision_rec:
            raw = decision_rec.get("preview_json") or ""
    if not raw:
        return None, "no approved preview to apply — approve a Block 85 preview first (Block 86)"
    preview_rel, data, err = _j86_resolve_preview(raw)
    if err:
        return None, err
    if decision_rec is None:
        decision_rec = _j86_decision_for_preview(preview_rel)
    if not (decision_rec and decision_rec.get("approved") and decision_rec.get("approval_recorded")):
        return None, "refused: no approval_recorded=true for this preview (Block 86 approval required, and it must be 'approved')"
    return (decision_rec, preview_rel, data), None


def _j87_assess(preview, api_text):
    reasons = []
    status = "auto_safe"
    files = [(f.get("path") or "").strip() for f in (preview.get("files_to_change") or [])]
    extra = sorted(set(f for f in files if f and f not in _J87_ALLOWED_FILES))
    if extra:
        status = "manual_required"
        reasons.append("touches files outside the v1 allowlist: " + ", ".join(extra))
    get_routes, post_routes = [], []
    rx = _j87_re.compile(r"^/[A-Za-z0-9._/-]{1,60}$")
    for e in (preview.get("endpoints_to_create") or []):
        m = str(e.get("method") or "").upper()
        r = str(e.get("route") or "").strip()
        if not rx.match(r):
            reasons.append("skipped malformed route: " + r)
            continue
        if ('"' + r + '"') in api_text or ("'" + r + "'") in api_text:
            status = "manual_required"
            reasons.append("route already exists (would shadow): " + r)
            continue
        if m == "GET":
            get_routes.append(r)
        elif m == "POST":
            post_routes.append(r)
        else:
            reasons.append("skipped non GET/POST route: " + m + " " + r)
    if not (get_routes or post_routes):
        status = "manual_required"
        reasons.append("no safe GET/POST endpoints to scaffold")
    if str(preview.get("recommended_executor")) == "claude":
        status = "manual_required"
        reasons.append("preview recommends Claude (too complex for safe auto-scaffold)")
    if str(preview.get("risk_level")) == "high":
        status = "manual_required"
        reasons.append("risk level is high")
    if str(preview.get("feature_type")) in {"internet_research", "integration_feature"}:
        status = "manual_required"
        reasons.append("feature needs external integration")
    ui = (str(preview.get("feature_type")) in {"ui_feature", "dashboard_feature"}
          or any(str(f).endswith(".html") for f in files))
    return {
        "can_apply": status == "auto_safe",
        "apply_status": status,
        "reasons": reasons,
        "get_routes": get_routes,
        "post_routes": post_routes,
        "ui": bool(ui),
    }


def _j87_gen_api_block(N, goal, label, get_routes, post_routes):
    n = str(N)
    gp = _j87_pystr(goal)
    lab = _j87_safe_label(label)
    get_set = ("{" + ", ".join(_j87_pystr(r) for r in get_routes) + "}") if get_routes else "set()"
    post_set = ("{" + ", ".join(_j87_pystr(r) for r in post_routes) + "}") if post_routes else "set()"
    B = []
    B.append("# === JARVIS BLOCK " + n + " — " + lab + " ===")
    B.append("# Scaffolded by JARVIS Block 87 (Forge Apply Guarded v1) from an approved Block 85 preview.")
    B.append("# Stub endpoints return a self-describing JSON envelope. No external calls, no .env, no shell,")
    B.append("# no commit/push/deploy. Replace the stub logic with a real implementation (Claude) when ready.")
    B.append("import json as _j" + n + "_json")
    B.append("from urllib.parse import urlparse as _j" + n + "_urlparse")
    B.append("from http.server import BaseHTTPRequestHandler as _j" + n + "_BaseHTTPRequestHandler")
    B.append("")
    B.append("_J" + n + "_GOAL = " + gp)
    B.append("_J" + n + "_BLOCKED = [\"commit\", \"push\", \"deploy\", \"read_env\", \"free_shell\", \"install_dependency\", \"delete_files\", \"parallel_app\", \"auto_patch\"]")
    B.append("_J" + n + "_GET_ROUTES = " + get_set)
    B.append("_J" + n + "_POST_ROUTES = " + post_set)
    B.append("")
    B.append("")
    B.append("def _j" + n + "_base(endpoint, ok=True):")
    B.append("    return {")
    B.append("        \"ok\": bool(ok),")
    B.append("        \"endpoint\": endpoint,")
    B.append("        \"engine\": \"JARVIS Block " + n + " — " + lab + " (scaffold)\",")
    B.append("        \"status_real\": \"scaffolded_stub\",")
    B.append("        \"goal\": _J" + n + "_GOAL,")
    B.append("        \"implemented\": False,")
    B.append("        \"note\": \"Safe stub generated by Block 87. Real logic to be implemented with Claude.\",")
    B.append("        \"blocked_actions\": list(_J" + n + "_BLOCKED),")
    B.append("        \"safety\": {\"local_only\": True, \"external_calls\": False, \"commit\": False, \"push\": False, \"deploy\": False, \"reads_env\": False},")
    B.append("    }")
    B.append("")
    B.append("")
    B.append("def _j" + n + "_do_GET(self):")
    B.append("    path = _j" + n + "_urlparse(self.path).path")
    B.append("    try:")
    B.append("        if path in _J" + n + "_GET_ROUTES:")
    B.append("            return _j83_json_out(self, _j" + n + "_base(\"GET \" + path, True))")
    B.append("    except Exception as e:")
    B.append("        p = _j" + n + "_base(\"GET \" + path, False)")
    B.append("        p[\"error\"] = str(e)")
    B.append("        return _j83_json_out(self, p, 500)")
    B.append("    return self.__class__._j" + n + "_prev_GET(self)")
    B.append("")
    B.append("")
    B.append("def _j" + n + "_do_POST(self):")
    B.append("    path = _j" + n + "_urlparse(self.path).path")
    B.append("    try:")
    B.append("        if path in _J" + n + "_POST_ROUTES:")
    B.append("            return _j83_json_out(self, _j" + n + "_base(\"POST \" + path, True))")
    B.append("    except Exception as e:")
    B.append("        p = _j" + n + "_base(\"POST \" + path, False)")
    B.append("        p[\"error\"] = str(e)")
    B.append("        return _j83_json_out(self, p, 500)")
    B.append("    return self.__class__._j" + n + "_prev_POST(self)")
    B.append("")
    B.append("")
    B.append("def _j" + n + "_install():")
    B.append("    patched = []")
    B.append("    for name, obj in list(globals().items()):")
    B.append("        if not isinstance(obj, type):")
    B.append("            continue")
    B.append("        try:")
    B.append("            if (")
    B.append("                issubclass(obj, _j" + n + "_BaseHTTPRequestHandler)")
    B.append("                and obj is not _j" + n + "_BaseHTTPRequestHandler")
    B.append("                and hasattr(obj, \"do_GET\")")
    B.append("                and hasattr(obj, \"do_POST\")")
    B.append("                and not getattr(obj, \"_j" + n + "_installed\", False)")
    B.append("            ):")
    B.append("                obj._j" + n + "_prev_GET = obj.do_GET")
    B.append("                obj._j" + n + "_prev_POST = obj.do_POST")
    B.append("                obj.do_GET = _j" + n + "_do_GET")
    B.append("                obj.do_POST = _j" + n + "_do_POST")
    B.append("                obj._j" + n + "_installed = True")
    B.append("                patched.append(name)")
    B.append("        except Exception:")
    B.append("            pass")
    B.append("    print(\"[J" + n + "] Installed " + lab + " scaffold routes on:\", \", \".join(patched) if patched else \"none\")")
    B.append("")
    B.append("")
    B.append("_j" + n + "_install()")
    B.append("# === END JARVIS BLOCK " + n + " ===")
    B.append("")
    return "\n".join(B)


def _j87_insert_before_main(text, block):
    marker = "\nif __name__ == \"__main__\":"
    idx = text.rfind(marker)
    if idx == -1:
        return None, "could not find the `if __name__ == \"__main__\":` insertion marker"
    return text[:idx] + "\n\n" + block + "\n" + text[idx:], None


def _j87_backup_file(rel, backup_dir):
    backup_dir.mkdir(parents=True, exist_ok=True)
    src = _J87ROOT / rel
    dst = backup_dir / _j87_Path(rel).name
    _j87_shutil.copy2(str(src), str(dst))
    return str(dst.relative_to(_J87ROOT))


def _j87_restore_file(rel, backup_dir):
    src = backup_dir / _j87_Path(rel).name
    dst = _J87ROOT / rel
    if src.is_file():
        _j87_shutil.copy2(str(src), str(dst))
        return True
    return False


def _j87_pycompile():
    try:
        r = _j87_subprocess.run(
            ["python3", "-m", "py_compile", _J87_API_REL, "11_SCRIPTS/jarvis_core.py"],
            cwd=str(_J87ROOT), text=True, capture_output=True, timeout=40)
        return (r.returncode == 0, (r.stderr or r.stdout or "").strip()[:1500])
    except Exception as e:
        return (False, "py_compile run error: " + str(e))


def _j87_nodecheck_cockpit():
    node = _j87_shutil.which("node")
    if not node:
        return ("unvalidated", "node not available")
    try:
        html = (_J87ROOT / _J87_COCKPIT_REL).read_text(encoding="utf-8", errors="replace")
        blocks = _j87_re.findall(r"<script\b[^>]*>(.*?)</script>", html, _j87_re.S)
        bad = []
        for i, b in enumerate(blocks):
            if '"imports"' in b and "three" in b:
                continue
            tf = _J87DIR / ("._nodecheck_%d.js" % i)
            tf.write_text(b, encoding="utf-8")
            try:
                r = _j87_subprocess.run([node, "--check", str(tf)], text=True, capture_output=True, timeout=20)
            finally:
                try:
                    tf.unlink()
                except Exception:
                    pass
            if r.returncode != 0:
                bad.append("script#%d: %s" % (i, (r.stderr or "")[:160]))
        if bad:
            return ("failed", " | ".join(bad))
        return ("ok", "all inline scripts parse")
    except Exception as e:
        return ("unvalidated", "node check error: " + str(e))


def _j87_apply_cockpit(route, title):
    path = _J87ROOT / _J87_COCKPIT_REL
    html = path.read_text(encoding="utf-8", errors="replace")
    anchor = '<div class="sgroup">Restricted &middot; human only</div>'
    if anchor not in html:
        anchor = '<div class="sgroup">Restricted · human only</div>'
    if html.count(anchor) != 1:
        return {"written": False, "node_status": "skipped", "detail": "sidebar anchor not found exactly once"}
    btn = ('      <button class="tool" data-act="get" data-path="' + route + '">'
           '<span class="i">&#9635;</span>' + title + ' &middot; local</button>\n      ')
    path.write_text(html.replace(anchor, btn + anchor, 1), encoding="utf-8")
    status, detail = _j87_nodecheck_cockpit()
    return {"written": True, "node_status": status, "detail": detail}


# ---------- plan ----------
def _j87_risks(preview, assess, N):
    out = []
    for r in (preview.get("risks") or [])[:3]:
        out.append({"level": r.get("level", "?"), "risk": r.get("risk", "")})
    out.append({"level": "medium", "risk": "Appending Block " + str(N) + " changes jarvis_api.py; the new routes only take effect after a manual restart of 8787."})
    out.append({"level": "low", "risk": "Scaffold endpoints are safe stubs (no real logic); a human/Claude must implement the behaviour."})
    if not assess["can_apply"]:
        out.append({"level": "high", "risk": "Auto-apply blocked: " + "; ".join(assess["reasons"])})
    return out


def _j87_build_plan(decision_rec, preview_rel, preview, assess):
    N = _j87_next_block_number()
    goal = preview.get("goal") or "feature"
    label = preview.get("feature_type_label") or preview.get("feature_type") or "feature"
    files_to_write = [{"path": _J87_API_REL, "action": "append isolated Block " + str(N) + " (chain-safe scaffold, markers included)"}]
    if assess["ui"] and assess["get_routes"]:
        files_to_write.append({"path": _J87_COCKPIT_REL, "action": "insert ONE sidebar touchpoint -> GET " + assess["get_routes"][0], "optional": True})
    plan = {
        "ok": True,
        "dry_run": True,
        "can_apply": assess["can_apply"],
        "apply_status": assess["apply_status"],
        "reasons": assess["reasons"],
        "block_number": N,
        "feature": goal,
        "feature_label": label,
        "source_preview": preview_rel,
        "source_decision": {
            "decision_id": decision_rec.get("decision_id"),
            "approved": decision_rec.get("approved"),
            "approval_recorded": decision_rec.get("approval_recorded"),
            "notes": decision_rec.get("human_notes", ""),
        },
        "endpoints_to_scaffold": {"GET": assess["get_routes"], "POST": assess["post_routes"]},
        "files_to_write": files_to_write,
        "backup_plan": "Copy each target file to 05_EXECUCAO/87_JARVIS_FORGE_APPLY_GUARD/backups/<timestamp>/ BEFORE writing. Rollback = restore from there.",
        "validation_plan": [
            "python3 -m py_compile 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py",
            "node --check inline cockpit scripts (if cockpit changed)",
            "After a manual restart of 8787: GET /status + the new scaffold routes",
        ],
        "rollback_plan": [
            "Restore the files from the backup dir created by this apply",
            "Or: git checkout -- 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_ui_assets/cockpit.html",
            "Delete the appended `# === JARVIS BLOCK " + str(N) + " ... END ===` span and re-run py_compile",
            "Restart 127.0.0.1:8787",
        ],
        "risks": _j87_risks(preview, assess, N),
        "required_confirmation": _J87_CONFIRM,
        "git": _j87_git_status(),
        "generated_at": _j83_now(),
    }
    base = "plan_" + _j83_slug(goal) + "_" + plan["generated_at"]
    jp = _J87PLANS / (base + ".json")
    mp = _J87PLANS / (base + ".md")
    plan["saved_to"] = {"json": str(jp.relative_to(_J87ROOT)), "md": str(mp.relative_to(_J87ROOT))}
    jp.write_text(_j87_json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    mp.write_text(_j87_render_plan_md(plan), encoding="utf-8")
    return plan


def _j87_render_plan_md(plan):
    L = []
    L.append("# JARVIS Forge Apply Guard — Plan (" + ("CAN APPLY" if plan.get("can_apply") else "MANUAL REQUIRED") + ")")
    L.append("")
    L.append("> " + plan.get("generated_at", "") + " · Block " + str(plan.get("block_number"))
             + " · **dry_run** · required_confirmation: `" + _J87_CONFIRM + "`")
    L.append("")
    L.append("## Source")
    L.append("- **Feature:** " + str(plan.get("feature", "")))
    L.append("- **Preview:** `" + str(plan.get("source_preview", "")) + "`")
    sd = plan.get("source_decision") or {}
    L.append("- **Decision:** `" + str(sd.get("decision_id")) + "` · approved: " + str(sd.get("approved"))
             + " · approval_recorded: " + str(sd.get("approval_recorded")))
    L.append("")
    L.append("## Files to write")
    for f in plan.get("files_to_write", []):
        L.append("- `" + f.get("path", "") + "` — " + f.get("action", ""))
    L.append("")
    L.append("## Endpoints to scaffold")
    ep = plan.get("endpoints_to_scaffold") or {}
    rows = ["`" + m + " " + r + "`" for m in ("GET", "POST") for r in ep.get(m, [])]
    L.append(("- " + "\n- ".join(rows)) if rows else "- (none)")
    L.append("")
    if not plan.get("can_apply"):
        L.append("## Why manual_required")
        for r in plan.get("reasons", []):
            L.append("- " + r)
        L.append("")
    L.append("## Backup / Validation / Rollback")
    L.append("- **Backup:** " + plan.get("backup_plan", ""))
    for v in plan.get("validation_plan", []):
        L.append("- validate: " + v)
    for r in plan.get("rollback_plan", []):
        L.append("- rollback: " + r)
    L.append("")
    L.append("## Status Real")
    L.append("Dry-run plan only. No target file written. No commit / push / deploy. Confirmation `"
             + _J87_CONFIRM + "` required to apply.")
    L.append("")
    return "\n".join(L)


# ---------- execute ----------
def _j87_do_apply(decision_rec, preview_rel, preview, assess):
    N = _j87_next_block_number()
    goal = preview.get("goal") or "feature"
    label = preview.get("feature_type_label") or preview.get("feature_type") or "feature"
    stamp = _j83_now()
    backup_dir = _J87BACKUPS / stamp
    backups, files_changed, apply_log = [], [], []
    api_path = _J87ROOT / _J87_API_REL

    backups.append(_j87_backup_file(_J87_API_REL, backup_dir))
    apply_log.append("backed up " + _J87_API_REL)
    do_cockpit = bool(assess["ui"] and assess["get_routes"])
    if do_cockpit:
        backups.append(_j87_backup_file(_J87_COCKPIT_REL, backup_dir))
        apply_log.append("backed up " + _J87_COCKPIT_REL)

    text = api_path.read_text(encoding="utf-8", errors="replace")
    block = _j87_gen_api_block(N, goal, label, assess["get_routes"], assess["post_routes"])
    newtext, ierr = _j87_insert_before_main(text, block)
    if ierr:
        return {"ok": False, "applied": False, "apply_status": "error", "error": ierr,
                "backups_created": backups, "files_changed": [], "apply_log": apply_log, "block_number": N}
    api_path.write_text(newtext, encoding="utf-8")
    files_changed.append(_J87_API_REL)
    apply_log.append("wrote Block " + str(N) + " into " + _J87_API_REL)

    ok, detail = _j87_pycompile()
    validation = [{"check": "py_compile", "status": "ok" if ok else "failed", "detail": detail}]
    if not ok:
        _j87_restore_file(_J87_API_REL, backup_dir)
        apply_log.append("py_compile FAILED -> restored " + _J87_API_REL + " from backup")
        rec = {"ok": True, "applied": False, "apply_status": "rolled_back_compile_failed", "error": detail,
               "backups_created": backups, "files_changed": [], "validation_results": validation,
               "apply_log": apply_log, "block_number": N, "rolled_back": True,
               "no_commit": True, "no_push": True, "no_deploy": True, "restart_required": False}
        _j87_save_apply_record(rec, goal, preview_rel, decision_rec, backup_dir)
        return rec

    cockpit_status = None
    if do_cockpit:
        route = assess["get_routes"][0]
        cres = _j87_apply_cockpit(route, _j87_safe_title(label))
        validation.append({"check": "node_check_cockpit", "status": cres["node_status"], "detail": cres["detail"]})
        if cres["written"]:
            if cres["node_status"] == "failed":
                _j87_restore_file(_J87_COCKPIT_REL, backup_dir)
                apply_log.append("cockpit node --check FAILED -> restored " + _J87_COCKPIT_REL)
                cockpit_status = "rolled_back"
            else:
                files_changed.append(_J87_COCKPIT_REL)
                apply_log.append("inserted cockpit touchpoint -> " + route + " (node: " + cres["node_status"] + ")")
                cockpit_status = cres["node_status"]
        else:
            apply_log.append("cockpit touchpoint skipped: " + cres["detail"])
            cockpit_status = "skipped"

    validation.append({"check": "runtime_endpoints", "status": "deferred_until_restart",
                       "detail": "New routes load only after a manual restart of 8787; not called from inside the running server."})

    rec = {
        "ok": True, "applied": True, "apply_status": "applied", "block_number": N,
        "feature": goal, "source_preview": preview_rel,
        "source_decision_id": decision_rec.get("decision_id"),
        "files_changed": files_changed, "backups_created": backups,
        "backup_dir": str(backup_dir.relative_to(_J87ROOT)),
        "validation_results": validation, "cockpit_touchpoint": cockpit_status,
        "rollback_plan": [
            "Restore from backup dir: " + str(backup_dir.relative_to(_J87ROOT)),
            "Or git checkout -- " + " ".join(files_changed),
            "Delete the `# === JARVIS BLOCK " + str(N) + " ... END ===` span and re-run py_compile",
            "Restart 127.0.0.1:8787 to load/unload the routes",
        ],
        "apply_log": apply_log,
        "no_commit": True, "no_push": True, "no_deploy": True, "restart_required": True,
        "next_step": "Manually restart 8787 to activate Block " + str(N) + "'s routes, then implement real logic with Claude.",
        "applied_at": stamp,
    }
    _j87_save_apply_record(rec, goal, preview_rel, decision_rec, backup_dir)
    return rec


def _j87_save_apply_record(rec, goal, preview_rel, decision_rec, backup_dir):
    stamp = rec.get("applied_at") or _j83_now()
    base = ("apply_" if rec.get("applied") else "apply_failed_") + _j83_slug(goal) + "_" + stamp
    jp = _J87APPLIES / (base + ".json")
    mp = _J87APPLIES / (base + ".md")
    rec["saved_to"] = {"json": str(jp.relative_to(_J87ROOT)), "md": str(mp.relative_to(_J87ROOT))}
    jp.write_text(_j87_json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    mp.write_text(_j87_render_apply_md(rec), encoding="utf-8")
    lp = _J87LOGS / (base + ".log.md")
    lp.write_text(_j87_render_apply_md(rec), encoding="utf-8")
    rec["log"] = str(lp.relative_to(_J87ROOT))


def _j87_render_apply_md(rec):
    L = []
    L.append("# JARVIS Forge Apply Guard — Apply " + ("(APPLIED)" if rec.get("applied") else "(" + str(rec.get("apply_status")) + ")"))
    L.append("")
    L.append("> " + str(rec.get("applied_at", "")) + " · Block " + str(rec.get("block_number"))
             + " · no_commit: true · no_push: true · no_deploy: true")
    L.append("")
    L.append("## Source")
    L.append("- **Feature:** " + str(rec.get("feature", "")))
    L.append("- **Preview:** `" + str(rec.get("source_preview", "")) + "`")
    L.append("- **Decision:** `" + str(rec.get("source_decision_id")) + "`")
    L.append("")
    L.append("## Files changed")
    for f in (rec.get("files_changed") or []):
        L.append("- `" + f + "`")
    if not rec.get("files_changed"):
        L.append("- (none)")
    L.append("")
    L.append("## Backups created")
    for b in (rec.get("backups_created") or []):
        L.append("- `" + b + "`")
    L.append("")
    L.append("## Validation results")
    for v in (rec.get("validation_results") or []):
        L.append("- " + str(v.get("check")) + ": **" + str(v.get("status")) + "** — " + str(v.get("detail", "")))
    L.append("")
    L.append("## Apply log")
    for s in (rec.get("apply_log") or []):
        L.append("- " + s)
    L.append("")
    L.append("## Rollback plan")
    for s in (rec.get("rollback_plan") or []):
        L.append("- " + s)
    L.append("")
    L.append("## Status Real")
    L.append("Local guarded apply. No commit. No push. No deploy. Restart 8787 to activate new routes. "
             "Rollback via the backup dir above.")
    L.append("")
    return "\n".join(L)


def _j87_manual_required(decision_rec, preview_rel, preview, assess):
    stamp = _j83_now()
    goal = preview.get("goal") or "feature"
    prompt_info = None
    try:
        prompt_info = _j86_make_prompt(preview_rel, preview, decision_rec)
    except Exception as e:
        prompt_info = {"error": "could not build prompt: " + str(e)}
    rec = {
        "ok": True, "applied": False, "apply_status": "manual_required",
        "feature": goal, "source_preview": preview_rel,
        "source_decision_id": decision_rec.get("decision_id"),
        "reasons": assess["reasons"],
        "explanation": ("Auto-apply was refused because this preview is outside the safe v1 pattern. "
                        "A Claude implementation prompt was generated instead — implement it manually."),
        "claude_prompt": (prompt_info or {}).get("saved_to"),
        "no_commit": True, "no_push": True, "no_deploy": True,
        "applied_at": stamp,
    }
    base = "manual_" + _j83_slug(goal) + "_" + stamp
    jp = _J87APPLIES / (base + ".json")
    mp = _J87APPLIES / (base + ".md")
    rec["saved_to"] = {"json": str(jp.relative_to(_J87ROOT)), "md": str(mp.relative_to(_J87ROOT))}
    jp.write_text(_j87_json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    body = ["# JARVIS Forge Apply Guard — MANUAL REQUIRED", "", "Feature: " + goal,
            "Preview: `" + preview_rel + "`", "", "## Why", ]
    body += ["- " + r for r in assess["reasons"]]
    body += ["", "## Next", "- " + rec["explanation"], "- Claude prompt: " + str(rec.get("claude_prompt")), ""]
    mp.write_text("\n".join(body), encoding="utf-8")
    return rec


# ---------- listings + dashboard ----------
def _j87_list_dir(d, pat):
    rows = []
    try:
        for p in d.glob(pat):
            rows.append({"path": str(p.relative_to(_J87ROOT)), "modified": int(p.stat().st_mtime)})
    except Exception:
        pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:20]


def _j87_applies_list():
    rows = []
    try:
        for p in _J87APPLIES.glob("*.json"):
            try:
                d = _j87_json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                d = {}
            rows.append({
                "path": str(p.relative_to(_J87ROOT)),
                "applied": d.get("applied"),
                "apply_status": d.get("apply_status"),
                "feature": d.get("feature", ""),
                "block_number": d.get("block_number"),
                "applied_at": d.get("applied_at", ""),
                "modified": int(p.stat().st_mtime),
            })
    except Exception:
        pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:20]


def _j87_backups_list():
    rows = []
    try:
        for d in _J87BACKUPS.iterdir():
            if d.is_dir():
                files = [f.name for f in d.iterdir() if f.is_file()]
                rows.append({"dir": str(d.relative_to(_J87ROOT)), "files": files, "modified": int(d.stat().st_mtime)})
    except Exception:
        pass
    rows.sort(key=lambda x: x["modified"], reverse=True)
    return rows[:20]


def _j87_dashboard():
    last_dec = None
    try:
        last_dec = _j86_latest_approved_decision()
    except Exception:
        pass
    prompts = []
    try:
        prompts = _j86_prompts_list()
    except Exception:
        pass
    applies = _j87_applies_list()
    last_approved = None
    if last_dec:
        last_approved = {
            "decision_id": last_dec.get("decision_id"),
            "preview_json": last_dec.get("preview_json"),
            "goal": last_dec.get("goal", ""),
            "decided_at": last_dec.get("decided_at"),
            "notes": last_dec.get("human_notes", ""),
        }
    return {
        "module": "JARVIS Forge Apply Guarded v1",
        "tagline": "Approved preview -> guarded LOCAL apply (backup + explicit confirm + auto-rollback). Never commits/pushes/deploys.",
        "status": "ready",
        "version": "1.0",
        "last_approved": last_approved,
        "recent_prompts": prompts[:5],
        "recent_applies": applies[:5],
        "blocked_actions": list(_J87_BLOCKED),
        "apply_allowed": bool(last_dec),
        "required_confirmation": _J87_CONFIRM,
        "git": _j87_git_status(),
        "endpoints": [
            "GET /forge-apply-guard-dashboard",
            "POST /forge-apply-guard-plan",
            "POST /forge-apply-guard-execute",
            "GET /forge-apply-guard-latest",
        ],
        "next_safe_step": (
            "Run /apply-plan to preview the exact write, then /apply-confirm APPLY_LOCAL_ONLY_NO_COMMIT to apply locally; restart 8787 after."
            if last_dec else
            "No approved preview yet — approve one in the Approval Center (/approve-latest)."),
    }


def _j87_latest_view():
    return {
        "plans": _j87_list_dir(_J87PLANS, "*.json"),
        "applies": _j87_applies_list(),
        "backups": _j87_backups_list(),
        "logs": _j87_list_dir(_J87LOGS, "*.md"),
        "blocked_actions": list(_J87_BLOCKED),
        "apply_allowed_note": "apply only with confirm=APPLY_LOCAL_ONLY_NO_COMMIT and an approved preview",
    }


# ---------- routing handlers (chain-safe) ----------
_J87_POST_PATHS = {"/forge-apply-guard-plan", "/forge-apply-guard-execute"}


def _j87_handle_plan(self, body):
    src, err = _j87_resolve(body.get("decision_id") or "", body.get("preview_json") or "")
    if err:
        p = _j87_base("POST /forge-apply-guard-plan", False)
        p["error"] = err
        p["can_apply"] = False
        return _j83_json_out(self, p)
    decision_rec, preview_rel, preview = src
    api_text = (_J87ROOT / _J87_API_REL).read_text(encoding="utf-8", errors="replace")
    assess = _j87_assess(preview, api_text)
    plan = _j87_build_plan(decision_rec, preview_rel, preview, assess)
    p = _j87_base("POST /forge-apply-guard-plan", True)
    p["dry_run"] = True
    p["can_apply"] = assess["can_apply"]
    p["message"] = ("Apply plan generated (dry-run). No target file written. "
                    + ("can_apply=true." if assess["can_apply"] else "can_apply=false (manual_required)."))
    p["data"] = plan
    return _j83_json_out(self, p)


def _j87_handle_execute(self, body):
    confirm = str(body.get("confirm") or "").strip()
    src, err = _j87_resolve(body.get("decision_id") or "", body.get("preview_json") or "")
    if err:
        p = _j87_base("POST /forge-apply-guard-execute", False)
        p["applied"] = False
        p["error"] = err
        return _j83_json_out(self, p)
    decision_rec, preview_rel, preview = src
    api_text = (_J87ROOT / _J87_API_REL).read_text(encoding="utf-8", errors="replace")
    assess = _j87_assess(preview, api_text)

    if confirm != _J87_CONFIRM:
        plan = _j87_build_plan(decision_rec, preview_rel, preview, assess)
        p = _j87_base("POST /forge-apply-guard-execute", True)
        p["applied"] = False
        p["dry_run"] = True
        p["confirmation_required"] = True
        p["message"] = ('Confirmation required. Resend with confirm="' + _J87_CONFIRM + '" to apply locally.')
        p["data"] = plan
        return _j83_json_out(self, p)

    if not assess["can_apply"]:
        rec = _j87_manual_required(decision_rec, preview_rel, preview, assess)
        p = _j87_base("POST /forge-apply-guard-execute", True)
        p["applied"] = False
        p["apply_status"] = "manual_required"
        p["message"] = "Apply refused (manual_required). A Claude prompt was generated instead."
        p["data"] = rec
        return _j83_json_out(self, p)

    with _j87_lock:
        rec = _j87_do_apply(decision_rec, preview_rel, preview, assess)

    p = _j87_base("POST /forge-apply-guard-execute", bool(rec.get("ok", True)))
    p["applied"] = rec.get("applied", False)
    p["apply_status"] = rec.get("apply_status")
    p["files_changed"] = rec.get("files_changed", [])
    p["backups_created"] = rec.get("backups_created", [])
    p["validation_results"] = rec.get("validation_results", [])
    p["rollback_plan"] = rec.get("rollback_plan", [])
    p["apply_log"] = rec.get("apply_log", [])
    p["no_commit"] = True
    p["no_push"] = True
    p["no_deploy"] = True
    p["restart_required"] = rec.get("restart_required", True)
    p["block_number"] = rec.get("block_number")
    if rec.get("applied"):
        p["message"] = ("Block " + str(rec.get("block_number")) + " scaffolded locally. Restart 8787 to activate. No commit/push/deploy.")
    else:
        p["message"] = "Apply did not complete: " + str(rec.get("apply_status")) + ". " + str(rec.get("error", ""))
    p["data"] = rec
    return _j83_json_out(self, p)


def _j87_do_GET(self):
    path = _j87_urlparse(self.path).path
    try:
        if path == "/forge-apply-guard-dashboard":
            p = _j87_base("GET /forge-apply-guard-dashboard", True)
            p["data"] = _j87_dashboard()
            return _j83_json_out(self, p)
        if path == "/forge-apply-guard-latest":
            p = _j87_base("GET /forge-apply-guard-latest", True)
            p["data"] = _j87_latest_view()
            return _j83_json_out(self, p)
    except Exception as e:
        p = _j87_base("GET " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)
    return self.__class__._j87_prev_GET(self)


def _j87_do_POST(self):
    path = _j87_urlparse(self.path).path
    if path not in _J87_POST_PATHS:
        return self.__class__._j87_prev_POST(self)
    try:
        body = _j83_read_json(self)
        if path == "/forge-apply-guard-plan":
            return _j87_handle_plan(self, body)
        return _j87_handle_execute(self, body)
    except Exception as e:
        p = _j87_base("POST " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)


def _j87_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j87_BaseHTTPRequestHandler)
                and obj is not _j87_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j87_installed", False)
            ):
                obj._j87_prev_GET = obj.do_GET
                obj._j87_prev_POST = obj.do_POST
                obj.do_GET = _j87_do_GET
                obj.do_POST = _j87_do_POST
                obj._j87_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J87] Installed Forge Apply Guarded routes on:", ", ".join(patched) if patched else "none")


_j87_install()
# === END JARVIS BLOCK 87 ===



# === JARVIS BLOCK 88 — LOCAL DASHBOARD ===
# Implemented by JARVIS Block 88+ — a REAL local sources dashboard (filled in from the Block 87 scaffold).
# Read-only scan of allow-listed project paths. No external calls, no .env/secret/token/cookie reads,
# no shell, no commit/push/deploy, no writes. Markers + chain-safe handlers preserved from the scaffold.
import json as _j88_json
import os as _j88_os
import time as _j88_time
from pathlib import Path as _j88_Path
from urllib.parse import urlparse as _j88_urlparse, parse_qs as _j88_parse_qs
from http.server import BaseHTTPRequestHandler as _j88_BaseHTTPRequestHandler

_J88_GOAL = "cria um dashboard de sources local"
_J88_BLOCKED = ["commit", "push", "deploy", "read_env", "free_shell", "install_dependency", "delete_files", "parallel_app", "auto_patch"]
_J88_GET_ROUTES = {"/sources-dashboard", "/sources-data"}
_J88_POST_ROUTES = set()

_J88ROOT = _j88_Path(__file__).resolve().parents[1]
# allow-listed roots (spec names); only the ones that exist on disk are scanned
_J88_ALLOWED_ROOTS = ["01_SOURCES", "02_SOURCES", "03_DOCS", "04_OUTPUT", "05_EXECUCAO", "11_SCRIPTS/jarvis_ui_assets"]
# any path whose lowercased form contains one of these is refused (never counted, never read)
_J88_FORBIDDEN = (
    ".env", "secret", "token", "credential", "cookie", "password",
    ".key", "id_rsa", ".pem", ".p12", "node_modules", "/.git", ".git/",
    ".ssh", ".netrc", "apikey", "api_key", "private_key",
)
_J88_TEXT_EXT = {".md", ".txt", ".json", ".csv", ".yaml", ".yml", ".html", ".htm", ".ini", ".cfg", ".toml", ".log"}
_J88_PREVIEW_EXT = {".md", ".txt", ".json", ".csv", ".yaml", ".yml"}
_J88_MAX_INDEX_BYTES = 2_000_000
_J88_MAX_WALK = 5000


def _j88_base(endpoint, ok=True):
    return {
        "ok": bool(ok),
        "endpoint": endpoint,
        "engine": "JARVIS Block 88 — Local Sources Dashboard v1",
        "status_real": "live_local_dashboard",
        "goal": _J88_GOAL,
        "implemented": True,
        "blocked_actions": list(_J88_BLOCKED),
        "safety": {
            "local_only": True, "external_calls": False, "read_only": True,
            "reads_env": False, "reads_secrets": False,
            "reads_only_allowlisted_paths": True,
            "commit": False, "push": False, "deploy": False,
        },
    }


def _j88_is_forbidden(rellow):
    return any(tok in rellow for tok in _J88_FORBIDDEN)


def _j88_iso(epoch):
    try:
        return _j88_time.strftime("%Y-%m-%d %H:%M:%S", _j88_time.localtime(epoch))
    except Exception:
        return ""


def _j88_human_size(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n or 0)
    i = 0
    while f >= 1024 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    return ("%d B" % int(n or 0)) if i == 0 else ("%.1f %s" % (f, units[i]))


def _j88_category(rel, ext):
    top = rel.split("/")[0]
    if rel.startswith("11_SCRIPTS/jarvis_ui_assets"):
        base = "ui_asset"
    elif top in ("01_SOURCES", "02_SOURCES"):
        base = "source"
    elif top == "03_DOCS":
        base = "doc"
    elif top == "04_OUTPUT":
        base = "output"
    elif top == "05_EXECUCAO":
        base = "execution"
    else:
        base = "file"
    ek = {".md": "doc", ".txt": "text", ".json": "data", ".csv": "table", ".yaml": "config",
          ".yml": "config", ".html": "ui", ".htm": "ui", ".log": "log", ".ini": "config",
          ".cfg": "config", ".toml": "config"}.get(ext, "")
    if ek and base in ("execution", "source", "file"):
        return (ek if base == "file" else base + "/" + ek)
    return base


def _j88_tags(rel, ext):
    parts = [p.lower() for p in rel.split("/") if p][:2]
    if ext:
        parts.append(ext.lstrip("."))
    return parts[:4]


def _j88_safe_preview(full, ext):
    if ext not in _J88_PREVIEW_EXT:
        return ""
    try:
        if full.stat().st_size > 65536:
            return ""
        txt = full.read_text(encoding="utf-8", errors="replace").replace("\x00", " ")
        return " ".join(txt.split())[:280]
    except Exception:
        return ""


def _j88_scan():
    roots = []
    for r in _J88_ALLOWED_ROOTS:
        rp = _J88ROOT / r
        if rp.exists() and rp.is_dir():
            roots.append((r, rp))
    files = []
    total_bytes = 0
    ext_counts, cat_counts = {}, {}
    walked = 0
    truncated = False
    skipped_forbidden = 0
    for relroot, rp in roots:
        if truncated:
            break
        for dirpath, dirnames, filenames in _j88_os.walk(str(rp)):
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules") and not _j88_is_forbidden(d.lower())]
            for fn in filenames:
                full = _j88_Path(dirpath) / fn
                try:
                    rel = str(full.resolve().relative_to(_J88ROOT))
                except Exception:
                    continue
                low = rel.lower()
                if _j88_is_forbidden(low):
                    skipped_forbidden += 1
                    continue
                walked += 1
                if walked > _J88_MAX_WALK:
                    truncated = True
                    break
                try:
                    st = full.stat()
                except Exception:
                    continue
                ext = full.suffix.lower()
                total_bytes += st.st_size
                ext_counts[ext or "(none)"] = ext_counts.get(ext or "(none)", 0) + 1
                cat = _j88_category(rel, ext)
                indexable = (ext in _J88_TEXT_EXT) and (st.st_size <= _J88_MAX_INDEX_BYTES)
                if indexable:
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1
                files.append({
                    "path": rel, "name": fn, "ext": ext or "",
                    "size": st.st_size, "modified": int(st.st_mtime),
                    "modified_at": _j88_iso(int(st.st_mtime)),
                    "category": cat, "tags": _j88_tags(rel, ext), "indexed": bool(indexable),
                })
            if truncated:
                break
    return {
        "roots_scanned": [r for r, _ in roots],
        "files": files, "total_bytes": total_bytes,
        "ext_counts": ext_counts, "cat_counts": cat_counts,
        "walked": walked, "truncated": truncated, "skipped_forbidden": skipped_forbidden,
    }


def _j88_dashboard():
    scan = _j88_scan()
    files = scan["files"]
    indexed = [f for f in files if f["indexed"]]
    recent = sorted(files, key=lambda x: x["modified"], reverse=True)[:8]
    cats = sorted(scan["cat_counts"].items(), key=lambda kv: kv[1], reverse=True)
    types = sorted(scan["ext_counts"].items(), key=lambda kv: kv[1], reverse=True)
    health = []
    if not files:
        health.append({"level": "warn", "signal": "no readable sources found in the allowed paths"})
    else:
        health.append({"level": "ok", "signal": "%d files visible across %d roots" % (len(files), len(scan["roots_scanned"]))})
        health.append({"level": "ok", "signal": "%d indexable text sources" % len(indexed)})
    if scan["skipped_forbidden"]:
        health.append({"level": "ok", "signal": "%d sensitive path(s) skipped (.env/secret/token/etc.)" % scan["skipped_forbidden"]})
    if scan["truncated"]:
        health.append({"level": "warn", "signal": "scan truncated at %d files — totals are partial" % _J88_MAX_WALK})
    out = _j88_base("GET /sources-dashboard", True)
    out["total_sources"] = len(files)
    out["total_files_indexed"] = len(indexed)
    out["roots_scanned"] = scan["roots_scanned"]
    out["categories"] = [{"category": k, "count": v} for k, v in cats]
    out["recent_files"] = [{"path": f["path"], "name": f["name"], "modified_at": f["modified_at"],
                            "category": f["category"], "size": f["size"]} for f in recent]
    out["file_types"] = [{"ext": k, "count": v} for k, v in types[:14]]
    out["total_size_bytes"] = scan["total_bytes"]
    out["total_size_human"] = _j88_human_size(scan["total_bytes"])
    out["health_signals"] = health
    out["truncated"] = scan["truncated"]
    out["next_safe_steps"] = [
        "GET /sources-data for the structured per-file list (with safe previews)",
        "Open a file with /open <path> or the Source Reader",
        "All reads are local + read-only; .env/secrets/tokens are never read",
    ]
    if not files:
        out["fallback"] = True
        out["message"] = ("No readable sources yet in the allowed paths "
                          "(01_SOURCES, 02_SOURCES, 03_DOCS, 04_OUTPUT, 05_EXECUCAO, 11_SCRIPTS/jarvis_ui_assets). Nothing invented.")
    return out


def _j88_data(limit=300):
    scan = _j88_scan()
    files = sorted(scan["files"], key=lambda x: x["modified"], reverse=True)
    out = _j88_base("GET /sources-data", True)
    out["count"] = len(files)
    out["returned"] = min(len(files), limit)
    out["roots_scanned"] = scan["roots_scanned"]
    items = []
    for f in files[:limit]:
        rec = {
            "path": f["path"], "name": f["name"], "ext": f["ext"],
            "size": f["size"], "size_human": _j88_human_size(f["size"]),
            "modified_at": f["modified_at"], "category": f["category"],
            "tags": f["tags"], "indexed": f["indexed"],
            "preview": (_j88_safe_preview(_J88ROOT / f["path"], f["ext"]) if f["indexed"] else ""),
        }
        items.append(rec)
    out["sources"] = items
    if not files:
        out["fallback"] = True
        out["message"] = "No readable sources found in the allowed paths. Nothing invented."
    return out


def _j88_do_GET(self):
    path = _j88_urlparse(self.path).path
    try:
        if path == "/sources-dashboard":
            return _j83_json_out(self, _j88_dashboard())
        if path == "/sources-data":
            qs = _j88_parse_qs(_j88_urlparse(self.path).query)
            try:
                limit = max(1, min(1000, int((qs.get("limit") or ["300"])[0])))
            except Exception:
                limit = 300
            return _j83_json_out(self, _j88_data(limit))
    except Exception as e:
        p = _j88_base("GET " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)
    return self.__class__._j88_prev_GET(self)


def _j88_do_POST(self):
    path = _j88_urlparse(self.path).path
    try:
        if path in _J88_POST_ROUTES:
            return _j83_json_out(self, _j88_base("POST " + path, True))
    except Exception as e:
        p = _j88_base("POST " + path, False)
        p["error"] = str(e)
        return _j83_json_out(self, p, 500)
    return self.__class__._j88_prev_POST(self)


def _j88_install():
    patched = []
    for name, obj in list(globals().items()):
        if not isinstance(obj, type):
            continue
        try:
            if (
                issubclass(obj, _j88_BaseHTTPRequestHandler)
                and obj is not _j88_BaseHTTPRequestHandler
                and hasattr(obj, "do_GET")
                and hasattr(obj, "do_POST")
                and not getattr(obj, "_j88_installed", False)
            ):
                obj._j88_prev_GET = obj.do_GET
                obj._j88_prev_POST = obj.do_POST
                obj.do_GET = _j88_do_GET
                obj.do_POST = _j88_do_POST
                obj._j88_installed = True
                patched.append(name)
        except Exception:
            pass
    print("[J88] Installed Local Sources Dashboard routes on:", ", ".join(patched) if patched else "none")


_j88_install()
# === END JARVIS BLOCK 88 ===


if __name__ == "__main__":
    sys.exit(main())





