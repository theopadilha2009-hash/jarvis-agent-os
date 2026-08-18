#!/usr/bin/env python3
"""Contrato do overlay /fala: sem gastar voz no boot, sem atalho frouxo, com token."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
FALA_JS = (ROOT / "web" / "fala.js").read_text(encoding="utf-8")
FALA_HTML = (ROOT / "web" / "fala.html").read_text(encoding="utf-8")


class FalaOverlayTest(unittest.TestCase):
    def test_boot_does_not_auto_call_speech(self):
        self.assertNotRegex(FALA_JS, r"setTimeout\(\s*\(\)\s*=>\s*speak\(")
        self.assertIn("user-gesture", FALA_JS)

    def test_sends_owner_token_when_present(self):
        self.assertIn("jarvis-owner-token-v1", FALA_JS)
        self.assertIn("X-Jarvis-Owner-Token", FALA_JS)

    def test_microphone_start_is_guarded(self):
        self.assertIn("rec.start()", FALA_JS)
        self.assertRegex(FALA_JS, r"try\s*\{[^}]*rec\.start\(\)", re.S)

    def test_does_not_open_gmail_on_any_email_mention(self):
        self.assertNotIn(r"\bgmail\b|\be-?mail\b", FALA_JS)
        self.assertIn("gmail", FALA_JS)

    def test_revokes_audio_after_playback_not_on_start(self):
        self.assertIn("ended", FALA_JS)
        self.assertNotRegex(FALA_JS, r"await audio\.play\(\);\s*URL\.revokeObjectURL")

    def test_overlay_page_is_self_contained(self):
        self.assertIn('id="orb"', FALA_HTML)
        self.assertIn("/download/mac", FALA_HTML)
        self.assertIn("creator-seal.js", FALA_HTML)
        self.assertIn('id="loginForm"', FALA_HTML)
        self.assertIn('id="accessLine"', FALA_HTML)
        self.assertIn('id="moreButton"', FALA_HTML)
        self.assertIn('id="extras"', FALA_HTML)

    def test_wake_loop_listens_for_oi_jarvis(self):
        self.assertIn("startWakeLoop", FALA_JS)
        self.assertIn("keepListening", FALA_JS)
        self.assertIn("continuous = true", FALA_JS)
        self.assertIn("/login", FALA_JS)
        self.assertIn("app-mode", FALA_JS)
        self.assertIn("jarvis-fala-listen", FALA_JS)
        self.assertIn("postJson", FALA_JS)
        self.assertIn("open.spotify.com", FALA_JS)
        self.assertIn("calendar.google.com", FALA_JS)
        self.assertIn("localClock", FALA_JS)

    def test_does_not_spend_speech_on_greeting(self):
        self.assertNotIn("greetOnce", FALA_JS)
        self.assertIn("speakLocal", FALA_JS)
        self.assertIn("slice(0, 220)", FALA_JS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
