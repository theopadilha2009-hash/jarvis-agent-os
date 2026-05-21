from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READONLY_DIR = ROOT / "05_EXECUCAO" / "12_READONLY_RUNS"

def main():
    print("JARVIS — Theo Padilha AI Worker Latest READONLY RUN")
    print("")

    if not READONLY_DIR.exists():
        print("Nenhum diretório de READONLY_RUN encontrado.")
        return

    files = sorted(
        [p for p in READONLY_DIR.glob("*.md") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not files:
        print("Nenhum READONLY_RUN encontrado.")
        return

    latest = files[0]

    print(f"Arquivo: {latest}")
    print("")
    print("=" * 80)
    print(latest.read_text(encoding="utf-8", errors="ignore"))
    print("=" * 80)

if __name__ == "__main__":
    main()
