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

if __name__ == "__main__":
    sys.exit(main())
