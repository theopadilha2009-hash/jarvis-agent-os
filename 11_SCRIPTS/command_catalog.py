from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / '01_SISTEMA' / '03_COMMANDS' / 'COMMAND_CATALOG.md'

def main():
    if not CATALOG.exists():
        print('COMMAND_CATALOG.md não encontrado.')
        return
    print('JARVIS — Theo Padilha AI Worker Command Catalog')
    print('')
    print(CATALOG.read_text(encoding='utf-8', errors='ignore'))

if __name__ == '__main__':
    main()
