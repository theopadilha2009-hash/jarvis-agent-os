#!/usr/bin/env python3
"""Pack JARVIS Theo para VS Code: Mac, Windows, extensão e VSIX."""

from io import BytesIO
from pathlib import Path
import importlib.util
import zipfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_vscode_pack",
    ROOT / "11_SCRIPTS" / "vscode_pack.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VSCodePackTest(unittest.TestCase):
    def test_pack_has_mac_windows_extension_and_launcher(self):
        packed = MODULE.build_vscode_pack("https://jarvis-theo.vercel.app")
        self.assertGreater(len(packed), 400)
        with zipfile.ZipFile(BytesIO(packed)) as archive:
            names = set(archive.namelist())
            self.assertIn("INSTALAR-MAC.command", names)
            self.assertIn("INSTALAR-WINDOWS.cmd", names)
            self.assertIn("INSTALAR-WINDOWS.ps1", names)
            self.assertIn("bin/jarvis-theo", names)
            self.assertIn("bin/jarvis-theo.cmd", names)
            self.assertIn("extension/package.json", names)
            self.assertIn("extension/extension.js", names)
            self.assertIn(MODULE.VSIX_NAME, names)
            self.assertIn("LER-ME.txt", names)
            readme = archive.read("LER-ME.txt").decode("utf-8")
            self.assertIn("Mac", readme)
            self.assertIn("Windows", readme)
            self.assertIn("/cockpit", readme)
            extension = archive.read("extension/extension.js").decode("utf-8")
            self.assertIn("jarvisTheo.fromClipboard", extension)
            self.assertIn("https://jarvis-theo.vercel.app/cockpit", extension)
            vsix = archive.read(MODULE.VSIX_NAME)
            with zipfile.ZipFile(BytesIO(vsix)) as inner:
                inner_names = set(inner.namelist())
                self.assertIn("extension.vsixmanifest", inner_names)
                self.assertIn("extension/package.json", inner_names)
                self.assertIn("theopadilha", inner.read("extension.vsixmanifest").decode("utf-8"))

    def test_os_specific_packs_drop_the_other_installer(self):
        mac = MODULE.build_vscode_pack(MODULE.DEFAULT_ORIGIN, "mac")
        win = MODULE.build_vscode_pack(MODULE.DEFAULT_ORIGIN, "windows")
        with zipfile.ZipFile(BytesIO(mac)) as archive:
            names = set(archive.namelist())
            self.assertIn("INSTALAR-MAC.command", names)
            self.assertNotIn("INSTALAR-WINDOWS.cmd", names)
        with zipfile.ZipFile(BytesIO(win)) as archive:
            names = set(archive.namelist())
            self.assertIn("INSTALAR-WINDOWS.cmd", names)
            self.assertNotIn("INSTALAR-MAC.command", names)

    def test_cockpit_url_stays_on_public_origin(self):
        self.assertEqual(
            MODULE.cockpit_url("https://jarvis-theo.vercel.app/fala"),
            "https://jarvis-theo.vercel.app/cockpit",
        )


class WindowsPackTest(unittest.TestCase):
    def test_windows_app_pack_has_installer_and_launcher(self):
        spec = importlib.util.spec_from_file_location(
            "jarvis_windows_pack",
            ROOT / "11_SCRIPTS" / "windows_pack.py",
        )
        windows = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(windows)
        packed = windows.build_windows_pack("https://jarvis-theo.vercel.app")
        with zipfile.ZipFile(BytesIO(packed)) as archive:
            names = set(archive.namelist())
            self.assertIn("JARVIS.cmd", names)
            self.assertIn("INSTALAR.cmd", names)
            self.assertIn("jarvis-theo.cmd", names)
            self.assertIn("--app=", archive.read("JARVIS.cmd").decode("utf-8"))
