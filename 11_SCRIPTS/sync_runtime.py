#!/usr/bin/env python3
"""sync_runtime.py — atualiza o checkout que o device worker executa.

O worker roda de ~/Library/Application Support/JARVIS/runtime/jarvis-agent-os
(um clone do repo). Ele não acompanha os deploys: ficou de 19/out enquanto o
repo já estava em 29/out, e por isso o app mandava "toca back in black" e o
worker, sem conhecer a faixa, caía na busca do Spotify.

Usage:
  ./jarvis runtime-sync            # mostra o que faria
  ./jarvis runtime-sync --apply    # atualiza e reinicia o worker
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RUNTIME = (
    Path.home() / "Library" / "Application Support" / "JARVIS" / "runtime" / "jarvis-agent-os"
)
WORKER_LABEL = "ai.theopadilha.jarvis-device-worker"


def run(cmd, cwd=None, timeout=180):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def runtime_state():
    if not (RUNTIME / ".git").is_dir():
        return {"ok": False, "reason": "runtime ausente (não é um clone git)"}
    head = run(["git", "rev-parse", "--short", "HEAD"], RUNTIME)
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], RUNTIME)
    return {
        "ok": True,
        "head": head.stdout.strip(),
        "branch": branch.stdout.strip(),
        "dirty": bool(run(["git", "status", "--porcelain"], RUNTIME).stdout.strip()),
    }


def restart_worker():
    if not shutil.which("launchctl"):
        return "sem launchctl"
    uid = run(["id", "-u"]).stdout.strip()
    result = run(["launchctl", "kickstart", "-k", f"gui/{uid}/{WORKER_LABEL}"])
    return "reiniciado" if result.returncode == 0 else f"falhou: {result.stderr.strip()[:80]}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis runtime-sync")
    parser.add_argument("--apply", action="store_true", help="atualiza de verdade e reinicia o worker")
    args = parser.parse_args(argv)

    print("JARVIS — Runtime Sync")
    print("Status real: sincroniza o checkout usado pelo device worker.")
    print(f"alvo: {RUNTIME}")
    print("")

    state = runtime_state()
    if not state["ok"]:
        print(f"FALHA: {state['reason']}")
        return 2

    print(f"HEAD atual: {state['head']} ({state['branch']})")
    fetched = run(["git", "fetch", "origin"], RUNTIME)
    if fetched.returncode != 0:
        print(f"FALHA ao buscar: {fetched.stderr.strip()[:160]}")
        return 2
    target = run(["git", "rev-parse", "--short", "origin/main"], RUNTIME).stdout.strip()
    print(f"origin/main: {target}")

    behind = run(["git", "rev-list", "--count", f"HEAD..origin/main"], RUNTIME).stdout.strip()
    print(f"commits atrás: {behind}")

    if not args.apply:
        print("")
        print("Modo: preview (nada alterado). Rode com --apply para atualizar.")
        print("Produção: nada alterado.")
        return 0

    reset = run(["git", "reset", "--hard", "origin/main"], RUNTIME)
    if reset.returncode != 0:
        print(f"FALHA ao atualizar: {reset.stderr.strip()[:160]}")
        return 2
    print(f"OK — runtime em {run(['git', 'rev-parse', '--short', 'HEAD'], RUNTIME).stdout.strip()}")
    print(f"worker: {restart_worker()}")
    print("Produção: nada alterado (só o checkout local do worker).")
    return 0


if __name__ == "__main__":
    sys.exit(main())