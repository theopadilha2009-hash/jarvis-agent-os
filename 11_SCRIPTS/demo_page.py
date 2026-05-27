#!/usr/bin/env python3
from __future__ import annotations

import re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "05_EXECUCAO" / "45_DEMO_PAGES"

def slug(s):
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9áàâãéèêíóôõúçñ]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")[:80] or "demo"

def main():
    idea = " ".join(sys.argv[1:]).strip()
    if not idea:
        print('uso: ./jarvis-demo "ideia"')
        return 2

    folder = OUT / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{slug(idea)}"
    folder.mkdir(parents=True, exist_ok=True)

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{idea}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:Arial;margin:0;background:#0f172a;color:#f8fafc}}
main{{max-width:900px;margin:auto;padding:60px 22px}}
h1{{font-size:44px;line-height:1.05}}
p,li{{font-size:19px;color:#cbd5e1;line-height:1.6}}
.card{{background:#111827;border:1px solid #334155;border-radius:18px;padding:24px;margin:22px 0}}
.btn{{display:inline-block;background:#38bdf8;color:#020617;padding:14px 20px;border-radius:12px;text-decoration:none;font-weight:bold}}
small{{color:#94a3b8}}
</style>
</head>
<body>
<main>
<small>DEMO MVP</small>
<h1>{idea}</h1>
<p>Uma solução simples para transformar ideia em produto testável, vendável e demonstrável.</p>

<div class="card">
<h2>O que resolve</h2>
<ul>
<li>Reduz trabalho manual.</li>
<li>Organiza operação.</li>
<li>Gera uma demo rápida para validar venda.</li>
</ul>
</div>

<div class="card">
<h2>Como funciona</h2>
<p>Entrada simples → processamento → saída clara → histórico/log.</p>
</div>

<div class="card">
<h2>Quer ver funcionando?</h2>
<p>Essa é uma prévia demonstrativa. A versão real é ajustada para cada caso.</p>
<a class="btn" href="mailto:contato@exemplo.com?subject=Quero ver a demo">Pedir demo</a>
</div>
</main>
</body>
</html>"""

    (folder / "index.html").write_text(html, encoding="utf-8")
    (folder / "README.md").write_text(f"# Demo Page\n\n{idea}\n\nAbrir:\n\n```bash\nopen index.html\n```\n", encoding="utf-8")

    print("DEMO_PAGE_OK")
    print(f"pasta: {folder.relative_to(ROOT)}")
    print(f"abrir: open {folder.relative_to(ROOT)}/index.html")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
