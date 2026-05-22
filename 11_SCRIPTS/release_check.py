from pathlib import Path
from datetime import datetime
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[1]

def build_checks():
    checks = []

    scripts_dir = ROOT / "11_SCRIPTS"
    scripts = sorted(p for p in scripts_dir.glob("*.py") if p.is_file())

    for script in scripts:
        rel = str(script.relative_to(ROOT))
        checks.append({
            "name": f"compile {rel}",
            "cmd": ["python3", "-m", "py_compile", rel],
            "expect": [],
        })

    checks.extend([
        {
            "name": "secret-scan",
            "cmd": ["./jarvis", "secret-scan"],
            "expect": ["SECRET SCAN PASSOU", "Nenhum segredo foi impresso"],
        },
        {
            "name": "storage-health",
            "cmd": ["./jarvis", "storage-health"],
            "expect": ["STORAGE HEALTH PASSOU", "Produção não alterada"],
        },
        {
            "name": "quality-gate",
            "cmd": ["./jarvis", "quality-gate"],
            "expect": ["QUALITY GATE PASSOU", "Git status"],
        },
        {
            "name": "safety-gate-no-report",
            "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "safety-gate"],
            "expect": ["SAFETY GATE PASSOU", "Relatório: desativado por JARVIS_NO_REPORT=1"],
        },
        {
            "name": "smoke-test",
            "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "smoke-test"],
            "expect": ["CLI SMOKE TEST PASSOU", "conteúdo esperado", "Relatório: desativado por JARVIS_NO_REPORT=1"],
        },
    ])

    return checks

def run(cmd):
    try:
        output = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
        return 0, output.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.strip()
    except Exception as e:
        return 1, f"ERRO: {e}"

def main():
    print("JARVIS — Theo Padilha AI Worker Release Check")
    print("Modo: compile + storage + secret + quality + safety no-report + content-aware smoke")
    print("")

    results = []

    checks = build_checks()

    for check in checks:
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
            print(output[-2000:])

    passed = all(r["ok"] for r in results)

    out_dir = ROOT / "10_TESTES" / "RELEASE_CHECKS"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    report = out_dir / f"{ts}_release-check.md"

    lines = [
        "# Release Check — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Resultado\n{'PASSOU' if passed else 'FALHOU'}",
        "",
        "## Status real",
        "Validação local de release. Produção não alterada.",
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
            r["output"][-5000:],
            "```",
            "",
        ]

    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    print("")
    print(f"Resultado: {'RELEASE CHECK PASSOU' if passed else 'RELEASE CHECK FALHOU'}")

    if no_report:
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
    else:
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Relatório: {report.relative_to(ROOT)}")

    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
