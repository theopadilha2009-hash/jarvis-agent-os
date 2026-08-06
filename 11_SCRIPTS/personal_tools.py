"""Small, deterministic personal tools for the local-first JARVIS.

The module intentionally uses Python's standard library plus native macOS
commands. It never invokes a shell, reads environment files, deletes files,
or overwrites outputs. Messages are sent only by the explicit `message-send`
command; `message-draft` remains a non-sending WhatsApp handoff.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
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
    print("")
    print(f"Disponíveis: {available}/{len(tools)}")
    print("Regra: somente message-send envia sob pedido explícito; nenhum arquivo é apagado automaticamente.")
    print("Produção: nada alterado.")


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
    _run_native([binary, *flags, str(output)])
    if not output.exists():
        _fail("captura cancelada ou arquivo não criado.")
    print("OK — captura criada localmente.")
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
    print("JARVIS — Storage Scan")
    print("Status real: somente metadados; nenhum conteúdo lido e nenhum arquivo apagado.")
    print(f"pasta: {_safe_path(target)}")
    print(f"arquivos analisados: {count}")
    print(f"tamanho observado: {_format_bytes(total)}")
    print(f"erros ignorados: {skipped}")
    if stopped:
        print(f"AVISO: limite de {args.max_files} arquivos atingido; resultado parcial.")
    print("")
    print(f"## Maiores arquivos acima de {args.min_mb} MB")
    if not largest:
        print("(nenhum)")
    for size, path in largest[: args.top]:
        print(f"- {_format_bytes(size):>10}  {_safe_path(path)}")
    print("")
    print("Nenhuma limpeza foi executada. Escolha os alvos antes de mover ou apagar.")
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

    triage = sub.add_parser("files-triage")
    triage.add_argument("path", nargs="?", default=".")
    triage.add_argument("--limit", type=int, default=100, choices=range(1, 1001))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    handlers = {
        "doctor": cmd_doctor,
        "screen-capture": cmd_screen_capture,
        "image-to-pdf": cmd_image_to_pdf,
        "image-convert": cmd_image_convert,
        "speak": cmd_speak,
        "message-draft": cmd_message_draft,
        "message-send": cmd_message_send,
        "memory-save": cmd_memory_save,
        "storage-scan": cmd_storage_scan,
        "files-triage": cmd_files_triage,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
