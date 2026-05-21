from pathlib import Path
from datetime import datetime
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def run(cmd):
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as e:
        return 'ERRO: ' + str(e)

def count_files(path):
    p = ROOT / path
    if not p.exists():
        return 0
    return len([x for x in p.rglob('*') if x.is_file()])

def main():
    commit = run(['git', 'rev-parse', '--short', 'HEAD'])
    status = run(['git', 'status', '--short']) or 'limpo'
    commands = ROOT / '01_SISTEMA/03_COMMANDS/COMMAND_CATALOG.md'
    task_status = ROOT / '07_RELATORIOS/02_TECNICOS/ULTIMO_TASK_STATUS.md'

    lines = [
        '# System Overview — JARVIS Theo Padilha AI Worker',
        '',
        f'## Data\n{datetime.now().isoformat(timespec="seconds")}',
        '',
        '## Criador / dono\nTheo Padilha',
        '',
        '## Status real\nLaboratório local estável. Não é produção.',
        '',
        f'## Git\nCommit: {commit}\nStatus: {status}',
        '',
        '## Capacidades atuais',
        '- mapear projetos do Mac',
        '- escolher projeto provável para uma tarefa',
        '- checar workspace antes de execução',
        '- gerar task-start',
        '- gerar handoff para Claude/VS Code',
        '- rodar preparação completa com auto-task',
        '- imprimir último handoff no terminal',
        '- revisar outputs manuais',
        '- rodar smoke-test, release-check e quality-gate',
        '- salvar checkpoints e releases locais',
        '',
        '## Comandos-chave',
        '- `./jarvis commands`',
        '- `./jarvis task-status`',
        '- `./jarvis project-index ~/VAMOO_PROJETOS`',
        '- `./jarvis project-select "tarefa"`',
        '- `./jarvis task-start "tarefa"`',
        '- `./jarvis auto-task "tarefa"`',
        '- `./jarvis auto-task-latest`',
        '- `./jarvis executor-handoff "tarefa"`',
        '- `./jarvis handoff-print`',
        '- `./jarvis release-check`',
        '',
        f'## Artefatos registrados\nSmoke tests: {count_files("10_TESTES/SMOKE_TESTS")}\nRelease checks: {count_files("10_TESTES/RELEASE_CHECKS")}\nCheckpoints: {count_files("10_TESTES/CHECKPOINTS")}',
        '',
        f'## Catálogo de comandos\n{commands.relative_to(ROOT) if commands.exists() else "não encontrado"}',
        '',
        f'## Último task-status\n{task_status.relative_to(ROOT) if task_status.exists() else "não encontrado"}',
        '',
        '## Produção\nNada alterado.',
        '',
        '## Próximo passo seguro\nConsolidar revisão de outputs e depois planejar executor read-only, sem edição automática ainda.',
    ]

    out = ROOT / '07_RELATORIOS/02_TECNICOS/ULTIMO_SYSTEM_OVERVIEW.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('JARVIS — Theo Padilha AI Worker System Overview')
    print('')
    print('\n'.join(lines))
    print('')
    print(f'Relatório salvo em: {out.relative_to(ROOT)}')

if __name__ == '__main__':
    main()
