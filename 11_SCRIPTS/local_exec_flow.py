from pathlib import Path
from datetime import datetime
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "17_LOCAL_EXEC_FLOWS"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "local-exec-flow"

def main():
    task = " ".join(sys.argv[1:]).strip()
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    if not task:
        print('Uso: ./jarvis local-exec-flow "tarefa"')
        sys.exit(1)

    print("JARVIS — Theo Padilha AI Worker LOCAL_EXEC Flow")
    print("")
    print("Status real: guia operacional local. Nenhum projeto foi alterado.")
    print(f"Tarefa: {task}")
    print("")

    lines = [
        "# LOCAL_EXEC Flow — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Tarefa\n{task}",
        "",
        "## Status real",
        "Guia operacional local criado. Nenhum projeto foi alterado.",
        "",
        "## Fluxo seguro",
        "1. PREPARE — classificar modo e preparar contexto.",
        "2. READONLY — inspecionar projeto sem alterar.",
        "3. LOCAL_EXEC PLAN — planejar edição local.",
        "4. LOCAL_EXEC READY — checar blockers antes de editar.",
        "5. LOCAL_EXEC HANDOFF — gerar pacote curto para Claude/VS Code.",
        "6. LOCAL_EXEC REVIEW — revisar saída do executor antes de aceitar patch.",
        "",
        "## Comandos recomendados",
        "```bash",
        f'./jarvis mode-plan "{task}"',
        f'./jarvis readonly-run "{task}"',
        f'./jarvis local-exec-plan "{task}"',
        f'./jarvis local-exec-ready "{task}"',
        f'./jarvis local-exec-handoff "{task}"',
        "# depois de rodar Claude/VS Code e salvar a resposta em arquivo:",
        "./jarvis local-exec-review caminho/da/resposta.md",
        "```",
        "",
        "## Travamentos obrigatórios",
        "- não editar main/master sem branch segura;",
        "- não abrir/copiar `.env`; usar apenas variáveis locais existentes;",
        "- não fazer push;",
        "- não fazer merge;",
        "- não fazer deploy;",
        "- não alterar VPS, n8n, banco real ou produção;",
        "- se a revisão bloquear, parar e revisar com humano.",
        "",
        "## Critério para avançar",
        "- `local-exec-ready` sem blocker crítico;",
        "- Claude/VS Code respondeu com arquivos alterados e validações;",
        "- `local-exec-review` não classificou como `PARAR E REVISAR COM HUMANO`; ",
        "- build/test reportado ou justificativa clara.",
        "",
        "## Ainda não executa",
        "- patch automático;",
        "- commit automático;",
        "- push/PR automático;",
        "- deploy;",
        "- VPS/n8n/produção.",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    for line in lines:
        print(line)

    if no_report:
        print("")
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out = OUT_DIR / f"{ts}_{slugify(task)}_local-exec-flow.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("")
    print(f"Relatório: {out.relative_to(ROOT)}")
    print("Status real: guia criado. Projeto não alterado.")

if __name__ == "__main__":
    main()
