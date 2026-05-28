#!/usr/bin/env python3
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "05_EXECUCAO" / "62_RESEARCH_DIGEST"

FILES = {
    "plan": "03_JARVIS_EVOLUTION_PLAN.md",
    "digest": "02_DIGEST.md",
    "n8n": "04_N8N_LOOP_POSITION.md",
    "status": "05_STATUS_REAL.md",
    "backlog": "06_TECHNICAL_BACKLOG.md",
    "index": "01_SOURCE_INDEX.md",
}

def latest_dir():
    if not BASE.exists():
        return None
    dirs = [p for p in BASE.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)

def main():
    parser = argparse.ArgumentParser(description="Mostra último research digest gerado.")
    parser.add_argument("--file", choices=sorted(FILES), default="plan")
    parser.add_argument("--lines", type=int, default=220)
    args = parser.parse_args()

    latest = latest_dir()
    if not latest:
        print("Nenhum digest encontrado.")
        print("Rode: ./jarvis research-digest")
        return 1

    target = latest / FILES[args.file]
    print("JARVIS — Latest Research Digest")
    print(f"Path: {latest.relative_to(ROOT)}")
    print(f"File: {FILES[args.file]}")
    print("")

    if not target.exists():
        print(f"Arquivo não encontrado: {target.relative_to(ROOT)}")
        return 1

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[: args.lines]:
        print(line)

    if len(lines) > args.lines:
        print("")
        print(f"... cortado em {args.lines} linhas")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
