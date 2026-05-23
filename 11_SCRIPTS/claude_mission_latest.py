from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"


def rel(path):
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def age_str(path):
    if not path or not path.exists():
        return "—"
    secs = int((datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


def main():
    print("JARVIS — Theo Padilha AI Worker Claude Mission Latest")
    print("Status real: leitura local da missão mais recente. Nenhum projeto foi editado.")
    print("")

    if not OUT_DIR.exists():
        print("Nenhuma missão registrada ainda.")
        print(f"Pasta esperada: 05_EXECUCAO/21_CLAUDE_MISSIONS")
        print("")
        print('Para criar: ./jarvis claude-mission --jarvis-core --type audit "tarefa"')
        print("Produção: nada alterado.")
        return

    dirs = [d for d in OUT_DIR.iterdir() if d.is_dir()]
    if not dirs:
        print("Nenhuma missão registrada ainda.")
        print(f"Pasta: {rel(OUT_DIR)} (vazia)")
        print("")
        print('Para criar: ./jarvis claude-mission --jarvis-core --type audit "tarefa"')
        print("Produção: nada alterado.")
        return

    latest = max(dirs, key=lambda d: d.stat().st_mtime)
    summary = latest / "00_MISSION_SUMMARY.md"
    prompt = latest / "01_CLAUDE_PROMPT.md"
    checklist = latest / "02_VALIDATION_CHECKLIST.md"
    return_fmt = latest / "03_RETURN_FORMAT.md"

    print(f"Mission pack: {rel(latest)}")
    print(f"Idade: {age_str(latest)}")
    print("")
    print("Arquivos:")
    for f in (summary, prompt, checklist, return_fmt):
        marker = "OK" if f.exists() else "AUSENTE"
        print(f"- [{marker}] {rel(f)}")
    print("")

    if summary.exists():
        print("=== Preview: 00_MISSION_SUMMARY.md (primeiras 30 linhas) ===")
        text = summary.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        for line in lines[:30]:
            print(line)
        if len(lines) > 30:
            print("...")
        print("")

    print(f"Para colar no Claude Code, abra: {rel(prompt)}")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
