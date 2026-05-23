from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RADAR = ROOT / "01_SISTEMA" / "06_FUTURE_TOOLS_RADAR" / "FUTURE_TOOLS_RADAR.md"

def main():
    print("JARVIS — Theo Padilha AI Worker Future Tools Radar")
    print("")
    print("Status real: leitura local. Nenhuma ferramenta foi instalada, configurada ou conectada.")
    print("")

    if not RADAR.exists():
        print("FALHA: FUTURE_TOOLS_RADAR.md não encontrado.")
        return

    print(RADAR.read_text(encoding="utf-8", errors="ignore"))
    print("")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
