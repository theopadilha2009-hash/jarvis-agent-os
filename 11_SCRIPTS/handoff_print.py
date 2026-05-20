from pathlib import Path

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
    handoff = latest / "01_CLAUDE_HANDOFF.md"

    if not handoff.exists():
        print(f"Arquivo não encontrado: {handoff}")
        return

    print("JARVIS — Theo Padilha AI Worker Handoff Print")
    print("")
    print(f"Arquivo: {handoff}")
    print("")
    print("=" * 80)
    print(handoff.read_text(encoding="utf-8", errors="ignore"))
    print("=" * 80)

if __name__ == "__main__":
    main()
