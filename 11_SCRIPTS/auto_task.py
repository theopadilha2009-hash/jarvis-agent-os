from pathlib import Path
from datetime import datetime
import subprocess
import sys
import re

ROOT = Path(__file__).resolve().parents[1]

def run(cmd):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
        return True, out.strip()
    except subprocess.CalledProcessError as e:
        return False, e.output.strip()
    except Exception as e:
        return False, str(e)

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:90] or 'auto-task'

def section(title, ok, output):
    return [
        '## ' + title,
        'Status: ' + ('OK' if ok else 'FALHA'),
        '',
        '```text',
        output[-5000:],
        '```',
        '',
    ]

def main():
    task = ' '.join(sys.argv[1:]).strip()
    if not task:
        print('Uso: ./jarvis auto-task "tarefa"')
        sys.exit(1)

    print('JARVIS — Theo Padilha AI Worker Auto Task')
    print('Modo: preparação local apenas. Nada executado no projeto real.')
    print('')

    steps = [
        ('project-index', ['./jarvis', 'project-index', '~/VAMOO_PROJETOS']),
        ('project-select', ['./jarvis', 'project-select', task]),
        ('task-brief', ['./jarvis', 'task-brief', task]),
        ('task-start', ['./jarvis', 'task-start', task]),
        ('executor-handoff', ['./jarvis', 'executor-handoff', task]),
        ('handoff-print', ['./jarvis', 'handoff-print']),
        ('task-status', ['./jarvis', 'task-status']),
        ('release-check', ['./jarvis', 'release-check']),
    ]

    results = []
    for name, cmd in steps:
        print('Rodando: ' + name)
        ok, output = run(cmd)
        results.append((name, ok, output))
        print(('OK' if ok else 'FALHA') + '  ' + name)
        if not ok:
            print('Parando em falha segura.')
            break

    passed = all(ok for _, ok, _ in results)

    out_dir = ROOT / '05_EXECUCAO' / '09_AUTO_TASK_RUNS'
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
    out = out_dir / f'{ts}_{slugify(task)}_auto-task.md'

    lines = [
        '# Auto Task Run — JARVIS Theo Padilha AI Worker',
        '',
        f'## Data\n{datetime.now().isoformat(timespec="seconds")}',
        '',
        f'## Tarefa\n{task}',
        '',
        '## Status real',
        'Preparação local automatizada. Nada executado no projeto real.',
        '',
        f'## Resultado\n{("PASSOU" if passed else "FALHOU")}',
        '',
    ]

    for name, ok, output in results:
        lines.extend(section(name, ok, output))

    lines.extend([
        '## Produção',
        'Nada alterado.',
        '',
        '## Próximo passo seguro',
        'Usar o handoff gerado manualmente em Claude/VS Code, começando read-only.',
    ])

    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print('')
    print('Resultado: ' + ('AUTO TASK PASSOU' if passed else 'AUTO TASK FALHOU'))
    print('Relatório: ' + str(out.relative_to(ROOT)))

    if not passed:
        sys.exit(1)

if __name__ == '__main__':
    main()
