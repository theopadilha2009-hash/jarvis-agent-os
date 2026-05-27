#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import html

ROOT = Path.cwd()

def latest(base):
    p = ROOT / base
    dirs = [x for x in p.iterdir() if x.is_dir()] if p.exists() else []
    return sorted(dirs)[-1] if dirs else None

def read(path):
    return path.read_text(encoding="utf-8") if path and path.exists() else ""

def clean_md(text):
    skip_titles = {
        "proposta",
        "preço inicial",
        "preco inicial",
        "escopo",
    }
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if s.startswith("#"):
            s = s.lstrip("#").strip()
        if s.lower() in skip_titles:
            continue
        if s.startswith("- "):
            s = "• " + s[2:]
        lines.append(s)
    return "\n".join(lines).strip()

client = latest("05_EXECUCAO/50_CLIENT_KITS")
sell = latest("05_EXECUCAO/48_SELL_KITS")

proposta = clean_md(read(client / "01_PROPOSTA.md" if client else None))
mensagem = clean_md(read(client / "03_MENSAGEM_CLIENTE.md" if client else None))
preco = clean_md(read(sell / "03_PRECO.md" if sell else None))
escopo = clean_md(read(sell / "04_ESCOPO.md" if sell else None))

out = ROOT / "05_EXECUCAO/53_PROPOSAL_PAGES" / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_proposal_pro")
out.mkdir(parents=True, exist_ok=True)

html_doc = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Proposta Comercial — JARVIS</title>
<style>
body {{
  margin:0;
  font-family: Arial, Helvetica, sans-serif;
  background:#f3f4f6;
  color:#111827;
}}
.wrap {{
  max-width: 980px;
  margin: 0 auto;
  padding: 42px 22px;
}}
.hero {{
  background: linear-gradient(135deg, #020617, #1e293b);
  color:white;
  border-radius:28px;
  padding:42px;
  margin-bottom:22px;
  box-shadow:0 18px 45px rgba(15,23,42,.25);
}}
.badge {{
  display:inline-block;
  background:#2563eb;
  color:white;
  padding:8px 13px;
  border-radius:999px;
  font-size:13px;
  margin-bottom:14px;
}}
h1 {{
  margin:0;
  font-size:42px;
  letter-spacing:-1px;
}}
.hero p {{
  font-size:18px;
  color:#dbeafe;
  max-width:720px;
}}
.grid {{
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap:18px;
}}
.card {{
  background:white;
  border:1px solid #e5e7eb;
  border-radius:22px;
  padding:26px;
  box-shadow:0 10px 24px rgba(15,23,42,.07);
}}
.card.full {{
  grid-column:1 / -1;
}}
h2 {{
  margin-top:0;
  color:#0f172a;
  font-size:24px;
}}
.text {{
  white-space:pre-wrap;
  line-height:1.62;
  font-size:16px;
  color:#374151;
}}
.cta {{
  margin-top:22px;
  background:#16a34a;
  color:white;
  border-radius:18px;
  padding:22px;
  font-size:20px;
  font-weight:bold;
  text-align:center;
}}
.footer {{
  margin-top:20px;
  color:#6b7280;
  font-size:13px;
  text-align:center;
}}
@media(max-width:760px){{
  .grid{{grid-template-columns:1fr}}
  h1{{font-size:34px}}
}}
</style>
</head>
<body>
<div class="wrap">
  <section class="hero">
    <span class="badge">Proposta gerada pelo JARVIS</span>
    <h1>Proposta Comercial de Automação</h1>
    <p>Uma entrega enxuta para validar a ideia rápido, mostrar uma demo funcional e transformar o projeto em uma solução vendável.</p>
  </section>

  <section class="grid">
    <div class="card full">
      <h2>Resumo da proposta</h2>
      <div class="text">{html.escape(proposta)}</div>
    </div>

    <div class="card">
      <h2>Modelo de mensagem</h2>
      <div class="text">{html.escape(mensagem)}</div>
    </div>

    <div class="card">
      <h2>Investimento inicial</h2>
      <div class="text">{html.escape(preco)}</div>
    </div>

    <div class="card full">
      <h2>Escopo da entrega</h2>
      <div class="text">{html.escape(escopo)}</div>
    </div>
  </section>

  <div class="cta">Próximo passo: apresentar a demo e validar o interesse do cliente.</div>
  <div class="footer">Arquivo local gerado automaticamente. Revisar antes de enviar para cliente real.</div>
</div>
</body>
</html>
"""

(out / "index.html").write_text(html_doc, encoding="utf-8")
print("PROPOSAL_PRO_OK")
print(f"pasta: {out}")
print(f"abrir: open {out/'index.html'}")
