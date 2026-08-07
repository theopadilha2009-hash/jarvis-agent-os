#!/usr/bin/env python3
"""Run a real, isolated JARVIS self-edit with the local Codex CLI."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = Path.home() / "Library" / "Application Support" / "JARVIS" / "self-edits"
SECRET_LIKE = re.compile(
    r"\b(?:sk-or-v1-|sbp_|vcp_|sk_)[A-Za-z0-9_-]{12,}|"
    r"\b(?:api[_ -]?key|token|password|senha)\b\s*[:=]\s*\S{8,}",
    re.I,
)


class SelfEditError(RuntimeError):
    """A self-edit could not be started or validated."""


def run(argv: list[str], cwd: Path, timeout: int = 180, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )


def slug(value: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:36]
    return safe or "melhoria"


def changed_files(worktree: Path) -> list[str]:
    result = run(["git", "status", "--short"], worktree)
    if result.returncode != 0:
        raise SelfEditError("Git não conseguiu listar o diff criado.")
    return [line[3:].strip() for line in result.stdout.splitlines() if len(line) > 3]


def validation_commands(files: list[str]) -> list[list[str]]:
    commands = [
        ["bash", "-n", "./jarvis"],
        ["git", "diff", "--check"],
    ]
    commands.extend(
        [[sys.executable, "-m", "py_compile", path] for path in files if path.endswith(".py")]
    )
    commands.extend([
        ["./jarvis", "command-audit"],
    ])
    return commands


def execute(goal: str, dry_run: bool = False) -> int:
    request = " ".join(str(goal or "").split()).strip()
    if len(request) < 12:
        raise SelfEditError("Descreva a melhoria dos scripts com pelo menos 12 caracteres.")
    if len(request) > 2_000:
        raise SelfEditError("O pedido de autoedição excede 2.000 caracteres.")
    if SECRET_LIKE.search(request):
        raise SelfEditError("O pedido parece conter uma credencial; remova o segredo antes da autoedição.")

    codex = shutil.which("codex")
    preview = dry_run or os.environ.get("JARVIS_NO_REPORT") == "1"
    if not codex and not preview:
        raise SelfEditError("Codex CLI não está instalado no Mac do worker.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    branch = f"jarvis/self-edit-{timestamp}-{slug(request)}"
    worktree = RUN_ROOT / "worktrees" / branch.replace("/", "-")
    report = RUN_ROOT / "reports" / f"{branch.replace('/', '-')}.md"

    print("JARVIS Self Edit")
    if codex:
        print("Status real: autoedição isolada preparada para o Codex local.")
    else:
        print("Status real: preview de autoedição; Codex local indisponível.")
    print(f"Objetivo: {request}")
    print(f"Branch: {branch}")
    print(f"Worktree: {worktree}")
    print(f"Codex CLI: {'disponível' if codex else 'indisponível'}.")
    if preview:
        print("Modo preview: nenhum worktree, diff ou commit criado.")
        print("Produção: nada alterado.")
        return 0

    RUN_ROOT.joinpath("worktrees").mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    created = run(["git", "worktree", "add", "-b", branch, str(worktree), "HEAD"], ROOT)
    if created.returncode != 0:
        raise SelfEditError("Git não conseguiu criar o worktree isolado.")

    prompt = f"""Você está no worktree isolado do próprio JARVIS.
Leia e obedeça completamente o AGENTS.md deste repositório.

OBJETIVO EXPLÍCITO DO THEO:
{request}

Implemente uma mudança pequena, real e verificável nos próprios scripts do JARVIS.
Trabalhe apenas dentro deste repositório. Não leia ou exponha segredos. Não faça push,
deploy, merge, PR, acesso a contas, mensagens ou outras ações externas. Não faça commit.
Preserve recursos existentes. Rode testes proporcionais e deixe o diff no worktree.
No fim, relate arquivos alterados, testes e o que não foi validado.
"""
    agent = run(
        [
            codex,
            "exec",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(worktree),
            "--output-last-message",
            str(report),
            prompt,
        ],
        worktree,
        timeout=900,
        env=os.environ.copy(),
    )
    if agent.returncode != 0:
        raise SelfEditError(
            f"Codex local terminou com exit code {agent.returncode}; o worktree foi preservado para inspeção."
        )

    files = changed_files(worktree)
    if not files:
        raise SelfEditError("Codex terminou sem criar um diff; nenhum resultado foi inventado.")

    validation_env = os.environ.copy()
    validation_env["JARVIS_NO_REPORT"] = "1"
    failures = []
    for command in validation_commands(files):
        result = run(command, worktree, timeout=300, env=validation_env)
        if result.returncode != 0:
            failures.append(f"{' '.join(command)} (exit {result.returncode})")
    if failures:
        raise SelfEditError(
            "Validação falhou; o diff foi preservado sem commit: " + "; ".join(failures)
        )

    added = run(["git", "add", "-A"], worktree)
    if added.returncode != 0:
        raise SelfEditError("Git não conseguiu preparar o diff validado.")
    committed = run(
        ["git", "commit", "-m", f"feat: self-edit {slug(request)}"],
        worktree,
        timeout=180,
    )
    if committed.returncode != 0:
        raise SelfEditError("O diff passou nos testes, mas o commit local não foi criado.")
    commit = run(["git", "rev-parse", "--short", "HEAD"], worktree).stdout.strip()

    safety = run(["./jarvis", "safety-gate"], worktree, timeout=300, env=validation_env)
    if safety.returncode != 0:
        raise SelfEditError(
            f"Safety gate pós-commit falhou; checkpoint local {commit} preservado sem push ou merge."
        )

    print(f"Arquivos alterados: {', '.join(files)}")
    print(f"Commit local: {commit}")
    print(f"Relatório do agente: {report}")
    print("Testes: bash -n, diff --check, py_compile aplicável e command-audit passaram antes do checkpoint; safety-gate passou com a árvore limpa.")
    print("Produção: nada alterado; branch local não enviada nem mesclada.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Autoedição isolada e validada do JARVIS")
    parser.add_argument("goal", nargs="+", help="melhoria explícita para os próprios scripts")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return execute(" ".join(args.goal), dry_run=args.dry_run)
    except SelfEditError as error:
        print("JARVIS Self Edit")
        print(f"Status real: autoedição não concluída — {error}")
        print("Produção: nada alterado.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
