#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path.cwd()

niche = " ".join(sys.argv[1:]).strip()
if not niche:
    print('uso: ./jarvis-opportunity "nicho"')
    raise SystemExit(2)

OUT = ROOT / "05_EXECUCAO/58_OPPORTUNITY"
OUT.mkdir(parents=True, exist_ok=True)

ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
file = OUT / f"{ts}_opportunity.md"

idea = f"Mini landing page + WhatsApp rastreável para {niche}"
client = f"{niche.title()} Teste"

message = f"""Oi, tudo bem?

Vi que negócios como {niche} normalmente dependem muito do WhatsApp, mas acabam perdendo interessados porque a apresentação, o link e a próxima ação ficam meio soltos.

Montei uma ideia simples: uma mini landing page com botão de WhatsApp rastreável e uma estrutura básica para captar melhor os contatos.

A ideia é começar com uma demo rápida, sem compromisso grande, só para validar se isso ajuda a gerar mais conversas boas.

Posso te mostrar uma primeira versão?"""

lines = []
lines.append("# JARVIS Opportunity")
lines.append("")
lines.append(f"Nicho: {niche}")
lines.append("")
lines.append("## Decisão rápida")
lines.append("")
lines.append(f"- Melhor ideia inicial: {idea}")
lines.append("- Motivo: fácil de demonstrar, rápido de entregar e simples de vender")
lines.append("- Produto de entrada: demo + página simples + botão WhatsApp")
lines.append("- Preço piloto: R$ 297 a R$ 700")
lines.append("- Upsell: automação WhatsApp, resumo de leads e follow-up")
lines.append("- Mensalidade possível: R$ 150 a R$ 300/mês")
lines.append("")
lines.append("## Mensagem para prospect")
lines.append("")
lines.append("```text")
lines.append(message)
lines.append("```")
lines.append("")
lines.append("## Comando para gerar pacote completo")
lines.append("")
lines.append("```bash")
lines.append(f'./jarvis-full "{client}" "{idea}"')
lines.append("```")
lines.append("")
lines.append("## Próximos passos")
lines.append("")
lines.append("1. Rodar o comando acima")
lines.append("2. Abrir demo/proposta")
lines.append("3. Copiar mensagem")
lines.append("4. Mandar para 3 negócios reais")
lines.append("5. Medir se alguém responde pedindo para ver")

file.write_text("\n".join(lines), encoding="utf-8")

print("JARVIS_OPPORTUNITY_OK")
print(f"arquivo: {file.relative_to(ROOT)}")
print("")
print("IDEIA:")
print(idea)
print("")
print("COMANDO:")
print(f'./jarvis-full "{client}" "{idea}"')
