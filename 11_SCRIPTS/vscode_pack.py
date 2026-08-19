#!/usr/bin/env python3
"""Pack instalável: JARVIS Theo no VS Code (Mac e Windows).

Gera um ZIP com extensão sideload, VSIX, instaladores e o launcher
jarvis-theo. Não inclui o cérebro Python nem segredos — o terminal abre o
cockpit web se o repositório local não estiver ao lado.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
import sys
import zipfile

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import jarvis_creator_seal as creator_seal  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORIGIN = "https://jarvis-theo.vercel.app"
PACK_NAME = "JARVIS-theo-vscode.zip"
PACK_NAME_MAC = "JARVIS-theo-macos.zip"
PACK_NAME_WIN = "JARVIS-theo-windows.zip"
EXTENSION_NAME = "jarvis-theo"
PUBLISHER = "theopadilha"
VERSION = "0.1.0"
EXTENSION_FOLDER = f"{PUBLISHER}.{EXTENSION_NAME}-{VERSION}"
VSIX_NAME = f"{EXTENSION_NAME}-{VERSION}.vsix"


def cockpit_url(url: str = DEFAULT_ORIGIN) -> str:
    raw = (url or DEFAULT_ORIGIN).strip() or DEFAULT_ORIGIN
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc or 'jarvis-theo.vercel.app'}"
    return f"{origin}/cockpit"


def _zip_bytes(archive: zipfile.ZipFile, name: str, data: bytes, executable: bool = False) -> None:
    info = zipfile.ZipInfo(name)
    info.date_time = (2026, 8, 19, 12, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    mode = 0o100755 if executable else 0o100644
    info.external_attr = mode << 16
    archive.writestr(info, data)


def extension_package_json() -> str:
    return (
        "{\n"
        f'  "name": "{EXTENSION_NAME}",\n'
        '  "displayName": "JARVIS Theo",\n'
        '  "description": "Cola código do JARVIS no VS Code e abre o jarvis-theo. Mac e Windows.",\n'
        f'  "version": "{VERSION}",\n'
        f'  "publisher": "{PUBLISHER}",\n'
        '  "engines": { "vscode": "^1.85.0" },\n'
        '  "categories": ["Other"],\n'
        '  "activationEvents": ["onUri"],\n'
        '  "main": "./extension.js",\n'
        '  "contributes": {\n'
        '    "commands": [\n'
        '      { "command": "jarvisTheo.fromClipboard", "title": "JARVIS: Colar da área de transferência" },\n'
        '      { "command": "jarvisTheo.openCockpit", "title": "JARVIS: Abrir cockpit" },\n'
        '      { "command": "jarvisTheo.openTheo", "title": "JARVIS: Terminal jarvis-theo" }\n'
        "    ],\n"
        '    "keybindings": [\n'
        '      { "command": "jarvisTheo.fromClipboard", "key": "ctrl+alt+v", "mac": "cmd+alt+v" }\n'
        "    ]\n"
        "  }\n"
        "}\n"
    )


def extension_js(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        '"use strict";\n'
        "const vscode = require(\"vscode\");\n"
        f"const COCKPIT = {cockpit!r};\n"
        "async function fromClipboard() {\n"
        "  const text = await vscode.env.clipboard.readText();\n"
        "  const doc = await vscode.workspace.openTextDocument({ content: text || \"\" });\n"
        "  await vscode.window.showTextDocument(doc);\n"
        "}\n"
        "function openTheo() {\n"
        "  const term = vscode.window.createTerminal({ name: \"jarvis-theo\" });\n"
        "  term.show();\n"
        "  term.sendText(\"jarvis-theo\");\n"
        "}\n"
        "function activate(context) {\n"
        "  context.subscriptions.push(\n"
        "    vscode.commands.registerCommand(\"jarvisTheo.fromClipboard\", fromClipboard),\n"
        "    vscode.commands.registerCommand(\"jarvisTheo.openCockpit\", () => vscode.env.openExternal(vscode.Uri.parse(COCKPIT))),\n"
        "    vscode.commands.registerCommand(\"jarvisTheo.openTheo\", openTheo),\n"
        "    vscode.window.registerUriHandler({\n"
        "      handleUri(uri) {\n"
        "        const path = String(uri.path || \"\");\n"
        "        if (path.indexOf(\"cockpit\") >= 0) vscode.env.openExternal(vscode.Uri.parse(COCKPIT));\n"
        "        else fromClipboard();\n"
        "      },\n"
        "    })\n"
        "  );\n"
        "}\n"
        "function deactivate() {}\n"
        "module.exports = { activate, deactivate };\n"
    )


def vsix_manifest() -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">\n'
        "  <Metadata>\n"
        f'    <Identity Language="en-US" Id="{EXTENSION_NAME}" Version="{VERSION}" Publisher="{PUBLISHER}" />\n'
        "    <DisplayName>JARVIS Theo</DisplayName>\n"
        "    <Description xml:space=\"preserve\">Cola código do JARVIS no VS Code e abre o jarvis-theo. Mac e Windows.</Description>\n"
        "    <Tags>jarvis,theo,vscode</Tags>\n"
        "  </Metadata>\n"
        "  <Installation>\n"
        '    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>\n'
        "  </Installation>\n"
        "  <Dependencies/>\n"
        "  <Assets>\n"
        '    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />\n'
        "  </Assets>\n"
        "</PackageManifest>\n"
    )


def vsix_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Types xmlns="http://schemas.microsoft.com/package/2006/content-types">\n'
        '  <Default Extension=".json" ContentType="application/json"/>\n'
        '  <Default Extension=".js" ContentType="application/javascript"/>\n'
        '  <Default Extension=".md" ContentType="text/markdown"/>\n'
        '  <Default Extension=".vsixmanifest" ContentType="text/xml"/>\n'
        "</Types>\n"
    )


def readme(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        "JARVIS Theo para VS Code\n"
        "========================\n\n"
        f"Cockpit: {cockpit}\n"
        f"{creator_seal.copyright_line()}\n\n"
        "O que este ZIP faz\n"
        "- Instala a extensão JARVIS Theo no VS Code (Mac e Windows).\n"
        "- Cola o código da área de transferência num arquivo novo.\n"
        "- Abre o cockpit e o comando jarvis-theo no terminal.\n"
        "- NÃO injeta código sozinho no seu projeto: o navegador copia; o VS Code cola.\n\n"
        "Mac\n"
        "1. Descompacte o ZIP.\n"
        "2. Dê dois cliques em INSTALAR-MAC.command (se o macOS bloquear: clique com o botão direito → Abrir).\n"
        "3. Reabra o Visual Studio Code.\n"
        "4. No JARVIS web: Code → Colar no VS Code. Ou no VS Code: ⌘⌥V.\n\n"
        "Windows\n"
        "1. Descompacte o ZIP.\n"
        "2. Clique com o botão direito em INSTALAR-WINDOWS.cmd → Executar como administrador se o Windows pedir.\n"
        "   Alternativa: clique direito em INSTALAR-WINDOWS.ps1 → Executar com PowerShell.\n"
        "3. Reabra o Visual Studio Code.\n"
        "4. No JARVIS web: Code → Colar no VS Code. Ou no VS Code: Ctrl+Alt+V.\n\n"
        "Se `code` não existir no PATH\n"
        "- VS Code → Command Palette → Shell Command: Install 'code' command in PATH (Mac).\n"
        "- Windows: a instalação padrão já coloca `code` no PATH; senão use Copiar pasta extension para:\n"
        f"  %USERPROFILE%\\.vscode\\extensions\\{EXTENSION_FOLDER}\\\n\n"
        "jarvis-theo no terminal\n"
        "- O launcher deste pack abre o cockpit no navegador.\n"
        "- Se você tiver o repositório JARVIS clonado, use o `jarvis-theo` da raiz do repo\n"
        "  (cérebro OpenRouter local). Este ZIP não leva o cérebro Python.\n\n"
        "URI da extensão\n"
        f"  vscode://{PUBLISHER}.{EXTENSION_NAME}/from-clipboard\n"
    )


def install_mac(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        "#!/bin/bash\n"
        "set -e\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        f"EXT_DIR=\"$HOME/.vscode/extensions/{EXTENSION_FOLDER}\"\n"
        "mkdir -p \"$EXT_DIR\" \"$HOME/.local/bin\"\n"
        "cp -R \"$ROOT/extension/.\" \"$EXT_DIR/\"\n"
        "cp \"$ROOT/bin/jarvis-theo\" \"$HOME/.local/bin/jarvis-theo\"\n"
        "chmod +x \"$HOME/.local/bin/jarvis-theo\" \"$ROOT/INSTALAR-MAC.command\"\n"
        "if command -v code >/dev/null 2>&1; then\n"
        f"  code --install-extension \"$ROOT/{VSIX_NAME}\" || true\n"
        "fi\n"
        "echo \"Status real: extensão JARVIS Theo copiada para $EXT_DIR\"\n"
        f"echo \"Cockpit: {cockpit}\"\n"
        "echo \"Reabra o VS Code. Produção: nada alterado neste instalador além da pasta local.\"\n"
        "open \"$ROOT\" >/dev/null 2>&1 || true\n"
    )


def install_windows_cmd() -> str:
    return (
        "@echo off\n"
        "setlocal\n"
        "set ROOT=%~dp0\n"
        f"set EXT=%USERPROFILE%\\.vscode\\extensions\\{EXTENSION_FOLDER}\n"
        "if not exist \"%EXT%\" mkdir \"%EXT%\"\n"
        "xcopy /E /I /Y \"%ROOT%extension\\*\" \"%EXT%\\\" >nul\n"
        "if not exist \"%USERPROFILE%\\.local\\bin\" mkdir \"%USERPROFILE%\\.local\\bin\"\n"
        "copy /Y \"%ROOT%bin\\jarvis-theo.cmd\" \"%USERPROFILE%\\.local\\bin\\jarvis-theo.cmd\" >nul\n"
        "where code >nul 2>&1 && code --install-extension \"%ROOT%" + VSIX_NAME + "\"\n"
        "echo Status real: extensao JARVIS Theo copiada para %EXT%\n"
        "echo Reabra o VS Code. Producao: nada alterado neste instalador alem da pasta local.\n"
        "pause\n"
    )


def install_windows_ps1() -> str:
    return (
        "$ErrorActionPreference = \"Stop\"\n"
        "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        f"$Ext = Join-Path $env:USERPROFILE \".vscode\\extensions\\{EXTENSION_FOLDER}\"\n"
        "New-Item -ItemType Directory -Force -Path $Ext | Out-Null\n"
        "Copy-Item -Recurse -Force (Join-Path $Root \"extension\\*\") $Ext\n"
        "$Bin = Join-Path $env:USERPROFILE \".local\\bin\"\n"
        "New-Item -ItemType Directory -Force -Path $Bin | Out-Null\n"
        "Copy-Item -Force (Join-Path $Root \"bin\\jarvis-theo.cmd\") (Join-Path $Bin \"jarvis-theo.cmd\")\n"
        f"$Vsix = Join-Path $Root \"{VSIX_NAME}\"\n"
        "if (Get-Command code -ErrorAction SilentlyContinue) {\n"
        "  & code --install-extension $Vsix\n"
        "}\n"
        "Write-Host \"Status real: extensao JARVIS Theo copiada para $Ext\"\n"
        "Write-Host \"Reabra o VS Code. Producao: nada alterado neste instalador alem da pasta local.\"\n"
    )


def bin_unix(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        "#!/usr/bin/env bash\n"
        "set -e\n"
        f"URL=\"${{JARVIS_URL:-{cockpit}}}\"\n"
        "if [ -n \"${JARVIS_HOME:-}\" ] && [ -x \"$JARVIS_HOME/jarvis-theo\" ]; then\n"
        "  exec \"$JARVIS_HOME/jarvis-theo\" \"$@\"\n"
        "fi\n"
        "HERE=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "if [ -x \"$HERE/../../jarvis-theo\" ]; then\n"
        "  exec \"$HERE/../../jarvis-theo\" \"$@\"\n"
        "fi\n"
        "if command -v open >/dev/null 2>&1; then open \"$URL\"\n"
        "elif command -v xdg-open >/dev/null 2>&1; then xdg-open \"$URL\"\n"
        "else echo \"Abra: $URL\"\n"
        "fi\n"
    )


def bin_cmd(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        "@echo off\n"
        "if defined JARVIS_HOME if exist \"%JARVIS_HOME%\\jarvis-theo.cmd\" (\n"
        "  \"%JARVIS_HOME%\\jarvis-theo.cmd\" %*\n"
        "  exit /b %ERRORLEVEL%\n"
        ")\n"
        f"start \"\" \"{cockpit}\"\n"
    )


def bin_ps1(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        "if ($env:JARVIS_HOME -and (Test-Path (Join-Path $env:JARVIS_HOME \"jarvis-theo.ps1\"))) {\n"
        "  & (Join-Path $env:JARVIS_HOME \"jarvis-theo.ps1\") @args\n"
        "  exit $LASTEXITCODE\n"
        "}\n"
        f"Start-Process {cockpit!r}\n"
    )


def tasks_json() -> str:
    return (
        "{\n"
        '  "version": "2.0.0",\n'
        '  "tasks": [\n'
        "    {\n"
        '      "label": "JARVIS Theo",\n'
        '      "type": "shell",\n'
        '      "command": "jarvis-theo",\n'
        '      "windows": { "command": "jarvis-theo.cmd" },\n'
        '      "problemMatcher": [],\n'
        '      "presentation": { "reveal": "always", "panel": "new" }\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )


def build_vsix(url: str) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        _zip_bytes(archive, "extension.vsixmanifest", vsix_manifest().encode("utf-8"))
        _zip_bytes(archive, "[Content_Types].xml", vsix_content_types().encode("utf-8"))
        _zip_bytes(archive, "extension/package.json", extension_package_json().encode("utf-8"))
        _zip_bytes(archive, "extension/extension.js", extension_js(url).encode("utf-8"))
        _zip_bytes(archive, "extension/README.md", readme(url).encode("utf-8"))
    return buffer.getvalue()


def pack_filename(platform: str = "all") -> str:
    if platform == "mac":
        return PACK_NAME_MAC
    if platform == "windows":
        return PACK_NAME_WIN
    return PACK_NAME


def build_vscode_pack(url: str = DEFAULT_ORIGIN, platform: str = "all") -> bytes:
    target = cockpit_url(url)
    vsix = build_vsix(target)
    want_mac = platform in {"all", "mac"}
    want_win = platform in {"all", "windows"}
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        _zip_bytes(archive, "extension/package.json", extension_package_json().encode("utf-8"))
        _zip_bytes(archive, "extension/extension.js", extension_js(target).encode("utf-8"))
        _zip_bytes(archive, "extension/README.md", readme(target).encode("utf-8"))
        _zip_bytes(archive, VSIX_NAME, vsix)
        if want_mac:
            _zip_bytes(archive, "INSTALAR-MAC.command", install_mac(target).encode("utf-8"), executable=True)
            _zip_bytes(archive, "bin/jarvis-theo", bin_unix(target).encode("utf-8"), executable=True)
        if want_win:
            _zip_bytes(archive, "INSTALAR-WINDOWS.cmd", install_windows_cmd().encode("utf-8"))
            _zip_bytes(archive, "INSTALAR-WINDOWS.ps1", install_windows_ps1().encode("utf-8"))
            _zip_bytes(archive, "bin/jarvis-theo.cmd", bin_cmd(target).encode("utf-8"))
            _zip_bytes(archive, "bin/jarvis-theo.ps1", bin_ps1(target).encode("utf-8"))
        _zip_bytes(archive, ".vscode/tasks.json", tasks_json().encode("utf-8"))
        _zip_bytes(archive, "LER-ME.txt", readme(target).encode("utf-8"))
        _zip_bytes(archive, "NOTICE.txt", (creator_seal.copyright_line() + "\n").encode("utf-8"))
        archive.comment = f"lock:{creator_seal.fingerprint()}".encode("ascii")
    return buffer.getvalue()


_PACK_CACHE: dict[tuple[str, str], bytes] = {}


def vscode_pack_bytes(url: str = DEFAULT_ORIGIN, platform: str = "all") -> bytes:
    key = (cockpit_url(url), platform)
    packed = _PACK_CACHE.get(key)
    if packed is None:
        packed = build_vscode_pack(key[0], platform)
        _PACK_CACHE[key] = packed
    return packed
