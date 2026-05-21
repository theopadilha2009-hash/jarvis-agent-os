from pathlib import Path
from datetime import datetime
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

COMMANDS = [
    ["./jarvis", "help"],
    ["./jarvis", "commands"],
    ["./jarvis", "execution-modes"],
    ["./jarvis", "overview"],
    ["./jarvis", "task-status"],
    ["./jarvis", "self-test"],
    ["./jarvis", "quality-gate"],
    ["./jarvis", "project-select", "corrigir bug de visitantes do GC"],
    ["./jarvis", "task-brief-latest"],
    ["./jarvis", "auto-task-latest"],
    ["./jarvis", "handoff-latest"],
    ["./jarvis", "handoff-print"],
]

def run(cmd):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
        return True, out.strip()
    except subprocess.CalledProcessError as e:
        return False, e.output.strip()
    except Exception as e:
        return False, str(e)

def main():
    print("JARVIS — Theo Padilha AI Worker CLI Smoke Test")
    print("")

    results = []
    for cmd in COMMANDS:
        ok, out = run(cmd)
        results.append((cmd, ok, out))
        print(("OK" if ok else "FALHA") + "  " + " ".join(cmd))

    passed = all(ok for _, ok, _ in results)

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
        "Teste local de comandos. Nada de produção.",
        "",
    ]

    for cmd, ok, out in results:
        lines += [
            f"## {' '.join(cmd)}",
            f"Status: {'OK' if ok else 'FALHA'}",
            "",
            "```text",
            out[-3000:],
            "```",
            "",
        ]

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("")
    print(f"Resultado: {'CLI SMOKE TEST PASSOU' if passed else 'CLI SMOKE TEST FALHOU'}")
    print(f"Relatório: {report.relative_to(ROOT)}")

    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
