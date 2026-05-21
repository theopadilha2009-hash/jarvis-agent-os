from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / '05_EXECUCAO' / '09_AUTO_TASK_RUNS'

def main():
    if not RUNS.exists():
        print('Nenhum diretório de auto-task encontrado.')
        return
    files = sorted([p for p in RUNS.glob('*.md') if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print('Nenhum auto-task encontrado.')
        return
    latest = files[0]
    print('JARVIS — Theo Padilha AI Worker Latest Auto Task')
    print('')
    print(f'Arquivo: {latest}')
    print('')
    print('=' * 80)
    print(latest.read_text(encoding='utf-8', errors='ignore'))
    print('=' * 80)

if __name__ == '__main__':
    main()
