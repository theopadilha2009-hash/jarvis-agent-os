from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def run(cmd):
    try:
        return 0, subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.strip()
    except Exception as e:
        return 1, str(e)

def check(label, ok, detail=""):
    status = "OK" if ok else "FALHA"
    print(f"{status}  {label}" + (f" — {detail}" if detail else ""))
    return ok

def main():
    print("JARVIS — Theo Padilha AI Worker Storage Health")
    print("")

    gitignore = ROOT / ".gitignore"
    gitignore_text = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""

    checks = []

    checks.append(check(
        ".gitignore existe",
        gitignore.exists(),
        ".gitignore encontrado" if gitignore.exists() else "ausente"
    ))

    checks.append(check(
        "ULTIMO_*.md ignorado",
        "07_RELATORIOS/02_TECNICOS/ULTIMO_*.md" in gitignore_text,
        "regra presente" if "07_RELATORIOS/02_TECNICOS/ULTIMO_*.md" in gitignore_text else "regra ausente"
    ))

    code, tracked_ultimos = run(["git", "ls-files", "07_RELATORIOS/02_TECNICOS/ULTIMO_*.md"])
    checks.append(check(
        "Nenhum ULTIMO_*.md versionado",
        tracked_ultimos.strip() == "",
        "limpo" if tracked_ultimos.strip() == "" else tracked_ultimos
    ))

    code, tracked = run(["git", "ls-files"])
    tracked_files = tracked.splitlines() if tracked else []

    forbidden_suffixes = (".env", ".pem", ".key", ".p12", ".pfx")
    forbidden_hits = [
        x for x in tracked_files
        if x.endswith(forbidden_suffixes)
        or "/.env" in x
        or x.split("/")[-1].startswith(".env")
    ]

    checks.append(check(
        "Nenhum arquivo secreto óbvio versionado",
        len(forbidden_hits) == 0,
        "limpo" if not forbidden_hits else ", ".join(forbidden_hits[:20])
    ))

    release_dir = ROOT / "07_RELATORIOS" / "03_RELEASES"
    release_count = len([p for p in release_dir.rglob("*") if p.is_file()]) if release_dir.exists() else 0
    checks.append(check(
        "Snapshots de release existem",
        release_count > 0,
        f"{release_count} arquivo(s)"
    ))

    smoke_dir = ROOT / "10_TESTES" / "SMOKE_TESTS"
    smoke_count = len([p for p in smoke_dir.glob("*.md")]) if smoke_dir.exists() else 0
    checks.append(check(
        "Smoke tests registrados",
        smoke_count > 0,
        f"{smoke_count} arquivo(s)"
    ))

    release_checks_dir = ROOT / "10_TESTES" / "RELEASE_CHECKS"
    release_check_count = len([p for p in release_checks_dir.glob("*.md")]) if release_checks_dir.exists() else 0
    checks.append(check(
        "Release checks registrados",
        release_check_count > 0,
        f"{release_check_count} arquivo(s)"
    ))

    print("")
    passed = all(checks)
    print("Resultado:", "STORAGE HEALTH PASSOU" if passed else "STORAGE HEALTH COM PENDÊNCIAS")
    print("Status real: validação local de armazenamento. Produção não alterada.")

    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
