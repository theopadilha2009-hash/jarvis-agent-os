import unittest
import zipfile
from io import BytesIO
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import windows_pack

class WindowsPackTest(unittest.TestCase):
    def test_windows_pack_contains_installer_and_exe(self):
        data = windows_pack.windows_pack_bytes()
        self.assertTrue(data.startswith(b"PK"))
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
            self.assertIn("INSTALAR.cmd", names)
            self.assertIn("JARVIS.cmd", names)
            self.assertIn("LER-ME.txt", names)
            if (ROOT / "11_SCRIPTS" / "jarvis_ui_assets" / "JARVIS.exe").is_file():
                self.assertIn("JARVIS.exe", names)

    def test_installer_script_launches_exe_if_present(self):
        script = windows_pack.installer()
        self.assertIn("JARVIS.exe", script)
        self.assertIn("%LOCALAPPDATA%\\JARVIS", script)

if __name__ == "__main__":
    unittest.main()
