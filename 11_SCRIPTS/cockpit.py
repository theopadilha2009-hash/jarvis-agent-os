from pathlib import Path
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]

def run(cmd):
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as e:
        return f"ERRO: {e}"

def latest_file(path, pattern="*"):
    p = ROOT / path
    if not p.exists():
        return None
    files = [x for x in p.glob(pattern) if x.is_file()]
    return max(files, key=lambda x: x.stat().st_mtime) if files else None

def latest_dir(path):
    p = ROOT / path
    if not p.exists():
        return None
    dirs = [x for x in p.iterdir() if x.is_dir()]
    return max(dirs, key=lambda x: x.stat().st_mtime) if dirs else None

def rel(path):
    if not path:
        return "nenhum"
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)

def extract_section(text, title):
    m = re.search(rf"## {re.escape(title)}\n(.*?)(?=\n## |\Z)", text, flags=re.S)
    return " ".join(m.group(1).strip().split()) if m else ""

def read_short(path, limit=900):
    if not path or not path.exists():
        return "nenhum"
    text = path.read_text(encoding="utf-8", errors="ignore")
    return text[-limit:].strip()

def main():
    git_commit = run(["git", "rev-parse", "--short", "HEAD"])
    git_status = run(["git", "status", "--short"]) or "limpo"

    latest_auto = latest_file("05_EXECUCAO/09_AUTO_TASK_RUNS", "*.md")
    latest_mode_plan = latest_file("05_EXECUCAO/11_MODE_PLANS", "*.md")
    latest_readonly = latest_file("05_EXECUCAO/12_READONLY_RUNS", "*.md")
    latest_local_exec = latest_file("05_EXECUCAO/13_LOCAL_EXEC_PLANS", "*.md")
    latest_review_index = ROOT / "07_RELATORIOS/02_TECNICOS/ULTIMO_EXECUTOR_OUTPUT_INDEX.md"
    latest_review = latest_file("05_EXECUCAO/10_EXECUTOR_OUTPUT_REVIEWS", "*.md")
    latest_handoff = latest_dir("05_EXECUCAO/07_EXECUTOR_HANDOFFS")
    latest_task_brief = latest_file("05_EXECUCAO/08_TASK_BRIEFS", "*.md")
    latest_release = latest_file("10_TESTES/RELEASE_CHECKS", "*.md")
    latest_safety = latest_file("10_TESTES/SAFETY_GATES", "*.md")
    latest_smoke = latest_file("10_TESTES/SMOKE_TESTS", "*.md")

    review_summary = "nenhum"
    if latest_review_index.exists():
        txt = latest_review_index.read_text(encoding="utf-8", errors="ignore")
        total = extract_section(txt, "Total de reviews")
        counts = extract_section(txt, "Contagem por decisão")
        review_summary = f"Total: {total or 'n/d'} | {counts or 'sem contagem'}"

    print("JARVIS — Theo Padilha AI Worker Cockpit")
    print("")
    print("Status real: painel local. Nada executado em projeto real.")
    print("")
    print("## Git")
    print(f"- Commit: {git_commit}")
    print(f"- Status: {git_status}")
    print("")
    print("## Execution modes")
    print("- PREPARE: preparar")
    print("- READONLY: inspecionar sem alterar")
    print("- LOCAL_EXEC: editar local e testar")
    print("- INFRA_EXEC: operar VPS/Docker/n8n com escopo")
    print("- PRODUCTION_ARMED: ação real sensível com autorização")
    print("")
    print("## Últimos artefatos")
    print(f"- Auto-task: {rel(latest_auto)}")
    print(f"- Mode plan: {rel(latest_mode_plan)}")
    print(f"- Readonly run: {rel(latest_readonly)}")
    print(f"- Local exec plan: {rel(latest_local_exec)}")
    print(f"- Task brief: {rel(latest_task_brief)}")
    print(f"- Handoff: {rel(latest_handoff)}")
    print(f"- Review latest: {rel(latest_review)}")
    print(f"- Review index: {rel(latest_review_index) if latest_review_index.exists() else 'nenhum'}")
    print(f"- Release-check: {rel(latest_release)}")
    print(f"- Safety-gate: {rel(latest_safety)}")
    print(f"- Smoke-test: {rel(latest_smoke)}")
    print("")
    print("## Executor output reviews")
    print(f"- {review_summary}")
    print("")
    print("## Próximo passo seguro")
    print("- Para classificar modo: ./jarvis mode-plan \"tarefa\"")
    print("- Para preparar tarefa: ./jarvis auto-task \"tarefa\"")
    print("- Para inspecionar sem alterar: ./jarvis readonly-run \"tarefa\"")
    print("- Para planejar edição local: ./jarvis local-exec-plan \"tarefa\"")
    print("- Para ver pendências geradas: ./jarvis pending-artifacts")
    print("- Para revisar resposta externa: ./jarvis review-output-v2 arquivo.md")
    print("- Para ver índice de revisões: ./jarvis review-output-index")
    print("- Para validação forte: ./jarvis safety-gate")
    print("- Para operação forte futura: declarar modo PREPARE/READONLY/LOCAL_EXEC/INFRA_EXEC/PRODUCTION_ARMED")
    print("")
    print("## Produção")
    print("Nada alterado.")

if __name__ == "__main__":
    main()
