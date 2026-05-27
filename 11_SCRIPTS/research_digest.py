#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def slugify(text: str, max_len: int = 80) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9áàâãéêíóôõúç]+", "-", text, flags=re.I)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text[:max_len].strip("-") or "research-digest")


def resolve_path(value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else ROOT / p


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def read_sources(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        return []

    allowed = {".md", ".txt", ".json", ".yml", ".yaml"}
    ignored_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}

    files = []
    for p in source_dir.rglob("*"):
        if not p.is_file():
            continue
        if any(part in ignored_dirs for part in p.parts):
            continue
        if p.suffix.lower() in allowed:
            files.append(p)

    return sorted(files)


def extract_headings(text: str, limit: int = 30) -> list[str]:
    headings = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            headings.append(line.strip())
        if len(headings) >= limit:
            break
    return headings


def extract_important_lines(text: str, limit: int = 30) -> list[str]:
    keys = [
        "n8n", "workflow", "agent", "produção", "production", "api", "mcp",
        "safety", "gate", "memória", "memory", "redis", "supabase",
        "postgres", "cron", "schedule", "webhook", "erro", "risco",
        "security", "credencial", "token", "automação", "automation",
    ]
    found = []
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if not line or len(line) > 260:
            continue
        if any(k in low for k in keys):
            found.append(line)
        if len(found) >= limit:
            break
    return found


def keyword_counts(all_text: str) -> dict[str, int]:
    terms = [
        "n8n", "workflow", "agent", "api", "webhook", "schedule",
        "safety", "gate", "memory", "memória", "supabase", "postgres",
        "redis", "produção", "production", "mcp", "credentials",
        "token", "automation", "automação",
    ]
    low = all_text.lower()
    return {t: low.count(t.lower()) for t in terms if low.count(t.lower())}


def build_outputs(goal: str, source_dir: Path, files: list[Path]) -> dict[str, str]:
    chunks = []
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        chunks.append((f, txt))

    all_text = "\n\n".join(txt for _, txt in chunks)
    counts = keyword_counts(all_text)

    source_index_lines = [
        "# Research Source Index",
        "",
        f"Goal: {goal}",
        f"Source dir: `{source_dir.relative_to(ROOT) if source_dir.is_relative_to(ROOT) else source_dir}`",
        f"Files: {len(files)}",
        "",
    ]

    for f, txt in chunks:
        rel = f.relative_to(ROOT) if f.is_relative_to(ROOT) else f
        source_index_lines += [
            f"## {rel}",
            f"- Linhas: {len(txt.splitlines())}",
            f"- Caracteres: {len(txt)}",
            "",
            "Headings principais:",
        ]
        hs = extract_headings(txt, limit=12)
        source_index_lines += [f"- {h}" for h in hs] if hs else ["- Sem headings detectados."]
        source_index_lines.append("")

    digest_lines = [
        "# Research Digest",
        "",
        "## Status real",
        "Leitura local. Sem Claude. Sem API. Sem produção.",
        "",
        "## Sinais encontrados",
    ]

    if counts:
        for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            digest_lines.append(f"- {k}: {v}")
    else:
        digest_lines.append("- Nenhum termo técnico relevante encontrado.")

    digest_lines += ["", "## Linhas importantes por fonte", ""]

    for f, txt in chunks:
        rel = f.relative_to(ROOT) if f.is_relative_to(ROOT) else f
        digest_lines += [f"### {rel}", ""]
        lines = extract_important_lines(txt, limit=18)
        digest_lines += [f"- {line}" for line in lines] if lines else ["- Nenhuma linha técnica destacada."]
        digest_lines.append("")

    evolution = """# JARVIS Evolution Plan — Professional Digest

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
Objetivo: usar o mesmo mecanismo para SWLTEC, VERITAS, Factory, Oficina e outros projetos.

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
Usar `./jarvis research-digest --source PATH --goal "..."` em uma pasta real de projeto e validar se o output ajuda.

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

    status = f"""# Status Real — Research Digest

## Execução
- Goal: {goal}
- Source dir: `{source_dir}`
- Sources lidas: {len(files)}
- Produção alterada: não
- Claude/API usado: não
- Commit/push automático: não

## Próximo passo seguro
Ler `03_JARVIS_EVOLUTION_PLAN.md` e decidir se o próximo ciclo é CLI local, digest por projeto ou API local.
"""

    backlog = """# JARVIS Technical Backlog — próximo ciclo

## P0 — Agora
- Garantir `./jarvis research-digest` estável.
- Manter outputs em `05_EXECUCAO/62_RESEARCH_DIGEST/` ignorados no Git.
- Gerar plano local sem Claude/API.
- Rodar safety-gate antes de commit/push.

## P1 — Próximo
- Validar `--source PATH` em uma pasta real de projeto.
- Validar `--out DIR` em uma pasta temporária.
- Fazer o `./jarvis do "..."` sugerir `research-digest` quando detectar fonte/research.
- Criar decisão automática: digest simples vs blueprint vs handoff.

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

    return {
        "01_SOURCE_INDEX.md": "\n".join(source_index_lines),
        "02_DIGEST.md": "\n".join(digest_lines),
        "03_JARVIS_EVOLUTION_PLAN.md": evolution,
        "04_N8N_LOOP_POSITION.md": n8n_position,
        "05_STATUS_REAL.md": status,
        "06_TECHNICAL_BACKLOG.md": backlog,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Digest local de research sources do JARVIS.")
    parser.add_argument("--goal", default="evolução do JARVIS usando deep research locais")
    parser.add_argument("--source", default="02_SOURCES/DEEP_RESEARCH", help="pasta de fontes markdown para ler")
    parser.add_argument("--out", default="05_EXECUCAO/62_RESEARCH_DIGEST", help="pasta base de saída")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    source_dir = resolve_path(args.source)
    out_base = resolve_path(args.out)

    if not source_dir.exists():
        print("JARVIS — Research Digest")
        print("ERRO: source não existe.")
        print(f"Source informado: {args.source}")
        print(f"Path resolvido: {source_dir}")
        print("Produção: nada alterado.")
        return 2

    files = read_sources(source_dir)

    if not files:
        print("JARVIS — Research Digest")
        print("ERRO: nenhum arquivo de fonte encontrado na source.")
        print(f"Source: {source_dir}")
        print("Produção: nada alterado.")
        return 2

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = out_base / f"{ts}_{slugify(args.goal)}"

    print("JARVIS — Research Digest")
    print("Status real: leitura local. Sem Claude. Sem API. Sem produção.")
    print(f"Goal: {args.goal}")
    print(f"Sources: {len(files)} arquivo(s) em {source_dir.relative_to(ROOT) if source_dir.is_relative_to(ROOT) else source_dir}")

    if args.dry_run:
        print(f"DRY-RUN: criaria pasta {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}/")
        return 0

    outputs = build_outputs(args.goal, source_dir, files)
    for name, content in outputs.items():
        write_file(out / name, content)

    print("")
    print(f"OK — digest criado em {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}/")
    print("")
    print("Arquivos:")
    for name in outputs:
        path = out / name
        print(f"  - {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    print("")
    print("Próximo passo seguro:")
    plan = out / "03_JARVIS_EVOLUTION_PLAN.md"
    print(f"  sed -n '1,220p' {plan.relative_to(ROOT) if plan.is_relative_to(ROOT) else plan}")
    print("Produção: nada alterado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
