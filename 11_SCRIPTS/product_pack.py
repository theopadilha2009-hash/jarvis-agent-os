#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "05_EXECUCAO" / "43_PRODUCT_PACKS"

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9áàâãéèêíïóôõöúçñ]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:90] or "produto"

def write(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")

def main() -> int:
    goal = " ".join(sys.argv[1:]).strip()
    if not goal:
        print('uso: python3 11_SCRIPTS/product_pack.py "ideia do produto"')
        return 2

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    slug = slugify(goal)
    pkg = OUT / f"{ts}_{slug}"
    pkg.mkdir(parents=True, exist_ok=True)

    write(pkg / "01_PRODUCT_BRIEF.md", f"""
# Product Brief

## Ideia

{goal}

## Objetivo

Transformar essa ideia em um produto testável, vendável e executável com pouca enrolação.

## Usuário-alvo

- pessoa ou empresa com dor clara;
- precisa economizar tempo, vender mais, organizar operação ou automatizar tarefa repetitiva;
- aceita uma primeira versão simples se ela resolver um problema real.

## Resultado esperado da v0

Uma versão demonstrável que prove valor rápido.

## Critério de sucesso

O produto só avança se alguém entender a proposta, ver a demo e demonstrar interesse real.
""")

    write(pkg / "02_BUILD_PLAN.md", f"""
# Build Plan

## Fase 1 — Demo simples

Criar a menor versão possível que mostre o valor.

Entregáveis:

- tela ou workflow demonstrável;
- entrada simples;
- processamento visível;
- saída clara;
- status salvo em arquivo/tabela/log.

## Fase 2 — Operação real controlada

Adicionar uso com dados reais pequenos.

Entregáveis:

- histórico de execuções;
- tratamento de erro básico;
- aprovação humana quando houver envio externo;
- logs suficientes para explicar o que aconteceu.

## Fase 3 — Produto vendável

Polir a entrega.

Entregáveis:

- nome;
- promessa clara;
- página simples;
- preço inicial;
- vídeo curto de demonstração;
- checklist de implantação.

## Stack sugerida

- n8n para orquestração;
- Postgres/Supabase/Data Tables para estado;
- ChatGPT/Claude/Gemini/Ollama conforme custo;
- GitHub para versão;
- página simples para venda/demo;
- logs locais ou tabela para rastreio.
""")

    write(pkg / "03_SHIP_CHECKLIST.md", f"""
# Ship Checklist

## Antes de mostrar para alguém

- A demo abre.
- O fluxo principal roda.
- A saída é fácil de entender.
- Tem exemplo pronto.
- Não depende de explicação gigante.
- O erro comum tem mensagem clara.
- Existe próximo passo de venda/teste.

## Antes de cobrar

- Problema está claro.
- Pessoa entende o ganho.
- Existe preço inicial.
- Existe processo de entrega.
- Existe limite do que está incluso.
- Existe forma de suporte.
""")

    write(pkg / "04_OFFER_AND_SALES.md", f"""
# Oferta e Venda

## Nome provisório

{goal[:80]}

## Promessa simples

Eu configuro uma automação/sistema que reduz trabalho manual e entrega resultado visível em poucos dias.

## Oferta inicial

- setup inicial;
- demo funcional;
- ajustes pequenos;
- documentação curta;
- suporte inicial.

## Modelo de cobrança

Opção 1: setup único.

Opção 2: setup + mensalidade.

Opção 3: mensalidade com limite de uso.

## Mensagem curta de validação

Tenho uma ideia de automação/produto que resolve isso aqui: {goal}

Estou montando uma primeira demo simples. Faz sentido eu te mostrar quando estiver rodando?
""")

    write(pkg / "05_NEXT_ACTIONS.md", f"""
# Próximas ações

1. Escolher se isso será workflow, app, bot ou serviço.
2. Criar demo mínima.
3. Criar exemplo com dado fake.
4. Rodar uma vez de ponta a ponta.
5. Gravar vídeo curto ou print da demo.
6. Mostrar para uma pessoa real.
7. Anotar objeções.
8. Melhorar só o que afeta venda/uso.
""")

    print("PRODUCT_PACK_OK")
    print(f"pasta: {pkg.relative_to(ROOT)}")
    print(f"abrir: code {pkg.relative_to(ROOT)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
