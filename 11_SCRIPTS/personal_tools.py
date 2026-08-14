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
    "whatsapp": ("WhatsApp", "net.whatsapp.WhatsApp"),
    "spotify": ("Spotify", "com.spotify.client"),
    "steam": ("Steam", "com.valvesoftware.steam"),
    "discord": ("Discord", "com.hnc.Discord"),
    "vscode": ("Visual Studio Code", "com.microsoft.VSCode"),
    "visual studio code": ("Visual Studio Code", "com.microsoft.VSCode"),
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
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
