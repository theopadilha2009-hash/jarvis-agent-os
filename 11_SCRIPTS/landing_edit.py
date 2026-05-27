#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import html
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEMOS = ROOT / "05_EXECUCAO/45_DEMO_PAGES"
VERSIONS = ROOT / "05_EXECUCAO/60_STUDIO/versions"
VERSIONS.mkdir(parents=True, exist_ok=True)

client = sys.argv[1].strip() if len(sys.argv) > 1 else ""
idea = sys.argv[2].strip() if len(sys.argv) > 2 else ""
request = " ".join(sys.argv[3:]).strip() if len(sys.argv) > 3 else ""

if not request:
    print("ERRO: escreve um pedido livre primeiro.")
    raise SystemExit(2)

def latest_demo():
    if not DEMOS.exists():
        return None
    dirs = [p for p in DEMOS.iterdir() if p.is_dir() and (p / "index.html").exists()]
    return sorted(dirs)[-1] if dirs else None

demo = latest_demo()
if not demo:
    print("ERRO: nenhuma landing encontrada. Rode Gerar Launch primeiro.")
    raise SystemExit(2)

index = demo / "index.html"
raw = index.read_text(encoding="utf-8")

ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
backup = VERSIONS / f"{ts}_backup_index.html"
backup.write_text(raw, encoding="utf-8")

req_low = request.lower()
brand = client or "Theo Padilha"

title = idea or "Landing page premium"
m = re.search(r"(?:t[ií]tulo|titulo)\s+(?:para|como|ser)\s+([^.,\n]+)", request, re.I)
if m:
    title = m.group(1).strip()

if "meu nome" in req_low or "theo" in req_low:
    brand = "Theo Padilha"

if "premium" in req_low:
    mood = "visual premium, moderno e mais forte"
else:
    mood = "visual melhorado pelo JARVIS"

safe_brand = html.escape(brand)
safe_title = html.escape(title)
safe_request = html.escape(request)
safe_mood = html.escape(mood)

patch_css = f"""
<style id="jarvis-edit-style">
  .jarvis-edit-hero {{
    margin: 0;
    padding: 42px 28px;
    background: radial-gradient(circle at top left, #2563eb 0%, #111827 42%, #030712 100%);
    color: #f9fafb;
    border-bottom: 1px solid rgba(255,255,255,.12);
    font-family: Arial, sans-serif;
  }}
  .jarvis-edit-top {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    max-width: 1120px;
    margin: 0 auto 28px;
  }}
  .jarvis-edit-brand {{
    font-weight: 800;
    letter-spacing: .02em;
    font-size: 18px;
  }}
  .jarvis-edit-badge {{
    border: 1px solid rgba(255,255,255,.25);
    background: rgba(255,255,255,.08);
    padding: 9px 13px;
    border-radius: 999px;
    font-size: 13px;
  }}
  .jarvis-edit-content {{
    max-width: 1120px;
    margin: 0 auto;
  }}
  .jarvis-edit-content h1 {{
    font-size: clamp(34px, 5vw, 68px);
    line-height: .95;
    margin: 0 0 18px;
    letter-spacing: -2px;
  }}
  .jarvis-edit-content p {{
    max-width: 760px;
    color: #d1d5db;
    font-size: 19px;
    line-height: 1.55;
  }}
  .jarvis-edit-actions {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 26px;
  }}
  .jarvis-edit-actions a {{
    text-decoration: none;
    background: #60a5fa;
    color: #07111f;
    padding: 14px 18px;
    border-radius: 14px;
    font-weight: 800;
  }}
  .jarvis-edit-actions a.secondary {{
    background: transparent;
    color: #f9fafb;
    border: 1px solid rgba(255,255,255,.25);
  }}
</style>
"""

hero = f"""
<!-- JARVIS_EDIT_LAYER_START -->
{patch_css}
<section class="jarvis-edit-hero">
  <div class="jarvis-edit-top">
    <div class="jarvis-edit-brand">{safe_brand}</div>
    <div class="jarvis-edit-badge">Editado pelo JARVIS Studio</div>
  </div>
  <div class="jarvis-edit-content">
    <h1>{safe_title}</h1>
    <p>{safe_mood}. Pedido aplicado: {safe_request}</p>
    <div class="jarvis-edit-actions">
      <a href="#contato">Quero conversar no WhatsApp</a>
      <a href="#proposta" class="secondary">Ver proposta</a>
    </div>
  </div>
</section>
<!-- JARVIS_EDIT_LAYER_END -->
"""

if "<!-- JARVIS_EDIT_LAYER_START -->" in raw:
    new = re.sub(
        r"<!-- JARVIS_EDIT_LAYER_START -->.*?<!-- JARVIS_EDIT_LAYER_END -->",
        hero,
        raw,
        flags=re.S
    )
elif "<body" in raw:
    new = re.sub(r"(<body[^>]*>)", r"\1\n" + hero, raw, count=1, flags=re.I)
else:
    new = hero + raw

index.write_text(new, encoding="utf-8")

subprocess.run(["open", str(index)], check=False)

print("JARVIS_LANDING_EDIT_OK")
print("landing:", index.relative_to(ROOT))
print("backup:", backup.relative_to(ROOT))
print("pedido:", request)
