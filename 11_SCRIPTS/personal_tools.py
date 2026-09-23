"""Small, deterministic personal tools for the local-first JARVIS.

The module intentionally uses Python's standard library plus native macOS
commands. It never invokes a shell, reads environment files, deletes files,
or overwrites outputs. Messages are sent only by the explicit `message-send`
command; `message-draft` remains a non-sending WhatsApp handoff.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
from spotify_control import SAFE_QUERY_PATTERN, TRACK_URI_PATTERN  # noqa: E402
RUNTIME_DIR = ROOT / "05_EXECUCAO" / "64_PERSONAL_TOOLS"
MEMORY_DIR = ROOT / "03_MEMORIA"
SCREENSHOT_DIR = RUNTIME_DIR / "screenshots"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp", ".svg"}
IMAGE_OUTPUT_FORMATS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "tif": "tiff", "tiff": "tiff"}
FILE_CATEGORIES = {
    "images": {".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp", ".svg", ".tif", ".tiff"},
    "documents": {".pdf", ".doc", ".docx", ".odt", ".txt", ".md", ".rtf", ".pages"},
    "spreadsheets": {".csv", ".xls", ".xlsx", ".ods", ".numbers"},
    "audio": {".mp3", ".wav", ".m4a", ".aif", ".aiff", ".flac", ".ogg"},
    "video": {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"},
    "archives": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"},
    "data": {".json", ".jsonl", ".yaml", ".yml", ".xml", ".sql"},
    "code": {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".sh"},
}

APP_ALIASES = {
    "chrome": ("Google Chrome", "com.google.Chrome"),
    "google chrome": ("Google Chrome", "com.google.Chrome"),
    "safari": ("Safari", "com.apple.Safari"),
    "calculator": ("Calculator", "com.apple.calculator"),
    "calculadora": ("Calculator", "com.apple.calculator"),
    "terminal": ("Terminal", "com.apple.Terminal"),
    "mensagens": ("Messages", "com.apple.MobileSMS"),
    "messages": ("Messages", "com.apple.MobileSMS"),
    "mail": ("Mail", "com.apple.mail"),
    "preview": ("Preview", "com.apple.Preview"),
    "fotos": ("Photos", "com.apple.Photos"),
    "photos": ("Photos", "com.apple.Photos"),
    "facetime": ("FaceTime", "com.apple.FaceTime"),
    "whatsapp": ("WhatsApp", "net.whatsapp.WhatsApp"),
    "spotify": ("Spotify", "com.spotify.client"),
    "jarvis": ("JARVIS", "ai.theopadilha.jarvis.cockpit"),
    "sistema": ("JARVIS", "ai.theopadilha.jarvis.cockpit"),
    "cockpit": ("JARVIS", "ai.theopadilha.jarvis.cockpit"),
    "steam": ("Steam", "com.valvesoftware.steam"),
    "discord": ("Discord", "com.hnc.Discord"),
    "slack": ("Slack", "com.tinyspeck.slackmacgap"),
    "telegram": ("Telegram", "ru.keepcoder.Telegram"),
    "cursor": ("Cursor", None),
    "obsidian": ("Obsidian", "md.obsidian"),
    "notion": ("Notion", "notion.id"),
    "figma": ("Figma", None),
    "zoom": ("zoom.us", "us.zoom.xos"),
    "vscode": ("Visual Studio Code", "com.microsoft.VSCode"),
    "visual studio code": ("Visual Studio Code", "com.microsoft.VSCode"),
    "monitor": ("Activity Monitor", "com.apple.ActivityMonitor"),
    "activity monitor": ("Activity Monitor", "com.apple.ActivityMonitor"),
    "monitor de atividade": ("Activity Monitor", "com.apple.ActivityMonitor"),
    "ajustes": ("System Settings", "com.apple.systempreferences"),
    "configuracoes": ("System Settings", "com.apple.systempreferences"),
    "configurações": ("System Settings", "com.apple.systempreferences"),
    "system settings": ("System Settings", "com.apple.systempreferences"),
    "orca": ("Orca", "com.stablyai.orca"),
    "finder": ("Finder", "com.apple.finder"),
}

PROTECTED_APP_BUNDLE_IDS = {
    "com.apple.finder",
    "com.stablyai.orca",
}

try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []


def _looks_secret_like(text: str) -> bool:
    return any(pattern.search(text or "") for _name, pattern in SECRET_PATTERNS)


def _fail(message: str, code: int = 1) -> None:
    print(f"FALHA: {message}")
    raise SystemExit(code)


def _safe_path(path: Path) -> str:
    value = str(path)
    if _looks_secret_like(value):
        return "[caminho ocultado por segurança]"
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return value


def _existing_file(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_file():
        _fail("arquivo de entrada não encontrado.")
    return path


def _output_file(raw: str | None, fallback: Path, suffixes: set[str]) -> Path:
    path = Path(raw).expanduser() if raw else fallback
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if path.suffix.lower() not in suffixes:
        _fail(f"extensão de saída inválida; use: {', '.join(sorted(suffixes))}")
    if path.exists():
        _fail("a saída já existe; nenhum arquivo foi sobrescrito.")
    return path


def _require_binary(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        _fail(f"comando nativo ausente: {name}")
    return resolved


def _run_native(argv: list[str]) -> None:
    result = subprocess.run(argv, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        _fail(f"comando nativo terminou com código {result.returncode}.")


def _slug(value: str, limit: int = 54) -> str:
    normalized = value.lower()
    normalized = re.sub(r"[^a-z0-9à-ÿ]+", "-", normalized).strip("-")
    return normalized[:limit].rstrip("-") or "memoria"


def _computer_fail(message: str, code: int = 1) -> None:
    print(f"FALHA: {message}")
    print("Produção: nada alterado.")
    raise SystemExit(code)


def _orca_apps() -> list[dict]:
    binary = shutil.which("orca")
    if not binary:
        _computer_fail("Orca CLI ausente; instale ou abra o Orca antes de controlar o Mac.")
    result = subprocess.run(
        [binary, "computer", "list-apps", "--json"],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        _computer_fail("o runtime de Computer Use do Orca não respondeu.")
    try:
        payload = json.loads(result.stdout)
        apps = payload.get("result", {}).get("apps", [])
    except (AttributeError, json.JSONDecodeError):
        _computer_fail("o Orca respondeu em formato inválido.")
    return [row for row in apps if isinstance(row, dict)]


def _orca_window_capture(output: Path) -> bool:
    binary = shutil.which("orca")
    if not binary or output.suffix.lower() != ".png":
        return False
    result = subprocess.run(
        [
            binary,
            "computer",
            "get-app-state",
            "--app",
            "com.google.Chrome",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout)
        source = Path(payload.get("result", {}).get("screenshot", {}).get("path", ""))
    except (AttributeError, TypeError, json.JSONDecodeError):
        return False
    if not source.is_file() or source.suffix.lower() != ".png":
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    return output.is_file() and output.stat().st_size > 0


def _app_identity(raw: str) -> tuple[str, str | None]:
    target = re.sub(r"\s+", " ", str(raw or "")).strip(" .")
    if not target or len(target) > 80 or not re.fullmatch(r"[\wÀ-ÿ ._-]+", target):
        _computer_fail("nome de aplicativo vazio ou inválido.", 2)
    if re.fullmatch(r"(?:com|net|org|dev)\.[A-Za-z0-9._-]+", target, re.I):
        return target, target
    return APP_ALIASES.get(target.casefold(), (target, None))


def _running_app(raw: str) -> dict | None:
    name, bundle_id = _app_identity(raw)
    apps = _orca_apps()
    if bundle_id:
        for app in apps:
            if str(app.get("bundleId") or "").casefold() == bundle_id.casefold():
                return app
    exact = [app for app in apps if str(app.get("name") or "").casefold() == name.casefold()]
    if exact:
        return exact[0]
    partial = [app for app in apps if name.casefold() in str(app.get("name") or "").casefold()]
    return partial[0] if len(partial) == 1 else None


def cmd_computer(args: argparse.Namespace) -> None:
    action = args.action
    print("JARVIS — Computer Use")
    print(f"Status real: controle local solicitado ({action}); nenhuma ação foi presumida.")

    if action == "list":
        apps = _orca_apps()
        print(f"Aplicativos visíveis: {len(apps)}")
        for app in apps:
            print(f"- {app.get('name', '?')} · {app.get('bundleId', '?')} · PID {app.get('pid', '?')}")
        print("Produção: nada alterado.")
        return

    if not args.app:
        _computer_fail("informe o aplicativo.", 2)
    name, known_bundle = _app_identity(args.app)

    if action == "open":
        print(f"Aplicativo: {name}")
        if args.dry_run:
            print("Modo: --dry-run (aplicativo não aberto).")
            print("Produção: nada alterado.")
            return
        binary = _require_binary("open")
        argv = [binary, "-b", known_bundle] if known_bundle else [binary, "-a", name]
        result = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=20)
        if result.returncode != 0:
            _computer_fail("o macOS não encontrou ou não abriu esse aplicativo.")
        time.sleep(0.8)
        visible = _running_app(known_bundle or name)
        evidence = "visível para o Computer Use" if visible else "abertura aceita pelo macOS"
        print(f"OK — {name} aberto ({evidence}).")
        print("Produção: aplicativo local aberto; nenhum deploy alterado.")
        return

    app = _running_app(known_bundle or name)
    if not app:
        if action == "close":
            print(f"OK — {name} já não está aberto.")
            print("Produção: nada alterado.")
            return
        _computer_fail("aplicativo não encontrado entre as janelas visíveis.")
    bundle_id = str(app.get("bundleId") or "")

    if action == "inspect":
        if args.dry_run:
            print(f"Modo: --dry-run (estado de {app.get('name')} não capturado).")
            print("Produção: nada alterado.")
            return
        binary = shutil.which("orca")
        argv = [binary, "computer", "get-app-state", "--app", bundle_id, "--no-screenshot", "--json"]
        result = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=30)
        if result.returncode != 0 and '"code": "window_not_found"' in result.stdout:
            result = subprocess.run(
                [*argv[:-1], "--restore-window", "--json"],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
        if result.returncode != 0:
            _computer_fail("não consegui observar esse aplicativo pelo Orca.")
        try:
            payload = json.loads(result.stdout)
            tree = payload.get("result", {}).get("snapshot", {}).get("treeText", "")
        except (AttributeError, json.JSONDecodeError):
            _computer_fail("o Orca respondeu em formato inválido.")
        print(f"Aplicativo: {app.get('name')} · {bundle_id}")
        print(str(tree or "(árvore de acessibilidade vazia)")[:8_000])
        print("Produção: nada alterado.")
        return

    if bundle_id in PROTECTED_APP_BUNDLE_IDS:
        _computer_fail(f"{app.get('name')} mantém o desktop ou o próprio worker ativo e não será fechado por este comando.", 3)
    print(f"Aplicativo: {app.get('name')} · {bundle_id}")
    if args.dry_run:
        print("Modo: --dry-run (aplicativo não fechado).")
        print("Produção: nada alterado.")
        return
    binary = _require_binary("osascript")
    script = 'tell application id "{}" to quit'.format(bundle_id.replace('"', ""))
    try:
        result = subprocess.run([binary, "-e", script], text=True, capture_output=True, check=False, timeout=20)
    except subprocess.TimeoutExpired:
        _computer_fail("o aplicativo não respondeu ao encerramento em 20 segundos; nada foi forçado.")
    if result.returncode != 0:
        _computer_fail("o aplicativo recusou o pedido de encerramento.")
    for _ in range(10):
        time.sleep(0.25)
        if _running_app(bundle_id) is None:
            print(f"OK — {app.get('name')} fechado e ausência confirmada pelo Orca.")
            print("Produção: aplicativo local fechado; nenhum deploy alterado.")
            return
    _computer_fail("o macOS aceitou o pedido, mas o aplicativo continuou visível.")


def cmd_doctor(_args: argparse.Namespace) -> None:
    print("JARVIS — Assistant Doctor")
    print("Status real: inspeção local de ferramentas. Nada foi editado.")
    print("")
    tools = {
        "screencapture": "captura de tela",
        "sips": "conversão de imagem",
        "say": "fala e áudio",
        "open": "abrir rascunho de mensagem",
        "pbcopy": "copiar rascunho",
        "osascript": "enviar pelo app Mensagens",
    }
    available = 0
    for binary, purpose in tools.items():
        path = shutil.which(binary)
        available += int(bool(path))
        print(f"{'OK' if path else 'AUSENTE':7} {purpose:28} {path or binary}")
    spotify_app = Path("/Applications/Spotify.app")
    available += int(spotify_app.is_dir())
    print(f"{'OK' if spotify_app.is_dir() else 'AUSENTE':7} {'controle real do Spotify':28} {spotify_app}")
    print("")
    print(f"Disponíveis: {available}/{len(tools) + 1}")
    print("Regra: somente message-send envia sob pedido explícito; nenhum arquivo é apagado automaticamente.")
    print("Produção: nada alterado.")


def _spotify_state() -> dict[str, str]:
    binary = _require_binary("osascript")
    script = """
if application "Spotify" is not running then return "closed"
tell application "Spotify"
  set currentState to (player state as text)
  set trackName to ""
  set artistName to ""
  if currentState is not "stopped" then
    set trackName to name of current track
    set artistName to artist of current track
  end if
  return currentState & (ASCII character 9) & trackName & (ASCII character 9) & artistName & (ASCII character 9) & (sound volume as text) & (ASCII character 9) & (shuffling as text) & (ASCII character 9) & (repeating as text)
end tell
""".strip()
    result = subprocess.run([binary, "-e", script], text=True, capture_output=True, check=False, timeout=20)
    if result.returncode != 0:
        if "-1743" in result.stderr or "not authorized" in result.stderr.lower():
            _computer_fail("permita que o Terminal controle o Spotify em Ajustes > Privacidade e Segurança > Automação.", 4)
        _computer_fail("o Spotify não respondeu ao controle do macOS.")
    values = result.stdout.strip().split("\t")
    if values == ["closed"]:
        return {"state": "closed", "track": "", "artist": "", "volume": "", "shuffle": "", "repeat": ""}
    values.extend([""] * (6 - len(values)))
    return dict(zip(("state", "track", "artist", "volume", "shuffle", "repeat"), values[:6]))


def _spotify_script(command: str) -> None:
    binary = _require_binary("osascript")
    result = subprocess.run(
        [binary, "-e", f'tell application "Spotify" to {command}'],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        if "-1743" in result.stderr or "not authorized" in result.stderr.lower():
            _computer_fail("permita que o Terminal controle o Spotify em Ajustes > Privacidade e Segurança > Automação.", 4)
        _computer_fail("o Spotify recusou o controle solicitado.")


def _print_spotify_state(state: dict[str, str]) -> None:
    labels = {"playing": "tocando", "paused": "pausado", "stopped": "parado", "closed": "fechado"}
    print(f"estado: {labels.get(state['state'], state['state'] or 'desconhecido')}")
    if state["track"]:
        print(f"faixa: {state['track']} — {state['artist']}")
    if state["volume"]:
        print(f"volume: {state['volume']}%")
    if state["shuffle"]:
        print(f"aleatório: {'ligado' if state['shuffle'] == 'true' else 'desligado'}")
    if state["repeat"]:
        print(f"repetição: {'ligada' if state['repeat'] == 'true' else 'desligada'}")


def cmd_spotify(args: argparse.Namespace) -> None:
    action = args.action
    value = " ".join(args.value or []).strip()
    print("JARVIS — Spotify")
    print(f"Status real: controle local allowlisted solicitado ({action}); sucesso depende da confirmação do Spotify.")
    if args.dry_run:
        print(f"Modo: --dry-run ({action}{f' · {value}' if value else ''}; Spotify não alterado).")
        print("Produção: nada alterado.")
        return

    if action == "search":
        if not SAFE_QUERY_PATTERN.fullmatch(value):
            _computer_fail("busca inválida; use entre 2 e 120 caracteres simples.", 2)
        result = subprocess.run(
            [_require_binary("open"), f"spotify:search:{quote(value, safe='')}"],
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
        if result.returncode != 0:
            _computer_fail("o macOS não conseguiu abrir a busca no Spotify.")
        print(f"OK — busca aberta no Spotify: {value}")
        print("Evidência: a busca foi entregue ao aplicativo; nenhuma faixa específica foi presumida como tocando.")
        print("Produção: Spotify local alterado; nenhum deploy alterado.")
        return

    if action in {"play", "play-uri"}:
        opened = subprocess.run(
            [_require_binary("open"), "-b", "com.spotify.client"],
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
        if opened.returncode != 0:
            _computer_fail("o Spotify não está instalado ou não pôde ser aberto.")
        time.sleep(0.8)

    before = _spotify_state()
    if action == "status":
        _print_spotify_state(before)
        print("Produção: nada alterado.")
        return
    if before["state"] == "closed" and action not in {"play", "play-uri"}:
        _computer_fail("o Spotify está fechado; abra ou peça para tocar antes desse controle.", 3)

    commands = {
        "play": "play",
        "pause": "pause",
        "next": "next track",
        "previous": "previous track",
        "toggle": "playpause",
        "shuffle": f"set shuffling to {'true' if value == 'on' else 'false'}",
        "repeat": f"set repeating to {'true' if value == 'on' else 'false'}",
    }
    if action == "volume":
        if not value.isdigit() or not 0 <= int(value) <= 100:
            _computer_fail("volume inválido; use um número de 0 a 100.", 2)
        command = f"set sound volume to {int(value)}"
    elif action == "play-uri":
        if not TRACK_URI_PATTERN.fullmatch(value):
            _computer_fail("URI inválida; somente spotify:track:<id> é permitido.", 2)
        command = f'play track "{value}"'
    else:
        if action in {"shuffle", "repeat"} and value not in {"on", "off"}:
            _computer_fail("use on ou off para esse controle.", 2)
        command = commands[action]
    _spotify_script(command)
    time.sleep(0.25)
    after = _spotify_state()
    print("OK — comando aceito e estado consultado novamente.")
    _print_spotify_state(after)
    print("Produção: Spotify local alterado; nenhum deploy alterado.")


def cmd_screen_capture(args: argparse.Namespace) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fallback = SCREENSHOT_DIR / f"screenshot-{stamp}.png"
    output = _output_file(args.output, fallback, {".png", ".jpg", ".jpeg", ".tiff", ".pdf"})
    print("JARVIS — Screen Capture")
    print("Status real: captura local sob comando explícito.")
    print(f"modo: {'interativo' if args.interactive else 'tela inteira'}")
    print(f"saída: {_safe_path(output)}")
    if args.dry_run:
        print("Modo: --dry-run (nenhuma captura realizada).")
        print("Produção: nada alterado.")
        return
    binary = _require_binary("screencapture")
    output.parent.mkdir(parents=True, exist_ok=True)
    flags = ["-i"] if args.interactive else ["-x"]
    result = subprocess.run(
        [binary, *flags, str(output)],
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        if args.interactive or not _orca_window_capture(output):
            _fail(f"comando nativo terminou com código {result.returncode}.")
        print("AVISO: captura nativa indisponível; usei a janela do Chrome via Orca.")
    if not output.exists():
        _fail("captura cancelada ou arquivo não criado.")
    print("OK — captura criada localmente.")
    print("Produção: nada alterado.")


def cmd_screen_record(args: argparse.Namespace) -> None:
    print("JARVIS — Screen Recorder")
    print("Status real: abertura do gravador nativo do macOS sob pedido explícito.")
    print("modo: painel interativo de gravação; o usuário confirma início, área e término")
    if args.dry_run:
        print("Modo: --dry-run (o gravador não foi aberto).")
        print("Produção: nada alterado.")
        return
    binary = _require_binary("screencapture")
    try:
        subprocess.Popen(
            [binary, "-i", "-v", "-Jvideo", "-U"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        _fail("não foi possível abrir o gravador nativo do macOS.")
    print("OK — painel de gravação aberto; escolha a área e clique em Gravar.")
    print("Produção: nada alterado.")


def cmd_github_overview(args: argparse.Namespace) -> None:
    print("JARVIS — GitHub Overview")
    print("Status real: leitura da conta GitHub autenticada no Mac; nenhum repositório foi alterado.")
    if args.dry_run:
        print(f"Modo: --dry-run (consultaria até {args.limit} repositórios via gh).")
        print("Produção: nada alterado.")
        return
    binary = _require_binary("gh")
    auth = subprocess.run(
        [binary, "auth", "status", "--active", "--hostname", "github.com"],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if auth.returncode != 0:
        _fail("GitHub CLI não está autenticado neste Mac.")
    user = subprocess.run(
        [binary, "api", "user", "--jq", ".login"],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    login = user.stdout.strip() if user.returncode == 0 else "@conta autenticada"
    result = subprocess.run(
        [
            binary,
            "repo",
            "list",
            login,
            "--limit",
            str(args.limit),
            "--json",
            "nameWithOwner,isPrivate,updatedAt,url",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=25,
    )
    if result.returncode != 0:
        _fail("GitHub não respondeu à listagem de repositórios.")
    try:
        repos = json.loads(result.stdout)
    except json.JSONDecodeError:
        _fail("GitHub retornou uma resposta inválida.")
    print(f"conta: {login}")
    print(f"repositórios recentes: {len(repos)}")
    for repo in repos:
        visibility = "privado" if repo.get("isPrivate") else "público"
        print(f"- {repo.get('nameWithOwner')} · {visibility} · {repo.get('updatedAt', '')}")
        print(f"  {repo.get('url', '')}")
    print("Produção: nada alterado.")


def cmd_image_to_pdf(args: argparse.Namespace) -> None:
    source = _existing_file(args.image)
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        _fail("entrada não é uma imagem suportada.")
    fallback = source.with_suffix(".pdf")
    output = _output_file(args.output, fallback, {".pdf"})
    print("JARVIS — Image to PDF")
    print("Status real: planejamento local; geração de PDF bloqueada pela doutrina.")
    print(f"entrada: {_safe_path(source)}")
    print(f"saída:   {_safe_path(output)}")
    if args.dry_run:
        print("Modo: --dry-run (nenhum PDF criado).")
        print("Produção: nada alterado.")
        return
    _fail("AGENTS.md proíbe gerar PDF. Use --dry-run para planejar ou image-convert para PNG/JPG/TIFF.", 3)


def cmd_image_convert(args: argparse.Namespace) -> None:
    source = _existing_file(args.image)
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        _fail("entrada não é uma imagem suportada.")
    requested = args.to.lower()
    native_format = IMAGE_OUTPUT_FORMATS[requested]
    extension = "jpg" if requested in {"jpg", "jpeg"} else "tiff" if requested in {"tif", "tiff"} else "png"
    fallback = source.with_name(f"{source.stem}-converted.{extension}")
    output = _output_file(args.output, fallback, {f".{extension}"})
    print("JARVIS — Image Convert")
    print("Status real: conversão local; original preservado.")
    print(f"entrada: {_safe_path(source)}")
    print(f"formato: {native_format}")
    print(f"saída:   {_safe_path(output)}")
    if args.dry_run:
        print("Modo: --dry-run (nenhuma imagem criada).")
        print("Produção: nada alterado.")
        return
    binary = _require_binary("sips")
    output.parent.mkdir(parents=True, exist_ok=True)
    _run_native([binary, "-s", "format", native_format, str(source), "--out", str(output)])
    if not output.is_file() or output.stat().st_size == 0:
        _fail("a imagem convertida não foi criada corretamente.")
    print(f"OK — imagem criada ({output.stat().st_size} bytes); original intacto.")
    print("Produção: nada alterado.")


def cmd_speak(args: argparse.Namespace) -> None:
    text = " ".join(args.text).strip()
    if not text:
        _fail("texto vazio.")
    if _looks_secret_like(text):
        _fail("o texto parece conter um segredo; nada foi falado ou gravado.", 2)
    output = None
    if args.output:
        output = _output_file(args.output, Path(args.output), {".aiff", ".aif"})
    print("JARVIS — Speak")
    print("Status real: síntese local usando a voz do macOS.")
    print(f"caracteres: {len(text)}")
    print(f"destino: {_safe_path(output) if output else 'alto-falantes'}")
    if args.dry_run:
        print("Modo: --dry-run (nenhum áudio reproduzido ou criado).")
        print("Produção: nada alterado.")
        return
    binary = _require_binary("say")
    argv = [binary, "-r", str(args.rate)]
    if args.voice:
        argv.extend(["-v", args.voice])
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        argv.extend(["-o", str(output)])
    argv.append(text)
    _run_native(argv)
    if output and not output.exists():
        _fail("arquivo de áudio não criado.")
    print("OK — fala concluída localmente.")
    print("Produção: nada alterado.")


def cmd_message_draft(args: argparse.Namespace) -> None:
    text = " ".join(args.text).strip()
    phone = "".join(char for char in args.phone if char.isdigit())
    if not text:
        _fail("mensagem vazia.")
    if _looks_secret_like(text):
        _fail("a mensagem parece conter segredo; nenhum rascunho foi criado.", 2)
    if not 8 <= len(phone) <= 15:
        _fail("telefone inválido; informe DDI + DDD + número.")
    url = f"https://wa.me/{phone}?{urlencode({'text': text})}"
    print("JARVIS — Message Draft")
    print("Status real: cria rascunho; nunca envia a mensagem automaticamente.")
    print(f"telefone final: ...{phone[-4:]}")
    print(f"caracteres: {len(text)}")
    if args.dry_run:
        print("Modo: --dry-run (nada aberto ou copiado).")
        print("Produção: nada alterado.")
        return
    acted = False
    if args.copy:
        binary = _require_binary("pbcopy")
        result = subprocess.run([binary], input=url, text=True, check=False)
        if result.returncode != 0:
            _fail("não foi possível copiar o rascunho.")
        print("OK — link do rascunho copiado.")
        acted = True
    if args.open:
        binary = _require_binary("open")
        _run_native([binary, url])
        print("OK — rascunho aberto; revise e pressione Enviar manualmente.")
        acted = True
    if not acted:
        print(f"link: {url}")
        print("Use --open para abrir ou --copy para copiar. Nada foi enviado.")
    print("Produção: nada alterado.")


def cmd_message_send(args: argparse.Namespace) -> None:
    text = " ".join(args.text).strip()
    phone = "".join(char for char in args.phone if char.isdigit())
    if not text:
        _fail("mensagem vazia.")
    if _looks_secret_like(text):
        _fail("a mensagem parece conter segredo; nada foi enviado.", 2)
    if not 8 <= len(phone) <= 15:
        _fail("telefone inválido; informe DDI + DDD + número.")
    print("JARVIS — Message Send")
    print("Status real: envio explícito pelo app Mensagens do macOS.")
    print(f"destino final: ...{phone[-4:]}")
    print(f"caracteres: {len(text)}")
    if args.dry_run:
        print("Modo: --dry-run (nenhuma mensagem enviada).")
        print("Produção: nada alterado.")
        return
    binary = _require_binary("osascript")
    script = """
on run argv
  set targetPhone to item 1 of argv
  set messageText to item 2 of argv
  tell application "Messages"
    set targetService to first service whose service type = iMessage
    set targetBuddy to buddy targetPhone of targetService
    send messageText to targetBuddy
  end tell
end run
""".strip()
    result = subprocess.run(
        [binary, "-e", script, phone, text],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        _fail("o app Mensagens recusou o envio; confirme que a conta está ativa e o destino usa iMessage.")
    print("OK — mensagem entregue ao app Mensagens para envio.")
    print("Produção: nada alterado.")


def cmd_memory_save(args: argparse.Namespace) -> None:
    text = " ".join(args.text).strip()
    if not text:
        _fail("memória vazia.")
    if _looks_secret_like(text):
        _fail("a memória parece conter segredo; nada foi salvo.", 2)
    categories = {
        "learning": "01_APRENDIZADOS",
        "decision": "02_DECISOES",
        "preference": "03_PREFERENCIAS",
    }
    category = categories[args.kind]
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    target = MEMORY_DIR / category / f"{stamp}_{_slug(text)}.md"
    print("JARVIS — Memory Save")
    print("Status real: memória operacional local e versionável.")
    print(f"tipo: {args.kind}")
    if args.dry_run:
        print(f"destino previsto: {_safe_path(target)}")
        print("Modo: --dry-run (nenhuma memória gravada).")
        print("Produção: nada alterado.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join([
            f"# Memória — {args.kind}",
            "",
            "## Conteúdo",
            text,
            "",
            "## Origem",
            "Conversa explícita com Theo pelo JARVIS.",
            "",
            "## Data",
            datetime.now().astimezone().isoformat(timespec="seconds"),
            "",
            "## Produção",
            "Nada alterado.",
            "",
        ]),
        encoding="utf-8",
    )
    print(f"Memória criada: {_safe_path(target)}")
    print("Produção: nada alterado.")


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def cmd_storage_scan(args: argparse.Namespace) -> None:
    target = Path(args.path).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    target = target.resolve()
    if not target.is_dir():
        _fail("diretório não encontrado.")
    if target == Path(target.anchor):
        _fail("varredura da raiz inteira recusada; escolha uma pasta específica.")

    min_bytes = max(0, args.min_mb) * 1024 * 1024
    largest: list[tuple[int, Path]] = []
    count = 0
    total = 0
    skipped = 0
    stopped = False

    def on_error(_error: OSError) -> None:
        nonlocal skipped
        skipped += 1

    for current, dirs, files in os.walk(target, followlinks=False, onerror=on_error):
        if not args.include_hidden:
            dirs[:] = [name for name in dirs if not name.startswith(".")]
            files = [name for name in files if not name.startswith(".")]
        for name in files:
            path = Path(current) / name
            try:
                if path.is_symlink():
                    continue
                size = path.stat().st_size
            except OSError:
                skipped += 1
                continue
            count += 1
            total += size
            if size >= min_bytes:
                largest.append((size, path))
            if count >= args.max_files:
                stopped = True
                break
        if stopped:
            break

    largest.sort(key=lambda item: item[0], reverse=True)
    disk = shutil.disk_usage(target)
    print("JARVIS — Storage Scan")
    print("Status real: somente metadados; nenhum conteúdo lido e nenhum arquivo apagado.")
    print(f"pasta: {_safe_path(target)}")
    print(f"disco total: {_format_bytes(disk.total)}")
    print(f"disco usado: {_format_bytes(disk.used)}")
    print(f"disco livre: {_format_bytes(disk.free)}")
    print(f"arquivos analisados: {count}")
    print(f"tamanho observado: {_format_bytes(total)}")
    print(f"erros ignorados: {skipped}")
    if stopped:
        print(f"AVISO: limite de {args.max_files} arquivos atingido; resultado parcial.")
    if count == 0 and skipped:
        print("AVISO: o serviço não recebeu permissão para listar esta pasta; o resumo do disco acima continua válido.")
    print("")
    print(f"## Maiores arquivos acima de {args.min_mb} MB")
    if not largest:
        print("(nenhum)")
    for size, path in largest[: args.top]:
        print(f"- {_format_bytes(size):>10}  {_safe_path(path)}")
    print("")
    print("Nenhuma limpeza foi executada. Escolha os alvos antes de mover ou apagar.")
    print("Produção: nada alterado.")


def _process_rows() -> list[dict[str, object]]:
    ps = _require_binary("ps")
    result = subprocess.run(
        [ps, "-axo", "pid=,ppid=,rss=,command="],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        _fail("não foi possível ler a lista de processos.")
    rows: list[dict[str, object]] = []
    for raw in result.stdout.splitlines():
        parts = raw.strip().split(maxsplit=3)
        if len(parts) != 4:
            continue
        try:
            pid, ppid, rss_kb = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            continue
        rows.append({"pid": pid, "ppid": ppid, "rss_kb": rss_kb, "command": parts[3]})
    return rows


def _ancestor_pids(rows: list[dict[str, object]]) -> set[int]:
    parents = {int(row["pid"]): int(row["ppid"]) for row in rows}
    ancestors = {os.getpid()}
    current = os.getpid()
    while current in parents and parents[current] > 0 and parents[current] not in ancestors:
        current = parents[current]
        ancestors.add(current)
    return ancestors


def _jarvis_temporary_process(row: dict[str, object], ancestors: set[int]) -> str | None:
    pid = int(row["pid"])
    if pid in ancestors:
        return None
    command = str(row["command"])
    lowered = command.casefold()
    root_marker = str(ROOT).casefold()
    if "api/index.py" in lowered and root_marker in lowered:
        return "servidor web JARVIS fora desta sessão"
    if "agent-browser" in lowered and (
        "chrome-headless-shell" in lowered
        or "/agent-browser/" in lowered
        or "agent-browser daemon" in lowered
    ):
        return "navegador temporário de teste JARVIS"
    return None


def _memory_free_percentage() -> int | None:
    binary = shutil.which("memory_pressure")
    if not binary:
        return None
    result = subprocess.run([binary], text=True, capture_output=True, check=False)
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", result.stdout)
    return int(match.group(1)) if match else None


def _display_process(command: str) -> str:
    lowered = command.casefold()
    known = (
        "Google Chrome Helper (Renderer)",
        "Google Chrome Helper (GPU)",
        "Google Chrome Helper",
        "Google Chrome",
        "WindowServer",
        "next-server",
        "Orca Helper (Renderer)",
        "Orca Helper",
        "Orca",
        "Claude",
        "Codex",
    )
    for label in known:
        if label.casefold() in lowered:
            return label
    executable = command.split(maxsplit=1)[0]
    return Path(executable).name[:48] or "processo"


def cmd_system_memory(args: argparse.Namespace) -> None:
    rows = _process_rows()
    ancestors = _ancestor_pids(rows)
    candidates = []
    for row in rows:
        reason = _jarvis_temporary_process(row, ancestors)
        if reason:
            candidates.append((row, reason))

    print("JARVIS — System Memory")
    print("Status real: diagnóstico da memória e processos do Mac; nada pessoal é encerrado.")
    free_percentage = _memory_free_percentage()
    if free_percentage is not None:
        pressure = "alta" if free_percentage < 15 else "moderada" if free_percentage < 30 else "normal"
        print(f"memória livre do sistema: {free_percentage}% (pressão {pressure})")
    else:
        print("memória livre do sistema: indisponível neste ambiente")
    print("")
    print("## Processos com maior memória residente")
    for row in sorted(rows, key=lambda item: int(item["rss_kb"]), reverse=True)[:8]:
        rss_mb = int(row["rss_kb"]) / 1024
        print(f"- PID {int(row['pid']):>6}  {rss_mb:>8.1f} MB  {_display_process(str(row['command']))}")
    print("")
    print("## Temporários controláveis pelo JARVIS")
    if not candidates:
        print("(nenhum processo temporário órfão encontrado)")
    for row, reason in candidates:
        print(f"- PID {int(row['pid'])}: {reason} ({int(row['rss_kb']) / 1024:.1f} MB)")

    if not args.cleanup_jarvis:
        print("")
        print("Somente diagnóstico: nenhum processo encerrado. Use --cleanup-jarvis para fechar apenas temporários do JARVIS.")
    elif args.dry_run:
        print("")
        print("Modo: --dry-run; nenhum processo encerrado.")
    else:
        requested = []
        for row, reason in candidates:
            pid = int(row["pid"])
            try:
                os.kill(pid, signal.SIGTERM)
                requested.append((pid, reason))
            except ProcessLookupError:
                continue
            except PermissionError:
                print(f"AVISO: sem permissão para encerrar PID {pid}.")
        if requested:
            time.sleep(0.15)
        print("")
        if not requested:
            print("Limpeza concluída: nada precisou ser encerrado.")
        for pid, reason in requested:
            try:
                os.kill(pid, 0)
                state = "encerramento solicitado"
            except ProcessLookupError:
                state = "encerrado"
            except PermissionError:
                state = "encerramento solicitado"
            print(f"- PID {pid}: {state} — {reason}")
    print("Chrome, Claude, Orca, Codex, WindowServer e outros processos pessoais foram preservados.")
    print("Produção: nada alterado.")


def _file_category(path: Path) -> str:
    suffix = path.suffix.lower()
    for category, suffixes in FILE_CATEGORIES.items():
        if suffix in suffixes:
            return category
    return "other"


def cmd_files_triage(args: argparse.Namespace) -> None:
    target = Path(args.path).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    target = target.resolve()
    if not target.is_dir():
        _fail("diretório não encontrado.")
    if target == Path(target.anchor):
        _fail("triagem da raiz inteira recusada; escolha uma pasta específica.")

    items = []
    skipped = 0
    try:
        candidates = sorted(target.iterdir(), key=lambda path: path.name.lower())
    except OSError:
        _fail("não foi possível listar a pasta.")
    for path in candidates:
        if path.name.startswith(".") or path.name == "JARVIS_ORGANIZED":
            skipped += 1
            continue
        if not path.is_file() or path.is_symlink():
            skipped += 1
            continue
        category = _file_category(path)
        destination = target / "JARVIS_ORGANIZED" / category / path.name
        items.append((path, destination, destination.exists()))
        if len(items) >= args.limit:
            break

    print("JARVIS — Files Triage")
    print("Status real: plano read-only; nenhum arquivo foi movido, renomeado ou apagado.")
    print(f"pasta: {_safe_path(target)}")
    print(f"arquivos no plano: {len(items)}")
    print(f"itens ignorados: {skipped}")
    print("")
    if not items:
        print("(nenhum arquivo solto para organizar)")
    for source, destination, collision in items:
        marker = "COLISÃO" if collision else "PLANO"
        print(f"- {marker:7} {_safe_path(source)}")
        print(f"          -> {_safe_path(destination)}")
    print("")
    print("Para segurança, este comando não possui --apply. Revise o plano antes de qualquer mudança.")
    print("Produção: nada alterado.")


def cmd_battery(args: argparse.Namespace) -> None:
    print("JARVIS — Battery Telemetry")
    print("Status real: leitura local da bateria do Mac. Nada foi alterado.")
    if getattr(args, "dry_run", False):
        print("Modo: --dry-run (telemetria não consultada).")
        print("Produção: nada alterado.")
        return

    state_str = "Desconhecido"
    pct_str = "0%"
    source_str = "Desconhecida"
    remaining_str = "N/A"
    try:
        res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if lines:
                if "AC Power" in lines[0]:
                    source_str = "Carregador (AC Power)"
                elif "Battery Power" in lines[0]:
                    source_str = "Bateria (Battery Power)"
            if len(lines) > 1:
                m = re.search(r"(\d+)%", lines[1])
                if m:
                    pct_str = f"{m.group(1)}%"
                if "charging;" in lines[1]:
                    state_str = "Carregando"
                elif "charged;" in lines[1]:
                    state_str = "Carregada (100%)"
                elif "discharging;" in lines[1]:
                    state_str = "Descarregando"
                else:
                    state_str = "Conectada"
                m_rem = re.search(r"(\d+:\d+) remaining", lines[1])
                if m_rem:
                    remaining_str = f"{m_rem.group(1)} restantes"
    except Exception as e:
        state_str = f"Erro ao ler pmset: {e}"

    cycle_str = "N/A"
    condition_str = "N/A"
    capacity_str = "N/A"
    try:
        res_prof = subprocess.run(["system_profiler", "SPPowerDataType"], capture_output=True, text=True, check=False, timeout=10)
        if res_prof.returncode == 0:
            for line in res_prof.stdout.splitlines():
                if "Cycle Count:" in line:
                    cycle_str = line.split(":", 1)[1].strip()
                elif "Condition:" in line:
                    condition_str = line.split(":", 1)[1].strip()
                elif "Maximum Capacity:" in line:
                    capacity_str = line.split(":", 1)[1].strip()
    except Exception:
        pass

    print(f"Fonte de energia: {source_str}")
    print(f"Carga atual:      {pct_str} ({state_str})")
    print(f"Tempo restante:   {remaining_str}")
    print(f"Ciclos de carga:  {cycle_str}")
    print(f"Condição:         {condition_str}")
    if capacity_str != "N/A":
        print(f"Saúde da bateria: {capacity_str}")
    print("Produção: nada alterado.")


def cmd_system_volume(args: argparse.Namespace) -> None:
    print("JARVIS — Mac System Volume")
    print("Status real: controle ou inspeção de volume do macOS.")
    action = getattr(args, "action", None)
    if getattr(args, "dry_run", False):
        print(f"Modo: --dry-run (ação {action or 'status'} não executada).")
        print("Produção: nada alterado.")
        return

    binary = _require_binary("osascript")
    if not action or action == "status":
        res = subprocess.run([binary, "-e", "get volume settings"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"Volume do sistema: {res.stdout.strip()}")
        else:
            _fail("não foi possível ler as configurações de volume.")
        print("Produção: nada alterado.")
        return

    if action == "mute":
        res = subprocess.run([binary, "-e", "set volume output muted true"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print("OK — Som do Mac silenciado (mute).")
        else:
            _fail("falha ao silenciar o som.")
        print("Produção: volume do Mac alterado localmente; nenhum deploy alterado.")
        return

    if action == "unmute":
        res = subprocess.run([binary, "-e", "set volume output muted false"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print("OK — Som do Mac ativado (unmute).")
        else:
            _fail("falha ao desativar mudo.")
        print("Produção: volume do Mac alterado localmente; nenhum deploy alterado.")
        return

    try:
        vol = int(action)
        if not 0 <= vol <= 100:
            _fail("volume deve estar entre 0 e 100.")
        subprocess.run([binary, "-e", f"set volume output volume {vol}"], capture_output=True, text=True, check=False)
        print(f"OK — Volume do Mac ajustado para {vol}%.")
        print("Produção: volume do Mac alterado localmente; nenhum deploy alterado.")
        return
    except ValueError:
        _fail("ação de volume inválida; use: status, mute, unmute ou um número de 0 a 100.")


def cmd_wifi_info(args: argparse.Namespace) -> None:
    print("JARVIS — Wi-Fi & Network Telemetry")
    print("Status real: leitura da rede local do Mac. Nada foi editado.")
    if getattr(args, "dry_run", False):
        print("Modo: --dry-run (leitura de rede não executada).")
        print("Produção: nada alterado.")
        return

    ssid = "N/A"
    phy_mode = "N/A"
    channel = "N/A"
    signal_str = "N/A"
    tx_rate = "N/A"
    status_str = "Desconectado"

    try:
        res = subprocess.run(["system_profiler", "SPAirPortDataType"], capture_output=True, text=True, check=False, timeout=12)
        if res.returncode == 0:
            in_current = False
            for line in res.stdout.splitlines():
                if "Current Network Information:" in line:
                    in_current = True
                    continue
                if in_current:
                    stripped = line.strip()
                    if stripped.endswith(":") and not stripped.startswith("Other Local"):
                        ssid = stripped.rstrip(":")
                    if "Status: Connected" in line:
                        status_str = "Conectado"
                    if "PHY Mode:" in line:
                        phy_mode = line.split(":", 1)[1].strip()
                    if "Channel:" in line:
                        channel = line.split(":", 1)[1].strip()
                    if "Signal / Noise:" in line:
                        signal_str = line.split(":", 1)[1].strip()
                    if "Transmit Rate:" in line:
                        tx_rate = line.split(":", 1)[1].strip()
                    if "Other Local Wi-Fi Networks:" in line:
                        break
    except Exception:
        pass

    local_ip = "N/A"
    try:
        res_ip = subprocess.run(["ipconfig", "getifaddr", "en0"], capture_output=True, text=True, check=False)
        if res_ip.returncode == 0 and res_ip.stdout.strip():
            local_ip = res_ip.stdout.strip()
    except Exception:
        pass

    gateway = "N/A"
    try:
        res_gw = subprocess.run(["route", "-n", "get", "default"], capture_output=True, text=True, check=False)
        for line in res_gw.stdout.splitlines():
            if "gateway:" in line:
                gateway = line.split(":", 1)[1].strip()
    except Exception:
        pass

    if local_ip != "N/A" and ssid != "N/A":
        status_str = "Conectado"

    print(f"Status:       {status_str}")
    print(f"Rede (SSID):  {ssid}")
    print(f"IP Local:     {local_ip}")
    print(f"Gateway:      {gateway}")
    print(f"Canal/Freq:   {channel}")
    print(f"Sinal/Ruído:  {signal_str}")
    print(f"Modo PHY:     {phy_mode}")
    print(f"Taxa TX:      {tx_rate} Mbps")
    print("Produção: nada alterado.")


def cmd_wifi_passwords(args: argparse.Namespace) -> None:
    print("JARVIS — Wi-Fi Keychain Assistant")
    print("Status real: inspeção de redes salvas no Keychain do macOS.")
    if getattr(args, "dry_run", False):
        print("Modo: --dry-run (consulta ao Keychain não executada).")
        print("Produção: nada alterado.")
        return

    ssid = getattr(args, "ssid", None)
    if not ssid:
        try:
            res = subprocess.run(["networksetup", "-listpreferredwirelessnetworks", "en0"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                print("Redes Wi-Fi conhecidas neste Mac:")
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip() and not l.startswith("Preferred networks")]
                limit = getattr(args, "limit", 25) or 25
                for net in lines[:limit]:
                    print(f"  • {net}")
                if len(lines) > limit:
                    print(f"  ... e mais {len(lines) - limit} redes. Use `./jarvis wifi-passwords \"NOME\"` para consultar uma específica.")
            else:
                _fail("não foi possível listar redes salvas.")
        except Exception as e:
            _fail(f"erro ao listar redes: {e}")
        print("Produção: nada alterado.")
        return

    print(f"Consultando credenciais da rede: {ssid}")
    try:
        res = subprocess.run(
            ["security", "find-generic-password", "-D", "AirPort network password", "-a", ssid, "-gw"],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
        if res.returncode == 0 and res.stdout.strip():
            retrieved = res.stdout.strip()
            masked = retrieved[0] + ("*" * (len(retrieved) - 2)) + retrieved[-1] if len(retrieved) > 2 else "***"
            if getattr(args, "show_clear", False):
                print(f"Senha recuperada: {retrieved}")
            else:
                print(f"Senha recuperada: {masked} (use --show-clear para exibir texto puro)")
        else:
            print(f"Senha não encontrada no Keychain ou acesso não autorizado para '{ssid}'.")
    except subprocess.TimeoutExpired:
        print("O macOS aguardou autorização no Keychain e expirou o tempo limite.")
    except Exception as e:
        print(f"Erro ao consultar Keychain: {e}")
    print("Produção: nada alterado.")


def cmd_mac_specs(args: argparse.Namespace) -> None:
    print("JARVIS — Mac Hardware & System Specifications")
    print("Status real: telemetria de hardware local.")
    if getattr(args, "dry_run", False):
        print("Modo: --dry-run.")
        print("Produção: nada alterado.")
        return

    os_ver = "macOS"
    try:
        r = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True, check=False)
        os_ver = f"macOS {r.stdout.strip()}"
    except Exception:
        pass

    chip = "Apple Silicon"
    try:
        r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, check=False)
        chip = r.stdout.strip() or chip
    except Exception:
        pass

    ram_gb = "16 GB"
    try:
        r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False)
        b = int(r.stdout.strip())
        ram_gb = f"{round(b / (1024**3))} GB"
    except Exception:
        pass

    cores = "8"
    try:
        r = subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True, check=False)
        cores = r.stdout.strip() or cores
    except Exception:
        pass

    disk_info = "N/A"
    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, check=False)
        lines = r.stdout.strip().splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            disk_info = f"Total: {parts[1]} · Usado: {parts[2]} · Livre: {parts[3]} ({parts[4]} ocupado)"
    except Exception:
        pass

    uptime_str = "N/A"
    try:
        r = subprocess.run(["uptime"], capture_output=True, text=True, check=False)
        uptime_str = r.stdout.strip()
    except Exception:
        pass

    print(f"Sistema Operacional: {os_ver}")
    print(f"Processador / Chip:  {chip} ({cores} núcleos)")
    print(f"Memória RAM Total:   {ram_gb}")
    print(f"Armazenamento (/):   {disk_info}")
    print(f"Tempo de Atividade:  {uptime_str}")
    print("Produção: nada alterado.")


def cmd_network_quality(args: argparse.Namespace) -> None:
    print("JARVIS — Network Quality & Speed Test")
    print("Status real: teste nativo de velocidade de conexão do macOS.")
    if getattr(args, "dry_run", False):
        print("Modo: --dry-run (teste de velocidade não executado).")
        print("Produção: nada alterado.")
        return

    binary = "/usr/bin/networkQuality"
    if not os.path.exists(binary):
        _fail("utilitário /usr/bin/networkQuality ausente neste macOS.")

    print("Executando teste de capacidade de rede (aguarde alguns segundos)...")
    try:
        res = subprocess.run([binary, "-c"], capture_output=True, text=True, check=False, timeout=35)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            dl_mbps = round((data.get("dl_throughput", 0) / 1_000_000) * 8, 2)
            ul_mbps = round((data.get("ul_throughput", 0) / 1_000_000) * 8, 2)
            responsiveness = round(data.get("responsiveness", 0))
            interface = data.get("interface_name", "en0")
            print(f"Interface:       {interface}")
            print(f"Download:        {dl_mbps} Mbps")
            print(f"Upload:          {ul_mbps} Mbps")
            print(f"Responsividade:  {responsiveness} RPM (Round-trips Per Minute)")
        else:
            res_seq = subprocess.run([binary, "-s"], capture_output=True, text=True, check=False, timeout=20)
            print(res_seq.stdout.strip())
    except Exception as e:
        _fail(f"falha durante o teste de qualidade de rede: {e}")
    print("Produção: nada alterado.")


def cmd_weather(args: argparse.Namespace) -> None:
    import urllib.parse
    print("JARVIS — Weather Intelligence")
    print("Status real: previsão do tempo consultada via wttr.in. Nada alterado.")
    location = getattr(args, "location", "") or ""
    if getattr(args, "dry_run", False):
        print(f"Modo: --dry-run (previsão para '{location or 'local'}' não consultada).")
        print("Produção: nada alterado.")
        return

    encoded = urllib.parse.quote(location)
    url = f"https://wttr.in/{encoded}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        curr = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]
        city = area.get("areaName", [{}])[0].get("value", location or "Local")
        region = area.get("region", [{}])[0].get("value", "")
        country = area.get("country", [{}])[0].get("value", "")
        temp_c = curr.get("temp_C")
        feels_c = curr.get("FeelsLikeC")
        desc = curr.get("weatherDesc", [{}])[0].get("value", "")
        humidity = curr.get("humidity")
        wind = curr.get("windspeedKmph")
        precip = curr.get("precipMM")

        loc_str = f"{city}" + (f", {region}" if region else "") + (f" ({country})" if country else "")
        print(f"Localização:     {loc_str}")
        print(f"Condição:        {desc}")
        print(f"Temperatura:     {temp_c}°C (Sensação térmica: {feels_c}°C)")
        print(f"Umidade do ar:   {humidity}%")
        print(f"Velocidade vento:{wind} km/h")
        print(f"Precipitação:    {precip} mm")

        weather_days = data.get("weather", [])
        if weather_days:
            today = weather_days[0]
            print(f"Previsão hoje:   Mín {today.get('mintempC')}°C / Máx {today.get('maxtempC')}°C")
            if len(weather_days) > 1:
                tomorrow = weather_days[1]
                print(f"Previsão amanhã: Mín {tomorrow.get('mintempC')}°C / Máx {tomorrow.get('maxtempC')}°C")
    except Exception as e:
        _fail(f"não foi possível obter previsão do tempo: {e}")
    print("Produção: nada alterado.")


def cmd_qr(args: argparse.Namespace) -> None:
    import urllib.parse
    print("JARVIS — QR Code Generator")
    print("Status real: geração de código QR local/visual.")
    text = " ".join(args.text) if isinstance(args.text, list) else str(args.text)
    if not text.strip():
        _fail("informe o texto ou URL para gerar o QR Code.")
    if getattr(args, "dry_run", False):
        print(f"Modo: --dry-run (QR Code para '{text[:30]}...' não gerado).")
        print("Produção: nada alterado.")
        return

    output = getattr(args, "output", None)
    if output:
        out_path = Path(output).expanduser()
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        if out_path.exists():
            _fail(f"o arquivo de saída já existe: {out_path}")
        encoded_data = urllib.parse.quote(text)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_data}"
        req = urllib.request.Request(qr_url, headers={"User-Agent": "curl/7.68.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                content = resp.read()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(content)
            print(f"OK — QR Code salvo com sucesso em: {_safe_path(out_path)}")
        except Exception as e:
            _fail(f"falha ao gerar imagem do QR Code: {e}")
    else:
        encoded_data = urllib.parse.quote(text)
        qr_url = f"https://qrenco.de/{encoded_data}"
        req = urllib.request.Request(qr_url, headers={"User-Agent": "curl/7.68.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                ascii_qr = resp.read().decode("utf-8")
            print(f"QR Code para: {text}\n")
            print(ascii_qr)
        except Exception as e:
            _fail(f"falha ao gerar QR Code no terminal: {e}")
    print("Produção: nada alterado.")


def cmd_crypto_stock(args: argparse.Namespace) -> None:
    print("JARVIS — Market & Crypto Telemetry")
    print("Status real: cotações em tempo real de ativos e moedas.")
    if getattr(args, "dry_run", False):
        print("Modo: --dry-run (cotações não consultadas).")
        print("Produção: nada alterado.")
        return

    try:
        url_crypto = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd,brl"
        req = urllib.request.Request(url_crypto, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        btc = data.get("bitcoin", {})
        eth = data.get("ethereum", {})
        sol = data.get("solana", {})
        print("— CRIPTOMOEDAS —")
        print(f"Bitcoin (BTC):  USD ${btc.get('usd', 0):,.2f}  |  R$ {btc.get('brl', 0):,.2f}")
        print(f"Ethereum (ETH): USD ${eth.get('usd', 0):,.2f}  |  R$ {eth.get('brl', 0):,.2f}")
        print(f"Solana (SOL):   USD ${sol.get('usd', 0):,.2f}  |  R$ {sol.get('brl', 0):,.2f}")
    except Exception as e:
        print(f"Criptomoedas: indisponível no momento ({e})")

    try:
        url_fiat = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url_fiat, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            fiat_data = json.loads(resp.read().decode("utf-8"))
        rates = fiat_data.get("rates", {})
        brl_usd = rates.get("BRL", 0)
        eur_usd = rates.get("EUR", 0)
        print("\n— CÂMBIO COMERCIAL —")
        print(f"Dólar (USD / BRL): R$ {brl_usd:.4f}")
        if eur_usd and brl_usd:
            eur_brl = brl_usd / eur_usd
            print(f"Euro (EUR / BRL):  R$ {eur_brl:.4f}")
    except Exception as e:
        print(f"Câmbio: indisponível no momento ({e})")

    print("Produção: nada alterado.")


def cmd_tech_brief(args: argparse.Namespace) -> None:
    print("JARVIS — Tech Intelligence Briefing (Hacker News)")
    print("Status real: leitura das principais novidades de tecnologia.")
    limit = getattr(args, "limit", 5) or 5
    if getattr(args, "dry_run", False):
        print(f"Modo: --dry-run (top {limit} não coletado).")
        print("Produção: nada alterado.")
        return

    try:
        top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        req = urllib.request.Request(top_url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            ids = json.loads(resp.read().decode("utf-8"))[:limit]

        print(f"Top {len(ids)} histórias em destaque agora:\n")
        for idx, item_id in enumerate(ids, 1):
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            item_req = urllib.request.Request(item_url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(item_req, timeout=8) as item_resp:
                story = json.loads(item_resp.read().decode("utf-8"))
            title = story.get("title", "")
            score = story.get("score", 0)
            url = story.get("url", f"https://news.ycombinator.com/item?id={item_id}")
            print(f"{idx}. {title}")
            print(f"   Pontos: {score} · Link: {url}")
    except Exception as e:
        _fail(f"falha ao coletar tech brief: {e}")
    print("\nProdução: nada alterado.")


def cmd_wiki(args: argparse.Namespace) -> None:
    import urllib.parse
    print("JARVIS — Wikipedia Summary Assistant")
    print("Status real: consulta enciclopédica rápida via Wikipedia REST API.")
    term = " ".join(args.term) if isinstance(args.term, list) else str(args.term)
    if not term.strip():
        _fail("informe o termo a ser pesquisado.")
    lang = getattr(args, "lang", "pt") or "pt"
    if getattr(args, "dry_run", False):
        print(f"Modo: --dry-run (pesquisa para '{term}' em {lang} não executada).")
        print("Produção: nada alterado.")
        return

    slug = urllib.parse.quote(term.strip().replace(" ", "_"))
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}"
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Assistant/1.0 (theopadilha)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        title = data.get("title", term)
        desc = data.get("description", "")
        extract = data.get("extract", "")
        if not extract:
            print(f"Nenhum resumo encontrado para '{term}'.")
            return
        print(f"Título: {title}" + (f" ({desc})" if desc else ""))
        print("")
        print(extract)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Tópico '{term}' não encontrado na Wikipedia ({lang}).")
        else:
            _fail(f"erro HTTP ao consultar Wikipedia: {e.code}")
    except Exception as e:
        _fail(f"falha ao acessar Wikipedia: {e}")
    print("\nProdução: nada alterado.")


def cmd_workspace(args: argparse.Namespace) -> None:
    print("JARVIS — Workspace & Operational Modes")
    mode = args.mode.lower()
    print(f"Status real: alternância para modo de trabalho: {mode.upper()}.")
    if getattr(args, "dry_run", False):
        print(f"Modo: --dry-run (modo {mode} não aplicado).")
        print("Produção: nada alterado.")
        return

    binary_osascript = _require_binary("osascript")

    if mode == "foco":
        subprocess.run([binary_osascript, "-e", "set volume output volume 40"], check=False)
        _spotify_script("play")
        notify_script = 'display notification "Modo Foco Ativado. Volume em 40% e som ambiente iniciado." with title "JARVIS"'
        subprocess.run([binary_osascript, "-e", notify_script], check=False)
        print("OK — Modo Foco ativado: volume em 40%, Spotify iniciado e notificações ajustadas.")

    elif mode == "reuniao":
        _spotify_script("pause")
        subprocess.run([binary_osascript, "-e", "set volume output volume 60"], check=False)
        notify_script = 'display notification "Modo Reunião Ativado. Spotify pausado e volume em 60%." with title "JARVIS"'
        subprocess.run([binary_osascript, "-e", notify_script], check=False)
        print("OK — Modo Reunião ativado: Spotify pausado, áudio ajustado.")

    elif mode == "codigo":
        subprocess.run(["open", "-a", "Visual Studio Code"], check=False)
        subprocess.run([binary_osascript, "-e", "set volume output volume 50"], check=False)
        notify_script = 'display notification "Ambiente de Desenvolvimento pronto." with title "JARVIS"'
        subprocess.run([binary_osascript, "-e", notify_script], check=False)
        print("OK — Modo Código ativado: VS Code aberto e áudio em 50%.")

    elif mode == "off":
        _spotify_script("pause")
        subprocess.run([binary_osascript, "-e", "set volume output volume 20"], check=False)
        notify_script = 'display notification "Expediente encerrado. Descanse!" with title "JARVIS"'
        subprocess.run([binary_osascript, "-e", notify_script], check=False)
        print("OK — Modo Off ativado: Spotify pausado e sistema em repouso.")
    else:
        _fail(f"modo desconhecido: '{mode}'. Opções válidas: foco, reuniao, codigo, off.")

    print("Produção: ambiente local configurado; nenhum deploy alterado.")


def cmd_file_organize(args: argparse.Namespace) -> None:
    target = Path(args.path).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    target = target.resolve()
    if not target.is_dir():
        _fail("diretório não encontrado.")
    if target == Path(target.anchor):
        _fail("organização da raiz inteira recusada; escolha uma pasta específica.")

    is_apply = getattr(args, "apply", False) and not getattr(args, "dry_run", False)

    print("JARVIS — File Organizer")
    if is_apply:
        print("Status real: organização ativa de arquivos soltos. Proteção contra sobrescrita ativada.")
    else:
        print("Status real: preview seguro (dry-run). Nenhum arquivo foi movido.")
    print(f"Pasta alvo: {_safe_path(target)}")

    items = []
    skipped = 0
    try:
        candidates = sorted(target.iterdir(), key=lambda path: path.name.lower())
    except OSError:
        _fail("não foi possível listar a pasta.")

    for path in candidates:
        if path.name.startswith(".") or path.name == "JARVIS_ORGANIZED":
            skipped += 1
            continue
        if not path.is_file() or path.is_symlink():
            skipped += 1
            continue
        category = _file_category(path)
        dest_folder = target / "JARVIS_ORGANIZED" / category
        destination = dest_folder / path.name

        if destination.exists() and is_apply:
            base = path.stem
            ext = path.suffix
            counter = 1
            while (dest_folder / f"{base}_{counter}{ext}").exists():
                counter += 1
            destination = dest_folder / f"{base}_{counter}{ext}"

        items.append((path, destination))
        if len(items) >= args.limit:
            break

    print(f"Arquivos identificados: {len(items)} (ignorados: {skipped})")
    print("")

    if not items:
        print("(nenhum arquivo solto para organizar)")
        print("Produção: nada alterado.")
        return

    moved = 0
    for source, destination in items:
        if is_apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            print(f"- MOVIDO  {_safe_path(source)} -> {_safe_path(destination)}")
            moved += 1
        else:
            print(f"- PLANO   {_safe_path(source)} -> {_safe_path(destination)}")

    print("")
    if is_apply:
        print(f"Concluído: {moved} arquivos movidos com segurança para subpastas em JARVIS_ORGANIZED/.")
        print("Produção: arquivos locais organizados; nenhum deploy alterado.")
    else:
        print("Dica: para aplicar as mudanças de fato, execute com a flag `--apply`.")
        print("Produção: nada alterado.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="personal_tools.py")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")

    capture = sub.add_parser("screen-capture")
    capture.add_argument("--output")
    capture.add_argument("--interactive", action="store_true")
    capture.add_argument("--dry-run", action="store_true")

    record = sub.add_parser("screen-record")
    record.add_argument("--dry-run", action="store_true")

    github = sub.add_parser("github-overview")
    github.add_argument("--limit", type=int, default=12, choices=range(1, 51))
    github.add_argument("--dry-run", action="store_true")

    image = sub.add_parser("image-to-pdf")
    image.add_argument("image")
    image.add_argument("--output")
    image.add_argument("--dry-run", action="store_true")

    convert = sub.add_parser("image-convert")
    convert.add_argument("image")
    convert.add_argument("--to", required=True, choices=sorted(IMAGE_OUTPUT_FORMATS))
    convert.add_argument("--output")
    convert.add_argument("--dry-run", action="store_true")

    speak = sub.add_parser("speak")
    speak.add_argument("text", nargs="+")
    speak.add_argument("--voice")
    speak.add_argument("--rate", type=int, default=190, choices=range(80, 401))
    speak.add_argument("--output")
    speak.add_argument("--dry-run", action="store_true")

    message = sub.add_parser("message-draft")
    message.add_argument("--phone", required=True)
    message.add_argument("text", nargs="+")
    message.add_argument("--open", action="store_true")
    message.add_argument("--copy", action="store_true")
    message.add_argument("--dry-run", action="store_true")

    message_send = sub.add_parser("message-send")
    message_send.add_argument("--phone", required=True)
    message_send.add_argument("text", nargs="+")
    message_send.add_argument("--dry-run", action="store_true")

    memory = sub.add_parser("memory-save")
    memory.add_argument("text", nargs="+")
    memory.add_argument("--kind", choices=("learning", "decision", "preference"), default="learning")
    memory.add_argument("--dry-run", action="store_true")

    storage = sub.add_parser("storage-scan")
    storage.add_argument("path", nargs="?", default=".")
    storage.add_argument("--top", type=int, default=20, choices=range(1, 101))
    storage.add_argument("--min-mb", type=int, default=100)
    storage.add_argument("--max-files", type=int, default=200000)
    storage.add_argument("--include-hidden", action="store_true")

    system_memory = sub.add_parser("system-memory")
    system_memory.add_argument("--cleanup-jarvis", action="store_true")
    system_memory.add_argument("--dry-run", action="store_true")

    spotify = sub.add_parser("spotify")
    spotify.add_argument(
        "action",
        choices=("status", "play", "pause", "toggle", "next", "previous", "volume", "shuffle", "repeat", "search", "play-uri"),
    )
    spotify.add_argument("value", nargs="*")
    spotify.add_argument("--dry-run", action="store_true")

    computer = sub.add_parser("computer")
    computer.add_argument("action", choices=("list", "inspect", "open", "close"))
    computer.add_argument("app", nargs="?")
    computer.add_argument("--dry-run", action="store_true")

    triage = sub.add_parser("files-triage")
    triage.add_argument("path", nargs="?", default=".")
    triage.add_argument("--limit", type=int, default=100, choices=range(1, 1001))

    # Novas ferramentas (inspiradas no sukeesh/Jarvis)
    batt = sub.add_parser("battery")
    batt.add_argument("--dry-run", action="store_true")

    vol = sub.add_parser("system-volume")
    vol.add_argument("action", nargs="?", default="status")
    vol.add_argument("--dry-run", action="store_true")

    wifi_inf = sub.add_parser("wifi-info")
    wifi_inf.add_argument("--dry-run", action="store_true")

    wifi_pwd = sub.add_parser("wifi-passwords")
    wifi_pwd.add_argument("ssid", nargs="?", default=None)
    wifi_pwd.add_argument("--limit", type=int, default=25)
    wifi_pwd.add_argument("--show-clear", action="store_true")
    wifi_pwd.add_argument("--dry-run", action="store_true")

    specs = sub.add_parser("mac-specs")
    specs.add_argument("--dry-run", action="store_true")

    net_q = sub.add_parser("network-quality")
    net_q.add_argument("--dry-run", action="store_true")

    wth = sub.add_parser("weather")
    wth.add_argument("location", nargs="?", default="")
    wth.add_argument("--dry-run", action="store_true")

    qr_cmd = sub.add_parser("qr")
    qr_cmd.add_argument("text", nargs="+")
    qr_cmd.add_argument("--output")
    qr_cmd.add_argument("--dry-run", action="store_true")

    cr_stock = sub.add_parser("crypto-stock")
    cr_stock.add_argument("tickers", nargs="*")
    cr_stock.add_argument("--dry-run", action="store_true")

    t_brief = sub.add_parser("tech-brief")
    t_brief.add_argument("--limit", type=int, default=5)
    t_brief.add_argument("--dry-run", action="store_true")

    wk = sub.add_parser("wiki")
    wk.add_argument("term", nargs="+")
    wk.add_argument("--lang", default="pt")
    wk.add_argument("--dry-run", action="store_true")

    wspace = sub.add_parser("workspace")
    wspace.add_argument("mode", choices=("foco", "reuniao", "codigo", "off"))
    wspace.add_argument("--dry-run", action="store_true")

    f_org = sub.add_parser("file-organize")
    f_org.add_argument("path", nargs="?", default=".")
    f_org.add_argument("--limit", type=int, default=100, choices=range(1, 1001))
    f_org.add_argument("--apply", action="store_true")
    f_org.add_argument("--dry-run", action="store_true")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    handlers = {
        "doctor": cmd_doctor,
        "screen-capture": cmd_screen_capture,
        "screen-record": cmd_screen_record,
        "github-overview": cmd_github_overview,
        "image-to-pdf": cmd_image_to_pdf,
        "image-convert": cmd_image_convert,
        "speak": cmd_speak,
        "message-draft": cmd_message_draft,
        "message-send": cmd_message_send,
        "memory-save": cmd_memory_save,
        "storage-scan": cmd_storage_scan,
        "system-memory": cmd_system_memory,
        "spotify": cmd_spotify,
        "computer": cmd_computer,
        "files-triage": cmd_files_triage,
        "battery": cmd_battery,
        "system-volume": cmd_system_volume,
        "wifi-info": cmd_wifi_info,
        "wifi-passwords": cmd_wifi_passwords,
        "mac-specs": cmd_mac_specs,
        "network-quality": cmd_network_quality,
        "weather": cmd_weather,
        "qr": cmd_qr,
        "crypto-stock": cmd_crypto_stock,
        "tech-brief": cmd_tech_brief,
        "wiki": cmd_wiki,
        "workspace": cmd_workspace,
        "file-organize": cmd_file_organize,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()

