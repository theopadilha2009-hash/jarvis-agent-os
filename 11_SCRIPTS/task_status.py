from pathlib import Path
from datetime import datetime
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def newest_file(path):
    p = ROOT / path
    if not p.exists():
        return None
    files = [x for x in p.rglob('*') if x.is_file()]
    return max(files, key=lambda x: x.stat().st_mtime) if files else None

def newest_dir(path):
    p = ROOT / path
    if not p.exists():
        return None
    dirs = [x for x in p.iterdir() if x.is_dir()]
    return max(dirs, key=lambda x: x.stat().st_mtime) if dirs else None

def run(cmd):
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as e:
        return 'ERRO: ' + str(e)

def rel(p):
    if not p:
        return 'nenhum'
    try:
        return str(p.relative_to(ROOT))
    except Exception:
        return str(p)

def main():
    git_commit = run(['git', 'rev-parse', '--short', 'HEAD'])
    git_status = run(['git', 'status', '--short'])
    latest_task = newest_file('05_EXECUCAO/06_TASK_STARTS')
    latest_handoff = newest_dir('05_EXECUCAO/07_EXECUTOR_HANDOFFS')
    latest_release = newest_file('10_TESTES/RELEASE_CHECKS')
    latest_smoke = newest_file('10_TESTES/SMOKE_TESTS')
    latest_checkpoint = newest_file('10_TESTES/CHECKPOINTS')
    project_index = ROOT / '04_PROJETOS/_INDEX/PROJECT_INDEX.md'

    lines = [
        '# Task Status — JARVIS Theo Padilha AI Worker',
        '',
        f'## Data\\n{datetime.now().isoformat(timespec="seconds")}',
        '',
        f'## Git commit\\n{git_commit}',
        '',
        f'## Git status\\n{git_status if git_status else "limpo"}',
        '',
        f'## Último task-start\\n{rel(latest_task)}',
        '',
        f'## Último handoff\\n{rel(latest_handoff)}',
        '',
        f'## Último release-check\\n{rel(latest_release)}',
        '',
        f'## Último smoke-test\\n{rel(latest_smoke)}',
        '',
        f'## Último checkpoint\\n{rel(latest_checkpoint)}',
        '',
        f'## Project index\\n{rel(project_index) if project_index.exists() else "não encontrado"}',
        '',
        '## Próximo passo seguro',
        'Se for tarefa real: `./jarvis task-start "tarefa"` ou `./jarvis executor-handoff "tarefa"`.',
        '',
        '## Produção',
        'Nada alterado.',
    ]

    out = ROOT / '07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print('JARVIS — Theo Padilha AI Worker Task Status')
    print('')
    print('\n'.join(lines))
    print('')
    print(f'Relatório salvo em: {out.relative_to(ROOT)}')

if __name__ == '__main__':
    main()
