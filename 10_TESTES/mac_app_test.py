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
                # Executável de verdade: Mach-O, não script do Chrome.
                self.assertTrue(binary.stat().st_mode & 0o111)
                self.assertTrue(MODULE.is_macho(binary))
                source = MODULE.SWIFT_SOURCE.read_text(encoding="utf-8")
                self.assertIn("WKWebView", source)
                self.assertIn("requestMediaCapturePermissionFor", source)
                self.assertNotIn("AVSpeechSynthesizer", source)
                self.assertNotIn("AVSpeechUtterance", source)
                self.assertIn("AVAudioPlayer", source)
                self.assertIn("SFSpeechRecognizer", source)
                self.assertIn("jarvisSpeak", source)
                self.assertIn("jarvisRestart", source)
                self.assertIn("reloadFromOrigin", source)
                self.assertIn("restartFromOrigin", source)
                self.assertIn("reloadIgnoringLocalCacheData", source)
                self.assertIn("isMovableByWindowBackground = compactOn", source)
                self.assertIn("shouldReportPartialResults = true", source)
                self.assertIn("contextualStrings", source)
                self.assertIn("JARVIS always listening", source)
                self.assertIn("startListen()", source)
                self.assertIn("restartListen", source)
                self.assertIn("beginRecognition", source)
                self.assertIn("isRestorable = false", source)
                self.assertNotIn("engine.prepare()", source)
                self.assertNotIn("Google Chrome", source)

                info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
                self.assertEqual(info["CFBundleIdentifier"], MODULE.BUNDLE_ID)
                self.assertEqual(info["CFBundleExecutable"], "JARVIS")
                self.assertFalse(info.get("NSQuitAlwaysKeepsWindows", True))
                self.assertEqual(info["CFBundleShortVersionString"], "3.8")
                self.assertIn("pause", source)
                self.assertIn("openExternal", source)
                self.assertIn('body == "stop"', source)
                self.assertIn(".miniaturizable", source)
                self.assertIn("idleHideAfter: TimeInterval = 12", source)
                self.assertIn("jarvisWindow", source)
                self.assertIn("hideWindow", source)
                self.assertIn("setCompact", source)
                self.assertIn("orbSize", source)
                self.assertIn("width: 72", source)
                self.assertIn("isHidden = true", source)
                self.assertIn("JarvisParkedOrigin", source)
                self.assertIn("frameKeepingPlace", source)
                self.assertIn("windowDidMove", source)
                self.assertIn("windowShouldMiniaturize", source)
                self.assertIn("orderFrontRegardless", source)
                self.assertIn("takeFocus", source)
                self.assertIn("pokeVoice", source)
                self.assertIn("kickVoice", source)
                self.assertIn("kickstart", source)
                self.assertIn("kickCooldown", source)
                self.assertIn("speakingNow", source)
                self.assertIn("voiceMisses", source)
                self.assertIn("cannotConnectToHost", source)
                self.assertIn("timeoutInterval = 15.0", source)
                self.assertNotIn("timeoutInterval = 4.0", source)
                self.assertIn("paintChrome", source)
                self.assertIn("underPageBackgroundColor", source)
                self.assertIn("cornerRadius", source)
                self.assertNotIn('["kickstart", "-k"', source)
                self.assertIn("JarvisLastMorning", source)
                self.assertIn("Bom dia, senhor.", source)
                self.assertIn("keyCode == 49", source)
                self.assertIn("containsWake", source)
                self.assertIn("SpeechAnalyzer", source)
                self.assertIn("SpeechTranscriber", source)
                self.assertTrue(info["NSHighResolutionCapable"])
                self.assertIn("Theo Lorentz Padilha", info["NSHumanReadableCopyright"])
                self.assertIn("JarvisCockpitURL", info)
                self.assertIn("/fala", info["JarvisCockpitURL"])
                self.assertIn("NSMicrophoneUsageDescription", info)
                self.assertIn("NSSpeechRecognitionUsageDescription", info)
                self.assertIn("NSScreenCaptureUsageDescription", info)
                self.assertIn("jarvisSee", source)
                self.assertIn("ScreenCaptureKit", source)
                self.assertIn("SCScreenshotManager", source)
                self.assertIn("captureScreen", source)
                self.assertIn("screencapture", source)
                self.assertTrue((app / "Contents" / "Resources" / "NOTICE.txt").is_file())
                if MODULE.ICON_ICNS.is_file():
                    self.assertEqual(info["CFBundleIconFile"], "jarvis")
                    self.assertTrue((app / "Contents" / "Resources" / "jarvis.icns").is_file())
                else:
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

    def test_downloadable_pack_has_app_installer_and_creator_lock(self):
        packed = MODULE.build_mac_pack(MODULE.DEFAULT_ORIGIN)
        self.assertGreater(len(packed), 200)
        with tempfile.TemporaryDirectory() as folder:
            zip_path = Path(folder) / "JARVIS.mac.zip"
            zip_path.write_bytes(packed)
            import zipfile
            with zipfile.ZipFile(zip_path) as archive:
                names = set(archive.namelist())
                self.assertIn("JARVIS.app/Contents/MacOS/JARVIS", names)
                self.assertIn("JARVIS.app/Contents/Info.plist", names)
                self.assertIn("INSTALAR.command", names)
                self.assertIn("LER-ME.txt", names)
                macho = archive.read("JARVIS.app/Contents/MacOS/JARVIS")
                self.assertIn(macho[:4], {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe"})
                source = archive.read("JARVIS.app/Contents/MacOS/jarvis_native_app.swift").decode("utf-8")
                self.assertIn("WKWebView", source)
                self.assertNotIn("AVSpeechSynthesizer", source)
                self.assertNotIn("AVSpeechUtterance", source)
                self.assertIn("jarvisSpeak", source)
                self.assertIn("jarvisRestart", source)
                self.assertNotIn("Google Chrome", source)
                self.assertNotIn("sleep 1.1", source)
                self.assertIn("Theo Lorentz Padilha", archive.read("NOTICE.txt").decode("utf-8"))
                self.assertTrue(archive.comment.decode("ascii").startswith("lock:"))
                info = plistlib.loads(archive.read("JARVIS.app/Contents/Info.plist"))
                self.assertEqual(info["CFBundleIdentifier"], MODULE.BUNDLE_ID)
                self.assertIn("Theo Lorentz Padilha", info["NSHumanReadableCopyright"])
                self.assertIn("/fala", info["JarvisCockpitURL"])
                installer = archive.getinfo("INSTALAR.command")
                launcher = archive.getinfo("JARVIS.app/Contents/MacOS/JARVIS")
                self.assertEqual(installer.external_attr >> 16, 0o100755)
                self.assertEqual(launcher.external_attr >> 16, 0o100755)
                packed_agent = plistlib.loads(archive.read("ai.theopadilha.jarvis.fala.plist"))
                self.assertNotIn("KeepAlive", packed_agent)
                self.assertEqual(packed_agent["ProgramArguments"], ["/usr/bin/open", "-a", "JARVIS"])
                self.assertIn("com.apple.quarantine", archive.read("INSTALAR.command").decode("utf-8"))
                self.assertIn("LaunchAgents", archive.read("INSTALAR.command").decode("utf-8"))
                self.assertIn("INSTALAR-WORKER.command", archive.read("INSTALAR.command").decode("utf-8"))
                self.assertIn("INSTALAR-WORKER.command", names)
                self.assertIn("computer-worker --install", archive.read("INSTALAR-WORKER.command").decode("utf-8"))
                self.assertIn("ai.theopadilha.jarvis.fala.plist", names)
                if MODULE.ICON_ICNS.is_file():
                    self.assertIn("JARVIS.app/Contents/Resources/jarvis.icns", names)
                    self.assertEqual(info["CFBundleIconFile"], "jarvis")

    def test_login_agent_starts_the_corner_widget(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            calls = []

            class Result:
                returncode = 0

            with patch.object(MODULE.Path, "home", return_value=home), patch.object(
                MODULE.os, "getuid", return_value=501
            ), patch.object(MODULE.subprocess, "run", lambda *a, **k: calls.append(list(a[0])) or Result()):
                MODULE.install_login_agent()
            path = home / "Library" / "LaunchAgents" / "ai.theopadilha.jarvis.fala.plist"
            self.assertTrue(path.is_file())
            payload = plistlib.loads(path.read_bytes())
            self.assertEqual(payload["Label"], "ai.theopadilha.jarvis.fala")
            self.assertTrue(payload["RunAtLoad"])
            self.assertNotIn("KeepAlive", payload)
            self.assertEqual(payload["ProgramArguments"], ["/usr/bin/open", "-a", "JARVIS"])
            self.assertTrue(any(cmd[:1] == ["launchctl"] for cmd in calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
