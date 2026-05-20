from pathlib import Path
import subprocess

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
    print(f"Abrindo: {latest}")
    subprocess.run(["open", str(latest)], check=False)

if __name__ == "__main__":
    main()
