from pathlib import Path
from datetime import datetime
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[1]

CHECKS = [
    {
        "name": "help",
        "cmd": ["./jarvis", "help"],
        "expect": ["Comandos:", "./jarvis help"],
    },
    {
        "name": "safety-gate",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "safety-gate"],
        "expect": ["Safety Gate", "SAFETY GATE PASSOU", "Produção não alterada", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "command-audit",
        "cmd": ["./jarvis", "command-audit"],
        "expect": ["Command Audit", "COMMAND AUDIT PASSOU", "Produção não alterada"],
    },
    {
        "name": "secret-scan",
        "cmd": ["./jarvis", "secret-scan"],
        "expect": ["Secret Scan", "SECRET SCAN PASSOU", "Nenhum segredo foi impresso"],
    },
    {
        "name": "storage-health",
        "cmd": ["./jarvis", "storage-health"],
        "expect": ["Storage Health", "STORAGE HEALTH PASSOU", "Produção não alterada"],
    },
    {
        "name": "pending-artifacts",
        "cmd": ["./jarvis", "pending-artifacts"],
        "expect": ["Pending Artifacts", "Status real", "Git status"],
    },
    {
        "name": "report-policy",
        "cmd": ["./jarvis", "report-policy"],
        "expect": ["Report Policy", "ULTIMO_*.md", "Snapshot versionado"],
    },
    {
        "name": "cockpit",
        "cmd": ["./jarvis", "cockpit"],
        "expect": ["JARVIS — Theo Padilha AI Worker Cockpit", "Execution modes", "Próximo passo seguro", "Produção"],
    },
    {
        "name": "commands",
        "cmd": ["./jarvis", "commands"],
        "expect": ["Command Catalog", "auto-task", "quality-gate"],
    },
    {
        "name": "execution-modes",
        "cmd": ["./jarvis", "execution-modes"],
        "expect": ["PREPARE", "READONLY", "LOCAL_EXEC", "INFRA_EXEC", "PRODUCTION_ARMED"],
    },
    {
        "name": "overview",
        "cmd": ["./jarvis", "overview"],
        "expect": ["System Overview", "Status real", "Produção"],
    },
    {
        "name": "task-status",
        "cmd": ["./jarvis", "task-status"],
        "expect": ["Task Status", "Git status", "Próximo passo seguro"],
    },
    {
        "name": "self-test",
        "cmd": ["./jarvis", "self-test"],
        "expect": ["SELF-TEST PASSOU", "Status real"],
    },
    {
        "name": "quality-gate",
        "cmd": ["./jarvis", "quality-gate"],
        "expect": ["QUALITY GATE", "Python compile", "Git status"],
    },
    {
        "name": "project-select",
        "cmd": ["./jarvis", "project-select", "corrigir bug de visitantes do GC"],
        "expect": ["Project Select", "Projeto sugerido", "Próximo passo seguro"],
    },
    {
        "name": "local-exec-handoff-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-handoff", "corrigir bug local no projeto oficina sem deploy"],
        "expect": ["LOCAL_EXEC Handoff", "Projeto selecionado", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-ready-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-ready", "corrigir bug local no projeto oficina sem deploy"],
        "expect": ["LOCAL_EXEC Ready Check", "Projeto selecionado", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-plan-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-plan", "corrigir bug local no projeto oficina sem deploy"],
        "expect": ["LOCAL_EXEC Plan", "Nenhum arquivo do projeto foi alterado", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "readonly-run-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "readonly-run", "investigar bug no projeto GC sem alterar produção"],
        "expect": ["READONLY RUN", "inspeção local read-only", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-review-latest",
        "cmd": ["./jarvis", "local-exec-review-latest"],
        "expect": ["Latest LOCAL_EXEC Review", "LOCAL_EXEC Review", "Decisão"],
    },
    {
        "name": "local-exec-review-fixtures",
        "cmd": ["./jarvis", "local-exec-review", "--fixtures"],
        "expect": ["LOCAL_EXEC Review", "Fixtures LOCAL_EXEC"],
    },
    {
        "name": "local-exec-handoff-latest",
        "cmd": ["./jarvis", "local-exec-handoff-latest"],
        "expect": ["Latest LOCAL_EXEC Handoff", "Arquivo principal", "LOCAL_EXEC"],
    },
    {
        "name": "local-exec-ready-latest",
        "cmd": ["./jarvis", "local-exec-ready-latest"],
        "expect": ["Latest LOCAL_EXEC Ready Check", "LOCAL_EXEC Ready Check", "Status real"],
    },
    {
        "name": "local-exec-plan-latest",
        "cmd": ["./jarvis", "local-exec-plan-latest"],
        "expect": ["Latest LOCAL_EXEC Plan", "LOCAL_EXEC Plan", "Status real"],
    },
    {
        "name": "readonly-run-latest",
        "cmd": ["./jarvis", "readonly-run-latest"],
        "expect": ["Latest READONLY RUN", "READONLY RUN", "Status real"],
    },
    {
        "name": "task-brief-latest",
        "cmd": ["./jarvis", "task-brief-latest"],
        "expect": ["Latest Task Brief", "Status real", "Próximo passo seguro"],
    },
    {
        "name": "auto-task-latest",
        "cmd": ["./jarvis", "auto-task-latest"],
        "expect": ["Latest Auto Task", "Auto Task Run", "Nada executado no projeto real"],
    },
    {
        "name": "review-output-index",
        "cmd": ["./jarvis", "review-output-index"],
        "expect": ["Executor Output Index", "Reviews indexados", "Relatório"],
    },
    {
        "name": "review-output-latest",
        "cmd": ["./jarvis", "review-output-latest"],
        "expect": ["Latest Executor Output Review", "Executor Output Review", "Status real"],
    },
    {
        "name": "handoff-latest",
        "cmd": ["./jarvis", "handoff-latest"],
        "expect": ["Latest Handoff", "Arquivo principal para Claude"],
    },
    {
        "name": "handoff-print",
        "cmd": ["./jarvis", "handoff-print"],
        "expect": ["Handoff Print", "Prompt para Claude", "Regras obrigatórias"],
    },
]

def run(cmd):
    try:
        output = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
        return 0, output.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.strip()
    except Exception as e:
        return 1, f"ERRO: {e}"

def main():
    print("JARVIS — Theo Padilha AI Worker CLI Smoke Test")
    print("Modo: exit code + conteúdo esperado")
    print("")

    results = []

    for check in CHECKS:
        code, output = run(check["cmd"])
        missing = [x for x in check["expect"] if x not in output]
        ok = code == 0 and not missing

        results.append({
            "name": check["name"],
            "cmd": check["cmd"],
            "ok": ok,
            "code": code,
            "missing": missing,
            "output": output,
        })

        if ok:
            print(f"OK  {' '.join(check['cmd'])}")
        else:
            print(f"FALHA  {' '.join(check['cmd'])}")
            if code != 0:
                print(f"  exit code: {code}")
            if missing:
                print(f"  conteúdo ausente: {', '.join(missing)}")

    passed = all(r["ok"] for r in results)

    out_dir = ROOT / "10_TESTES" / "SMOKE_TESTS"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    report = out_dir / f"{ts}_cli-smoke-test.md"

    lines = [
        "# CLI Smoke Test — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Resultado\n{'PASSOU' if passed else 'FALHOU'}",
        "",
        "## Status real",
        "Teste local de CLI. Nada de produção.",
        "",
    ]

    for r in results:
        lines += [
            f"## {r['name']}",
            f"Comando: `{' '.join(r['cmd'])}`",
            f"Status: {'OK' if r['ok'] else 'FALHA'}",
            f"Exit code: {r['code']}",
            f"Conteúdo ausente: {', '.join(r['missing']) if r['missing'] else 'nenhum'}",
            "",
            "```text",
            r["output"][-4000:],
            "```",
            "",
        ]

    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    print("")
    print(f"Resultado: {'CLI SMOKE TEST PASSOU' if passed else 'CLI SMOKE TEST FALHOU'}")

    if no_report:
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
    else:
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Relatório: {report.relative_to(ROOT)}")

    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
