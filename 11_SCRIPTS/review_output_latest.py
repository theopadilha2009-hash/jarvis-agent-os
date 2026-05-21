from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "05_EXECUCAO" / "10_EXECUTOR_OUTPUT_REVIEWS"

def main():
    print("JARVIS — Theo Padilha AI Worker Latest Executor Output Review")
    print("")

    if not REVIEWS.exists():
        print("Nenhum diretório de executor output reviews encontrado.")
        return

    files = sorted(
        [p for p in REVIEWS.glob("*.md") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not files:
        print("Nenhum executor output review encontrado.")
        return

    latest = files[0]

    print(f"Arquivo: {latest}")
    print("")
    print("=" * 80)
    print(latest.read_text(encoding="utf-8", errors="ignore"))
    print("=" * 80)

if __name__ == "__main__":
    main()
