#!/usr/bin/env python3
"""Contract tests for the isolated JARVIS self-edit command."""

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_self_edit",
    ROOT / "11_SCRIPTS" / "self_edit.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SelfEditTest(unittest.TestCase):
    def run_preview(self, codex_path):
        output = StringIO()
        with patch.object(MODULE.shutil, "which", return_value=codex_path), redirect_stdout(output):
            result = MODULE.execute("melhorar os próprios scripts com evidência", dry_run=True)
        return result, output.getvalue()

    def test_dry_run_reports_codex_cli_available(self):
        result, output = self.run_preview("/usr/local/bin/codex")
        self.assertEqual(result, 0)
        self.assertIn("Codex CLI: disponível.", output)
        self.assertIn("Modo preview: nenhum worktree, diff ou commit criado.", output)

    def test_dry_run_reports_codex_cli_unavailable_without_failing(self):
        result, output = self.run_preview(None)
        self.assertEqual(result, 0)
        self.assertIn("Codex CLI: indisponível.", output)
        self.assertIn("Status real: preview de autoedição; Codex local indisponível.", output)
        self.assertIn("Produção: nada alterado.", output)

    def test_live_run_still_requires_codex_cli(self):
        with patch.object(MODULE.shutil, "which", return_value=None):
            with self.assertRaisesRegex(MODULE.SelfEditError, "Codex CLI não está instalado"):
                MODULE.execute("melhorar os próprios scripts com evidência")

    def test_safety_gate_is_post_commit_not_a_dirty_tree_validation(self):
        commands = MODULE.validation_commands(["11_SCRIPTS/self_edit.py"])
        self.assertIn(["./jarvis", "command-audit"], commands)
        self.assertNotIn(["./jarvis", "safety-gate"], commands)


if __name__ == "__main__":
    unittest.main()
