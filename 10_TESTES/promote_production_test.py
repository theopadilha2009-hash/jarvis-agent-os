#!/usr/bin/env python3
"""Alias jarvis-theo.vercel.app stays locked to jarvis-agent-os."""

from io import StringIO
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_promote_production",
    ROOT / "11_SCRIPTS" / "promote_production.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PromoteProductionTest(unittest.TestCase):
    def test_only_jarvis_agent_os_hosts_are_accepted(self):
        self.assertEqual(MODULE.deployment_host("https://jarvis-agent-os-abc.vercel.app"), "jarvis-agent-os-abc.vercel.app")
        self.assertEqual(MODULE.deployment_host("https://jarvis-agent-os.vercel.app/"), "jarvis-agent-os.vercel.app")
        self.assertEqual(MODULE.deployment_host("https://copytrade.vercel.app"), "")
        self.assertEqual(MODULE.deployment_host("https://evil.vercel.app"), "")

    def test_dry_run_does_not_call_vercel_alias(self):
        output = StringIO()
        with patch.object(MODULE.shutil, "which", return_value=None), redirect_stdout(output):
            code = MODULE.main(["--dry-run"])
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("Promote Production", text)
        self.assertIn("jarvis-theo.vercel.app", text)
        self.assertIn("Produção: nada alterado.", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
