#!/usr/bin/env python3
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "05_EXECUCAO" / "62_RESEARCH_DIGEST"

REQUIRED = [
    "01_SOURCE_INDEX.md",
    "02_DIGEST.md",
    "03_JARVIS_EVOLUTION_PLAN.md",
    "04_N8N_LOOP_POSITION.md",
    "05_STATUS_REAL.md",
    "06_TECHNICAL_BACKLOG.md",
]

BAD_TEXT = [
    "outputsmap",
    "`./jarvis ignorados",
    "research-digest ignorados",
    "n8n position",
    "TODO genérico",
]

def latest_dir():
    if not BASE.exists():
        return None
    dirs = [p for p in BASE.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)

def main():
    parser = argparse.ArgumentParser(description="Valida um research digest gerado.")
    parser.add_argument("--path", default="", help="Pasta do digest. Se vazio, usa o último digest local.")
    args = parser.parse_args()

    target = Path(args.path).expanduser() if args.path else latest_dir()

    if not target or not target.exists():
        print("FAIL — nenhum digest encontrado.")
        print("Rode: ./jarvis research-digest")
        return 1

    missing = []
    bad_hits = []

    for name in REQUIRED:
        f = target / name
        if not f.exists():
            missing.append(name)
            continue

        text = f.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            bad_hits.append(f"{name}: arquivo vazio")

        for bad in BAD_TEXT:
            if bad in text:
                bad_hits.append(f"{name}: texto quebrado encontrado: {bad}")

    print("JARVIS — Research Digest Validate")
    print(f"Path: {target}")
    print("")

    if missing:
        print("FAIL — arquivos faltando:")
        for item in missing:
            print(f"  - {item}")

    if bad_hits:
        print("FAIL — problemas encontrados:")
        for item in bad_hits:
            print(f"  - {item}")

    if missing or bad_hits:
        return 1

    print("OK — digest válido.")
    print("Arquivos obrigatórios presentes.")
    print("Nenhum texto quebrado conhecido encontrado:
        return 1

    print("OK — digest válido.")
    print("Arquivos obrigatórios presentes.")
    print("Nen.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
