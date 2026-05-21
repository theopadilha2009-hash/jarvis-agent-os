from pathlib import Path
from datetime import datetime
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

CHECKS = [
    ("secret-scan", ["./jarvis", "secret-scan"]),
    ("storage-health", ["./jarvis", "storage-health"]),
    ("quality-gate", ["./jarvis", "quality-gate"]),
]

def run(cmd):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.strip()
    except Exception as e:
        return 1, f"ERRO: {e}"

def main():
    print("JARVIS — Theo Padilha AI Worker Safety Gate")
    print("Status real: validação local forte. Produção não alterada.")
    print("")

    results = []

    for name, cmd in CHECKS:
        code, output = run(cmd)
        ok = code == 0
        results.append((name, cmd, ok, code, output))

        if ok:
            print(f"OK  {name}")
        else:
            print(f"FALHA  {name}")
            print(output[-2000:])

    passed = all(x[2] for x in results)

    print("")
    print("Resultado:", "SAFETY GATE PASSOU" if passed else "SAFETY GATE COM PENDÊNCIAS")
    print("Status real: nada aplicado em projeto real, VPS, n8n ou produção.")

    out_dir = ROOT / "10_TESTES" / "SAFETY_GATES"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    report = out_dir / f"{ts}_safety-gate.md"

    lines = [
        "# Safety Gate — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Resultado\n{'PASSOU' if passed else 'FALHOU'}",
        "",
        "## Status real",
        "Validação local forte. Produção não alterada.",
        "",
    ]

    for name, cmd, ok, code, output in results:
        lines += [
            f"## {name}",
            f"Comando: `{' '.join(cmd)}`",
            f"Status: {'OK' if ok else 'FALHA'}",
            f"Exit code: {code}",
            "",
            "```text",
            output[-5000:],
            "```",
            "",
        ]

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Relatório: {report.relative_to(ROOT)}")

    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
