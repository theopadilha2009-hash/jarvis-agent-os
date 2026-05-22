from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF_DIR = ROOT / "05_EXECUCAO" / "15_LOCAL_EXEC_HANDOFFS"

def main():
    print("JARVIS — Theo Padilha AI Worker Latest LOCAL_EXEC Handoff")
    print("")

    if not HANDOFF_DIR.exists():
        print("Nenhum diretório de LOCAL_EXEC handoffs encontrado.")
        return

    dirs = sorted(
        [p for p in HANDOFF_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not dirs:
        print("Nenhum LOCAL_EXEC handoff encontrado.")
        return

    latest = dirs[0]
    main_file = latest / "01_CLAUDE_LOCAL_EXEC.md"

    print(f"Pasta: {latest}")
    print("")
    print("Arquivos:")
    for item in sorted(latest.iterdir()):
        if item.is_file():
            print(f"- {item.name}")

    print("")

    if main_file.exists():
        print(f"Arquivo principal: {main_file}")
        print("")
        print("=" * 80)
        print(main_file.read_text(encoding="utf-8", errors="ignore"))
        print("=" * 80)
    else:
        print("Arquivo principal não encontrado: 01_CLAUDE_LOCAL_EXEC.md")

if __name__ == "__main__":
    main()
