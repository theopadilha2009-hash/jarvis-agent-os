from pathlib import Path
from datetime import datetime
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "07_RELATORIOS" / "03_RELEASES"

def run(cmd):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.strip()

def write(path, text):
    path.write_text(text.strip() + "\n", encoding="utf-8")

def run_to_file(tmp, filename, cmd):
    code, output = run(cmd)
    write(tmp / filename, output)
    if code != 0:
        print(f"FALHA  {' '.join(cmd)}")
        print(output[-2000:])
        sys.exit(code)
    print(f"OK  {' '.join(cmd)}")

def main():
    print("JARVIS — Theo Padilha AI Worker Snapshot Preparation Core")
    print("Status real: snapshot local. Produção não alterada.")
    print("")

    code, status = run(["git", "status", "--short"])
    if status.strip():
        print("FALHA  Git precisa estar limpo antes do snapshot.")
        print(status)
        sys.exit(1)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    final_dir = RELEASES / f"v0.4-preparation-core-clean-{ts}"
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-prep-core-"))

    write(tmp / "GIT_COMMIT_BEFORE_SNAPSHOT.txt", run(["git", "rev-parse", "--short", "HEAD"])[1])
    write(tmp / "GIT_HISTORY.txt", run(["git", "log", "--oneline", "-90"])[1])

    run_to_file(tmp, "COCKPIT.txt", ["./jarvis", "cockpit"])
    run_to_file(tmp, "EXECUTION_MODES.txt", ["./jarvis", "execution-modes"])
    run_to_file(tmp, "MODE_PLAN_READONLY_NO_REPORT.txt", ["env", "JARVIS_NO_REPORT=1", "./jarvis", "mode-plan", "investigar bug no projeto GC sem alterar produção"])
    run_to_file(tmp, "PENDING_ARTIFACTS.txt", ["./jarvis", "pending-artifacts"])
    run_to_file(tmp, "LATEST_AUTO_TASK.txt", ["./jarvis", "auto-task-latest"])
    run_to_file(tmp, "LATEST_HANDOFF.txt", ["./jarvis", "handoff-latest"])
    run_to_file(tmp, "SECRET_SCAN.txt", ["./jarvis", "secret-scan"])
    run_to_file(tmp, "STORAGE_HEALTH.txt", ["./jarvis", "storage-health"])
    run_to_file(tmp, "SAFETY_GATE_NO_REPORT.txt", ["env", "JARVIS_NO_REPORT=1", "./jarvis", "safety-gate"])
    run_to_file(tmp, "RELEASE_CHECK_NO_REPORT.txt", ["env", "JARVIS_NO_REPORT=1", "./jarvis", "release-check"])
    run_to_file(tmp, "QUALITY_GATE.txt", ["./jarvis", "quality-gate"])

    status_doc = [
        "# Status v0.4 Preparation Core Clean Snapshot",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Status real",
        "Snapshot local criado com temp folder e no-report onde aplicável. Produção não alterada.",
        "",
        "## Correção aplicada",
        "Este snapshot evita gerar artefatos surpresa durante o processo.",
        "",
        "## Técnica",
        "- Comandos rodam primeiro em diretório temporário fora do repo.",
        "- `mode-plan`, `safety-gate`, `release-check` e `smoke-test` usam no-report quando aplicável.",
        "- O diretório de release só é criado depois das validações.",
        "",
        "## Produção",
        "Nada alterado.",
    ]
    write(tmp / "STATUS_V0_4_PREPARATION_CORE_CLEAN.md", "\n".join(status_doc))

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(tmp, final_dir)

    print("")
    print(f"Snapshot criado: {final_dir.relative_to(ROOT)}")
    print("Próximo passo seguro:")
    print(f"git add {final_dir.relative_to(ROOT)} && git commit -m \"chore: snapshot v0.4 preparation core clean\"")

if __name__ == "__main__":
    main()
