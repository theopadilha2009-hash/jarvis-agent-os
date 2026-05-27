#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
import subprocess
import json
import urllib.parse
import webbrowser
import sys

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "05_EXECUCAO/60_STUDIO"
REQUESTS = STUDIO / "requests"
REQUESTS.mkdir(parents=True, exist_ok=True)

PORT = 8765

HTML = r'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>JARVIS Studio</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin:0; font-family: Arial, sans-serif; background:#0b0f19; color:#e5e7eb; }
    .wrap { max-width:1100px; margin:0 auto; padding:28px; }
    .top { display:flex; justify-content:space-between; align-items:center; gap:20px; margin-bottom:24px; }
    .badge { background:#172554; border:1px solid #2563eb; color:#bfdbfe; padding:8px 12px; border-radius:999px; font-size:13px; }
    h1 { margin:0; font-size:34px; letter-spacing:-1px; }
    p { color:#9ca3af; line-height:1.5; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    .card { background:#111827; border:1px solid #1f2937; border-radius:18px; padding:18px; box-shadow:0 18px 50px rgba(0,0,0,.25); }
    label { display:block; font-size:13px; color:#9ca3af; margin:10px 0 6px; }
    input, textarea { width:100%; box-sizing:border-box; border:1px solid #374151; background:#030712; color:#f9fafb; border-radius:12px; padding:12px; font-size:15px; outline:none; }
    textarea { min-height:125px; resize:vertical; }
    button { border:0; border-radius:12px; padding:12px 14px; margin:6px 6px 6px 0; cursor:pointer; font-weight:700; color:#07111f; background:#60a5fa; }
    button.secondary { background:#c4b5fd; }
    button.dark { background:#374151; color:#fff; }
    button.green { background:#86efac; }
    pre { white-space:pre-wrap; word-break:break-word; background:#030712; border:1px solid #1f2937; border-radius:14px; padding:14px; min-height:260px; max-height:520px; overflow:auto; color:#d1d5db; }
    .small { font-size:13px; color:#6b7280; }
    .full { grid-column:1 / -1; }
    @media(max-width:800px){ .grid{grid-template-columns:1fr;} .top{display:block;} }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>JARVIS Studio</h1>
        <p>Cria pacotes, propostas, demos e pedidos de edição sem voltar para o ChatGPT toda hora.</p>
      </div>
      <div class="badge">local • v0</div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Construir</h2>

        <label>Nicho</label>
        <input id="niche" placeholder="ex: barbearias pequenas que atendem pelo WhatsApp">

        <label>Cliente</label>
        <input id="client" placeholder="ex: Barbearia Teste">

        <label>Ideia / serviço</label>
        <input id="idea" placeholder="ex: landing page com WhatsApp rastreável">

        <label>Pedido livre</label>
        <textarea id="request" placeholder="ex: quero que você bote meu nome no topo, deixe mais premium, troque a imagem principal e gere uma proposta"></textarea>

        <div>
          <button onclick="runAction('launch')">Gerar Launch</button>
          <button onclick="runAction('full')" class="green">Gerar Pacote Completo</button>
          <button onclick="runAction('opportunity')" class="secondary">Gerar Oportunidade</button>
          <button onclick="runAction('landing_pro')" class="secondary">Gerar Landing PRO</button>
          <button onclick="runAction('save_request')" class="dark">Salvar Pedido</button>
          <button onclick="runAction('apply_landing_edit')" class="green">Aplicar Pedido na Landing</button>
        </div>
      </div>

      <div class="card">
        <h2>Operação</h2>
        <p>Use depois de gerar algo.</p>

        <button onclick="runAction('open_latest')">Abrir Último</button>
        <button onclick="runAction('copy_msg')">Copiar Mensagem</button>
        <button onclick="runAction('doctor')" class="dark">Status</button>

        <p class="small">O pedido livre ainda fica salvo como tarefa. Na próxima etapa ligamos isso ao editor da landing page.</p>
      </div>

      <div class="card full">
        <h2>Saída</h2>
        <pre id="out">JARVIS Studio pronto.</pre>
      </div>
    </div>
  </div>

<script>
function val(id){ return document.getElementById(id).value.trim(); }

function saveLocal(){
  ["niche","client","idea","request"].forEach(id => localStorage.setItem("jarvis_"+id, val(id)));
}

function loadLocal(){
  ["niche","client","idea","request"].forEach(id => {
    const v = localStorage.getItem("jarvis_"+id);
    if(v) document.getElementById(id).value = v;
  });
}

async function runAction(action){
  saveLocal();
  const out = document.getElementById("out");
  out.textContent = "Rodando " + action + "...";
  try {
    const res = await fetch("/api/run", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        action,
        niche:val("niche"),
        client:val("client"),
        idea:val("idea"),
        request:val("request")
      })
    });
    const data = await res.json();
    out.textContent = data.output || JSON.stringify(data,null,2);
  } catch(e) {
    out.textContent = "ERRO: " + e.message;
  }
}

loadLocal();
</script>
</body>
</html>'''

def now():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def run_cmd(cmd, timeout=900):
    try:
        r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT: comando demorou demais."

def write_request(data):
    file = REQUESTS / f"{now()}_pedido.md"
    text = []
    text.append("# Pedido JARVIS Studio")
    text.append("")
    text.append(f"Data: {datetime.now().isoformat(timespec='seconds')}")
    text.append(f"Nicho: {data.get('niche','')}")
    text.append(f"Cliente: {data.get('client','')}")
    text.append(f"Ideia: {data.get('idea','')}")
    text.append("")
    text.append("## Pedido livre")
    text.append("")
    text.append(data.get("request","").strip() or "Sem pedido livre.")
    text.append("")
    text.append("## Status")
    text.append("")
    text.append("Pendente de execução/edição.")
    file.write_text("\n".join(text), encoding="utf-8")
    return file

class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/" or path == "/studio":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/run":
            self.send_json({"ok": False, "output": "rota inválida"}, 404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw or "{}")

        action = data.get("action", "")
        niche = data.get("niche", "").strip()
        client = data.get("client", "").strip()
        idea = data.get("idea", "").strip()

        if action == "landing_pro":
            if not client:
                client = "Cliente Teste"
            if not idea:
                idea = "Landing page premium com WhatsApp rastreável"
            if not niche:
                niche = "negócios locais"
            code, out = run_cmd(["./jarvis-landing-pro", client, idea, niche])
            self.send_json({"ok": code == 0, "output": out})
            return

        if action == "save_request":
            file = write_request(data)
            self.send_json({"ok": True, "output": f"PEDIDO_SALVO\narquivo: {file.relative_to(ROOT)}"})
            return

        if action == "opportunity":
            if not niche:
                self.send_json({"ok": False, "output": "Preenche o nicho primeiro."})
                return
            code, out = run_cmd(["./jarvis-opportunity", niche])
            self.send_json({"ok": code == 0, "output": out})
            return

        if action == "launch":
            if not niche:
                self.send_json({"ok": False, "output": "Preenche o nicho primeiro."})
                return
            code, out = run_cmd(["./jarvis-launch", niche])
            self.send_json({"ok": code == 0, "output": out})
            return

        if action == "full":
            if not client:
                client = "Cliente Teste"
            if not idea:
                if niche:
                    idea = f"Mini landing page + WhatsApp rastreável para {niche}"
                else:
                    self.send_json({"ok": False, "output": "Preenche a ideia ou o nicho primeiro."})
                    return
            code, out = run_cmd(["./jarvis-full", client, idea])
            self.send_json({"ok": code == 0, "output": out})
            return

        if action == "apply_landing_edit":
            request = data.get("request", "").strip()
            if not request:
                self.send_json({"ok": False, "output": "Escreve um pedido livre primeiro."})
                return
            code, out = run_cmd(["python3", "11_SCRIPTS/landing_edit.py", client, idea, request])
            self.send_json({"ok": code == 0, "output": out})
            return

        if action == "open_latest":
            code, out = run_cmd(["./jarvis-open-latest"])
            self.send_json({"ok": code == 0, "output": out})
            return

        if action == "copy_msg":
            code, out = run_cmd(["./jarvis-copy-msg"])
            self.send_json({"ok": code == 0, "output": out})
            return

        if action == "doctor":
            code, out = run_cmd(["./jarvis-doctor"])
            self.send_json({"ok": code == 0, "output": out})
            return

        self.send_json({"ok": False, "output": "ação não reconhecida"})

def main():
    url = f"http://localhost:{PORT}"
    print("JARVIS_STUDIO_START")
    print("abrir:", url)
    webbrowser.open(url)
    HTTPServer(("localhost", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
