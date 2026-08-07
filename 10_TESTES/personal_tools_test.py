#!/usr/bin/env python3
"""Focused tests for personal actions that may persist or send externally."""

from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import importlib.util
import io
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("personal_tools", ROOT / "11_SCRIPTS" / "personal_tools.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PersonalToolsTest(unittest.TestCase):
    def test_computer_open_dry_run_never_invokes_native_command(self):
        with patch.object(MODULE.subprocess, "run") as run:
            output = io.StringIO()
            with redirect_stdout(output):
                MODULE.cmd_computer(Namespace(
                    action="open",
                    app="Chrome",
                    dry_run=True,
                ))
        run.assert_not_called()
        self.assertIn("Google Chrome", output.getvalue())
        self.assertIn("aplicativo não aberto", output.getvalue())

    def test_computer_close_refuses_orca_worker(self):
        app = {"name": "Orca", "bundleId": "com.stablyai.orca", "pid": 457}
        with patch.object(MODULE, "_running_app", return_value=app):
            with self.assertRaises(SystemExit) as error:
                MODULE.cmd_computer(Namespace(
                    action="close",
                    app="Orca",
                    dry_run=False,
                ))
        self.assertEqual(error.exception.code, 3)

    def test_memory_save_persists_markdown_in_selected_category(self):
        with TemporaryDirectory() as directory:
            with patch.object(MODULE, "MEMORY_DIR", Path(directory)):
                output = io.StringIO()
                with redirect_stdout(output):
                    MODULE.cmd_memory_save(Namespace(
                        text=["Theo prefere respostas diretas"],
                        kind="preference",
                        dry_run=False,
                    ))
            files = list((Path(directory) / "03_PREFERENCIAS").glob("*.md"))
            self.assertEqual(len(files), 1)
            self.assertIn("Theo prefere respostas diretas", files[0].read_text(encoding="utf-8"))
            self.assertIn("Memória criada:", output.getvalue())

    def test_message_send_dry_run_never_invokes_osascript(self):
        with patch.object(MODULE.subprocess, "run") as run:
            output = io.StringIO()
            with redirect_stdout(output):
                MODULE.cmd_message_send(Namespace(
                    phone="5511999999999",
                    text=["teste local"],
                    dry_run=True,
                ))
        run.assert_not_called()
        self.assertIn("nenhuma mensagem enviada", output.getvalue())

    def test_orca_capture_fallback_copies_real_png(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "orca-source.png"
            target = Path(directory) / "jarvis-capture.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\nreal-pixels")
            completed = MODULE.subprocess.CompletedProcess(
                args=["orca"],
                returncode=0,
                stdout=json.dumps({"result": {"screenshot": {"path": str(source)}}}),
                stderr="",
            )
            with patch.object(MODULE.shutil, "which", return_value="/usr/local/bin/orca"), patch.object(
                MODULE.subprocess, "run", return_value=completed
            ):
                copied = MODULE._orca_window_capture(target)
            self.assertTrue(copied)
            self.assertEqual(target.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
