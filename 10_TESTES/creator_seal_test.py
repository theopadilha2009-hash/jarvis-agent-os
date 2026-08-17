#!/usr/bin/env python3
"""O nome do criador reconstrói do ciphertext; adulterar o selo não passa no HMAC."""

from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_creator_seal",
    ROOT / "11_SCRIPTS" / "jarvis_creator_seal.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CreatorSealTest(unittest.TestCase):
    def test_unlocks_full_and_short_name(self):
        self.assertEqual(MODULE.creator_name(), "Theo Lorentz Padilha")
        self.assertEqual(MODULE.creator_short_name(), "Theo Padilha")
        self.assertTrue(MODULE.verify())
        self.assertIn("Theo Lorentz Padilha", MODULE.copyright_line())
        self.assertEqual(len(MODULE.fingerprint()), 16)
        self.assertNotIn("Theo Lorentz Padilha", MODULE.CIPHER_B64)

    def test_tampered_cipher_falls_back_to_mark(self):
        original = MODULE.CIPHER_B64
        try:
            MODULE.CIPHER_B64 = "AAAA"
            self.assertEqual(MODULE.creator_name(), "Theo Lorentz Padilha")
        finally:
            MODULE.CIPHER_B64 = original

    def test_invalid_base64_does_not_crash_the_runtime(self):
        original = MODULE.CIPHER_B64
        try:
            MODULE.CIPHER_B64 = "!!!"
            self.assertEqual(MODULE.creator_name(), "Theo Lorentz Padilha")
        finally:
            MODULE.CIPHER_B64 = original

    def test_js_seal_matches_python_cipher(self):
        js = (ROOT / "web" / "creator-seal.js").read_text(encoding="utf-8")
        self.assertIn(MODULE.CIPHER_B64, js)
        self.assertIn(MODULE.MARK_B64, js)
        self.assertIn(MODULE.seal_key().hex(), js)
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("creator-seal.js", html)
        self.assertIn("data-creator-lock", (ROOT / "web" / "fala.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
