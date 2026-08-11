#!/usr/bin/env python3
"""Contract tests for the allowlisted JARVIS device queue worker."""

from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
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
        cleanup = MODULE.command_argv({
            "action": "system_memory",
            "target": "jarvis-temporaries",
            "request_text": "limpa os processos temporários do jarvis",
        })
        broad_cleanup = MODULE.command_argv({
            "action": "system_memory",
            "target": "",
            "request_text": "limpa os processos do Mac",
        })
        self.assertEqual(opened, [str(ROOT / "jarvis"), "computer", "open", "Calculator"])
        self.assertEqual(closed, [str(ROOT / "jarvis"), "computer", "close", "Spotify"])
        self.assertEqual(memory, [str(ROOT / "jarvis"), "system-memory"])
        self.assertEqual(cleanup, [str(ROOT / "jarvis"), "system-memory", "--cleanup-jarvis"])
        self.assertEqual(broad_cleanup, [str(ROOT / "jarvis"), "system-memory"])
        self_edit = MODULE.command_argv({
            "action": "self_edit",
            "target": "",
            "request_text": "melhore seus próprios scripts de diagnóstico",
        })
        self.assertEqual(
            self_edit,
            [str(ROOT / "jarvis"), "self-edit", "melhore seus próprios scripts de diagnóstico"],
        )
        self_publish = MODULE.command_argv({
            "action": "self_edit",
            "target": "",
            "request_text": "melhore seus próprios scripts, publique e faça deploy",
        })
        self.assertEqual(
            self_publish,
            [
                str(ROOT / "jarvis"),
                "self-edit",
                "melhore seus próprios scripts, publique e faça deploy",
                "--publish",
            ],
        )
        self.assertFalse(MODULE.self_publish_requested("melhore seus próprios scripts"))
        self.assertFalse(MODULE.self_publish_requested("melhore seus scripts sem fazer deploy"))
        self.assertFalse(MODULE.self_publish_requested("edite seus arquivos, somente local"))
        self.assertTrue(MODULE.self_publish_requested("crie a melhoria e suba para produção"))

        capture = MODULE.command_argv({"action": "screen_capture", "target": ""})
        recording = MODULE.command_argv({"action": "screen_record", "target": "native-recorder"})
        github = MODULE.command_argv({"action": "github_overview", "target": "theopadilha2009-hash"})
        storage = MODULE.command_argv({"action": "storage_scan", "target": "downloads"})
        message = MODULE.command_argv({
            "action": "message_send",
            "target": "5511999999999",
            "request_text": 'mande mensagem para 5511999999999 "teste real"',
        })
        self.assertEqual(capture, [str(ROOT / "jarvis"), "screen-capture"])
        self.assertEqual(recording, [str(ROOT / "jarvis"), "screen-record"])
        self.assertEqual(github, [str(ROOT / "jarvis"), "github-overview", "--limit", "12"])
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
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({
                "action": "self_edit",
                "target": "",
                "request_text": "edite scripts token=placeholdervalue123456",
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

    def test_run_envelope_preserves_step_request_and_dependency(self):
        envelope = json.dumps({
            "schema": "jarvis-device-run/1",
            "run_id": "run-test",
            "step": 2,
            "total": 3,
            "depends_on": 41,
            "request": "limpe os processos temporários do jarvis",
            "original_request": "abra o Spotify e depois limpe os processos temporários do jarvis",
        })
        job = {"action": "system_memory", "target": "jarvis-temporaries", "request_text": envelope}
        self.assertEqual(MODULE.job_dependency_id(job), 41)
        self.assertEqual(MODULE.job_request_text(job), "limpe os processos temporários do jarvis")
        self.assertEqual(
            MODULE.command_argv(job),
            [str(ROOT / "jarvis"), "system-memory", "--cleanup-jarvis"],
        )

    def test_run_once_never_executes_step_after_failed_dependency(self):
        envelope = json.dumps({
            "schema": "jarvis-device-run/1",
            "run_id": "run-test",
            "step": 2,
            "total": 2,
            "depends_on": 51,
            "request": "tire um print da tela",
        })
        pending = {"id": 52, "action": "screen_capture", "target": "", "request_text": envelope}
        with patch.object(MODULE, "pending_command", return_value=pending), patch.object(
            MODULE, "dependency_status", return_value="failed"
        ), patch.object(MODULE, "claim_command", return_value=pending), patch.object(
            MODULE, "execute_job"
        ) as execute, patch.object(MODULE, "finish_command") as finish:
            message = MODULE.run_once()
        self.assertIn("bloqueada pela falha", message)
        execute.assert_not_called()
        finish.assert_called_once()
        self.assertEqual(finish.call_args.args[:2], (52, False))
        self.assertIn("dependência 51", finish.call_args.args[2])

    def test_run_once_executes_step_after_succeeded_dependency(self):
        envelope = json.dumps({
            "schema": "jarvis-device-run/1",
            "run_id": "run-test",
            "step": 2,
            "total": 2,
            "depends_on": 61,
            "request": "tire um print da tela",
        })
        pending = {"id": 62, "action": "screen_capture", "target": "", "request_text": envelope}
        with patch.object(MODULE, "pending_command", return_value=pending), patch.object(
            MODULE, "dependency_status", return_value="succeeded"
        ), patch.object(MODULE, "claim_command", return_value=pending), patch.object(
            MODULE, "execute_job", return_value=(True, "capturado")
        ) as execute, patch.object(MODULE, "screenshot_path", return_value=None), patch.object(
            MODULE, "finish_command"
        ) as finish:
            message = MODULE.run_once()
        self.assertIn("Ação 62 concluída", message)
        execute.assert_called_once_with(pending)
        finish.assert_called_once()

    def test_heartbeat_upserts_single_worker_identity(self):
        with patch.object(MODULE, "rest_request", return_value=[]) as request:
            MODULE.heartbeat()
        args, kwargs = request.call_args
        self.assertEqual(args[:2], (MODULE.WORKERS_TABLE, "POST"))
        self.assertEqual(kwargs["query"], "on_conflict=worker_id")
        self.assertEqual(kwargs["body"]["worker_id"], "theo-mac")
        self.assertEqual(kwargs["body"]["version"], "9")
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
            {"id": 33, "action": "self_edit"},
        ]
        with patch.object(MODULE, "rest_request", side_effect=[stale, [], [], []]) as request:
            requeued, failed = MODULE.recover_stale_commands()
        self.assertEqual((requeued, failed), (1, 2))
        retry_body = request.call_args_list[1].kwargs["body"]
        message_body = request.call_args_list[2].kwargs["body"]
        self.assertEqual(retry_body["status"], "pending")
        self.assertIsNone(retry_body["claimed_at"])
        self.assertEqual(message_body["status"], "failed")
        self.assertIn("não foi repetida", message_body["result"])
        self.assertEqual(request.call_args_list[3].kwargs["body"]["status"], "failed")
        recovery_query = request.call_args_list[0].kwargs["query"]
        self.assertIn("%2B00:00", recovery_query)
        self.assertNotIn("+00:00", recovery_query)

    def test_artifact_retention_keeps_newest_twenty_and_only_removes_old_remote_copy(self):
        rows = [{
            "id": index + 1,
            "artifact_path": f"theo/{index + 1}-capture.png",
            "completed_at": "2026-08-01T12:00:00Z",
        } for index in range(20)]
        rows.append({
            "id": 21,
            "artifact_path": "theo/21-old.png",
            "completed_at": "2026-05-01T12:00:00Z",
        })
        with patch.object(MODULE, "rest_request", side_effect=[rows, []]) as request, patch.object(
            MODULE, "delete_private_artifact"
        ) as delete:
            removed = MODULE.prune_private_artifacts(
                now=datetime(2026, 8, 7, 18, 0, tzinfo=timezone.utc)
            )
        self.assertEqual(removed, 1)
        delete.assert_called_once_with("theo/21-old.png")
        self.assertEqual(request.call_args_list[1].kwargs["body"]["artifact_path"], "")

    def test_artifact_delete_rejects_paths_outside_private_prefix(self):
        with self.assertRaises(MODULE.WorkerError):
            MODULE.delete_private_artifact("someone-else/file.png")

    def test_watch_defaults_keep_polling_lightweight(self):
        args = MODULE.build_parser().parse_args(["--watch"])
        self.assertEqual(args.interval, 3.0)
        self.assertGreaterEqual(MODULE.HEARTBEAT_INTERVAL_SECONDS, 15.0)

    def test_launch_agent_path_includes_orca_install_locations(self):
        path = MODULE.launch_payload()["EnvironmentVariables"]["PATH"]
        self.assertIn(str(Path.home() / ".local" / "bin"), path)
        self.assertIn("/usr/local/bin", path)
        self.assertIn("/opt/homebrew/bin", path)

    def test_runtime_v2_resolves_alias_and_small_app_typo(self):
        catalog = {
            MODULE.normalized_application_name("Spotify"): "Spotify",
            MODULE.normalized_application_name("Visual Studio Code"): "Visual Studio Code",
        }
        self.assertEqual(MODULE.resolve_application_target("spotify", catalog), "Spotify")
        self.assertEqual(MODULE.resolve_application_target("Spotfy", catalog), "Spotify")
        self.assertEqual(MODULE.resolve_application_target("vs code", catalog), "Visual Studio Code")

    def test_runtime_v2_accepts_device_run_v2_and_evidence_contract(self):
        envelope = json.dumps({
            "schema": "jarvis-device-run/2",
            "run_id": "run-v2",
            "step": 1,
            "total": 2,
            "depends_on": None,
            "request": "abra o Spotify",
            "retry_policy": {"max_attempts": 2, "idempotent": True},
            "success_evidence": "application_state",
        })
        parsed = MODULE.request_envelope({"request_text": envelope})
        self.assertEqual(parsed["schema"], "jarvis-device-run/2")
        self.assertTrue(parsed["retry_policy"]["idempotent"])

    def test_runtime_v2_requires_independent_app_confirmation(self):
        job = {"action": "open_application", "target": "Spotify"}
        completed = MODULE.subprocess.CompletedProcess(
            args=[str(ROOT / "jarvis"), "computer", "open", "Spotify"],
            returncode=0,
            stdout="Status real: aplicativo aberto.",
            stderr="",
        )
        with patch.object(MODULE, "resolve_application_target", return_value="Spotify"), patch.object(
            MODULE.subprocess, "run", return_value=completed
        ), patch.object(MODULE, "confirm_application_state", return_value=True):
            succeeded, output = MODULE.execute_job(job)
        self.assertTrue(succeeded)
        self.assertIn("Confirmação independente: Spotify está aberto", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
