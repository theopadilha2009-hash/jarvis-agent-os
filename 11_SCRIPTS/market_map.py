#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path.cwd()

niche = " ".join(sys.argv[1:]).strip()
if not niche:
    print('uso: ./jarvis-market "nicho"')
    raise SystemExit(2)

OUT = ROOT / "05_EXECUCAO/57_MARKET_MAP"
OUT.mkdir(parents=True, exist_ok=True)

ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
file = OUT / f"{ts}_market_map.md"

ideas = [
    ("Mini landing page + WhatsApp rastreável", 15, "rápido de vender e mostrar"),
    ("Captura de lead WhatsApp + resumo automático", 14, "resolve perda de atendimento"),
    ("Follow-up automático de orçamento parado", 12, "ajuda a recuperar venda"),
    ("Relatório diário automático para dono", 11, "bom para dono ocupado"),
]

clients = [
    ("Academias pequenas", "querem mais alunos e respondem muitos interessados"),
    ("Barbearias e salões", "atendem muito por WhatsApp e perdem cliente por demora"),
    ("Clínicas pequenas", "precisam organizar triagem e agenda"),
    ("Oficinas mecânicas", "recebem pedidos bagunçados e precisam registrar problema"),
]

best_idea = ideas[0]
best_client = clients[0]

solution = f"{best_idea[0]} para {niche}"
client_name = f"{best_client[0]} Teste"

message = f"""Oi, tudo bem?

Vi que negócios nesse perfil de {niche} muitas vezes perdem oportunidades porque o atendimento fica espalhado no WhatsApp.

Montei uma ideia simples: {solution}.

A ideia é começar com uma demo rápida, sem complicar, para validar se isso ajuda a captar mais interessados ou economizar tempo.

Posso te mostrar a primeira versão?"""

lines = []
lines.append("# JARVIS Market Map")
lines.append("")
lines.append(f"Nicho: {niche}")
lines.append("")
lines.append("## Melhor caminho agora")
lines.append("")
lines.append(f"- Ideia principal: {best_idea[0]}")
lines.append(f"- Motivo: {best_idea[2]}")
lines.append(f"- Cliente inicial: {best_client[0]}")
lines.append(f"- Por que vender para ele: {best_client[1]}")
lines.append(f"- Oferta: {solution}")
lines.append(f"- Preço de entrada: R$ 297 a R$ 700")
lines.append(f"- Upsell: automação WhatsApp + resumo + follow-up")
lines.append(f"- Mensalidade possível: R$ 150 a R$ 300/mês")
lines.append("")
lines.append("## Mensagem de abordagem")
lines.append("")
lines.append("```text")
lines.append(message)
lines.append("```")
lines.append("")
lines.append("## Comando para gerar pacote")
lines.append("")
lines.append("```bash")
lines.append(f'./jarvis-full "{client_name}" "{solution}"')
lines.append("```")
lines.append("")
lines.append("## Ranking de ideias")
lines.append("")
for name, score, reason in ideas:
    lines.append(f"- {name} — score {score}/15 — {reason}")
lines.append("")
lines.append("## Ranking de clientes")
lines.append("")
for name, reason in clients:
    lines.append(f"- {name} — {reason}")

file.write_text("\n".join(lines), encoding="utf-8")

print("JARVIS_MARKET_OK")
print(f"arquivo: {file.relative_to(ROOT)}")
print("")
print("MELHOR CAMINHO:")
print(solution)
print("")
print("COMANDO:")
print(f'./jarvis-full "{client_name}" "{solution}"')
