#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path.cwd()

idea = " ".join(sys.argv[1:]).strip()
if not idea:
    print('uso: ./jarvis-client-hunt "ideia/solução"')
    raise SystemExit(2)

OUT = ROOT / "05_EXECUCAO/56_CLIENT_HUNT"
OUT.mkdir(parents=True, exist_ok=True)

ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
file = OUT / f"{ts}_client_hunt.md"

segments = [
    {
        "name": "Academias pequenas",
        "pain": "perdem interessados no WhatsApp e não fazem follow-up",
        "angle": "mais alunos entrando sem depender só de anúncio",
        "price": "R$ 497 a R$ 1.500 setup + R$ 197/mês",
        "easy": 8,
        "money": 8,
    },
    {
        "name": "Barbearias e salões",
        "pain": "clientes chamam, perguntam preço e somem",
        "angle": "organizar pedidos, horários e retorno automático",
        "price": "R$ 297 a R$ 900 setup + R$ 150/mês",
        "easy": 9,
        "money": 7,
    },
    {
        "name": "Clínicas pequenas",
        "pain": "atendimento manual, dúvidas repetidas e leads esquecidos",
        "angle": "triagem simples e resumo para equipe",
        "price": "R$ 700 a R$ 2.000 setup + R$ 300/mês",
        "easy": 7,
        "money": 9,
    },
    {
        "name": "Oficinas mecânicas",
        "pain": "orçamentos e pedidos chegam bagunçados",
        "angle": "organizar solicitação, placa, problema e retorno",
        "price": "R$ 700 a R$ 1.800 setup + R$ 250/mês",
        "easy": 7,
        "money": 8,
    },
    {
        "name": "Imobiliárias pequenas",
        "pain": "leads de imóveis chegam sem perfil claro",
        "angle": "qualificar interesse, cidade, orçamento e urgência",
        "price": "R$ 900 a R$ 2.500 setup + R$ 300/mês",
        "easy": 6,
        "money": 9,
    },
    {
        "name": "Cursos e escolas locais",
        "pain": "interessados pedem informação e não viram matrícula",
        "angle": "capturar interesse e puxar próximo passo",
        "price": "R$ 700 a R$ 2.000 setup + R$ 250/mês",
        "easy": 7,
        "money": 8,
    },
]

def score(s):
    return s["easy"] + s["money"]

segments = sorted(segments, key=score, reverse=True)

lines = []
lines.append("# JARVIS Client Hunt")
lines.append("")
lines.append(f"Ideia: {idea}")
lines.append("")
lines.append("## Melhores tipos de cliente")
lines.append("")

for i, s in enumerate(segments, 1):
    msg = f"Oi, tudo bem? Vi que muitos negócios como {s['name'].lower()} acabam perdendo oportunidades no WhatsApp. Montei uma ideia simples para {idea}. A proposta é começar com uma demo rápida, sem complicar, e validar se economiza tempo ou ajuda a vender mais. Posso te mostrar?"
    full_cmd = f'./jarvis-full "{s["name"]} Teste" "{idea} para {s["name"].lower()}"'

    lines.append(f"### {i}. {s['name']}")
    lines.append("")
    lines.append(f"- Dor: {s['pain']}")
    lines.append(f"- Ângulo de venda: {s['angle']}")
    lines.append(f"- Preço sugerido: {s['price']}")
    lines.append(f"- Facilidade: {s['easy']}/10")
    lines.append(f"- Potencial de dinheiro: {s['money']}/10")
    lines.append(f"- Score: {score(s)}")
    lines.append("")
    lines.append("Mensagem:")
    lines.append("```text")
    lines.append(msg)
    lines.append("```")
    lines.append("")
    lines.append("Comando para gerar pacote:")
    lines.append("```bash")
    lines.append(full_cmd)
    lines.append("```")
    lines.append("")

best = segments[0]
lines.append("## Melhor alvo agora")
lines.append("")
lines.append(best["name"])
lines.append("")
lines.append("## Comando recomendado")
lines.append("")
lines.append("```bash")
lines.append(f'./jarvis-full "{best["name"]} Teste" "{idea} para {best["name"].lower()}"')
lines.append("```")

file.write_text("\n".join(lines), encoding="utf-8")

print("JARVIS_CLIENT_HUNT_OK")
print(f"arquivo: {file.relative_to(ROOT)}")
print("")
print("MELHOR ALVO:")
print(best["name"])
print("")
print("COMANDO:")
print(f'./jarvis-full "{best["name"]} Teste" "{idea} para {best["name"].lower()}"')
