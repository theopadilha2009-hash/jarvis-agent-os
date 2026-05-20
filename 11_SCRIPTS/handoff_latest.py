from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
HANDOFFS = ROOT / "05_EXECUCAO" / "07_EXECUTOR_HANDOFFS"

def main():
    if not HANDOFFS.exists():
        print("Nenhum diretório de handoffs encontrado.")
        return

    dirs = sorted([p for p in HANDOFFS.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)

    if not dirs:
        print("Nenhum handoff encontrado.")
        return

    latest = dirs[0]

    print("JARVIS — Theo Padilha AI Worker Latest Handoff")
    print("")
    print(f"Pasta: {latest}")
    print("")
    print("Arquivos:")
    for f in sorted(latest.glob("*.md")):
        print(f"- {f.name}")
    print("")
    print("Comando para abrir:")
    print(f"open {latest}")
    print("")
    print("Arquivo principal para Claude:")
    print(latest / "01_CLAUDE_HANDOFF.md")

if __name__ == "__main__":
    main()
