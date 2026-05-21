from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "01_SISTEMA" / "00_REGRAS" / "REPORT_STORAGE_POLICY.md"

def main():
    print("JARVIS — Theo Padilha AI Worker Report Policy")
    print("")
    if POLICY.exists():
        print(POLICY.read_text(encoding="utf-8", errors="ignore"))
    else:
        print("REPORT_STORAGE_POLICY.md não encontrado.")

if __name__ == "__main__":
    main()
