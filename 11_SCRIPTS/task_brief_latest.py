from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / '05_EXECUCAO' / '08_TASK_BRIEFS'

def main():
    if not BRIEFS.exists():
        print('Nenhum diretório de task briefs encontrado.')
        return
    files = sorted([p for p in BRIEFS.glob('*.md') if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print('Nenhum task brief encontrado.')
        return
    latest = files[0]
    print('JARVIS — Theo Padilha AI Worker Latest Task Brief')
    print('')
    print(f'Arquivo: {latest}')
    print('')
    print('=' * 80)
    print(latest.read_text(encoding='utf-8', errors='ignore'))
    print('=' * 80)

if __name__ == '__main__':
    main()
