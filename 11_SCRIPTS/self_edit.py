#!/usr/bin/env python3
"""Run a real, isolated JARVIS self-edit with the local Codex CLI."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = Path.home() / "Library" / "Application Support" / "JARVIS" / "self-edits"
RESTART_MARKER = RUN_ROOT / "restart-device-worker"
PUBLISH_REMOTE = "jarvis-origin"
PUBLISH_REPOSITORY = "theopadilha2009-hash/jarvis-agent-os"
PUBLISH_REMOTE_URL = "https://github.com/theopadilha2009-hash/jarvis-agent-os.git"
PUBLISH_BASE_BRANCH = "main"
VERCEL_PROJECT = {
    "projectId": "prj_GwOIFRIqDjSOr97UT3z2BZwmjpqF",
    "orgId": "team_NZSAr4PoQtmbTxc2MxkMpKUu",
    "projectName": "jarvis-agent-os",
}
PRODUCTION_URL = "https://jarvis-agent-os-delta.vercel.app"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECRET_LIKE = re.compile(
    r"\b(?:sk-or-v1-|sbp_|vcp_|sk_)[A-Za-z0-9_-]{12,}|"
    r"\b(?:api[_ -]?key|token|password|senha)\b\s*[:=]\s*\S{8,}",
    re.I,
)


class SelfEditError(RuntimeError):
    """A self-edit could not be started or validated."""

    def __init__(self, message: str, production: str = "nada alterado.") -> None:
        super().__init__(message)
        self.production = production


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


def format_duration(seconds: float) -> str:
    total = max(0.0, seconds)
    minutes, remaining_seconds = divmod(total, 60)
    hours, remaining_minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours}h {remaining_minutes:02d}m {remaining_seconds:06.3f}s"
    if minutes:
        return f"{int(minutes)}m {remaining_seconds:06.3f}s"
    return f"{remaining_seconds:.3f}s"


def print_footer(started_at: float, production: str) -> None:
    print(f"Duração total: {format_duration(time.monotonic() - started_at)}.")
    print(production)


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


def normalized_remote_url(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("git@github.com:"):
        text = "https://github.com/" + text.split(":", 1)[1]
    if text.startswith("ssh://git@github.com/"):
        text = "https://github.com/" + text.split("ssh://git@github.com/", 1)[1]
    return text.removesuffix("/").removesuffix(".git") + ".git"


def publish_preflight() -> dict[str, str]:
    gh = shutil.which("gh")
    vercel = shutil.which("vercel")
    if not gh:
        raise SelfEditError("GitHub CLI não está instalado no Mac do worker.")
    if not vercel:
        raise SelfEditError("Vercel CLI não está instalado no Mac do worker.")

    remote = run(["git", "remote", "get-url", PUBLISH_REMOTE], ROOT)
    actual_remote = normalized_remote_url(remote.stdout) if remote.returncode == 0 else ""
    if actual_remote != PUBLISH_REMOTE_URL:
        raise SelfEditError(
            f"O remoto autorizado {PUBLISH_REMOTE} não aponta para {PUBLISH_REPOSITORY}; publicação recusada."
        )

    linked_project = ROOT / ".vercel" / "project.json"
    try:
        linked = json.loads(linked_project.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        raise SelfEditError("O vínculo local com o projeto Vercel do JARVIS não está disponível.")
    if any(linked.get(key) != value for key, value in VERCEL_PROJECT.items()):
        raise SelfEditError("O projeto Vercel vinculado não é o jarvis-agent-os autorizado.")

    auth = run([gh, "auth", "status", "--hostname", "github.com"], ROOT, timeout=30)
    if auth.returncode != 0:
        raise SelfEditError("GitHub CLI não está autenticado para publicar o JARVIS.")
    repository = run(
        [gh, "repo", "view", PUBLISH_REPOSITORY, "--json", "nameWithOwner"],
        ROOT,
        timeout=30,
    )
    try:
        repository_name = json.loads(repository.stdout).get("nameWithOwner")
    except (ValueError, json.JSONDecodeError, AttributeError):
        repository_name = ""
    if repository.returncode != 0 or repository_name != PUBLISH_REPOSITORY:
        raise SelfEditError("A conta GitHub ativa não confirmou acesso ao repositório JARVIS.")
    identity = run([vercel, "whoami"], ROOT, timeout=60)
    if identity.returncode != 0:
        raise SelfEditError("Vercel CLI não está autenticado para o deploy do JARVIS.")
    return {"gh": gh, "vercel": vercel}


def production_healthcheck(attempts: int = 6) -> dict:
    last_error = "sem resposta"
    for attempt in range(max(1, attempts)):
        try:
            request = Request(
                f"{PRODUCTION_URL}/status",
                headers={"Accept": "application/json", "User-Agent": "jarvis-self-edit/1"},
            )
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read(200_000).decode("utf-8"))
            if response.status == 200 and payload.get("ok") and payload.get("service") == "jarvis-web":
                return payload
            last_error = "payload de status inválido"
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            last_error = type(error).__name__
        if attempt + 1 < attempts:
            time.sleep(2)
    raise SelfEditError(
        f"O deploy terminou, mas a produção não confirmou saúde ({last_error}).",
        "GitHub main foi atualizado e a Vercel recebeu um deploy; saúde pública ainda não confirmada.",
    )


def deployment_url(output: str) -> str:
    clean = ANSI_ESCAPE.sub("", str(output or ""))
    urls = re.findall(r"https://[A-Za-z0-9.-]+\.vercel\.app", clean)
    generated = [url for url in urls if url != PRODUCTION_URL]
    return generated[-1] if generated else PRODUCTION_URL if urls else ""


def write_publish_report(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# JARVIS self-publish — status real",
        "",
        f"- Repository: `{PUBLISH_REPOSITORY}`",
        f"- Pull request: {result['pr_url']}",
        f"- Merge commit: `{result['merge_commit']}`",
        f"- Vercel project: `{VERCEL_PROJECT['projectName']}`",
        f"- Deployment: {result['deployment_url'] or 'URL individual não retornada'}",
        f"- Production: {PRODUCTION_URL}",
        f"- Health: `{result['health']}`",
        f"- Local runtime: `{result['local_runtime']}`",
        "",
        "Autorização: `--publish` explícito fornecido pelo operador Theo.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def activate_local_runtime(merge_commit: str) -> str:
    status = run(["git", "status", "--porcelain"], ROOT)
    if status.returncode != 0 or status.stdout.strip():
        return "skipped_dirty_worktree"
    activated = run(["git", "merge", "--ff-only", merge_commit], ROOT, timeout=180)
    if activated.returncode != 0:
        return "skipped_non_fast_forward"
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    RESTART_MARKER.write_text(merge_commit + "\n", encoding="utf-8")
    return "fast_forwarded_restart_requested"


def publish_release(
    worktree: Path,
    branch: str,
    goal: str,
    binaries: dict[str, str],
    report: Path,
) -> dict:
    gh = binaries["gh"]
    vercel = binaries["vercel"]
    pushed = run(
        ["git", "push", "--set-upstream", PUBLISH_REMOTE, branch],
        worktree,
        timeout=300,
    )
    if pushed.returncode != 0:
        raise SelfEditError("O GitHub recusou o push da branch validada.")

    title = f"Self-edit: {goal}"[:100]
    body = (
        "## Mudança\n\n"
        f"Autoedição solicitada explicitamente por Theo: {goal}\n\n"
        "## Validação\n\n"
        "- bash -n ./jarvis\n"
        "- git diff --check\n"
        "- py_compile nos Python alterados\n"
        "- command-audit\n"
        "- safety-gate pós-commit\n\n"
        "## Publicação\n\n"
        "Autorização explícita registrada pelo modo `self-edit --publish`.\n"
    )
    created = run(
        [
            gh,
            "pr",
            "create",
            "--repo",
            PUBLISH_REPOSITORY,
            "--base",
            PUBLISH_BASE_BRANCH,
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ],
        worktree,
        timeout=120,
    )
    pr_url = next(
        (line.strip() for line in created.stdout.splitlines() if line.strip().startswith("https://github.com/")),
        "",
    )
    if created.returncode != 0 or not pr_url:
        raise SelfEditError(
            "A branch foi enviada, mas o pull request não foi criado.",
            f"branch {branch} enviada ao GitHub; main e Vercel não alterados.",
        )

    merged = run(
        [gh, "pr", "merge", pr_url, "--repo", PUBLISH_REPOSITORY, "--merge"],
        worktree,
        timeout=300,
    )
    if merged.returncode != 0:
        raise SelfEditError(
            "O pull request foi criado, mas o GitHub não confirmou o merge.",
            f"PR aberto em {pr_url}; main e Vercel não alterados.",
        )

    viewed = run(
        [gh, "pr", "view", pr_url, "--repo", PUBLISH_REPOSITORY, "--json", "state,mergeCommit,url"],
        worktree,
        timeout=60,
    )
    try:
        pr = json.loads(viewed.stdout)
        merge_commit = str((pr.get("mergeCommit") or {}).get("oid") or "")
    except (ValueError, json.JSONDecodeError, AttributeError):
        pr = {}
        merge_commit = ""
    if viewed.returncode != 0 or pr.get("state") != "MERGED" or not re.fullmatch(r"[0-9a-f]{40}", merge_commit):
        raise SelfEditError(
            "O GitHub não retornou evidência válida do merge.",
            f"PR {pr_url} recebeu operação de merge; estado final não confirmado e Vercel não alterada.",
        )
    run(["git", "push", PUBLISH_REMOTE, "--delete", branch], worktree, timeout=120)

    fetched = run(["git", "fetch", PUBLISH_REMOTE, PUBLISH_BASE_BRANCH], ROOT, timeout=180)
    if fetched.returncode != 0:
        raise SelfEditError(
            "O merge ocorreu, mas o commit não foi baixado para o deploy.",
            f"GitHub main atualizado em {merge_commit}; Vercel não alterada.",
        )

    deploy_worktree = RUN_ROOT / "deployments" / merge_commit
    deploy_worktree.parent.mkdir(parents=True, exist_ok=True)
    deployed_tree = run(
        ["git", "worktree", "add", "--detach", str(deploy_worktree), merge_commit],
        ROOT,
        timeout=180,
    )
    if deployed_tree.returncode != 0:
        raise SelfEditError(
            "O merge ocorreu, mas o worktree exato de deploy não foi criado.",
            f"GitHub main atualizado em {merge_commit}; Vercel não alterada.",
        )

    deploy = None
    try:
        vercel_dir = deploy_worktree / ".vercel"
        vercel_dir.mkdir(parents=True, exist_ok=True)
        project_file = vercel_dir / "project.json"
        project_file.write_text(json.dumps(VERCEL_PROJECT, separators=(",", ":")), encoding="utf-8")
        deploy = run([vercel, "--prod", "--yes"], deploy_worktree, timeout=900, env=os.environ.copy())
        if deploy.returncode != 0:
            raise SelfEditError(
                "O GitHub main foi atualizado, mas a Vercel recusou o deploy.",
                f"GitHub main atualizado em {merge_commit}; deploy Vercel não confirmado.",
            )
        health = production_healthcheck()
        local_runtime = activate_local_runtime(merge_commit)
        result = {
            "pr_url": pr_url,
            "merge_commit": merge_commit,
            "deployment_url": deployment_url((deploy.stdout or "") + "\n" + (deploy.stderr or "")),
            "health": health.get("status_real", "web_cockpit_ready"),
            "local_runtime": local_runtime,
        }
        publish_report = report.with_name(report.stem + "-publish.md")
        write_publish_report(publish_report, result)
        result["report"] = str(publish_report)
        return result
    finally:
        project_file = deploy_worktree / ".vercel" / "project.json"
        if project_file.exists():
            project_file.unlink()
        vercel_dir = deploy_worktree / ".vercel"
        if vercel_dir.is_dir():
            try:
                vercel_dir.rmdir()
            except OSError:
                pass
        run(["git", "worktree", "remove", str(deploy_worktree)], ROOT, timeout=180)


def execute(
    goal: str,
    dry_run: bool = False,
    publish: bool = False,
    started_at: float | None = None,
) -> int:
    started_at = time.monotonic() if started_at is None else started_at
    request = " ".join(str(goal or "").split()).strip()
    if len(request) < 12:
        raise SelfEditError("Descreva a melhoria dos scripts com pelo menos 12 caracteres.")
    if len(request) > 2_000:
        raise SelfEditError("O pedido de autoedição excede 2.000 caracteres.")
    if SECRET_LIKE.search(request):
        raise SelfEditError("O pedido parece conter uma credencial; remova o segredo antes da autoedição.")

    preview = dry_run or os.environ.get("JARVIS_NO_REPORT") == "1"
    codex = shutil.which("codex")
    if not codex and not preview:
        raise SelfEditError("Codex CLI não está instalado no Mac do worker.")
    publish_binaries = publish_preflight() if publish and not preview else {}

    if publish and not preview:
        fetched = run(["git", "fetch", PUBLISH_REMOTE, PUBLISH_BASE_BRANCH], ROOT, timeout=180)
        if fetched.returncode != 0:
            raise SelfEditError("Não foi possível atualizar a referência jarvis-origin/main antes da autoedição.")

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
    print(f"Publicação: {'GitHub main + Vercel production autorizados' if publish else 'desativada'}.")
    if publish:
        print(f"Alvos fixos: {PUBLISH_REPOSITORY} · {VERCEL_PROJECT['projectName']} · {PRODUCTION_URL}")
    if preview:
        print("Modo preview: nenhum worktree, diff ou commit criado.")
        print_footer(started_at, "Produção: nada alterado.")
        return 0

    RUN_ROOT.joinpath("worktrees").mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    base_ref = f"{PUBLISH_REMOTE}/{PUBLISH_BASE_BRANCH}" if publish else "HEAD"
    created = run(["git", "worktree", "add", "-b", branch, str(worktree), base_ref], ROOT)
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
    if publish:
        released = publish_release(worktree, branch, request, publish_binaries, report)
        print(f"Pull request: {released['pr_url']}")
        print(f"Merge commit: {released['merge_commit']}")
        print(f"Deploy: {released['deployment_url'] or PRODUCTION_URL}")
        print(f"Saúde pública: {released['health']}")
        print(f"Runtime local: {released['local_runtime']}")
        print(f"Relatório de publicação: {released['report']}")
        print_footer(
            started_at,
            f"Produção: GitHub main e {PRODUCTION_URL} atualizados e verificados.",
        )
    else:
        print_footer(started_at, "Produção: nada alterado; branch local não enviada nem mesclada.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Autoedição isolada e validada do JARVIS")
    parser.add_argument("goal", nargs="+", help="melhoria explícita para os próprios scripts")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="após os gates, envia ao jarvis-origin, mescla em main e faz deploy no jarvis-agent-os",
    )
    return parser


def main() -> int:
    started_at = time.monotonic()
    args = build_parser().parse_args()
    try:
        return execute(
            " ".join(args.goal),
            dry_run=args.dry_run,
            publish=args.publish,
            started_at=started_at,
        )
    except SelfEditError as error:
        print("JARVIS Self Edit")
        print(f"Status real: autoedição não concluída — {error}")
        print_footer(started_at, f"Produção: {error.production}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
