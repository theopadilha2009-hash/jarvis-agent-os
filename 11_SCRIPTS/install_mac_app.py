#!/usr/bin/env python3
"""JARVIS como aplicativo do Mac: ícone no Launchpad, no Dock e no Spotlight.

Monta um bundle .app de verdade a partir do logo do cockpit. Abrir o ícone
sobe o cockpit numa janela própria — sem abas, sem barra de endereço — pelo
modo aplicativo do Chrome, com o navegador padrão como rede de segurança.

    python3 11_SCRIPTS/install_mac_app.py            # instala em ~/Applications
    python3 11_SCRIPTS/install_mac_app.py --check    # só diz o que faria
    python3 11_SCRIPTS/install_mac_app.py --remove   # desinstala
"""

from __future__ import annotations

import argparse
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "web" / "jarvis-logo.png"
APP_NAME = "JARVIS"
BUNDLE_ID = "ai.theopadilha.jarvis.cockpit"
DEFAULT_URL = "https://jarvis-agent-os-delta.vercel.app"
# Fundo do cockpit: o ícone fica quadrado sem esticar o logo.
ICON_BACKGROUND = "130824"
ICON_SIZES = (16, 32, 64, 128, 256, 512, 1024)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


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


def launcher_script(url: str) -> str:
    return f"""#!/bin/sh
# Abre o cockpit numa janela própria; sem o Chrome, cai no navegador padrão.
URL="${{JARVIS_COCKPIT_URL:-{url}}}"
CHROME="{CHROME}"
if [ -x "$CHROME" ]; then
  exec "$CHROME" --app="$URL" --new-window
fi
exec /usr/bin/open "$URL"
"""


def install(url: str, system_wide: bool) -> Path:
    app = install_root(system_wide) / f"{APP_NAME}.app"
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    if app.exists():
        shutil.rmtree(app)
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    binary = macos / APP_NAME
    binary.write_text(launcher_script(url), encoding="utf-8")
    binary.chmod(0o755)

    info = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": "1.0",
        "CFBundleShortVersionString": "1.0",
        "CFBundleExecutable": APP_NAME,
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    }
    if build_icon(resources / "jarvis.icns"):
        info["CFBundleIconFile"] = "jarvis"
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))

    # Sem isso o Finder pode continuar mostrando o ícone genérico.
    subprocess.run(["touch", str(app)], capture_output=True, timeout=10, check=False)
    return app


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
        print(f"Janela própria pelo Chrome: {'sim' if Path(CHROME).exists() else 'não, usaria o navegador padrão'}")
        return 0

    if args.remove:
        print(f"Removido: {target}" if remove(args.system) else f"Nada para remover em {target}")
        return 0

    app = install(args.url, args.system)
    print(f"JARVIS instalado em {app}")
    print("Está no Launchpad e no Spotlight. Arraste o ícone para o Dock para deixá-lo fixo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
