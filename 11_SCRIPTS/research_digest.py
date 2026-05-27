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

    evolution = f"""# JARVIS Evolution Plan — Professional Digest

## Status real
Gerado por `./jarvis research-digest`.
Nada executado em produção. Nenhum código alterado por este digest.
Este arquivo é plano técnico local, não automação autônoma.

## Veredito técnico
O JARVIS deve evoluir primeiro como cockpit local auditável.
A camada n8n entra depois como orquestrador de rotina, alerta e agendamento.
Não deve existir auto-evolução com escrita real sem aprovação humana.

## Princípio de arquitetura
- JARVIS CLI = execução local segura.
- Research Digest = transformar fontes em decisão.
- Blueprint = transformar decisão em plano.
- Safety Gate = bloquear risco.
- Jarvis API futura = ponte controlada.
- n8n futuro = agenda/loop/notificação.
- Theo = aprovação final para commit, push, deploy e produção.

## Roadmap recomendado

### v0 — Digest local profissional
Objetivo: ler fontes locais e gerar decisão prática.
Entrega:
- `./jarvis research-digest`
- arquivos markdown com índice, digest, plano, posição n8n, status real e backlog técnico
- outputs gerados ignorados pelo Git, mantendo só `.gitkeep`

Teste:
- `./jarvis research-digest --dry-run`
- `./jarvis research-digest`
- `env JARVIS_NO_REPORT=1 ./jarvis safety-gate`

Critério de pronto:
- gera plano útil sem Claude, sem API e sem produção.

### v1 — Digest por projeto/pasta
Objetivo: usar o mesmo mecanismo para SWLTEC, VERITAS, Factory, Oficina etc.
Entrega futura:
- `./jarvis research-digest --source PATH --goal "..."`
- geração de plano por projeto
- checklist específico por tipo: n8n, app, suporte, workflow, produto

Critério de pronto:
- consegue ler uma pasta de fontes e gerar plano sem inventar execução.

### v2 — Jarvis API local
Objetivo: expor apenas comandos seguros para ferramentas externas.
Endpoints permitidos:
- `GET /status`
- `GET /next`
- `POST /digest`
- `POST /blueprint`
- `POST /safety-gate`

Bloqueios obrigatórios:
- sem commit automático
- sem push automático
- sem deploy
- sem ler `.env`
- sem comando shell arbitrário
- sem produção
- allowlist rígida de comandos

### v3 — n8n loop controlado
Objetivo: criar rotina automatizada sem perder controle.
Fluxo:
1. Schedule Trigger no n8n
2. HTTP Request para Jarvis API local
3. JARVIS gera digest/blueprint/status
4. n8n registra resultado
5. n8n avisa Theo
6. Theo decide a ação real

Critério de pronto:
- n8n apenas chama endpoint permitido e avisa.
- nenhuma escrita real ocorre sem aprovação.

## Matriz de decisão

| Opção | Fazer agora? | Valor | Risco | Decisão |
|------|--------------|-------|-------|---------|
| Melhorar CLI local | sim | alto | baixo | prioridade |
| Melhorar digest | sim | alto | baixo | prioridade |
| Criar Jarvis API | depois | alto | médio | aguardar CLI forte |
| Criar n8n loop | depois da API | médio/alto | médio | não agora |
| Auto-commit/push | não | baixo | alto | bloqueado |
| n8n mexer em produção | não | baixo | alto | bloqueado |

## Próximo passo seguro
Melhorar o `research-digest` para gerar backlog técnico local e critérios de pronto por fase.

## O que NÃO fazer agora
- Não criar workflow n8n ainda.
- Não criar Jarvis API antes do CLI ficar confiável.
- Não deixar n8n editar código.
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

    backlog = f"""# JARVIS Technical Backlog — próximo ciclo

## P0 — Agora
- Garantir `./jarvis research-digest` estável.
- Manter outputs em `05_EXECUCAO/62_RESEARCH_DIGEST/` ignorados no Git.
- Gerar plano local sem Claude/API.
- Rodar safety-gate antes de commit/push.

## P1 — Próximo
- Aceitar `--source PATH` para digest por projeto.
- Aceitar `--out DIR` para escolher saída.
- Criar `06_BACKLOG.md` automático.
- Criar `07_DECISION_MATRIX.md` automático.
- Fazer o `./jarvis do "..."` sugerir `research-digest` quando detectar fonte/research.

## P2 — Depois
- Criar Jarvis API local com allowlist.
- Criar workflow n8n de schedule + aviso.
- Criar painel local de últimos digests.

## Bloqueios
- Nada de produção autônoma.
- Nada de push automático.
- Nada de n8n executando shell livre.
- Nada de ler `.env`.
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
    write_file(out / "06_TECHNICAL_BACKLOG.md", backlog)

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
