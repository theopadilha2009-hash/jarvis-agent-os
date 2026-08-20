#!/usr/bin/env python3
"""Contract tests for the allowlisted JARVIS device queue worker."""

from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_device_worker",
    ROOT / "11_SCRIPTS" / "device_worker.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _boom(*_args, **_kwargs):
    raise OSError("servidor de voz fora do ar")


class DeviceWorkerTest(unittest.TestCase):
    def test_screen_lock_detection_and_arrival_cooldown(self):
        """Desbloqueou o Mac depois de um tempo: abre o cockpit, uma vez por hora."""
        self.assertTrue(MODULE.screen_locked_flag('    "CGSSessionScreenIsLocked" = Yes'))
        self.assertFalse(MODULE.screen_locked_flag('    "CGSSessionScreenIsLocked" = No'))
        # A chave só existe quando bloqueado; ausência é tela livre.
        self.assertFalse(MODULE.screen_locked_flag("ioreg sem a chave"))
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "last-arrival"
            with patch.object(MODULE, "ARRIVAL_STATE", state):
                opened = []
                spoken = []
                with patch.object(MODULE, "speak_on_mac", lambda text: spoken.append(text) or "say"), \
                        patch.object(MODULE.subprocess, "run", lambda *a, **k: opened.append(a[0]) or None):
                    self.assertTrue(MODULE.announce_arrival(10_000.0))
                    # Ele fala pelo alto-falante antes de abrir a aba: o
                    # navegador silencia áudio que ninguém pediu com um clique.
                    self.assertEqual(spoken, [MODULE.ARRIVAL_GREETING])
                    self.assertIn("/usr/bin/open", opened[0])
                    # spoken=1: a aba mostra a saudação sem repetir o áudio.
                    self.assertTrue(opened[0][1].endswith("/cockpit?arrival=worker&spoken=1"), opened[0][1])
                    spoken.clear()
                    # Dentro do cooldown não abre de novo.
                    self.assertFalse(MODULE.announce_arrival(10_600.0))
                    self.assertTrue(MODULE.announce_arrival(10_000.0 + MODULE.ARRIVAL_COOLDOWN_SECONDS + 1))
                with patch.dict(MODULE.os.environ, {"JARVIS_ARRIVAL": "0"}):
                    self.assertFalse(MODULE.announce_arrival(99_999.0))
        # Boot: uma saudação por ligada, e só depois do sistema subir.
        self.assertGreater(MODULE.machine_booted_at(), 0)
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "last-boot"
            with patch.object(MODULE, "BOOT_STATE", state):
                with patch.object(MODULE, "machine_booted_at", lambda: 1_000.0):
                    self.assertFalse(MODULE.boot_greeting_due(1_010.0))  # ainda subindo
                    self.assertTrue(MODULE.boot_greeting_due(2_000.0))
                    MODULE.mark_boot_greeting(1_000.0)
                    self.assertFalse(MODULE.boot_greeting_due(2_000.0))
                with patch.object(MODULE, "machine_booted_at", lambda: 9_000.0):
                    self.assertTrue(MODULE.boot_greeting_due(10_000.0))
        # A chegada roda antes do heartbeat: Supabase fora do ar não impede
        # receber Theo (o except do heartbeat pularia o resto do ciclo).
        source = Path(MODULE.__file__).read_text(encoding="utf-8")
        loop = source[source.index("while running:"):]
        self.assertLess(loop.index("screen_is_locked()"), loop.index("heartbeat()"))

    def test_boot_greeting_is_good_morning_and_does_not_wait_three_minutes(self):
        self.assertIn("Bom dia", MODULE.BOOT_GREETING)
        self.assertLessEqual(MODULE.BOOT_QUIET_SECONDS, 30)
        self.assertEqual(MODULE.resolve_application_target("sistema", {}), "JARVIS")
        self.assertEqual(MODULE.resolve_application_target("cockpit", {}), "JARVIS")

    def test_boot_greeting_survives_a_recent_arrival(self):
        """Reiniciar logo depois de um desbloqueio não pode engolir o bem-vindo."""
        with tempfile.TemporaryDirectory() as folder:
            arrival = Path(folder) / "last-arrival"
            boot = Path(folder) / "last-boot"
            arrival.write_text("10000.0")  # saudou há um minuto
            spoken = []
            with patch.object(MODULE, "ARRIVAL_STATE", arrival), \
                    patch.object(MODULE, "BOOT_STATE", boot), \
                    patch.object(MODULE, "speak_on_mac", lambda text: spoken.append(text) or "say"), \
                    patch.object(MODULE.subprocess, "run", lambda *a, **k: None):
                # Chegada comum continua respeitando o cooldown de uma hora.
                self.assertFalse(MODULE.announce_arrival(10_060.0))
                # O boot tem a própria trava e não passa pelo cooldown.
                self.assertTrue(MODULE.announce_arrival(10_060.0, "boot"))
                self.assertEqual(spoken, [MODULE.BOOT_GREETING])
                # Desligar a chegada continua desligando tudo.
                with patch.dict(MODULE.os.environ, {"JARVIS_ARRIVAL": "0"}):
                    self.assertFalse(MODULE.announce_arrival(20_000.0, "boot"))

        # A marca do boot só é escrita depois de a saudação acontecer.
        source = Path(MODULE.__file__).read_text(encoding="utf-8")
        loop = source[source.index("while running:"):]
        self.assertLess(
            loop.index('announce_arrival(wall_now, "boot")'),
            loop.index("mark_boot_greeting("),
        )

    def test_speak_on_mac_prefers_own_voice_and_falls_back_to_say(self):
        """A saudação sai do alto-falante mesmo sem o servidor de voz de pé."""
        calls = []

        class FakeResponse:
            def read(self):
                return b"ID3fake-mp3"

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with patch.object(MODULE.shutil, "which", lambda name: f"/usr/bin/{name}"), \
                patch.object(MODULE, "urlopen", lambda *a, **k: FakeResponse()), \
                patch.object(MODULE.subprocess, "run", lambda *a, **k: calls.append(a[0]) or None):
            self.assertEqual(MODULE.speak_on_mac("Bem-vindo, Theo."), "local_tts")
            self.assertEqual(calls[0][0], "/usr/bin/afplay")

        # Servidor local fora do ar: o macOS assume com voz masculina.
        calls.clear()
        with patch.object(MODULE.shutil, "which", lambda name: f"/usr/bin/{name}"), \
                patch.object(MODULE, "urlopen", _boom), \
                patch.object(MODULE.subprocess, "run", lambda *a, **k: calls.append(a[0]) or None):
            self.assertEqual(MODULE.speak_on_mac("Bem-vindo, Theo."), "say")
            self.assertEqual(calls[0][:3], ["/usr/bin/say", "-v", MODULE.LOCAL_SAY_VOICE])

        # Texto vazio e desligamento explícito não fazem barulho nenhum.
        calls.clear()
        with patch.object(MODULE.subprocess, "run", lambda *a, **k: calls.append(a[0]) or None):
            self.assertEqual(MODULE.speak_on_mac("   "), "skipped")
            with patch.dict(MODULE.os.environ, {"JARVIS_LOCAL_VOICE": "0"}):
                self.assertEqual(MODULE.speak_on_mac("oi"), "skipped")
        self.assertEqual(calls, [])

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
        self.assertTrue(MODULE.self_publish_requested("faça deploy e merge do que você melhorou no jarvis"))
        note_argv = MODULE.command_argv({
            "action": "save_note",
            "target": "comprar-pao",
            "request_text": json.dumps({
                "schema": "jarvis-note/1",
                "title": "comprar pão",
                "body": "comprar pão",
            }),
        })
        self.assertEqual(note_argv[0], "jarvis-note-save")

        capture = MODULE.command_argv({"action": "screen_capture", "target": ""})
        recording = MODULE.command_argv({"action": "screen_record", "target": "native-recorder"})
        github = MODULE.command_argv({"action": "github_overview", "target": "theopadilha2009-hash"})
        spotify = MODULE.command_argv({
            "action": "spotify_control",
            "target": "volume 35",
            "request_text": "volume do Spotify para 35",
        })
        storage = MODULE.command_argv({"action": "storage_scan", "target": "downloads"})
        message = MODULE.command_argv({
            "action": "message_send",
            "target": "5511999999999",
            "request_text": 'mande mensagem para 5511999999999 "teste real"',
        })
        self.assertEqual(capture, [str(ROOT / "jarvis"), "screen-capture"])
        self.assertEqual(recording, [str(ROOT / "jarvis"), "screen-record"])
        self.assertEqual(github, [str(ROOT / "jarvis"), "github-overview", "--limit", "12"])
        self.assertEqual(spotify, [str(ROOT / "jarvis"), "spotify", "volume", "35"])
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
        folder = MODULE.command_argv({"action": "open_folder", "target": "downloads", "request_text": "abre a pasta downloads"})
        self.assertEqual(folder[0], "/usr/bin/open")
        self.assertTrue(str(folder[1]).endswith("Downloads"))
        volume = MODULE.command_argv({"action": "volume_set", "target": "40", "request_text": "volume do mac para 40"})
        self.assertEqual(volume[:2], ["osascript", "-e"])
        self.assertIn("output volume 40", volume[2])
        opened_url = MODULE.command_argv({
            "action": "open_url",
            "target": "browser",
            "request_text": "abra https://github.com no mac",
        })
        self.assertEqual(opened_url, ["/usr/bin/open", "https://github.com"])

    def test_command_argv_rejects_arbitrary_shell_and_invalid_target(self):
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "shell", "target": "rm -rf"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "open_application", "target": "Calculator; echo nope"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "storage_scan", "target": "/"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "spotify_control", "target": "invalid", "request_text": "Spotify faça qualquer coisa"})
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
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "open_url", "target": "browser", "request_text": "abra javascript:alert(1) no mac"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "open_folder", "target": "/", "request_text": "abre a pasta /"})
        with self.assertRaises(MODULE.WorkerError):
            MODULE.command_argv({"action": "volume_set", "target": "140", "request_text": "volume do mac para 140"})

    def test_native_jobs_run_allowlisted_binaries_only(self):
        class Result:
            def __init__(self, code=0, stdout="40"):
                self.returncode = code
                self.stdout = stdout
                self.stderr = ""

        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs.get("input")))
            return Result()

        with patch.object(MODULE.platform, "system", return_value="Darwin"), patch.object(
            MODULE.subprocess, "run", side_effect=fake_run
        ):
            ok, message = MODULE.execute_clipboard_job({
                "action": "clipboard_set",
                "target": "clipboard",
                "request_text": "copia isso: hello jarvis",
            })
            self.assertTrue(ok)
            self.assertEqual(calls[0][0], ["/usr/bin/pbcopy"])
            self.assertEqual(calls[0][1], "hello jarvis")
            ok, message = MODULE.execute_open_url_job({
                "action": "open_url",
                "target": "browser",
                "request_text": "abra https://github.com no mac",
            })
            self.assertTrue(ok)
            self.assertEqual(calls[1][0], ["/usr/bin/open", "https://github.com"])
            ok, message = MODULE.execute_volume_job({
                "action": "volume_set",
                "target": "40",
                "request_text": "volume do mac para 40",
            })
            self.assertTrue(ok)
            self.assertIn("output volume 40", calls[2][0][2])

    def test_image_convert_uses_sips_and_opens_downloads(self):
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            downloads = home / "Downloads"
            downloads.mkdir()
            source = downloads / "foto.png"
            source.write_bytes(b"source-bytes")
            calls = []

            def fake_run(argv, **kwargs):
                calls.append(argv)
                if argv and argv[0] == "/usr/bin/sips":
                    Path(argv[-1]).write_bytes(b"converted")
                return Result()

            with patch.object(MODULE, "newest_download_image", return_value=source), patch.object(
                MODULE.Path, "home", return_value=home
            ), patch.object(MODULE.platform, "system", return_value="Darwin"), patch.object(
                MODULE.subprocess, "run", side_effect=fake_run
            ):
                ok, message = MODULE.execute_image_convert_job({
                    "action": "image_convert",
                    "target": "png",
                    "request_text": "converta esta imagem para png",
                })
            self.assertTrue(ok)
            self.assertEqual(calls[0][0], "/usr/bin/sips")
            self.assertEqual(calls[1], ["/usr/bin/open", str(downloads)])
            self.assertIn("Downloads aberto", message)
            self.assertTrue((downloads / "foto-converted.png").is_file())

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
        self.assertEqual(kwargs["body"]["version"], "13")
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

    def test_stale_recovery_never_repeats_side_effecting_actions(self):
        stale = [
            {"id": 31, "action": "screen_capture"},
            {"id": 32, "action": "message_send"},
            {"id": 33, "action": "self_edit"},
            {"id": 34, "action": "spotify_control"},
        ]
        with patch.object(MODULE, "rest_request", side_effect=[stale, [], [], [], []]) as request:
            requeued, failed = MODULE.recover_stale_commands()
        self.assertEqual((requeued, failed), (1, 3))
        retry_body = request.call_args_list[1].kwargs["body"]
        message_body = request.call_args_list[2].kwargs["body"]
        self.assertEqual(retry_body["status"], "pending")
        self.assertIsNone(retry_body["claimed_at"])
        self.assertEqual(message_body["status"], "failed")
        self.assertIn("não foi repetida", message_body["result"])
        self.assertEqual(request.call_args_list[3].kwargs["body"]["status"], "failed")
        self.assertEqual(request.call_args_list[4].kwargs["body"]["status"], "failed")
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

    def test_save_note_writes_markdown_in_jarvis_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            job = {
                "action": "save_note",
                "target": "comprar-pao",
                "request_text": json.dumps({
                    "schema": "jarvis-note/1",
                    "title": "comprar pão",
                    "body": "comprar pão amanhã",
                }),
            }
            with patch.object(MODULE.Path, "home", return_value=home), \
                    patch.object(MODULE, "write_apple_note", return_value="Cópia no app Notas."):
                ok, output = MODULE.persist_mac_note(job)
            self.assertTrue(ok)
            notes = list((home / "Documents" / "JARVIS" / "Notas").glob("*.md"))
            self.assertEqual(len(notes), 1)
            self.assertIn("comprar pão amanhã", notes[0].read_text(encoding="utf-8"))
            self.assertIn("app Notas", output)

    def test_applescript_string_escapes_newlines_and_quotes(self):
        escaped = MODULE.applescript_string('linha 1\n"quebra"\r\\fim')
        self.assertEqual(escaped, 'linha 1\\n\\"quebra\\"\\r\\\\fim')
        self.assertNotIn("\n", escaped)
        self.assertNotIn("\r", escaped)

    def test_write_apple_note_keeps_multiline_body_inside_the_string(self):
        with patch.object(MODULE.platform, "system", return_value="Darwin"), \
                patch.object(MODULE.subprocess, "run") as run:
            run.return_value = type("Proc", (), {"returncode": 0})()
            message = MODULE.write_apple_note("compra", "leite\npão")
        script = run.call_args.args[0][2]
        self.assertEqual(message, "Cópia no app Notas.")
        self.assertIn('body:"leite\\npão"', script)
        self.assertNotRegex(script, r'body:"[^"]*\n[^"]*"')

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
