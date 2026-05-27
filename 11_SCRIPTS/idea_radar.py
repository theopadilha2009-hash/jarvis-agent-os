#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path.cwd()

niche = " ".join(sys.argv[1:]).strip()
if not niche:
    print('uso: ./jarvis-ideas "nicho"')
    raise SystemExit(2)

OUT = ROOT / "05_EXECUCAO/55_IDEA_RADAR"
OUT.mkdir(parents=True, exist_ok=True)

ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
file = OUT / f"{ts}_ideas.md"

ideas = [
    {
        "name": "Captura de lead WhatsApp + resumo automático",
        "pain": "dono perde mensagem, esquece de responder ou não sabe prioridade",
        "offer": "receber lead organizado com resumo e próxima ação",
        "price": "R$ 497 setup + R$ 197/mês",
        "speed": 9,
        "sale": 9,
        "difficulty": 4,
    },
    {
        "name": "Follow-up automático de orçamento parado",
        "pain": "cliente pede preço e some",
        "offer": "mensagem automática educada para recuperar venda",
        "price": "R$ 700 setup + R$ 250/mês",
        "speed": 8,
        "sale": 9,
        "difficulty": 5,
    },
    {
        "name": "Relatório diário automático para dono",
        "pain": "dono não sabe o que aconteceu no atendimento do dia",
        "offer": "resumo diário de leads, dúvidas e oportunidades",
        "price": "R$ 497 setup + R$ 150/mês",
        "speed": 9,
        "sale": 8,
        "difficulty": 3,
    },
    {
        "name": "Triagem inicial com perguntas fixas",
        "pain": "atendente perde tempo perguntando sempre a mesma coisa",
        "offer": "coletar nome, interesse, urgência e encaminhar pronto",
        "price": "R$ 700 setup + R$ 200/mês",
        "speed": 8,
        "sale": 8,
        "difficulty": 4,
    },
    {
        "name": "Mini landing page + WhatsApp rastreável",
        "pain": "negócio só manda Instagram/WhatsApp sem apresentação clara",
        "offer": "página simples com oferta, botão e mensagem pronta",
        "price": "R$ 297 a R$ 700",
        "speed": 10,
        "sale": 7,
        "difficulty": 2,
    },
    {
        "name": "Organizador de pedidos e solicitações",
        "pain": "pedidos chegam bagunçados pelo WhatsApp",
        "offer": "transformar mensagens em lista organizada",
        "price": "R$ 900 setup + R$ 300/mês",
        "speed": 7,
        "sale": 8,
        "difficulty": 6,
    },
    {
        "name": "Reativação de clientes antigos",
        "pain": "base antiga parada sem contato",
        "offer": "mensagens de reativação com controle de resposta",
        "price": "R$ 700 setup + R$ 250/mês",
        "speed": 7,
        "sale": 9,
        "difficulty": 5,
    },
]

def final_score(i):
    return i["speed"] + i["sale"] - i["difficulty"]

ideas = sorted(ideas, key=final_score, reverse=True)

lines = []
lines.append("# JARVIS Idea Radar")
lines.append("")
lines.append(f"Nicho: {niche}")
lines.append("")
lines.append("## Ranking")
lines.append("")

for idx, idea in enumerate(ideas, 1):
    full_idea = f"{idea['name']} para {niche}"
    lines.append(f"### {idx}. {idea['name']}")
    lines.append("")
    lines.append(f"- Dor: {idea['pain']}")
    lines.append(f"- Oferta: {idea['offer']}")
    lines.append(f"- Preço sugerido: {idea['price']}")
    lines.append(f"- Score: {final_score(idea)}")
    lines.append(f"- Velocidade: {idea['speed']}/10")
    lines.append(f"- Venda: {idea['sale']}/10")
    lines.append(f"- Dificuldade: {idea['difficulty']}/10")
    lines.append("")
    lines.append("Comando:")
    lines.append("```bash")
    lines.append(f'./jarvis-full "Cliente Teste" "{full_idea}"')
    lines.append("```")
    lines.append("")

best = ideas[0]
best_idea = f"{best['name']} para {niche}"

lines.append("## Melhor ideia para testar agora")
lines.append("")
lines.append(best["name"])
lines.append("")
lines.append("## Comando recomendado")
lines.append("")
lines.append("```bash")
lines.append(f'./jarvis-full "Cliente Teste" "{best_idea}"')
lines.append("```")

file.write_text("\n".join(lines), encoding="utf-8")

print("JARVIS_IDEAS_OK")
print(f"arquivo: {file.relative_to(ROOT)}")
print("")
print("MELHOR IDEIA:")
print(best["name"])
print("")
print("COMANDO:")
print(f'./jarvis-full "Cliente Teste" "{best_idea}"')
