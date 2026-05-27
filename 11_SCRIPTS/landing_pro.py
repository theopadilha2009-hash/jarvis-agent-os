#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import html
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEMOS = ROOT / "05_EXECUCAO/45_DEMO_PAGES"
LOGS = ROOT / "05_EXECUCAO/61_LANDING_PRO"

client = sys.argv[1].strip() if len(sys.argv) > 1 else "Cliente Teste"
idea = sys.argv[2].strip() if len(sys.argv) > 2 else "Landing page premium com WhatsApp rastreável"
niche = sys.argv[3].strip() if len(sys.argv) > 3 else "negócios locais"

def slug(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9áéíóúãõâêôç]+", "-", s, flags=re.I)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:90] or "landing-pro"

ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
folder = DEMOS / f"{ts}_landing-pro_{slug(client)}"
folder.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

brand = client
title = idea
subtitle = f"Uma página moderna para {niche}, feita para transformar visitantes em conversas no WhatsApp."
whatsapp = "https://wa.me/5500000000000?text=Oi%2C%20quero%20saber%20mais%20sobre%20a%20demo"

b = html.escape(brand)
t = html.escape(title)
st = html.escape(subtitle)
ni = html.escape(niche)

page = f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>{b} — Landing PRO</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Arial, sans-serif;
      background: #050816;
      color: #f8fafc;
    }}
    a {{ color: inherit; }}
    .hero {{
      min-height: 92vh;
      padding: 34px 26px 70px;
      background:
        radial-gradient(circle at 20% 20%, rgba(96,165,250,.35), transparent 28%),
        radial-gradient(circle at 80% 0%, rgba(168,85,247,.28), transparent 30%),
        linear-gradient(145deg, #050816 0%, #0f172a 45%, #020617 100%);
      overflow: hidden;
    }}
    .nav {{
      max-width: 1180px;
      margin: 0 auto 70px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }}
    .brand {{
      font-size: 20px;
      font-weight: 900;
      letter-spacing: -.03em;
    }}
    .nav-badge {{
      border: 1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.07);
      color: #cbd5e1;
      padding: 10px 14px;
      border-radius: 999px;
      font-size: 13px;
    }}
    .hero-grid {{
      max-width: 1180px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 1.1fr .9fr;
      gap: 42px;
      align-items: center;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #bfdbfe;
      background: rgba(37,99,235,.16);
      border: 1px solid rgba(96,165,250,.25);
      padding: 9px 13px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 13px;
      margin-bottom: 22px;
    }}
    h1 {{
      font-size: clamp(42px, 6vw, 78px);
      line-height: .92;
      letter-spacing: -4px;
      margin: 0 0 22px;
    }}
    .subtitle {{
      color: #cbd5e1;
      font-size: 20px;
      line-height: 1.55;
      max-width: 760px;
      margin: 0 0 30px;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin: 32px 0;
    }}
    .btn {{
      display: inline-block;
      text-decoration: none;
      padding: 16px 20px;
      border-radius: 16px;
      font-weight: 900;
      background: #60a5fa;
      color: #06101f;
      box-shadow: 0 20px 45px rgba(96,165,250,.25);
    }}
    .btn.secondary {{
      background: rgba(255,255,255,.08);
      color: #f8fafc;
      border: 1px solid rgba(255,255,255,.16);
      box-shadow: none;
    }}
    .trust {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      max-width: 720px;
      margin-top: 30px;
    }}
    .trust div {{
      border: 1px solid rgba(255,255,255,.12);
      background: rgba(255,255,255,.055);
      border-radius: 18px;
      padding: 16px;
    }}
    .trust strong {{
      display: block;
      font-size: 24px;
      margin-bottom: 4px;
    }}
    .trust span {{
      color: #94a3b8;
      font-size: 13px;
    }}
    .mockup {{
      border: 1px solid rgba(255,255,255,.13);
      background: rgba(15,23,42,.7);
      border-radius: 30px;
      padding: 18px;
      box-shadow: 0 30px 90px rgba(0,0,0,.45);
    }}
    .phone {{
      background: #020617;
      border-radius: 24px;
      padding: 20px;
      border: 1px solid rgba(255,255,255,.08);
    }}
    .screen-top {{
      display: flex;
      justify-content: space-between;
      color: #94a3b8;
      font-size: 12px;
      margin-bottom: 18px;
    }}
    .card {{
      background: linear-gradient(145deg, rgba(37,99,235,.22), rgba(168,85,247,.14));
      border: 1px solid rgba(255,255,255,.1);
      border-radius: 22px;
      padding: 22px;
      margin-bottom: 14px;
    }}
    .card h3 {{
      margin: 0 0 10px;
      font-size: 24px;
    }}
    .card p {{
      color: #cbd5e1;
      margin: 0;
      line-height: 1.45;
    }}
    .mini {{
      display: grid;
      gap: 10px;
    }}
    .mini div {{
      background: rgba(255,255,255,.06);
      border: 1px solid rgba(255,255,255,.08);
      padding: 14px;
      border-radius: 16px;
      color: #cbd5e1;
    }}
    section {{
      padding: 76px 26px;
      background: #f8fafc;
      color: #0f172a;
    }}
    .section-inner {{
      max-width: 1180px;
      margin: 0 auto;
    }}
    .section-title {{
      font-size: clamp(32px, 4vw, 52px);
      line-height: 1;
      letter-spacing: -2px;
      margin: 0 0 16px;
    }}
    .section-sub {{
      color: #475569;
      font-size: 18px;
      max-width: 760px;
      line-height: 1.55;
      margin-bottom: 34px;
    }}
    .features {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
    }}
    .feature {{
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 24px;
      padding: 24px;
      box-shadow: 0 20px 50px rgba(15,23,42,.06);
    }}
    .feature h3 {{
      margin: 0 0 10px;
      font-size: 21px;
    }}
    .feature p {{
      color: #475569;
      line-height: 1.55;
    }}
    .offer {{
      background: #0f172a;
      color: #f8fafc;
    }}
    .offer .section-sub {{ color: #cbd5e1; }}
    .price-box {{
      background: rgba(255,255,255,.08);
      border: 1px solid rgba(255,255,255,.14);
      border-radius: 28px;
      padding: 30px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 20px;
      align-items: center;
    }}
    .price {{
      font-size: 38px;
      font-weight: 950;
    }}
    footer {{
      background: #020617;
      color: #94a3b8;
      padding: 30px 26px;
      text-align: center;
    }}
    @media(max-width: 860px) {{
      .hero-grid, .features, .price-box {{
        grid-template-columns: 1fr;
      }}
      .trust {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        letter-spacing: -2px;
      }}
    }}
  </style>
</head>
<body>
  <main class="hero">
    <nav class="nav">
      <div class="brand">{b}</div>
      <div class="nav-badge">Landing demonstrativa • ajustável pelo JARVIS</div>
    </nav>

    <div class="hero-grid">
      <div>
        <div class="eyebrow">Página premium para {ni}</div>
        <h1>{t}</h1>
        <p class="subtitle">{st}</p>

        <div class="actions">
          <a class="btn" href="{whatsapp}">Chamar no WhatsApp</a>
          <a class="btn secondary" href="#proposta">Ver proposta</a>
        </div>

        <div class="trust">
          <div><strong>24h</strong><span>para validar uma primeira versão</span></div>
          <div><strong>1 página</strong><span>com foco em conversão</span></div>
          <div><strong>0 enrolação</strong><span>demo simples para vender rápido</span></div>
        </div>
      </div>

      <div class="mockup">
        <div class="phone">
          <div class="screen-top">
            <span>WhatsApp</span>
            <span>online</span>
          </div>
          <div class="card">
            <h3>Cliente interessado</h3>
            <p>“Oi, quero saber valores e horários disponíveis.”</p>
          </div>
          <div class="mini">
            <div>Lead capturado pela página</div>
            <div>Botão direto para conversa</div>
            <div>Mensagem pronta para atendimento</div>
          </div>
        </div>
      </div>
    </div>
  </main>

  <section>
    <div class="section-inner">
      <h2 class="section-title">O que essa página resolve</h2>
      <p class="section-sub">Ela tira o negócio do improviso e cria uma apresentação simples, bonita e focada em gerar conversa real pelo WhatsApp.</p>

      <div class="features">
        <div class="feature">
          <h3>Apresentação melhor</h3>
          <p>O cliente entende rapidamente quem você é, o que oferece e por que deve chamar agora.</p>
        </div>
        <div class="feature">
          <h3>WhatsApp no centro</h3>
          <p>A página leva direto para uma conversa, sem formulário complicado e sem perder o interessado.</p>
        </div>
        <div class="feature">
          <h3>Demo vendável</h3>
          <p>Você consegue mostrar uma prévia profissional antes de construir um sistema maior.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="offer" id="proposta">
    <div class="section-inner">
      <h2 class="section-title">Comece com uma versão piloto</h2>
      <p class="section-sub">A ideia é validar rápido: página demonstrativa, ajuste visual e chamada para WhatsApp. Depois dá para evoluir para automação, CRM e follow-up.</p>

      <div class="price-box">
        <div>
          <h3>Pacote inicial</h3>
          <p>Landing page demonstrativa + copy básica + CTA WhatsApp + entrega em ZIP.</p>
        </div>
        <div class="price">R$ 297+</div>
      </div>

      <div class="actions">
        <a class="btn" href="{whatsapp}">Quero essa demo</a>
      </div>
    </div>
  </section>

  <footer>
    Prévia demonstrativa gerada pelo JARVIS. Revisar dados reais antes de enviar para cliente.
  </footer>
</body>
</html>
'''

index = folder / "index.html"
readme = folder / "README.md"
index.write_text(page, encoding="utf-8")
readme.write_text(f"# Landing PRO\n\nCliente: {client}\nIdeia: {idea}\nNicho: {niche}\n", encoding="utf-8")

log = LOGS / f"{ts}_landing_pro.md"
log.write_text(f"# Landing PRO\n\nlanding: {index.relative_to(ROOT)}\ncliente: {client}\nideia: {idea}\nnicho: {niche}\n", encoding="utf-8")

subprocess.run(["open", str(index)], check=False)

print("JARVIS_LANDING_PRO_OK")
print("pasta:", folder.relative_to(ROOT))
print("abrir:", f'open "{index.relative_to(ROOT)}"')
