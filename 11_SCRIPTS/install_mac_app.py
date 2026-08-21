#!/usr/bin/env python3
"""JARVIS como aplicativo nativo do Mac: WKWebView, não Chrome.

Monta um bundle .app de verdade. Abrir o ícone sobe o canto /fala numa
janela própria do processo JARVIS — Dock, mic e Spotlight no nome dele.

    python3 11_SCRIPTS/install_mac_app.py            # instala em ~/Applications
    python3 11_SCRIPTS/install_mac_app.py --check    # só diz o que faria
    python3 11_SCRIPTS/install_mac_app.py --remove   # desinstala
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
import os
import zipfile

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import jarvis_creator_seal as creator_seal  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "web" / "jarvis-logo.png"
ICON_PNG = ROOT / "web" / "jarvis-icon-512.png"
ICON_ICNS = ROOT / "web" / "jarvis.icns"
LAUNCH_AGENT_LABEL = "ai.theopadilha.jarvis.fala"
APP_NAME = "JARVIS"
BUNDLE_ID = "ai.theopadilha.jarvis.cockpit"
# Origem única do cockpit. Permissão de microfone, escuta pelo nome e estilo
# ficam presos ao domínio: dois endereços significam duas configurações.
DEFAULT_ORIGIN = "https://jarvis-theo.vercel.app"
DEFAULT_URL = f"{DEFAULT_ORIGIN}/fala?app=1"
PACK_NAME = "JARVIS.mac.zip"
# Fundo do cockpit: o ícone fica quadrado sem esticar o logo.
ICON_BACKGROUND = "130824"
ICON_SIZES = (16, 32, 64, 128, 256, 512, 1024)
SWIFT_SOURCE = SCRIPTS / "jarvis_native_app.swift"
MACHO_MAGICS = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe"}


def install_root(system_wide: bool) -> Path:
    return Path("/Applications") if system_wide else Path.home() / "Applications"


def build_icon(destination: Path) -> bool:
    """Gera o .icns a partir do logo. Sem as ferramentas do macOS, segue sem ícone."""
    if not LOGO.is_file() or not shutil.which("sips") or not shutil.which("iconutil"):
        return False
    iconset = destination.parent / "jarvis.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    try:
        for size in ICON_SIZES:
            for name, pixels in ((f"icon_{size}x{size}.png", size), (f"icon_{size // 2}x{size // 2}@2x.png", size)):
                if pixels // 2 < 8 and "@2x" in name:
                    continue
                subprocess.run(
                    [
                        "sips", "-s", "format", "png",
                        "--padToHeightWidth", str(pixels), str(pixels),
                        "--padColor", ICON_BACKGROUND,
                        str(LOGO), "--out", str(iconset / name),
                    ],
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(destination)],
            capture_output=True,
            timeout=60,
            check=False,
        )
        return result.returncode == 0 and destination.is_file()
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        shutil.rmtree(iconset, ignore_errors=True)


def app_url(url: str) -> str:
    cleaned = (url or DEFAULT_ORIGIN).rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.path.rstrip("/") in {"", "/"}:
        return f"{cleaned}/fala?app=1"
    if parsed.path.rstrip("/").endswith("/fala"):
        if "app=1" in (parsed.query or ""):
            return cleaned
        joiner = "&" if parsed.query else "?"
        return f"{cleaned}{joiner}app=1"
    return cleaned


def is_macho(path: Path) -> bool:
    try:
        return path.read_bytes()[:4] in MACHO_MAGICS
    except OSError:
        return False


def compile_native_binary(destination: Path) -> None:
    swiftc = shutil.which("swiftc")
    if not swiftc:
        raise RuntimeError("swiftc não encontrado. Instale as Command Line Tools da Apple.")
    if not SWIFT_SOURCE.is_file():
        raise RuntimeError(f"Fonte nativa ausente: {SWIFT_SOURCE}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            swiftc,
            "-parse-as-library",
            "-O",
            "-framework", "AppKit",
            "-framework", "WebKit",
            "-framework", "AVFoundation",
            "-framework", "Speech",
            "-framework", "ScreenCaptureKit",
            "-o", str(destination),
            str(SWIFT_SOURCE),
        ],
        capture_output=True,
        timeout=180,
        check=False,
        text=True,
    )
    if result.returncode != 0 or not destination.is_file() or not is_macho(destination):
        detail = (result.stderr or result.stdout or "compile falhou").strip()[-2_000:]
        raise RuntimeError(detail)
    destination.chmod(0o755)


def sign_app(app: Path) -> None:
    codesign = shutil.which("codesign")
    if not codesign:
        return
    subprocess.run(
        [codesign, "--force", "--sign", "-", "--deep", str(app)],
        capture_output=True,
        timeout=30,
        check=False,
    )


_NATIVE_BYTES: bytes | None = None
_NATIVE_STAMP = 0.0


def native_binary_bytes() -> bytes:
    global _NATIVE_BYTES, _NATIVE_STAMP
    stamp = SWIFT_SOURCE.stat().st_mtime if SWIFT_SOURCE.is_file() else 0.0
    if _NATIVE_BYTES is not None and _NATIVE_STAMP == stamp:
        return _NATIVE_BYTES
    handle = tempfile.NamedTemporaryFile(delete=False, prefix="jarvis-native-")
    handle.close()
    path = Path(handle.name)
    try:
        compile_native_binary(path)
        _NATIVE_BYTES = path.read_bytes()
        _NATIVE_STAMP = stamp
        return _NATIVE_BYTES
    finally:
        path.unlink(missing_ok=True)


def launch_agent_plist() -> bytes:
    return plistlib.dumps({
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": ["/usr/bin/open", "-a", "JARVIS"],
        "RunAtLoad": True,
    })


def bundle_info(version: str = "3.9", url: str = DEFAULT_URL) -> dict:
    author = creator_seal.creator_name()
    return {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": version,
        "CFBundleShortVersionString": version,
        "CFBundleExecutable": APP_NAME,
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": creator_seal.copyright_line(),
        "CFBundleGetInfoString": f"JARVIS · {author}",
        "NSMicrophoneUsageDescription": f"O JARVIS de {author} ouve o pedido para responder por voz.",
        "NSSpeechRecognitionUsageDescription": f"O JARVIS de {author} ouve “Jarvis” para executar o pedido.",
        "NSScreenCaptureUsageDescription": f"O JARVIS de {author} olha a tela quando você pede para analisar o que está vendo.",
        "JarvisCockpitURL": app_url(url),
        "LSUIElement": False,
        "NSQuitAlwaysKeepsWindows": False,
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True, "NSAllowsArbitraryLoads": False},
    }


def _zip_bytes(archive: zipfile.ZipFile, name: str, data: bytes, executable: bool = False) -> None:
    info = zipfile.ZipInfo(name)
    info.date_time = (2026, 8, 17, 12, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    mode = 0o100755 if executable else 0o100644
    info.external_attr = mode << 16
    archive.writestr(info, data)


def build_mac_pack(url: str = DEFAULT_URL) -> bytes:
    """ZIP instalável sem o repositório: .app + INSTALAR.command."""
    target = app_url(url)
    info = bundle_info(url=target)
    try:
        native = native_binary_bytes()
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        native = b"#!/bin/sh\necho 'Compile o JARVIS no Mac com INSTALAR.command.'\nexit 1\n"
    worker_install = """#!/bin/bash
set -euo pipefail
install_device_worker() {
  if command -v jarvis >/dev/null 2>&1; then
    jarvis computer-worker --install
    return 0
  fi
  if [ -x "$HOME/.local/bin/jarvis" ]; then
    "$HOME/.local/bin/jarvis" computer-worker --install
    return 0
  fi
  for ROOT in "${JARVIS_HOME:-}" "$HOME/Theo/JARVIS/VAMOO_JARVIS_LAB_v0_2_PRONTO"; do
    if [ -n "$ROOT" ] && [ -f "$ROOT/11_SCRIPTS/device_worker.py" ]; then
      /usr/bin/python3 "$ROOT/11_SCRIPTS/device_worker.py" --install
      return 0
    fi
  done
  echo "Worker do Mac NÃO instalado."
  echo "O App abre o cockpit, mas ações no Mac precisam do worker."
  echo "No repositório JARVIS rode: ./jarvis computer-worker --install"
  return 1
}
install_device_worker
"""
    installer = f"""#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${{HOME}}/Applications"
LAUNCH="${{HOME}}/Library/LaunchAgents"
mkdir -p "$DEST" "$LAUNCH"
rm -rf "$DEST/JARVIS.app"
xattr -dr com.apple.quarantine "$HERE/JARVIS.app" 2>/dev/null || true
cp -R "$HERE/JARVIS.app" "$DEST/JARVIS.app"
BIN="$DEST/JARVIS.app/Contents/MacOS/JARVIS"
SRC="$DEST/JARVIS.app/Contents/MacOS/jarvis_native_app.swift"
if command -v file >/dev/null 2>&1 && ! file "$BIN" | grep -q "Mach-O"; then
  swiftc -parse-as-library -O -framework AppKit -framework WebKit -framework AVFoundation -framework Speech -o "$BIN" "$SRC"
fi
chmod +x "$BIN"
xattr -dr com.apple.quarantine "$DEST/JARVIS.app" 2>/dev/null || true
if [ -f "$HERE/ai.theopadilha.jarvis.fala.plist" ]; then
  cp "$HERE/ai.theopadilha.jarvis.fala.plist" "$LAUNCH/{LAUNCH_AGENT_LABEL}.plist"
  launchctl bootout "gui/$(id -u)/{LAUNCH_AGENT_LABEL}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$LAUNCH/{LAUNCH_AGENT_LABEL}.plist" 2>/dev/null || \\
    launchctl load "$LAUNCH/{LAUNCH_AGENT_LABEL}.plist" 2>/dev/null || true
fi
if [ -x "$HERE/INSTALAR-WORKER.command" ]; then
  "$HERE/INSTALAR-WORKER.command" || true
fi
open "$DEST/JARVIS.app"
"""
    readme = (
        f"JARVIS no Mac\nCriado por {creator_seal.creator_name()}.\n\n"
        "1. Dê dois cliques em INSTALAR.command\n"
        "   Se o Mac recusar, botão direito > Abrir.\n"
        "2. O app nativo vai para ~/Applications (não é Chrome)\n"
        "3. INSTALAR.command também tenta ligar o worker do Mac\n"
        "   (jarvis computer-worker --install). Sem o repo, rode INSTALAR-WORKER.command.\n"
        "4. Toque no brilho uma vez e diga \"Jarvis\"\n"
        "5. No login do Mac o app sobe sozinho\n\n"
        "Visitante não controla o Mac do dono.\n"
        "Ações no Mac recusam se o worker nunca enviou heartbeat.\n"
    )
    if ICON_ICNS.is_file():
        info["CFBundleIconFile"] = "jarvis"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        _zip_bytes(archive, "JARVIS.app/Contents/MacOS/JARVIS", native, executable=True)
        _zip_bytes(archive, "JARVIS.app/Contents/MacOS/jarvis_native_app.swift", SWIFT_SOURCE.read_bytes())
        _zip_bytes(archive, "JARVIS.app/Contents/Info.plist", plistlib.dumps(info))
        _zip_bytes(archive, "INSTALAR.command", installer.encode("utf-8"), executable=True)
        _zip_bytes(archive, "INSTALAR-WORKER.command", worker_install.encode("utf-8"), executable=True)
        _zip_bytes(archive, "LER-ME.txt", readme.encode("utf-8"))
        _zip_bytes(archive, "NOTICE.txt", creator_seal.copyright_line().encode("utf-8"))
        _zip_bytes(archive, f"{LAUNCH_AGENT_LABEL}.plist", launch_agent_plist())
        icon = ICON_PNG if ICON_PNG.is_file() else LOGO
        if icon.is_file() and icon.stat().st_size < 500_000:
            archive.write(icon, "JARVIS.app/Contents/Resources/jarvis-mark.png")
        if ICON_ICNS.is_file():
            archive.write(ICON_ICNS, "JARVIS.app/Contents/Resources/jarvis.icns")
        archive.comment = f"lock:{creator_seal.fingerprint()}".encode("ascii")
    return buffer.getvalue()


_PACK_CACHE: dict[tuple, bytes] = {}


def mac_pack_bytes(url: str = DEFAULT_URL) -> bytes:
    stamp = ICON_PNG.stat().st_mtime if ICON_PNG.is_file() else 0
    icns = ICON_ICNS.stat().st_mtime if ICON_ICNS.is_file() else 0
    key = (app_url(url), stamp, icns)
    packed = _PACK_CACHE.get(key)
    if packed is None:
        packed = build_mac_pack(url)
        _PACK_CACHE[key] = packed
    return packed


def install(url: str, system_wide: bool) -> Path:
    app = install_root(system_wide) / f"{APP_NAME}.app"
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    if app.exists():
        shutil.rmtree(app)
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    binary = macos / APP_NAME
    binary.write_bytes(native_binary_bytes())
    binary.chmod(0o755)

    info = bundle_info(url=url)
    if ICON_ICNS.is_file():
        shutil.copy2(ICON_ICNS, resources / "jarvis.icns")
        info["CFBundleIconFile"] = "jarvis"
    elif build_icon(resources / "jarvis.icns"):
        info["CFBundleIconFile"] = "jarvis"
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
    (resources / "NOTICE.txt").write_text(creator_seal.copyright_line() + "\n", encoding="utf-8")

    # Sem isso o Finder pode continuar mostrando o ícone genérico.
    subprocess.run(["touch", str(app)], capture_output=True, timeout=10, check=False)
    sign_app(app)
    return app


def install_login_agent() -> None:
    """Abre o canto uma vez no login. Sem loop — open -a de novo empilha janela."""
    launch = Path.home() / "Library" / "LaunchAgents"
    launch.mkdir(parents=True, exist_ok=True)
    path = launch / f"{LAUNCH_AGENT_LABEL}.plist"
    path.write_bytes(launch_agent_plist())
    domain = f"gui/{os.getuid()}"
    label = f"{domain}/{LAUNCH_AGENT_LABEL}"
    subprocess.run(["launchctl", "bootout", label], capture_output=True, timeout=15, check=False)
    subprocess.run(["launchctl", "bootstrap", domain, str(path)], capture_output=True, timeout=15, check=False)


def remove(system_wide: bool) -> bool:
    app = install_root(system_wide) / f"{APP_NAME}.app"
    if not app.exists():
        return False
    shutil.rmtree(app)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Instala o JARVIS como aplicativo do Mac")
    parser.add_argument("--url", default=DEFAULT_URL, help="endereço do cockpit")
    parser.add_argument("--system", action="store_true", help="instala em /Applications (pede permissão)")
    parser.add_argument("--check", action="store_true", help="mostra o que seria feito e sai")
    parser.add_argument("--remove", action="store_true", help="desinstala")
    args = parser.parse_args()

    if sys.platform != "darwin":
        print("FALHA: este instalador é do macOS.")
        return 1

    target = install_root(args.system) / f"{APP_NAME}.app"
    if args.check:
        print(f"Instalaria em {target}")
        print(f"Apontando para {args.url}")
        print(f"Ícone a partir de {LOGO} ({'encontrado' if LOGO.is_file() else 'AUSENTE'})")
        print(f"Binário nativo (swiftc): {'sim' if shutil.which('swiftc') else 'NÃO'}")
        print("Janela: WKWebView JARVIS, não Chrome.")
        return 0

    if args.remove:
        print(f"Removido: {target}" if remove(args.system) else f"Nada para remover em {target}")
        return 0

    app = install(args.url, args.system)
    install_login_agent()
    print(f"JARVIS instalado em {app}")
    print("Está no Launchpad, no Spotlight e no canto no login.")
    print("Arraste o ícone para o Dock para deixá-lo fixo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
