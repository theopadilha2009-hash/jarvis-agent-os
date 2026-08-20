#!/usr/bin/env python3
"""Lightweight Supabase queue worker for allowlisted JARVIS Mac actions."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from difflib import get_close_matches
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import signal
import subprocess
import tempfile
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
from spotify_control import command_args as spotify_command_args  # noqa: E402
from device_actions import (  # noqa: E402
    IMAGE_NATIVE_FORMATS,
    clipboard_text,
    extract_https_url,
    folder_id,
    image_convert_format,
    image_convert_source,
    notify_text,
    payload_from_text,
    safe_https_url,
    speak_text,
    volume_level,
)
COMMANDS_TABLE = "jarvis_device_commands"
WORKERS_TABLE = "jarvis_device_workers"
WORKER_ID = "theo-mac"
WORKER_VERSION = "13"
HEARTBEAT_INTERVAL_SECONDS = 15.0
RECOVERY_INTERVAL_SECONDS = 60.0
STALE_AFTER_SECONDS = 300
RETENTION_INTERVAL_SECONDS = 21_600.0
ARTIFACT_KEEP_COUNT = 20
ARTIFACT_MAX_AGE_DAYS = 30
ARRIVAL_COCKPIT_URL = os.environ.get("JARVIS_COCKPIT_URL", "https://jarvis-theo.vercel.app")
ARRIVAL_MIN_LOCKED_SECONDS = 600.0
ARRIVAL_COOLDOWN_SECONDS = 3_600.0
ARRIVAL_STATE = (
    Path.home() / "Library" / "Application Support" / "JARVIS" / "last-arrival"
)
BOOT_STATE = (
    Path.home() / "Library" / "Application Support" / "JARVIS" / "last-boot"
)
BOOT_QUIET_SECONDS = 20.0
# A saudação sai pelo alto-falante do Mac: o navegador cala áudio sem clique.
LOCAL_TTS_URL = os.environ.get("JARVIS_LOCAL_TTS_URL", "http://127.0.0.1:8123/speech")
LOCAL_SAY_VOICE = os.environ.get("JARVIS_SAY_VOICE", "Reed")
BOOT_GREETING = "Bom dia, Theo. Sistemas no ar. Estou pronto."
ARRIVAL_GREETING = "Bem-vindo de volta, Theo. Estou pronto."
LAUNCH_LABEL = "ai.theopadilha.jarvis-device-worker"
LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_LABEL}.plist"
LOG_DIR = ROOT / "09_LOGS"
SCREENSHOT_DIR = ROOT / "05_EXECUCAO" / "64_PERSONAL_TOOLS" / "screenshots"
SELF_EDIT_RESTART_MARKER = (
    Path.home()
    / "Library"
    / "Application Support"
    / "JARVIS"
    / "self-edits"
    / "restart-device-worker"
)
ARTIFACTS_BUCKET = "jarvis-artifacts"
RETRYABLE_STALE_ACTIONS = {
    "open_application",
    "close_application",
    "screen_capture",
    "github_overview",
    "storage_scan",
    "system_memory",
    "open_url",
    "open_folder",
    "volume_set",
}
ALLOWED_ACTIONS = {
    "open_application",
    "close_application",
    "spotify_control",
    "message_send",
    "screen_capture",
    "screen_record",
    "github_overview",
    "storage_scan",
    "system_memory",
    "self_edit",
    "save_note",
    "open_url",
    "clipboard_set",
    "speak",
    "open_folder",
    "notify",
    "volume_set",
    "image_convert",
    "files_triage",
}
ALLOWED_FOLDER_PATHS = {
    "downloads": lambda: Path.home() / "Downloads",
    "desktop": lambda: Path.home() / "Desktop",
    "documents": lambda: Path.home() / "Documents",
    "home": Path.home,
}
TARGET_PATTERN = re.compile(r"^[\wÀ-ÿ ._-]{0,120}$")
APPLICATION_ALIASES = {
    "calendario": "Calendar",
    "calendar": "Calendar",
    "chrome": "Google Chrome",
    "codigo": "Visual Studio Code",
    "discord": "Discord",
    "finder": "Finder",
    "mensagens": "Messages",
    "messages": "Messages",
    "musica": "Music",
    "music": "Music",
    "notas": "Notes",
    "notes": "Notes",
    "roblox": "Roblox",
    "safari": "Safari",
    "spotify": "Spotify",
    "steam": "Steam",
    "terminal": "Terminal",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "cursor": "Cursor",
    "slack": "Slack",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "obsidian": "Obsidian",
    "figma": "Figma",
    "notion": "Notion",
    "zoom": "zoom.us",
    "mail": "Mail",
    "preview": "Preview",
    "calculadora": "Calculator",
    "calculator": "Calculator",
    "monitor": "Activity Monitor",
    "activity monitor": "Activity Monitor",
    "monitor de atividade": "Activity Monitor",
    "ajustes": "System Settings",
    "configuracoes": "System Settings",
    "system settings": "System Settings",
    "fotos": "Photos",
    "photos": "Photos",
    "facetime": "FaceTime",
    "jarvis": "JARVIS",
    "sistema": "JARVIS",
    "cockpit": "JARVIS",
}
JARVIS_CLEANUP_PATTERN = re.compile(
    r"\b(?:limp(?:a|e|ar)|fech(?:a|e|ar)|encerr(?:a|e|ar))\b.{0,120}"
    r"\b(?:processos?\s+(?:tempor[aá]rios?\s+)?(?:do\s+)?jarvis|"
    r"tempor[aá]rios?\s+(?:do\s+)?jarvis)\b",
    re.I,
)
SELF_PUBLISH_PATTERN = re.compile(
    r"\b(?:public(?:a|ar|ação)|publiqu(?:e|ar)|sub(?:a|ir)|push|envi(?:a|e|ar)\s+(?:pro|para\s+o)\s+github|"
    r"merge|mescl(?:a|e|ar)|deploy|produção|producao)\b",
    re.I,
)
SELF_PUBLISH_DENY_PATTERN = re.compile(
    r"\b(?:n[aã]o|nunca|sem)\b.{0,24}\b(?:public(?:a|ar|ação)|publiqu(?:e|ar)|"
    r"sub(?:a|ir)|push|merge|mescl(?:a|e|ar)|deploy|produção|producao)\b|"
    r"\b(?:somente|apenas|s[oó])\s+local\b",
    re.I,
)


def self_publish_requested(request_text: str) -> bool:
    text = str(request_text or "")[:2_000]
    return bool(SELF_PUBLISH_PATTERN.search(text) and not SELF_PUBLISH_DENY_PATTERN.search(text))

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


def screen_locked_flag(ioreg_output: str) -> bool:
    """A chave só existe quando a sessão está bloqueada; ausência é tela livre."""
    match = re.search(r'"CGSSessionScreenIsLocked"\s*=\s*(Yes|No|true|false|1|0)', ioreg_output, re.I)
    return bool(match) and match.group(1).lower() in {"yes", "true", "1"}


def screen_is_locked() -> bool:
    try:
        result = subprocess.run(
            ["/usr/sbin/ioreg", "-n", "Root", "-d1", "-k", "CGSSessionScreenIsLocked"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return screen_locked_flag(result.stdout or "")


def machine_booted_at() -> float:
    """Momento do último boot, para saudar uma vez por ligada do Mac."""
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "kern.boottime"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0.0
    match = re.search(r"sec\s*=\s*(\d+)", result.stdout or "")
    return float(match.group(1)) if match else 0.0


def boot_greeting_due(now: float) -> bool:
    """Uma saudação por boot, e só depois do sistema terminar de subir."""
    booted = machine_booted_at()
    if not booted or now - booted < BOOT_QUIET_SECONDS:
        return False
    try:
        last = float(BOOT_STATE.read_text().strip() or 0)
    except (OSError, ValueError):
        last = 0.0
    return last < booted


def mark_boot_greeting(booted: float) -> None:
    try:
        BOOT_STATE.parent.mkdir(parents=True, exist_ok=True)
        BOOT_STATE.write_text(str(booted))
    except OSError:
        pass


def arrival_allowed(now: float, reason: str = "worker") -> bool:
    if os.environ.get("JARVIS_ARRIVAL") == "0":
        return False
    # O boot já tem a própria trava (uma por ligada); passar pelo cooldown de
    # chegada faria a saudação sumir quando o Mac reinicia logo depois de um
    # desbloqueio — sem erro nenhum, que é o pior jeito de falhar.
    if reason == "boot":
        return True
    try:
        last = float(ARRIVAL_STATE.read_text().strip() or 0)
    except (OSError, ValueError):
        last = 0.0
    return now - last >= ARRIVAL_COOLDOWN_SECONDS


def speak_on_mac(text: str) -> str:
    """Fala pelo alto-falante da máquina, sem depender de aba aberta.

    A voz própria do cockpit vem primeiro; o `say` do macOS é a rede de
    segurança para quando o servidor local não está de pé.
    """
    text = (text or "").strip()
    if not text or os.environ.get("JARVIS_LOCAL_VOICE") == "0":
        return "skipped"
    if shutil.which("afplay"):
        try:
            request = Request(
                LOCAL_TTS_URL,
                data=json.dumps({"text": text}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                audio = response.read()
            if audio:
                suffix = ".wav" if audio[:4] == b"RIFF" else ".mp3"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                    handle.write(audio)
                    path = handle.name
                try:
                    subprocess.run(["/usr/bin/afplay", path], capture_output=True, timeout=90, check=False)
                    return "local_tts"
                finally:
                    Path(path).unlink(missing_ok=True)
        except (URLError, OSError, subprocess.TimeoutExpired, ValueError):
            pass
    try:
        subprocess.run(
            ["/usr/bin/say", "-v", LOCAL_SAY_VOICE, "-r", "180", text],
            capture_output=True,
            timeout=60,
            check=False,
        )
        return "say"
    except (OSError, subprocess.TimeoutExpired):
        return "failed"


def announce_arrival(now: float, reason: str = "worker") -> bool:
    """Theo chegou: falar com ele e abrir o cockpit."""
    if not arrival_allowed(now, reason):
        return False
    spoken = speak_on_mac(BOOT_GREETING if reason == "boot" else ARRIVAL_GREETING)
    # A aba não repete o que o alto-falante já disse.
    silence = "&spoken=1" if spoken in {"local_tts", "say"} else ""
    url = f"{ARRIVAL_COCKPIT_URL.rstrip('/')}/cockpit?arrival={reason}{silence}"
    try:
        subprocess.run(["/usr/bin/open", url], capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    try:
        ARRIVAL_STATE.parent.mkdir(parents=True, exist_ok=True)
        ARRIVAL_STATE.write_text(str(now))
    except OSError:
        pass
    return True


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


ARTIFACT_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def allowed_artifact_roots() -> tuple[Path, ...]:
    return (
        SCREENSHOT_DIR.resolve(),
        (Path.home() / "Downloads").resolve(),
    )


def upload_private_artifact(path: Path, command_id: int) -> tuple[str, str]:
    resolved = path.resolve()
    mime = ARTIFACT_MIME.get(resolved.suffix.lower())
    if not mime or not resolved.is_file():
        raise WorkerError("O artefato não é uma imagem allowlisted.")
    if not any(root == resolved or root in resolved.parents for root in allowed_artifact_roots()):
        raise WorkerError("A captura terminou fora da pasta privada permitida.")
    if resolved.stat().st_size <= 0 or resolved.stat().st_size > 10_485_760:
        raise WorkerError("A captura não tem um tamanho aceito para o preview privado.")
    object_path = f"theo/{int(command_id)}-{resolved.name}"
    base_url, api_key = configuration()
    request = Request(
        f"{base_url}/storage/v1/object/{ARTIFACTS_BUCKET}/{quote(object_path, safe='/')}",
        data=resolved.read_bytes(),
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": mime,
            "x-upsert": "false",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read(100_000)
    except HTTPError as error:
        raise WorkerError(f"Supabase Storage recusou o preview (HTTP {error.code}).") from error
    except (URLError, TimeoutError) as error:
        raise WorkerError("Supabase Storage não confirmou o preview.") from error
    return object_path, mime


def download_private_artifact(object_path: str, destination: Path) -> Path:
    safe_path = str(object_path or "").strip("/")
    if not re.fullmatch(r"theo/[A-Za-z0-9._/-]{1,480}", safe_path):
        raise WorkerError("Artefato fora do prefixo privado permitido.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    base_url, api_key = configuration()
    request = Request(
        f"{base_url}/storage/v1/object/{ARTIFACTS_BUCKET}/{quote(safe_path, safe='/')}",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read(10_485_760)
    except HTTPError as error:
        raise WorkerError(f"Supabase Storage recusou o download (HTTP {error.code}).") from error
    except (URLError, TimeoutError) as error:
        raise WorkerError("Supabase Storage não entregou o arquivo.") from error
    if not data:
        raise WorkerError("O arquivo de origem chegou vazio.")
    destination.write_bytes(data)
    return destination


def delete_private_artifact(object_path: str) -> None:
    safe_path = str(object_path or "").strip("/")
    if not re.fullmatch(r"theo/[A-Za-z0-9._/-]{1,480}", safe_path):
        raise WorkerError("Artefato fora do prefixo privado permitido.")
    base_url, api_key = configuration()
    request = Request(
        f"{base_url}/storage/v1/object/{ARTIFACTS_BUCKET}/{quote(safe_path, safe='/')}",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
        },
        method="DELETE",
    )
    try:
        with urlopen(request, timeout=20) as response:
            response.read(100_000)
    except HTTPError as error:
        raise WorkerError(f"Supabase Storage recusou a retenção (HTTP {error.code}).") from error
    except (URLError, TimeoutError) as error:
        raise WorkerError("Supabase Storage não confirmou a retenção.") from error


def screenshot_path(output: str) -> Path | None:
    match = re.search(r"^sa[ií]da:\s*(.+?\.(?:png|jpe?g|tiff?))\s*$", str(output or ""), re.I | re.M)
    if not match:
        return None
    path = Path(match.group(1).strip()).expanduser()
    return path if path.is_absolute() else ROOT / path


def redact_secrets(value: str) -> str:
    safe = str(value or "")[:8_000]
    for _name, pattern in SECRET_PATTERNS:
        safe = pattern.sub("[REDACTED]", safe)
    return safe


def contains_secret(value: str) -> bool:
    return any(pattern.search(str(value or "")) for _name, pattern in SECRET_PATTERNS)


def request_envelope(job: dict) -> dict:
    raw = str(job.get("request_text") or "")[:8_000].strip()
    if not raw.startswith("{"):
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(value, dict) or value.get("schema") not in {"jarvis-device-run/1", "jarvis-device-run/2"}:
        return {}
    return value


def normalized_application_name(value: str) -> str:
    safe = str(value or "").casefold().strip()
    safe = safe.translate(str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", safe).strip()


def installed_applications(app_roots: list[Path] | None = None) -> dict[str, str]:
    """Build a shallow, deterministic app catalog without launching anything."""
    roots = app_roots or [Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications"]
    catalog = {normalized_application_name(name): name for name in APPLICATION_ALIASES.values()}
    for root in roots:
        if not root.is_dir():
            continue
        candidates = [*root.glob("*.app"), *root.glob("*/*.app")]
        for path in sorted(candidates, key=lambda item: str(item).casefold()):
            name = path.stem.strip()
            if name:
                catalog[normalized_application_name(name)] = name
    return catalog


def resolve_application_target(target: str, catalog: dict[str, str] | None = None) -> str:
    """Resolve aliases and small speech-to-text typos to a real app display name."""
    if not TARGET_PATTERN.fullmatch(str(target or "")) or not str(target or "").strip():
        raise WorkerError("Aplicativo recebido com nome inválido.")
    normalized = normalized_application_name(target)
    alias = APPLICATION_ALIASES.get(normalized)
    rows = catalog if catalog is not None else installed_applications()
    if alias:
        return rows.get(normalized_application_name(alias), alias)
    if normalized in rows:
        return rows[normalized]
    close = get_close_matches(normalized, list(rows), n=1, cutoff=0.86)
    return rows[close[0]] if close else str(target).strip()


def application_running(application: str) -> bool | None:
    """Ask macOS for independent process state; None means evidence unavailable."""
    if platform.system() != "Darwin" or not TARGET_PATTERN.fullmatch(application):
        return None
    try:
        result = subprocess.run(
            ["osascript", "-e", f'application "{application}" is running'],
            text=True,
            capture_output=True,
            check=False,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip().casefold()
    return value == "true" if result.returncode == 0 and value in {"true", "false"} else None


def confirm_application_state(application: str, expected_open: bool) -> bool | None:
    for _attempt in range(8):
        observed = application_running(application)
        if observed is expected_open:
            return True
        if observed is None:
            return None
        time.sleep(0.25)
    return False


def job_request_text(job: dict) -> str:
    envelope = request_envelope(job)
    return str(envelope.get("request") if envelope else job.get("request_text") or "")[:8_000].strip()


def job_dependency_id(job: dict) -> int | None:
    value = request_envelope(job).get("depends_on")
    return int(value) if re.fullmatch(r"[0-9]{1,18}", str(value or "")) else None


def dependency_status(command_id: int) -> str:
    rows = rest_request(
        COMMANDS_TABLE,
        query=f"select=id,status&owner_id=eq.theo&id=eq.{int(command_id)}&limit=1",
    )
    return str(rows[0].get("status") or "") if rows else "missing"


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


def finish_command(
    command_id: int,
    succeeded: bool,
    result: str,
    artifact_path: str = "",
    artifact_mime: str = "",
) -> None:
    rest_request(
        COMMANDS_TABLE,
        "PATCH",
        query=f"owner_id=eq.theo&id=eq.{command_id}&status=eq.running",
        body={
            "status": "succeeded" if succeeded else "failed",
            "result": redact_secrets(result),
            "artifact_path": artifact_path if succeeded else "",
            "artifact_mime": artifact_mime if succeeded else "",
            "completed_at": now_iso(),
        },
        prefer="return=minimal",
    )


def applescript_string(value: str) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def mac_note_from_job(job: dict) -> dict:
    raw = str(job.get("request_text") or "")[:8_000].strip()
    title = str(job.get("target") or "").strip() or "Nota"
    body = raw
    if raw.startswith("{"):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = {}
        if isinstance(value, dict) and value.get("schema") == "jarvis-note/1":
            title = str(value.get("title") or title).strip()[:120] or "Nota"
            body = str(value.get("body") or "").strip()[:8_000]
    if not body or contains_secret(body) or contains_secret(title):
        raise WorkerError("Nota recebida sem texto seguro.")
    return {"title": title, "body": body}


def write_apple_note(title: str, body: str) -> str:
    if platform.system() != "Darwin":
        return "Notas do macOS indisponível neste sistema."
    script = (
        'tell application "Notes"\n'
        'set jarvisFolder to missing value\n'
        'repeat with f in folders\n'
        'if name of f is "JARVIS" then set jarvisFolder to f\n'
        'end repeat\n'
        'if jarvisFolder is missing value then set jarvisFolder to make new folder with properties {name:"JARVIS"}\n'
        f'make new note at jarvisFolder with properties {{name:"{applescript_string(title)}", body:"{applescript_string(body)}"}}\n'
        'end tell'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "Não consegui falar com o app Notas."
    if result.returncode != 0:
        return "O app Notas recusou a nota."
    return "Cópia no app Notas."


def persist_mac_note(job: dict) -> tuple[bool, str]:
    note = mac_note_from_job(job)
    folder = Path.home() / "Documents" / "JARVIS" / "Notas"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    slug = re.sub(r"[^\wÀ-ÿ]+", "-", note["title"].casefold()).strip("-")[:40] or "nota"
    path = folder / f"{stamp}_{slug}.md"
    path.write_text(f"# {note['title']}\n\n{note['body']}\n", encoding="utf-8")
    apple = write_apple_note(note["title"], note["body"])
    return True, f"Arquivo: {path}. {apple}"


def job_text_source(job: dict) -> str:
    return job_request_text(job) or str(job.get("request_text") or "")


def job_open_url(job: dict) -> str:
    source = job_text_source(job)
    payload = payload_from_text(source)
    if payload.get("kind") == "open_url":
        url = safe_https_url(str(payload.get("value") or ""))
        if url:
            return url
    return extract_https_url(source)


def execute_open_url_job(job: dict) -> tuple[bool, str]:
    url = job_open_url(job)
    if not url:
        raise WorkerError("URL https válida não encontrada.")
    if platform.system() != "Darwin":
        return False, "Abrir URL no Mac indisponível neste sistema."
    result = subprocess.run(["/usr/bin/open", url], text=True, capture_output=True, check=False, timeout=12)
    if result.returncode != 0:
        return False, "O macOS recusou abrir o endereço."
    return True, f"Aberto no Mac: {url}"


def execute_clipboard_job(job: dict) -> tuple[bool, str]:
    text = clipboard_text(job_text_source(job), job_text_source(job))
    if not text or contains_secret(text):
        raise WorkerError("Texto para copiar ausente ou inseguro.")
    if platform.system() != "Darwin":
        return False, "Área de transferência do Mac indisponível neste sistema."
    result = subprocess.run(
        ["/usr/bin/pbcopy"],
        input=text,
        text=True,
        capture_output=True,
        check=False,
        timeout=8,
    )
    if result.returncode != 0:
        return False, "Não consegui copiar para a área de transferência."
    return True, "Texto copiado para a área de transferência do Mac."


def execute_speak_job(job: dict) -> tuple[bool, str]:
    text = speak_text(job_text_source(job), job_text_source(job))
    if not text or contains_secret(text):
        raise WorkerError("Fala recebida sem texto seguro.")
    spoken = speak_on_mac(text)
    if spoken == "skipped":
        return False, "A voz local está desligada."
    if spoken == "failed":
        return False, "Não consegui falar pelo alto-falante do Mac."
    return True, f"Falei no Mac ({spoken})."


def execute_open_folder_job(job: dict) -> tuple[bool, str]:
    alias = folder_id(job_text_source(job), str(job.get("target") or ""), job_text_source(job))
    builder = ALLOWED_FOLDER_PATHS.get(alias)
    if not builder:
        raise WorkerError("Pasta fora do allowlist.")
    path = builder()
    if not path.exists():
        return False, f"A pasta {alias} não existe neste Mac."
    if platform.system() != "Darwin":
        return False, "Finder indisponível neste sistema."
    result = subprocess.run(["/usr/bin/open", str(path)], text=True, capture_output=True, check=False, timeout=12)
    if result.returncode != 0:
        return False, "O Finder recusou abrir a pasta."
    return True, f"Finder aberto em {path}."


def execute_notify_job(job: dict) -> tuple[bool, str]:
    text = notify_text(job_text_source(job), job_text_source(job))
    if not text or contains_secret(text):
        raise WorkerError("Notificação recebida sem texto seguro.")
    if platform.system() != "Darwin":
        return False, "Notificações do macOS indisponíveis neste sistema."
    script = (
        f'display notification "{applescript_string(text[:180])}" '
        f'with title "JARVIS"'
    )
    result = subprocess.run(["osascript", "-e", script], text=True, capture_output=True, check=False, timeout=8)
    if result.returncode != 0:
        return False, "O macOS recusou a notificação."
    return True, "Notificação enviada no Mac."


def execute_volume_job(job: dict) -> tuple[bool, str]:
    level = volume_level(job_text_source(job), str(job.get("target") or ""), job_text_source(job))
    if level is None:
        raise WorkerError("Volume fora de 0 a 100.")
    if platform.system() != "Darwin":
        return False, "Volume do sistema indisponível neste sistema."
    result = subprocess.run(
        ["osascript", "-e", f"set volume output volume {int(level)}"],
        text=True,
        capture_output=True,
        check=False,
        timeout=8,
    )
    if result.returncode != 0:
        return False, "O macOS recusou o ajuste de volume."
    observed = subprocess.run(
        ["osascript", "-e", "output volume of (get volume settings)"],
        text=True,
        capture_output=True,
        check=False,
        timeout=8,
    )
    evidence = (observed.stdout or "").strip()
    if observed.returncode == 0 and evidence.isdigit() and abs(int(evidence) - int(level)) > 5:
        return False, f"O volume não ficou em {level}; o sistema reportou {evidence}."
    return True, f"Volume do Mac ajustado para {level}."


DOWNLOAD_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp"}


def newest_download_image() -> Path | None:
    folder = Path.home() / "Downloads"
    if not folder.is_dir():
        return None
    candidates = []
    try:
        for path in folder.iterdir():
            if path.name.startswith(".") or not path.is_file() or path.is_symlink():
                continue
            if path.suffix.lower() in DOWNLOAD_IMAGE_SUFFIXES:
                candidates.append(path)
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def execute_image_convert_job(job: dict) -> tuple[bool, str]:
    source_text = job_text_source(job)
    fmt = image_convert_format(source_text, str(job.get("target") or ""), source_text)
    native = IMAGE_NATIVE_FORMATS.get(fmt)
    if not native:
        raise WorkerError("Formato de conversão fora do allowlist.")
    origin = image_convert_source(source_text)
    work = Path(tempfile.mkdtemp(prefix="jarvis-convert-"))
    try:
        if origin.get("source") == "storage" and origin.get("path"):
            suffix = Path(origin.get("name") or origin["path"]).suffix.lower() or ".png"
            if suffix not in DOWNLOAD_IMAGE_SUFFIXES:
                suffix = ".png"
            incoming = work / f"source{suffix}"
            source = download_private_artifact(origin["path"], incoming)
        else:
            source = newest_download_image()
            if source is None:
                raise WorkerError("Não achei imagem em Downloads nem anexo para converter.")
        extension = "jpg" if fmt == "jpg" else fmt
        output = Path.home() / "Downloads" / f"{source.stem}-converted.{extension}"
        if output.exists():
            stamp = datetime.now().strftime("%H%M%S")
            output = output.with_name(f"{source.stem}-converted-{stamp}.{extension}")
        if platform.system() != "Darwin":
            return False, "sips indisponível neste sistema."
        result = subprocess.run(
            ["/usr/bin/sips", "-s", "format", native, str(source), "--out", str(output)],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
            return False, "A conversão não gerou um arquivo válido; o original ficou intacto."
        opened = subprocess.run(
            ["/usr/bin/open", str(Path.home() / "Downloads")],
            text=True,
            capture_output=True,
            check=False,
            timeout=12,
        )
        finder = "Downloads aberto no Finder." if opened.returncode == 0 else "A pasta Downloads não abriu."
        return True, f"Imagem convertida para {fmt}.\nsaída: {output}\n{finder}"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def execute_files_triage_job(job: dict) -> tuple[bool, str]:
    folder = Path.home() / "Downloads"
    if not folder.is_dir():
        raise WorkerError("Downloads não existe neste Mac.")
    result = subprocess.run(
        [sys.executable, str(ROOT / "11_SCRIPTS" / "personal_tools.py"), "files-triage", str(folder), "--limit", "40"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
        env=os.environ.copy(),
    )
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        return False, output or "A triagem de arquivos falhou."
    return True, output or "Plano de triagem gerado; nenhum arquivo foi movido."


def command_argv(job: dict) -> list[str]:
    action = str(job.get("action") or "")
    target = str(job.get("target") or "").strip()
    if action not in ALLOWED_ACTIONS:
        raise WorkerError("Ação recebida fora do allowlist.")
    if action == "save_note":
        note = mac_note_from_job(job)
        return ["jarvis-note-save", note["title"][:80]]
    if action == "open_url":
        url = job_open_url(job)
        if not url:
            raise WorkerError("URL https válida não encontrada.")
        return ["/usr/bin/open", url]
    if action == "clipboard_set":
        text = clipboard_text(job_request_text(job), str(job.get("request_text") or ""))
        if not text:
            raise WorkerError("Texto para copiar ausente.")
        return ["/usr/bin/pbcopy"]
    if action == "speak":
        text = speak_text(job_request_text(job), str(job.get("request_text") or ""))
        if not text:
            raise WorkerError("Fala recebida sem texto.")
        return ["/usr/bin/say", "-v", LOCAL_SAY_VOICE, text]
    if action == "open_folder":
        alias = folder_id(job_request_text(job), target, str(job.get("request_text") or ""))
        builder = ALLOWED_FOLDER_PATHS.get(alias)
        if not builder:
            raise WorkerError("Pasta fora do allowlist.")
        return ["/usr/bin/open", str(builder())]
    if action == "notify":
        text = notify_text(job_request_text(job), str(job.get("request_text") or ""))
        if not text:
            raise WorkerError("Notificação recebida sem texto.")
        return ["osascript", "-e", f'display notification "{applescript_string(text[:180])}" with title "JARVIS"']
    if action == "volume_set":
        level = volume_level(job_request_text(job), target, str(job.get("request_text") or ""))
        if level is None:
            raise WorkerError("Volume fora de 0 a 100.")
        return ["osascript", "-e", f"set volume output volume {int(level)}"]
    if not TARGET_PATTERN.fullmatch(target):
        raise WorkerError("Aplicativo recebido com nome inválido.")
    if action == "self_edit":
        request_text = job_request_text(job)[:2_000]
        if len(request_text) < 12 or contains_secret(request_text):
            raise WorkerError("Autoedição recebida sem objetivo seguro e explícito.")
        argv = [str(ROOT / "jarvis"), "self-edit", request_text]
        if self_publish_requested(request_text):
            argv.append("--publish")
        return argv
    if action == "system_memory":
        argv = [str(ROOT / "jarvis"), "system-memory"]
        request_text = job_request_text(job)
        if JARVIS_CLEANUP_PATTERN.search(request_text):
            argv.append("--cleanup-jarvis")
        return argv
    if action == "screen_capture":
        return [str(ROOT / "jarvis"), "screen-capture"]
    if action == "spotify_control":
        spotify_args = spotify_command_args(job_request_text(job))
        if not spotify_args:
            raise WorkerError("Controle do Spotify não reconhecido ou fora do allowlist.")
        return [str(ROOT / "jarvis"), "spotify", *spotify_args]
    if action == "screen_record":
        return [str(ROOT / "jarvis"), "screen-record"]
    if action == "github_overview":
        return [str(ROOT / "jarvis"), "github-overview", "--limit", "12"]
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
        details = message_details(job_request_text(job), target)
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
    if not re.fullmatch(r"[0-9]{8,15}", expected_phone):
        return None
    phone_match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", text)
    phone = "".join(char for char in phone_match.group(0) if char.isdigit()) if phone_match else expected_phone
    if phone != expected_phone:
        return None
    quoted = re.search(r'["“](.+?)["”]', text)
    alias_match = re.search(
        r"(?:mensagem|msg)\s+(?:para|pro|pra|ao|a)\s+[\wÀ-ÿ ._-]{1,80}?\s+"
        r"(?:dizendo|falando|com\s+(?:o\s+)?texto|texto)\s*[:,-]?\s*(?P<body>.+)$",
        text,
        re.I,
    ) if not phone_match and not quoted else None
    body = quoted.group(1).strip() if quoted else alias_match.group("body").strip() if alias_match else (
        re.sub(re.escape(phone_match.group(0)), "", text, count=1).strip(" :-")
        if phone_match
        else text.strip(" :-")
    )
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
    action = str(job.get("action") or "")
    effective_job = dict(job)
    if action == "save_note":
        return persist_mac_note(effective_job)
    native = {
        "open_url": execute_open_url_job,
        "clipboard_set": execute_clipboard_job,
        "speak": execute_speak_job,
        "open_folder": execute_open_folder_job,
        "notify": execute_notify_job,
        "volume_set": execute_volume_job,
        "image_convert": execute_image_convert_job,
        "files_triage": execute_files_triage_job,
    }.get(action)
    if native:
        return native(effective_job)
    if action in {"open_application", "close_application"}:
        effective_job["target"] = resolve_application_target(str(job.get("target") or ""))
    argv = command_argv(effective_job)
    envelope = request_envelope(job)
    retry_policy = envelope.get("retry_policy") if isinstance(envelope.get("retry_policy"), dict) else {}
    try:
        requested_attempts = int(retry_policy.get("max_attempts") or 1)
    except (TypeError, ValueError):
        requested_attempts = 1
    max_attempts = 2 if retry_policy.get("idempotent") is True and requested_attempts >= 2 else 1
    result = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                argv,
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                timeout=2_400 if action == "self_edit" else 90,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            if attempt == max_attempts:
                return False, "A ação local excedeu o tempo máximo e foi interrompida."
            continue
        if result.returncode == 0 or attempt == max_attempts:
            break
    assert result is not None
    output = (result.stdout or result.stderr or "").strip()
    succeeded = result.returncode == 0
    if succeeded and action in {"open_application", "close_application"}:
        application = str(effective_job.get("target") or "")
        # O bundle JARVIS só lança o Chrome em --app; o AppleScript
        # "application JARVIS is running" fica falso mesmo com a janela aberta.
        if application.casefold() == "jarvis":
            return True, f"{output}\nCockpit JARVIS aberto no macOS.".strip()
        confirmed = confirm_application_state(application, expected_open=action == "open_application")
        if confirmed is True:
            evidence = f"Confirmação independente: {application} está {'aberto' if action == 'open_application' else 'fechado'}."
            output = f"{output}\n{evidence}".strip()
        elif confirmed is False:
            return False, f"O comando terminou, mas o estado de {application} não corresponde ao pedido."
        else:
            return False, f"O comando terminou, mas o macOS não forneceu confirmação independente de {application}."
    return succeeded, output or f"Processo finalizado com exit code {result.returncode}."


def recover_stale_commands() -> tuple[int, int]:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_SECONDS)).isoformat()
    rows = rest_request(
        COMMANDS_TABLE,
        query=(
            "select=id,action&owner_id=eq.theo&status=eq.running"
            f"&claimed_at=lt.{quote(cutoff, safe=':.-T')}&limit=50"
        ),
    )
    requeued = 0
    failed = 0
    for row in rows:
        command_id = row.get("id")
        action = str(row.get("action") or "")
        if not re.fullmatch(r"[0-9]{1,18}", str(command_id or "")):
            continue
        if action in RETRYABLE_STALE_ACTIONS:
            rest_request(
                COMMANDS_TABLE,
                "PATCH",
                query=f"owner_id=eq.theo&id=eq.{command_id}&status=eq.running",
                body={"status": "pending", "claimed_at": None},
                prefer="return=minimal",
            )
            requeued += 1
        else:
            rest_request(
                COMMANDS_TABLE,
                "PATCH",
                query=f"owner_id=eq.theo&id=eq.{command_id}&status=eq.running",
                body={
                    "status": "failed",
                    "result": "A execução perdeu o heartbeat e não foi repetida para evitar efeito duplicado.",
                    "completed_at": now_iso(),
                },
                prefer="return=minimal",
            )
            failed += 1
    return requeued, failed


def prune_private_artifacts(now: datetime | None = None) -> int:
    reference = now or datetime.now(timezone.utc)
    cutoff = reference.astimezone(timezone.utc) - timedelta(days=ARTIFACT_MAX_AGE_DAYS)
    rows = rest_request(
        COMMANDS_TABLE,
        query=(
            "select=id,artifact_path,completed_at&owner_id=eq.theo"
            "&order=completed_at.desc.nullslast&limit=200"
        ),
    )
    candidates = []
    artifact_rows = [row for row in rows if str(row.get("artifact_path") or "").strip()]
    for index, row in enumerate(artifact_rows):
        if index < ARTIFACT_KEEP_COUNT:
            continue
        raw_completed = str(row.get("completed_at") or "")
        try:
            completed = datetime.fromisoformat(raw_completed.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue
        if completed < cutoff:
            candidates.append(row)

    removed = 0
    for row in candidates:
        command_id = row.get("id")
        artifact_path = str(row.get("artifact_path") or "")
        if not re.fullmatch(r"[0-9]{1,18}", str(command_id or "")):
            continue
        delete_private_artifact(artifact_path)
        rest_request(
            COMMANDS_TABLE,
            "PATCH",
            query=f"owner_id=eq.theo&id=eq.{command_id}&artifact_path=eq.{quote(artifact_path, safe='')}",
            body={"artifact_path": "", "artifact_mime": ""},
            prefer="return=minimal",
        )
        removed += 1
    return removed


def run_once(preview: bool = False) -> str:
    job = pending_command()
    if not job:
        return "Fila vazia; nenhum comando executado."
    command_id = int(job.get("id"))
    action = str(job.get("action") or "")
    target = str(job.get("target") or "")
    if preview:
        return f"Preview: ação {command_id} aguardando ({action} {target})."
    dependency = job_dependency_id(job)
    if dependency is not None:
        dependency_state = dependency_status(dependency)
        if dependency_state in {"pending", "running"}:
            return f"Ação {command_id} aguarda a etapa anterior {dependency}."
        if dependency_state != "succeeded":
            claimed = claim_command(command_id)
            if not claimed:
                return f"Ação {command_id} já foi assumida por outro worker."
            finish_command(
                command_id,
                False,
                f"Etapa não executada: a dependência {dependency} terminou como {dependency_state}.",
            )
            return f"Ação {command_id} bloqueada pela falha da etapa {dependency}."
    claimed = claim_command(command_id)
    if not claimed:
        return f"Ação {command_id} já foi assumida por outro worker."
    try:
        succeeded, output = execute_job(claimed)
    except WorkerError as error:
        succeeded, output = False, str(error)
    artifact_path = ""
    artifact_mime = ""
    if succeeded and action in {"screen_capture", "image_convert"}:
        captured = screenshot_path(output)
        if not captured:
            output = f"{output}\nAVISO: preview não publicado; caminho da captura não foi confirmado."
        else:
            try:
                artifact_path, artifact_mime = upload_private_artifact(captured, command_id)
                output = f"{output}\nPreview privado publicado no Supabase Storage."
            except WorkerError as error:
                output = f"{output}\nAVISO: preview não publicado: {error}"
    if artifact_path:
        finish_command(command_id, succeeded, output, artifact_path, artifact_mime)
    else:
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
            "PATH": (
                f"{Path.home() / '.local' / 'bin'}:"
                "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            ),
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
    source = ""
    if LAUNCH_AGENT.is_file():
        try:
            payload = plistlib.loads(LAUNCH_AGENT.read_bytes())
            arguments = payload.get("ProgramArguments") if isinstance(payload, dict) else []
            source = str(arguments[1]) if isinstance(arguments, list) and len(arguments) > 1 else ""
        except (OSError, plistlib.InvalidFileException):
            source = ""
    print(f"Fonte instalada: {source or 'não identificada'}")
    print(f"Fonte existe: {'sim' if source and Path(source).is_file() else 'não'}")
    try:
        configuration()
        print("Ponte Supabase: configurada nas Chaves do macOS ou ambiente")
    except WorkerError:
        print("Ponte Supabase: não configurada")
    print(f"Spotify instalado: {'sim' if Path('/Applications/Spotify.app').is_dir() else 'não'}")
    expected = str(Path(__file__).resolve())
    if source and Path(source).resolve() != Path(expected):
        print(f"AVISO: este checkout não é a fonte instalada; fonte atual esperada: {expected}")


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
                locked_since = 0.0
                last_heartbeat = 0.0
                last_recovery = 0.0
                last_retention = 0.0

                def stop(_signum, _frame):
                    nonlocal running
                    running = False

                signal.signal(signal.SIGTERM, stop)
                signal.signal(signal.SIGINT, stop)
                while running:
                    wall_now = time.time()
                    if boot_greeting_due(wall_now):
                        # Só marca depois de falar: marcar antes perde a
                        # saudação inteira se o anúncio não acontecer.
                        if announce_arrival(wall_now, "boot"):
                            mark_boot_greeting(machine_booted_at())
                            print("Chegada: Mac ligado, cockpit aberto com a saudação de boas-vindas.", flush=True)
                    if screen_is_locked():
                        if not locked_since:
                            locked_since = wall_now
                    elif locked_since:
                        away = wall_now - locked_since
                        locked_since = 0.0
                        if away >= ARRIVAL_MIN_LOCKED_SECONDS and announce_arrival(wall_now):
                            print(f"Chegada: cockpit aberto após {int(away // 60)} min de tela bloqueada.", flush=True)
                    try:
                        monotonic_now = time.monotonic()
                        if monotonic_now - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                            heartbeat()
                            last_heartbeat = monotonic_now
                        if monotonic_now - last_recovery >= RECOVERY_INTERVAL_SECONDS:
                            requeued, failed = recover_stale_commands()
                            if requeued or failed:
                                print(
                                    f"Recuperação: {requeued} ação(ões) reencaminhada(s), "
                                    f"{failed} não repetida(s).",
                                    flush=True,
                                )
                            last_recovery = monotonic_now
                        if monotonic_now - last_retention >= RETENTION_INTERVAL_SECONDS:
                            removed = prune_private_artifacts()
                            if removed:
                                print(f"Retenção: {removed} preview(s) remoto(s) antigo(s) removido(s).", flush=True)
                            last_retention = monotonic_now
                        message = run_once()
                        if not message.startswith("Fila vazia"):
                            print(message, flush=True)
                        if SELF_EDIT_RESTART_MARKER.is_file():
                            SELF_EDIT_RESTART_MARKER.unlink()
                            print(
                                "Autoedição publicada: reiniciando o worker para carregar o código novo.",
                                flush=True,
                            )
                            running = False
                            continue
                    except WorkerError as error:
                        print(f"Worker aguardando reconexão: {error}", flush=True)
                    time.sleep(max(1.0, min(args.interval, 30.0)))
        else:
            if preview:
                print("Preview: consultaria uma ação pendente; nenhum heartbeat ou comando foi gravado.")
            else:
                heartbeat()
                recover_stale_commands()
                prune_private_artifacts()
                print(run_once())
    except WorkerError as error:
        print(f"FALHA: {error}")
        print("Produção: nenhum deploy alterado.")
        return 1
    print("Produção: nenhum deploy alterado; somente ações locais allowlisted podem ser executadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
