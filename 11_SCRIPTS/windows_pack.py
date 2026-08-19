#!/usr/bin/env python3
"""Pack instalável: JARVIS no Windows (cockpit em janela + jarvis-theo)."""

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

DEFAULT_ORIGIN = "https://jarvis-theo.vercel.app"
PACK_NAME = "JARVIS.windows.zip"


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


def launcher_cmd(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        "@echo off\n"
        "setlocal\n"
        f"set URL={cockpit}\n"
        "if defined JARVIS_URL set URL=%JARVIS_URL%\n"
        "where msedge >nul 2>&1 && (\n"
        "  start \"\" msedge --app=\"%URL%\"\n"
        "  exit /b 0\n"
        ")\n"
        "where chrome >nul 2>&1 && (\n"
        "  start \"\" chrome --app=\"%URL%\"\n"
        "  exit /b 0\n"
        ")\n"
        "start \"\" \"%URL%\"\n"
    )


def launcher_theo(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        "@echo off\n"
        "if defined JARVIS_HOME if exist \"%JARVIS_HOME%\\jarvis-theo.cmd\" (\n"
        "  \"%JARVIS_HOME%\\jarvis-theo.cmd\" %*\n"
        "  exit /b %ERRORLEVEL%\n"
        ")\n"
        f"start \"\" \"{cockpit}\"\n"
    )


def installer() -> str:
    return (
        "@echo off\n"
        "setlocal\n"
        "set ROOT=%~dp0\n"
        "set DEST=%LOCALAPPDATA%\\JARVIS\n"
        "if not exist \"%DEST%\" mkdir \"%DEST%\"\n"
        "copy /Y \"%ROOT%JARVIS.cmd\" \"%DEST%\\JARVIS.cmd\" >nul\n"
        "copy /Y \"%ROOT%jarvis-theo.cmd\" \"%DEST%\\jarvis-theo.cmd\" >nul\n"
        "copy /Y \"%ROOT%LER-ME.txt\" \"%DEST%\\LER-ME.txt\" >nul\n"
        "powershell -NoProfile -Command \"$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\JARVIS.lnk'); $s.TargetPath='%DEST%\\JARVIS.cmd'; $s.WorkingDirectory='%DEST%'; $s.Save()\"\n"
        "echo Status real: JARVIS copiado para %DEST% e atalho na Area de Trabalho.\n"
        "echo Clique duas vezes em JARVIS.cmd. Producao: nada alterado neste instalador alem da pasta local.\n"
        "start \"\" \"%DEST%\\JARVIS.cmd\"\n"
        "pause\n"
    )


def readme(url: str) -> str:
    cockpit = cockpit_url(url)
    return (
        "JARVIS no Windows\n"
        "=================\n\n"
        f"Cockpit: {cockpit}\n"
        f"{creator_seal.copyright_line()}\n\n"
        "1. Descompacte o ZIP.\n"
        "2. Clique duas vezes em INSTALAR.cmd.\n"
        "3. O JARVIS vai para %%LOCALAPPDATA%%\\JARVIS e ganha atalho na Área de Trabalho.\n"
        "4. JARVIS.cmd abre o cockpit em janela (Edge ou Chrome).\n"
        "5. jarvis-theo.cmd no terminal abre o mesmo cockpit "
        "(ou o cérebro local se JARVIS_HOME apontar para o repositório).\n\n"
        "Visitante não controla o Mac do dono.\n"
    )


def build_windows_pack(url: str = DEFAULT_ORIGIN) -> bytes:
    target = cockpit_url(url)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        _zip_bytes(archive, "JARVIS.cmd", launcher_cmd(target).encode("utf-8"))
        _zip_bytes(archive, "jarvis-theo.cmd", launcher_theo(target).encode("utf-8"))
        _zip_bytes(archive, "INSTALAR.cmd", installer().encode("utf-8"))
        _zip_bytes(archive, "LER-ME.txt", readme(target).encode("utf-8"))
        _zip_bytes(archive, "NOTICE.txt", (creator_seal.copyright_line() + "\n").encode("utf-8"))
        archive.comment = f"lock:{creator_seal.fingerprint()}".encode("ascii")
    return buffer.getvalue()


_PACK_CACHE: dict[str, bytes] = {}


def windows_pack_bytes(url: str = DEFAULT_ORIGIN) -> bytes:
    key = cockpit_url(url)
    packed = _PACK_CACHE.get(key)
    if packed is None:
        packed = build_windows_pack(key)
        _PACK_CACHE[key] = packed
    return packed
