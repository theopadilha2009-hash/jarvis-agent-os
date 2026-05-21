from pathlib import Path
from datetime import datetime
import subprocess
import sys
import json
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / '04_PROJETOS/_INDEX/PROJECT_INDEX.json'

def run(cmd):
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as e:
        return 'ERRO: ' + str(e)

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:90] or 'task-brief'

def score(task, project):
    text = task.lower()
    name = project.get('name', '').lower()
    path = project.get('path', '').lower()
    ptype = project.get('type', '').lower()
    s = 0
    reasons = []
    for w in re.findall(r'[a-zA-Z0-9À-ÿ_-]+', text):
        w = w.lower()
        if len(w) < 3:
            continue
        if w in name:
            s += 10; reasons.append('nome contém ' + w)
        if w in path:
            s += 4; reasons.append('caminho contém ' + w)
        if w in ptype:
            s += 3; reasons.append('tipo contém ' + w)
    if any(x in text for x in ['gc', 'gestao', 'gestão', 'cristo', 'visitantes']):
        if 'gc' in name or 'gestao' in name:
            s += 12; reasons.append('contexto GC')
    if any(x in text for x in ['ls', 'clinica', 'clínica', 'larissa']):
        if 'ls' in name:
            s += 12; reasons.append('contexto LS Clínica')
    if any(x in text for x in ['oficina', 'mecanica', 'mecânica', 'agenda', 'os']):
        if 'oficina' in name:
            s += 12; reasons.append('contexto Oficina')
    if project.get('status') == 'limpo':
        s += 2; reasons.append('git limpo')
    return s, reasons

def main():
    task = ' '.join(sys.argv[1:]).strip()
    if not task:
        print('Uso: ./jarvis task-brief "tarefa"')
        sys.exit(1)

    print('JARVIS — Theo Padilha AI Worker Task Brief')
    print('')
    print('1/3 Atualizando project-index...')
    print(run(['./jarvis', 'project-index', '~/VAMOO_PROJETOS']))

    if not INDEX.exists():
        print('FALHA: PROJECT_INDEX.json não encontrado.')
        sys.exit(1)

    projects = json.loads(INDEX.read_text(encoding='utf-8'))
    ranked = []
    for p in projects:
        sc, rs = score(task, p)
        ranked.append((sc, p, rs))
    ranked.sort(key=lambda x: x[0], reverse=True)
    best_score, best, reasons = ranked[0]

    project_path = best.get('path')
    company = '/VAMOO_PROJETOS/' in project_path or 'VAMOO_PROJETOS' in project_path
    profile = 'COMPANY_WORKSPACE' if company else 'THEO_OWNER'

    print('')
    print('2/3 Projeto sugerido:')
    print('- ' + best.get('name', ''))
    print('- ' + project_path)
    print('- perfil: ' + profile)
    print('- score: ' + str(best_score))

    print('')
    print('3/3 Salvando briefing...')
    out_dir = ROOT / '05_EXECUCAO/08_TASK_BRIEFS'
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
    out = out_dir / f'{ts}_{slugify(task)}_task-brief.md'

    lines = [
        '# Task Brief — JARVIS Theo Padilha AI Worker',
        '',
        f'## Data\n{datetime.now().isoformat(timespec="seconds")}',
        '',
        f'## Tarefa\n{task}',
        '',
        '## Status real',
        'Briefing local criado. Nada executado no projeto real.',
        '',
        f'## Projeto sugerido\n{best.get("name")}',
        '',
        f'## Caminho\n`{project_path}`',
        '',
        f'## Perfil\n{profile}',
        '',
        f'## Tipo\n{best.get("type")}',
        '',
        f'## Branch\n{best.get("branch")}',
        '',
        f'## Git status no índice\n{best.get("status")}',
        '',
        f'## Risco inicial\n{best.get("risk")}',
        '',
        f'## Motivos\n{", ".join(reasons) if reasons else "sem match forte"}',
        '',
        '## Comandos seguros sugeridos',
        f'`./jarvis workspace-check {project_path}`',
        f'`./jarvis executor-handoff "{task}"`',
        f'`./jarvis handoff-print`',
        '',
        '## Bloqueios',
        '- sem deploy',
        '- sem push/merge/main sem autorização',
        '- sem credenciais em executor externo',
        '- sem produção',
        '',
        '## Próximo passo seguro',
        'Gerar executor-handoff e usar executor manual em modo read-only.',
    ]

    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Brief salvo: ' + str(out.relative_to(ROOT)))
    print('')
    print('Próximo comando seguro:')
    print(f'./jarvis executor-handoff "{task}"')

if __name__ == '__main__':
    main()
