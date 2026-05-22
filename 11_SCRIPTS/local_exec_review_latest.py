from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWS_DIR = ROOT / "05_EXECUCAO" / "16_LOCAL_EXEC_REVIEWS"

def main():
    print("JARVIS — Theo Padilha AI Worker Latest LOCAL_EXEC Review")
    print("")

    if not REVIEWS_DIR.exists():
        print("Nenhum diretório de LOCAL_EXEC reviews encontrado.")
        return

    files = sorted(
        [p for p in REVIEWS_DIR.glob("*.md") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not files:
        print("Nenhum LOCAL_EXEC review encontrado.")
        return

    latest = files[0]

    print(f"Arquivo: {latest}")
    print("")
    print("=" * 80)
    print(latest.read_text(encoding="utf-8", errors="ignore"))
    print("=" * 80)

if __name__ == "__main__":
    main()
