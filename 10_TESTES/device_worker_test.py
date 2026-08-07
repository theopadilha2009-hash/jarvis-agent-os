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

        capture = MODULE.command_argv({"action": "screen_capture", "target": ""})
        storage = MODULE.command_argv({"action": "storage_scan", "target": "downloads"})
        message = MODULE.command_argv({
            "action": "message_send",
            "target": "5511999999999",
            "request_text": 'mande mensagem para 5511999999999 "teste real"',
        })
        self.assertEqual(capture, [str(ROOT / "jarvis"), "screen-capture"])
        self.assertEqual(storage[:3], [str(ROOT / "jarvis"), "storage-scan", str(Path.home() / "Downloads")])
        self.assertEqual(
            message,
            [str(ROOT / "jarvis"), "message-send", "--phone", "5511999999999", "teste real"],
        )
        alias_message = MODULE.command_argv({
            "action": "message_send",
            "target": "5511999999999",
            "request_text": "mande mensagem para Arthur dizendo estou chegando",
        })
        self.assertEqual(
            alias_message,
            [str(ROOT / "jarvis"), "message-send", "--phone", "5511999999999", "estou chegando"],
        )

    def test_command_argv_rejects_arbitrary_shell_and_invalid_target(self):
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "shell", "target": "rm -rf"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "open_application", "target": "Calculator; echo nope"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "storage_scan", "target": "/"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({
                "action": "message_send",
                "target": "5511999999999",
                "request_text": "mande mensagem para 5511999999999 token=placeholdervalue123456",
            })

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

    def test_screen_capture_uploads_private_preview_before_success(self):
        pending = {"id": 23, "action": "screen_capture", "target": ""}
        capture = ROOT / "05_EXECUCAO" / "64_PERSONAL_TOOLS" / "screenshots" / "capture.png"
        output = f"Status real: captura.\nsaída: {capture}\nOK"
        with patch.object(MODULE, "pending_command", return_value=pending), patch.object(
            MODULE, "claim_command", return_value=pending
        ), patch.object(MODULE, "execute_job", return_value=(True, output)), patch.object(
            MODULE, "upload_private_artifact", return_value=("theo/23-capture.png", "image/png")
        ) as upload, patch.object(MODULE, "finish_command") as finish:
            message = MODULE.run_once()
        self.assertIn("Ação 23 concluída", message)
        upload.assert_called_once_with(capture, 23)
        finish.assert_called_once_with(
            23,
            True,
            output + "\nPreview privado publicado no Supabase Storage.",
            "theo/23-capture.png",
            "image/png",
        )

    def test_stale_recovery_never_repeats_message_send(self):
        stale = [
            {"id": 31, "action": "screen_capture"},
            {"id": 32, "action": "message_send"},
        ]
        with patch.object(MODULE, "rest_request", side_effect=[stale, [], []]) as request:
            requeued, failed = MODULE.recover_stale_commands()
        self.assertEqual((requeued, failed), (1, 1))
        retry_body = request.call_args_list[1].kwargs["body"]
        message_body = request.call_args_list[2].kwargs["body"]
        self.assertEqual(retry_body["status"], "pending")
        self.assertIsNone(retry_body["claimed_at"])
        self.assertEqual(message_body["status"], "failed")
        self.assertIn("não foi repetida", message_body["result"])

    def test_watch_defaults_keep_polling_lightweight(self):
        args = MODULE.build_parser().parse_args(["--watch"])
        self.assertEqual(args.interval, 3.0)
        self.assertGreaterEqual(MODULE.HEARTBEAT_INTERVAL_SECONDS, 15.0)

    def test_launch_agent_path_includes_orca_install_locations(self):
        path = MODULE.launch_payload()["EnvironmentVariables"]["PATH"]
        self.assertIn("/usr/local/bin", path)
        self.assertIn("/opt/homebrew/bin", path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
