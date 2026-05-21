from pathlib import Path
from datetime import datetime
import re

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "05_EXECUCAO" / "10_EXECUTOR_OUTPUT_REVIEWS"
OUT = ROOT / "07_RELATORIOS" / "02_TECNICOS" / "ULTIMO_EXECUTOR_OUTPUT_INDEX.md"

def extract_section(text, title):
    pattern = rf"## {re.escape(title)}\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, flags=re.S)
    return m.group(1).strip() if m else ""

def one_line(text):
    return " ".join(text.split())[:240] if text else ""

def main():
    print("JARVIS — Theo Padilha AI Worker Executor Output Index")
    print("")

    OUT.parent.mkdir(parents=True, exist_ok=True)

    if not REVIEWS.exists():
        msg = "Nenhum diretório de reviews encontrado."
        print(msg)
        OUT.write_text(f"# Executor Output Index\n\n{msg}\n", encoding="utf-8")
        return

    files = sorted(
        [p for p in REVIEWS.glob("*.md") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    rows = []
    counts = {}

    for p in files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        decision = one_line(extract_section(text, "Decisão")) or "não detectado"
        status = one_line(extract_section(text, "Status do output")) or "não detectado"
        source = one_line(extract_section(text, "Source")) or "não detectado"
        risks = one_line(extract_section(text, "Riscos fortes detectados")) or "não detectado"
        next_step = one_line(extract_section(text, "Próximo passo seguro")) or "não detectado"

        counts[decision] = counts.get(decision, 0) + 1

        rows.append({
            "file": p,
            "decision": decision,
            "status": status,
            "source": source,
            "risks": risks,
            "next_step": next_step,
        })

    lines = [
        "# Executor Output Index — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Status real",
        "Índice local de revisões de outputs externos. Nada aplicado no projeto real.",
        "",
        f"## Total de reviews\n{len(rows)}",
        "",
        "## Contagem por decisão",
    ]

    if counts:
        for k, v in sorted(counts.items()):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- nenhum")

    lines += [
        "",
        "## Últimas revisões",
        "",
    ]

    for item in rows[:20]:
        rel = item["file"].relative_to(ROOT)
        lines += [
            f"### {rel}",
            f"- Decisão: {item['decision']}",
            f"- Status: {item['status']}",
            f"- Source: {item['source']}",
            f"- Riscos fortes: {item['risks']}",
            f"- Próximo passo: {item['next_step']}",
            "",
        ]

    lines += [
        "## Regra",
        "Esse índice não valida execução real. Ele organiza evidência para decisão humana ou próximo executor.",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Reviews indexados: {len(rows)}")
    print(f"Relatório: {OUT.relative_to(ROOT)}")
    print("")
    for k, v in sorted(counts.items()):
        print(f"- {k}: {v}")

if __name__ == "__main__":
    main()
