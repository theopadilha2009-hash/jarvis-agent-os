#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "02_SOURCES" / "DEEP_RESEARCH"
OUT_ROOT = ROOT / "05_EXECUCAO" / "62_RESEARCH_DIGEST"

KEYWORDS = [
    "n8n", "workflow", "agent", "ai agent", "subworkflow", "postgres",
    "pgvector", "redis", "chatwoot", "error trigger", "monitoring",
    "uptime", "grafana", "prometheus", "api", "webhook", "security",
    "credentials", "production", "staging", "logs", "human approval",
]

def slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:80] or "research-digest"

def read_sources():
    files = sorted(SRC_DIR.glob("*.md"))
    docs = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        docs.append((p, text))
    return docs

def headings(text: str, limit: int = 40):
    found = []
    for line in text.splitlines():
        if line.startswith("#"):
            clean = line.strip()
            if clean:
                found.append(clean)
        if len(found) >= limit:
            break
    return found

def keyword_hits(text: str):
    low = text.lower()
    hits = []
    for kw in KEYWORDS:
        count = low.count(kw.lower())
        if count:
            hits.append((kw, count))
    return sorted(hits, key=lambda x: (-x[1], x[0]))

def important_lines(text: str, limit: int = 28):
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or len(line) < 20:
            continue
        low = line.lower()
        if any(k in low for k in KEYWORDS):
            line = re.sub(r"\s+", " ", line)
            if len(line) > 220:
                line = line[:217] + "..."
            if line not in lines:
                lines.append(line)
        if len(lines) >= limit:
            break
    return lines

def write_file(path: Path, content: str):
    path.write_text(content.rstrip() + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(description="Generate local digest from 02_SOURCES/DEEP_RESEARCH.")
    ap.add_argument("--goal", default="evolução do JARVIS usando deep research locais")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    docs = read_sources()
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = OUT_ROOT / f"{ts}_{slug(args.goal)}"

    print("JARVIS — Research Digest")
    print("Status real: leitura local. Sem Claude. Sem API. Sem produção.")
    print(f"Goal: {args.goal}")
    print(f"Sources: {len(docs)} arquivo(s) em {SRC_DIR.relative_to(ROOT)}")

    if not docs:
        print("FALHA: nenhum .md encontrado em 02_SOURCES/DEEP_RESEARCH")
        raise SystemExit(1)

    if args.dry_run:
        print(f"DRY-RUN: criaria pasta {out.relative_to(ROOT)}/")
        return

    out.mkdir(parents=True, exist_ok=False)

    source_index = [
        "# Research Digest — Source Index",
        "",
        "## Status real",
        "Gerado localmente. Nenhuma API externa usada. Nenhuma produção alterada.",
        "",
        "## Fontes lidas",
    ]

    digest = [
        "# Research Digest — Deep Research para evolução do JARVIS",
        "",
        "## Status real",
        "Leitura local determinística dos arquivos em `02_SOURCES/DEEP_RESEARCH/`.",
        "Sem Claude, sem OpenAI, sem web, sem n8n real, sem produção.",
        "",
        "## Objetivo",
        args.goal,
        "",
        "## Sinais técnicos encontrados",
    ]

    for p, text in docs:
        rel = p.relative_to(ROOT)
        hs = headings(text)
        hits = keyword_hits(text)
        lines = important_lines(text)

        source_index += [
            "",
            f"### {rel}",
            f"- tamanho: {len(text)} caracteres",
            f"- headings capturados: {len(hs)}",
            "- top keywords: " + (", ".join(f"{k}({c})" for k, c in hits[:12]) if hits else "nenhuma"),
        ]

        if hs:
            source_index.append("- headings principais:")
            for h in hs[:18]:
                source_index.append(f"  - {h}")

        digest += [
            "",
            f"### {rel}",
            "",
            "**Keywords fortes:** " + (", ".join(f"{k}({c})" for k, c in hits[:12]) if hits else "nenhuma"),
            "",
            "**Trechos/sinais úteis:**",
        ]
        if lines:
            for line in lines[:18]:
                digest.append(f"- {line}")
        else:
            digest.append("- Sem linha relevante detectada por keyword; revisar manualmente se a fonte for importante.")

    evolution = f"""# JARVIS Evolution Plan — digest local

## Status real
Gerado por `./jarvis research-digest`.
Nada executado em produção. Nenhum código alterado por este digest.

## Leitura prática
Os deep research apontam que o JARVIS deve evoluir como cockpit local primeiro, com gates, arquivos, histórico e comandos auditáveis.
n8n entra depois como orquestrador/scheduler, não como cérebro que altera código sozinho.

## Plano recomendado

### v0 — Base local forte
Objetivo: melhorar comandos locais que reduzem retrabalho.
Entregas:
- `./jarvis research-digest`
- blueprints melhores
- status real claro
- safety-gate antes de commit/push

Teste:
- `python3 -m py_compile 11_SCRIPTS/*.py`
- `./jarvis research-digest --dry-run`
- `env JARVIS_NO_REPORT=1 ./jarvis safety-gate`

Critério de pronto:
- gera artefato local útil sem API e sem Claude.

### v1 — Uso real das sources
Objetivo: transformar fontes locais em decisões práticas.
Entregas:
- digest por pasta/projeto
- plano v0/v1/v2 automático
- checklist de validação por tipo de projeto

Risco:
- virar resumo genérico.

Controle:
- obrigar próximo comando seguro + arquivos prováveis + o que não fazer.

### v2 — Jarvis API local
Objetivo: expor só ações seguras para automação.
Endpoints futuros permitidos:
- `POST /digest`
- `POST /blueprint`
- `GET /status`
- `POST /safety-gate`
- `GET /next`

Bloqueado:
- commit automático
- push automático
- editar produção
- ler `.env`
- executar n8n/VPS real

### v3 — n8n loop controlado
Objetivo: n8n agenda e avisa, mas não decide sozinho.
Fluxo ideal:
1. Schedule Trigger no n8n
2. HTTP Request para Jarvis API local
3. Jarvis gera digest/blueprint/status
4. n8n envia aviso para Theo
5. Theo aprova ação real manualmente

Regra:
n8n = agenda, alerta e painel.
JARVIS = análise local e comandos seguros.
Theo = aprovação de commit/push/produção.

## Próximo passo seguro
Criar e validar o comando local `./jarvis research-digest` antes de qualquer Jarvis API ou workflow n8n.

## O que NÃO fazer agora
- Não criar workflow n8n ainda.
- Não criar API antes do comando local estar bom.
- Não deixar n8n alterar código.
- Não automatizar commit/push.
- Não usar API paga.
"""

    n8n_position = """# Onde o n8n entra no JARVIS

## Veredito
Sim, n8n faz sentido no futuro, mas só como camada de loop/orquestração.

## Não fazer
- n8n escrevendo código direto.
- n8n commitando.
- n8n dando push.
- n8n mexendo em produção.
- n8n chamando API paga sem aprovação.

## Fazer depois
Workflow simples:
Schedule Trigger → HTTP Jarvis API local → registrar resultado → avisar Theo.

## Exemplo futuro
`POST http://localhost:8787/jarvis/research-digest`

Resposta esperada:
- status
- path do artefato
- próximo passo
- precisa_aprovacao=true

## Critério para liberar n8n
Só depois que:
1. `./jarvis research-digest` estiver bom.
2. `./jarvis safety-gate` estiver confiável.
3. existir Jarvis API local com allowlist de comandos.
4. nenhum endpoint permitir commit/push/produção.
"""

    status = f"""# Status Real — Research Digest

created_at: {ts}
goal: {args.goal}
source_dir: 02_SOURCES/DEEP_RESEARCH
source_count: {len(docs)}
created: true
tested: local_generation
claude_used: false
paid_api_used: false
production_changed: false
n8n_changed: false
next_action: revisar 03_JARVIS_EVOLUTION_PLAN.md
"""

    write_file(out / "01_SOURCE_INDEX.md", "\n".join(source_index))
    write_file(out / "02_DIGEST.md", "\n".join(digest))
    write_file(out / "03_JARVIS_EVOLUTION_PLAN.md", evolution)
    write_file(out / "04_N8N_LOOP_POSITION.md", n8n_position)
    write_file(out / "05_STATUS_REAL.md", status)

    print("")
    print(f"OK — digest criado em {out.relative_to(ROOT)}/")
    print("")
    print("Arquivos:")
    for name in [
        "01_SOURCE_INDEX.md",
        "02_DIGEST.md",
        "03_JARVIS_EVOLUTION_PLAN.md",
        "04_N8N_LOOP_POSITION.md",
        "05_STATUS_REAL.md",
    ]:
        print(f"  - {out.relative_to(ROOT) / name}")
    print("")
    print("Próximo passo seguro:")
    print(f"  sed -n '1,220p' {out.relative_to(ROOT)}/03_JARVIS_EVOLUTION_PLAN.md")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
