#!/usr/bin/env python3
from __future__ import annotations

import re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "05_EXECUCAO" / "44_QUICK_FACTORY"

def slug(s):
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9áàâãéèêíóôõúçñ]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")[:80] or "pack"

def write(path, txt):
    path.write_text(txt.strip() + "\n", encoding="utf-8")

def pack(mode, goal):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder = OUT / f"{ts}_{mode}_{slug(goal)}"
    folder.mkdir(parents=True, exist_ok=True)

    write(folder / "00_GOAL.md", f"# Goal\n\n{goal}\n\nMode: `{mode}`")

    if mode == "n8n":
        write(folder / "01_N8N_SPEC.md", f"# n8n Spec\n\nObjetivo: {goal}\n\nEntrada:\n- webhook/manual/schedule\n\nProcessamento:\n- normalizar\n- decidir rota\n- executar ação\n- salvar log\n\nSaída:\n- resposta clara\n- registro do resultado")
        write(folder / "02_NODES.md", "# Nodes\n\nWebhook/Manual Trigger\nSet Normalizar\nCode Validar\nIF/Switch Roteamento\nAI/HTTP quando precisar\nData Table/Postgres Log\nRespond/Output")
        write(folder / "03_TEST.md", "# Teste rápido\n\n1. Rodar com dado fake\n2. Ver output\n3. Ver log salvo\n4. Ajustar campo quebrado\n5. Só depois pensar em produção")
    elif mode == "app":
        write(folder / "01_PRD.md", f"# PRD rápido\n\nProduto: {goal}\n\nUsuário:\n- quem tem dor clara\n\nDor:\n- trabalho manual\n- perda de tempo\n- falta de organização\n\nMVP:\n- uma tela\n- um input\n- uma saída útil")
        write(folder / "02_BUILD.md", "# Build\n\nStack simples:\n- React/Vite ou Next\n- SQLite/Supabase se precisar\n- deploy depois\n\nTelas:\n- Home\n- Criar\n- Resultado\n- Histórico")
        write(folder / "03_TASKS.md", "# Tasks\n\n- criar projeto\n- criar tela principal\n- salvar exemplo\n- gerar saída\n- testar fluxo\n- gravar demo")
    elif mode == "sales":
        write(folder / "01_OFFER.md", f"# Oferta\n\nIdeia: {goal}\n\nPromessa:\nEu resolvo isso com uma automação simples e entrego uma primeira versão funcional rápido.")
        write(folder / "02_MESSAGES.md", f"# Mensagens\n\nCurta:\nTenho uma ideia para automatizar isso: {goal}. Posso te mostrar uma demo simples?\n\nFollow-up:\nFiz uma prévia pequena. Se fizer sentido, ajusto para seu caso.")
        write(folder / "03_PRICE.md", "# Preço inicial\n\nOpção A: setup único\nOpção B: setup + mensalidade\nOpção C: piloto barato por 7 dias")
    elif mode == "workflow":
        write(folder / "01_FLOW.md", f"# Workflow\n\nObjetivo: {goal}\n\nFluxo:\nEntrada -> Normalizar -> Decidir -> Executar -> Log -> Resultado")
        write(folder / "02_DATA.md", "# Dados\n\nCampos mínimos:\n- id\n- origem\n- status\n- payload\n- resultado\n- erro\n- created_at")
        write(folder / "03_NEXT.md", "# Próximo\n\nCriar mock local primeiro. Depois n8n. Depois integração real.")
    elif mode == "content":
        write(folder / "01_SCRIPT.md", f"# Conteúdo\n\nTema: {goal}\n\nHook:\nVocê está perdendo tempo nisso sem perceber.\n\nCorpo:\nMostra o problema, mostra a solução, mostra exemplo.\n\nCTA:\nQuer que eu te mostre a demo?")
        write(folder / "02_SHORTS.md", "# Shorts\n\n1. Problema em 3s\n2. Demonstração em 10s\n3. Resultado em 5s\n4. CTA curto")
    elif mode == "daily":
        write(folder / "01_TODAY.md", f"# Plano do dia\n\nFoco: {goal}\n\nBloco 1: criar\nBloco 2: testar\nBloco 3: melhorar\nBloco 4: registrar")
        write(folder / "02_DONE.md", "# Feito / Pendente\n\nFeito:\n-\n\nPendente:\n-\n\nPróximo:\n-")
    else:
        write(folder / "01_GENERIC.md", f"# Pack genérico\n\n{goal}\n\nPróximo: transformar em demo mínima.")

    print("QUICK_FACTORY_OK")
    print(f"mode: {mode}")
    print(f"pasta: {folder.relative_to(ROOT)}")

def main():
    if len(sys.argv) < 3:
        print('uso: ./jarvis-fast n8n "ideia"')
        print("modos: n8n app sales workflow content daily")
        return 2
    mode = sys.argv[1].strip().lower()
    goal = " ".join(sys.argv[2:]).strip()
    pack(mode, goal)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
