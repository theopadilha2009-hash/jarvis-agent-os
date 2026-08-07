#!/usr/bin/env python3
"""Lightweight Supabase queue worker for allowlisted JARVIS Mac actions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import signal
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
COMMANDS_TABLE = "jarvis_device_commands"
WORKERS_TABLE = "jarvis_device_workers"
WORKER_ID = "theo-mac"
WORKER_VERSION = "1"
HEARTBEAT_INTERVAL_SECONDS = 15.0
LAUNCH_LABEL = "ai.theopadilha.jarvis-device-worker"
LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_LABEL}.plist"
LOG_DIR = ROOT / "09_LOGS"
ALLOWED_ACTIONS = {
    "open_application",
    "close_application",
    "message_send",
    "screen_capture",
    "storage_scan",
    "system_memory",
}
TARGET_PATTERN = re.compile(r"^[\wÀ-ÿ ._-]{0,120}$")

try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from secret_scan import SECRET_PATTERNS  # type: ignore
except ImportError:
    SECRET_PATTERNS = []


class WorkerError(RuntimeError):
    """Safe worker error with no credential material."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def keychain_value(service: str) -> str:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", "theo", "-w"],
            text=True,
            capture_output=True,
            check=False,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def configuration() -> tuple[str, str]:
    base_url = (
        os.environ.get("SUPABASE_URL")
        or keychain_value("jarvis-agent-os.supabase-url")
    ).strip().rstrip("/")
    api_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or keychain_value("jarvis-agent-os.supabase-service-role-key")
    ).strip()
    if not base_url.startswith("https://") or not api_key:
        raise WorkerError("Supabase URL/chave server-side não estão disponíveis no ambiente ou Chaves do macOS.")
    return base_url, api_key


def rest_request(
    table: str,
    method: str = "GET",
    query: str = "",
    body: dict | None = None,
    prefer: str = "",
) -> list[dict]:
    if table not in {COMMANDS_TABLE, WORKERS_TABLE}:
        raise WorkerError("Tabela fora do allowlist do worker.")
    base_url, api_key = configuration()
    url = f"{base_url}/rest/v1/{table}"
    if query:
        url = f"{url}?{query}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(1_000_000)
    except HTTPError as error:
        raise WorkerError(f"Supabase recusou o worker (HTTP {error.code}).") from error
    except (URLError, TimeoutError) as error:
        raise WorkerError("Supabase não respondeu ao worker.") from error
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else []
    except json.JSONDecodeError as error:
        raise WorkerError("Supabase respondeu em formato inválido.") from error
    return parsed if isinstance(parsed, list) else []


def redact_secrets(value: str) -> str:
    safe = str(value or "")[:8_000]
    for _name, pattern in SECRET_PATTERNS:
        safe = pattern.sub("[REDACTED]", safe)
    return safe


def contains_secret(value: str) -> bool:
    return any(pattern.search(str(value or "")) for _name, pattern in SECRET_PATTERNS)


def heartbeat() -> None:
    row = {
        "worker_id": WORKER_ID,
        "owner_id": "theo",
        "hostname": platform.node() or "Theo-Mac",
        "version": WORKER_VERSION,
        "last_seen_at": now_iso(),
    }
    rest_request(
        WORKERS_TABLE,
        "POST",
        query="on_conflict=worker_id",
        body=row,
        prefer="resolution=merge-duplicates,return=minimal",
    )


def pending_command() -> dict | None:
    rows = rest_request(
        COMMANDS_TABLE,
        query=(
            "select=id,action,target,request_text,status,created_at"
            "&owner_id=eq.theo&status=eq.pending&order=created_at.asc&limit=1"
        ),
    )
    return rows[0] if rows else None


def claim_command(command_id: int) -> dict | None:
    rows = rest_request(
        COMMANDS_TABLE,
        "PATCH",
        query=f"owner_id=eq.theo&id=eq.{command_id}&status=eq.pending",
        body={"status": "running", "claimed_at": now_iso()},
        prefer="return=representation",
    )
    return rows[0] if rows else None


def finish_command(command_id: int, succeeded: bool, result: str) -> None:
    rest_request(
        COMMANDS_TABLE,
        "PATCH",
        query=f"owner_id=eq.theo&id=eq.{command_id}&status=eq.running",
        body={
            "status": "succeeded" if succeeded else "failed",
            "result": redact_secrets(result),
            "completed_at": now_iso(),
        },
        prefer="return=minimal",
    )


def command_argv(job: dict) -> list[str]:
    action = str(job.get("action") or "")
    target = str(job.get("target") or "").strip()
    if action not in ALLOWED_ACTIONS:
        raise WorkerError("Ação recebida fora do allowlist.")
    if not TARGET_PATTERN.fullmatch(target):
        raise WorkerError("Aplicativo recebido com nome inválido.")
    if action == "system_memory":
        return [str(ROOT / "jarvis"), "system-memory"]
    if action == "screen_capture":
        return [str(ROOT / "jarvis"), "screen-capture"]
    if action == "storage_scan":
        if target != "downloads":
            raise WorkerError("Destino de armazenamento fora do allowlist.")
        return [
            str(ROOT / "jarvis"),
            "storage-scan",
            str(Path.home() / "Downloads"),
            "--top",
            "20",
            "--min-mb",
            "50",
        ]
    if action == "message_send":
        details = message_details(str(job.get("request_text") or ""), target)
        if not details:
            raise WorkerError("Mensagem recebida sem telefone e texto válidos.")
        return [
            str(ROOT / "jarvis"),
            "message-send",
            "--phone",
            details["phone"],
            details["text"],
        ]
    if not target:
        raise WorkerError("A ação de aplicativo chegou sem alvo.")
    verb = "open" if action == "open_application" else "close"
    return [str(ROOT / "jarvis"), "computer", verb, target]


def message_details(request_text: str, expected_phone: str) -> dict | None:
    text = str(request_text or "")[:8_000]
    phone_match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", text)
    if not phone_match:
        return None
    phone = "".join(char for char in phone_match.group(0) if char.isdigit())
    if phone != expected_phone or not 8 <= len(phone) <= 15:
        return None
    quoted = re.search(r'["“](.+?)["”]', text)
    body = quoted.group(1).strip() if quoted else re.sub(
        re.escape(phone_match.group(0)), "", text, count=1
    ).strip(" :-")
    if not quoted:
        body = re.sub(
            r"^\s*(?:jarvis[,\s]+)?(?:mand(?:a|e|ar)|envi(?:a|e|ar)|escrev(?:a|e|er))\s+"
            r"(?:uma\s+)?(?:mensagem|msg)\s*(?:para)?\s*",
            "",
            body,
            flags=re.I,
        ).strip(" :-")
        body = re.sub(
            r"^(?:dizendo|falando|com\s+(?:o\s+)?texto|texto)\s*",
            "",
            body,
            flags=re.I,
        ).strip(" :-")
    if not body or len(body) > 4_000 or contains_secret(body):
        return None
    return {"phone": phone, "text": body}


def execute_job(job: dict) -> tuple[bool, str]:
    argv = command_argv(job)
    try:
        result = subprocess.run(
            argv,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=90,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return False, "A ação local excedeu 90 segundos e foi interrompida."
    output = (result.stdout or result.stderr or "").strip()
    return result.returncode == 0, output or f"Processo finalizado com exit code {result.returncode}."


def run_once(preview: bool = False) -> str:
    job = pending_command()
    if not job:
        return "Fila vazia; nenhum comando executado."
    command_id = int(job.get("id"))
    action = str(job.get("action") or "")
    target = str(job.get("target") or "")
    if preview:
        return f"Preview: ação {command_id} aguardando ({action} {target})."
    claimed = claim_command(command_id)
    if not claimed:
        return f"Ação {command_id} já foi assumida por outro worker."
    try:
        succeeded, output = execute_job(claimed)
    except WorkerError as error:
        succeeded, output = False, str(error)
    finish_command(command_id, succeeded, output)
    state = "concluída" if succeeded else "falhou"
    return f"Ação {command_id} {state}: {action} {target}".strip()


def launch_domain() -> str:
    return f"gui/{os.getuid()}"


def launch_payload() -> dict:
    return {
        "Label": LAUNCH_LABEL,
        "ProgramArguments": [
            sys.executable,
            str(Path(__file__).resolve()),
            "--watch",
            "--interval",
            "3",
        ],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "StandardOutPath": str(LOG_DIR / "device-worker.log"),
        "StandardErrorPath": str(LOG_DIR / "device-worker-error.log"),
    }


def install_agent(preview: bool = False) -> None:
    payload = launch_payload()
    if preview:
        print(f"Preview: criaria {LAUNCH_AGENT} e ativaria {LAUNCH_LABEL}.")
        return
    LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENT.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True))
    subprocess.run(
        ["launchctl", "bootout", f"{launch_domain()}/{LAUNCH_LABEL}"],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    result = None
    for _attempt in range(5):
        result = subprocess.run(
            ["launchctl", "bootstrap", launch_domain(), str(LAUNCH_AGENT)],
            text=True,
            capture_output=True,
            check=False,
            timeout=15,
        )
        if result.returncode == 0:
            break
        time.sleep(0.4)
    assert result is not None
    if result.returncode != 0:
        raise WorkerError("O launchd recusou a ativação do worker local.")
    print(f"Worker instalado: {LAUNCH_LABEL}")


def uninstall_agent(preview: bool = False) -> None:
    if preview:
        print(f"Preview: desativaria {LAUNCH_LABEL} e removeria {LAUNCH_AGENT}.")
        return
    subprocess.run(
        ["launchctl", "bootout", f"{launch_domain()}/{LAUNCH_LABEL}"],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if LAUNCH_AGENT.exists():
        LAUNCH_AGENT.unlink()
    print(f"Worker removido: {LAUNCH_LABEL}")


def agent_status() -> None:
    result = subprocess.run(
        ["launchctl", "print", f"{launch_domain()}/{LAUNCH_LABEL}"],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if result.returncode == 0:
        pid_match = re.search(r"\bpid\s*=\s*(\d+)", result.stdout)
        pid = pid_match.group(1) if pid_match else "iniciando"
        print(f"Worker ativo no launchd · PID {pid}")
    else:
        print("Worker não está ativo no launchd.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JARVIS local device queue worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="processa no máximo uma ação")
    mode.add_argument("--watch", action="store_true", help="mantém polling leve e heartbeat")
    mode.add_argument("--install", action="store_true", help="instala e ativa LaunchAgent")
    mode.add_argument("--uninstall", action="store_true", help="remove LaunchAgent")
    mode.add_argument("--status", action="store_true", help="consulta LaunchAgent")
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    preview = bool(args.dry_run or os.environ.get("JARVIS_NO_REPORT") == "1")
    print("JARVIS — Device Worker")
    print("Status real: ponte local allowlisted entre Supabase e o Mac.")
    try:
        if args.install:
            install_agent(preview)
        elif args.uninstall:
            uninstall_agent(preview)
        elif args.status:
            agent_status()
        elif args.watch:
            if preview:
                print("Preview: consultaria a fila continuamente; nenhum heartbeat ou comando foi gravado.")
            else:
                running = True
                last_heartbeat = 0.0

                def stop(_signum, _frame):
                    nonlocal running
                    running = False

                signal.signal(signal.SIGTERM, stop)
                signal.signal(signal.SIGINT, stop)
                while running:
                    try:
                        monotonic_now = time.monotonic()
                        if monotonic_now - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                            heartbeat()
                            last_heartbeat = monotonic_now
                        message = run_once()
                        if not message.startswith("Fila vazia"):
                            print(message, flush=True)
                    except WorkerError as error:
                        print(f"Worker aguardando reconexão: {error}", flush=True)
                    time.sleep(max(1.0, min(args.interval, 30.0)))
        else:
            if preview:
                print("Preview: consultaria uma ação pendente; nenhum heartbeat ou comando foi gravado.")
            else:
                heartbeat()
                print(run_once())
    except WorkerError as error:
        print(f"FALHA: {error}")
        print("Produção: nenhum deploy alterado.")
        return 1
    print("Produção: nenhum deploy alterado; somente ações locais allowlisted podem ser executadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
