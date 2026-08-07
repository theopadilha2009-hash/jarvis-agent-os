#!/usr/bin/env python3
"""Contract tests for the allowlisted JARVIS device queue worker."""

from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_device_worker",
    ROOT / "11_SCRIPTS" / "device_worker.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DeviceWorkerTest(unittest.TestCase):
    def test_command_argv_maps_only_explicit_actions(self):
        opened = MODULE.command_argv({"action": "open_application", "target": "Calculator"})
        closed = MODULE.command_argv({"action": "close_application", "target": "Spotify"})
        memory = MODULE.command_argv({"action": "system_memory", "target": ""})
        self.assertEqual(opened, [str(ROOT / "jarvis"), "computer", "open", "Calculator"])
        self.assertEqual(closed, [str(ROOT / "jarvis"), "computer", "close", "Spotify"])
        self.assertEqual(memory, [str(ROOT / "jarvis"), "system-memory"])

    def test_command_argv_rejects_arbitrary_shell_and_invalid_target(self):
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "shell", "target": "rm -rf"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "open_application", "target": "Calculator; echo nope"})

    def test_run_once_claims_executes_and_finishes_persisted_job(self):
        pending = {"id": 17, "action": "open_application", "target": "Calculator"}
        with patch.object(MODULE, "pending_command", return_value=pending), patch.object(
            MODULE, "claim_command", return_value=pending
        ), patch.object(MODULE, "execute_job", return_value=(True, "aberto")) as execute, patch.object(
            MODULE, "finish_command"
        ) as finish:
            message = MODULE.run_once()
        self.assertIn("Ação 17 concluída", message)
        execute.assert_called_once_with(pending)
        finish.assert_called_once_with(17, True, "aberto")

    def test_heartbeat_upserts_single_worker_identity(self):
        with patch.object(MODULE, "rest_request", return_value=[]) as request:
            MODULE.heartbeat()
        args, kwargs = request.call_args
        self.assertEqual(args[:2], (MODULE.WORKERS_TABLE, "POST"))
        self.assertEqual(kwargs["query"], "on_conflict=worker_id")
        self.assertEqual(kwargs["body"]["worker_id"], "theo-mac")
        self.assertIn("resolution=merge-duplicates", kwargs["prefer"])

    def test_watch_defaults_keep_polling_lightweight(self):
        args = MODULE.build_parser().parse_args(["--watch"])
        self.assertEqual(args.interval, 3.0)
        self.assertGreaterEqual(MODULE.HEARTBEAT_INTERVAL_SECONDS, 15.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
