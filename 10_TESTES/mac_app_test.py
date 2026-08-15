#!/usr/bin/env python3
"""O ícone do JARVIS na tela do Mac: bundle real, não atalho de navegador."""

from pathlib import Path
from unittest.mock import patch
import importlib.util
import plistlib
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_install_mac_app",
    ROOT / "11_SCRIPTS" / "install_mac_app.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MacAppTest(unittest.TestCase):
    def test_bundle_has_launcher_plist_and_survives_reinstall(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            with patch.object(MODULE, "install_root", lambda system_wide: home / "Applications"), \
                    patch.object(MODULE, "build_icon", lambda destination: False):
                app = MODULE.install("https://cockpit.exemplo/", system_wide=False)
                self.assertTrue(app.is_dir())

                binary = app / "Contents" / "MacOS" / "JARVIS"
                self.assertTrue(binary.is_file())
                # Executável de verdade: sem o bit +x o Finder recusa o bundle.
                self.assertTrue(binary.stat().st_mode & 0o111)
                launcher = binary.read_text(encoding="utf-8")
                self.assertIn("https://cockpit.exemplo/", launcher)
                self.assertIn("--app=", launcher)          # janela própria
                self.assertIn("/usr/bin/open", launcher)   # rede de segurança

                info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
                self.assertEqual(info["CFBundleIdentifier"], MODULE.BUNDLE_ID)
                self.assertEqual(info["CFBundleExecutable"], "JARVIS")
                self.assertTrue(info["NSHighResolutionCapable"])
                # Sem ícone gerado, o plist não promete um arquivo que não existe.
                self.assertNotIn("CFBundleIconFile", info)

                # Reinstalar por cima não deixa restos da versão anterior.
                (app / "Contents" / "sujeira.txt").write_text("resto")
                app = MODULE.install("https://cockpit.exemplo/", system_wide=False)
                self.assertFalse((app / "Contents" / "sujeira.txt").exists())

                self.assertTrue(MODULE.remove(system_wide=False))
                self.assertFalse(app.exists())
                self.assertFalse(MODULE.remove(system_wide=False))

    def test_icon_declared_only_when_it_was_really_generated(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            with patch.object(MODULE, "install_root", lambda system_wide: home / "Applications"), \
                    patch.object(MODULE, "build_icon", lambda destination: True):
                app = MODULE.install("https://cockpit.exemplo/", system_wide=False)
            info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
            self.assertEqual(info["CFBundleIconFile"], "jarvis")


if __name__ == "__main__":
    unittest.main(verbosity=2)
