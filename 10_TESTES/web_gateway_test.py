#!/usr/bin/env python3
"""Contract tests for the stdlib-only JARVIS web gateway."""

from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import base64
import importlib.util
from datetime import datetime
import json
import os
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("jarvis_web_gateway", ROOT / "api" / "index.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WebGatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_local_exec = os.environ.get("JARVIS_WEB_LOCAL_EXEC")
        cls.previous_supabase_url = os.environ.pop("SUPABASE_URL", None)
        cls.previous_supabase_key = os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
        cls.previous_owner_token = os.environ.pop("JARVIS_OWNER_TOKEN", None)
        os.environ["JARVIS_WEB_LOCAL_EXEC"] = "0"
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MODULE.handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        if cls.previous_local_exec is None:
            os.environ.pop("JARVIS_WEB_LOCAL_EXEC", None)
        else:
            os.environ["JARVIS_WEB_LOCAL_EXEC"] = cls.previous_local_exec
        if cls.previous_supabase_url is not None:
            os.environ["SUPABASE_URL"] = cls.previous_supabase_url
        if cls.previous_supabase_key is not None:
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = cls.previous_supabase_key
        if cls.previous_owner_token is not None:
            os.environ["JARVIS_OWNER_TOKEN"] = cls.previous_owner_token

    def request(self, path, method="GET", payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def json_request(self, path, method="GET", payload=None):
        status, headers, raw = self.request(path, method, payload)
        return status, headers, json.loads(raw)

    def test_status_and_security_headers(self):
        status, headers, payload = self.json_request("/status")
        self.assertEqual(status, 200)
        self.assertEqual(payload["service"], "jarvis-web")
        self.assertIn("voice", payload)
        self.assertEqual(payload["voice"]["fallback"], "text_only")
        self.assertIn("n8n", payload["automations"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_cockpit_and_model_asset(self):
        status, _, html = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"JARVIS", html)
        self.assertIn(b'id="voiceButton"', html)
        self.assertIn(b'<svg aria-hidden="true" viewBox="0 0 24 24">', html)
        self.assertIn(b'id="muteButton"', html)
        self.assertIn(b'id="avatar3d"', html)
        self.assertIn(b'id="liveSurface"', html)
        self.assertIn(b'id="conversationState"', html)
        self.assertIn(b'class="mark-j"', html)
        self.assertIn(b'/ui/jarvis.js?v=20260808-files1', html)
        self.assertIn(b'/ui/jarvis.css?v=20260808-files1', html)
        self.assertIn(b'id="pulseButton"', html)
        self.assertIn(b'id="attachmentInput"', html)
        self.assertIn(b'id="attachmentTray"', html)
        self.assertIn(b'/ui/vendor/three.module.js', html)
        self.assertIn(b"requestIdleCallback", html)
        self.assertNotIn(b"fallback-core", html)
        self.assertNotIn(b'unpkg.com', html)

        status, headers, app_js = self.request("/ui/jarvis.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"SpeechRecognition", app_js)
        self.assertIn(b'input_mode: options.source || "text"', app_js)
        self.assertIn("Áudio não reproduzido".encode(), app_js)
        self.assertIn(b"memory-command", app_js)
        self.assertIn(b"X-Jarvis-Owner-Token", app_js)
        self.assertIn(b"monitorDeviceCommand", app_js)
        self.assertIn(b"agendaDate", app_js)
        self.assertIn(b"revealLatest", app_js)
        self.assertIn(b"saveOwnerToken", app_js)
        self.assertIn(b"ElevenLabs sem cr\xc3\xa9ditos", app_js)
        self.assertIn(b"new AbortController()", app_js)
        self.assertIn(b"signal: controller.signal", app_js)
        self.assertIn(b"currentSpeechController?.abort()", app_js)
        self.assertIn(b"compactCaption", app_js)
        self.assertIn(b"session.voicePending", app_js)
        self.assertIn(b'data.provider === "openrouter"', app_js)
        self.assertIn(b"renderEventStream", app_js)
        self.assertIn(b'protocol !== "jarvis-events/1"', app_js)
        self.assertIn(b"renderUICards", app_js)
        self.assertIn(b'class="ui-card"', app_js)
        self.assertIn(b"refreshPulse", app_js)
        self.assertIn(b"10 * 60 * 1000", app_js)
        self.assertIn(b'"/device-cancel"', app_js)
        self.assertIn(b"canceledJobs", app_js)
        self.assertIn(b"addAttachments", app_js)
        self.assertIn(b"readAsDataURL", app_js)

        status, headers, app_css = self.request("/ui/jarvis.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".conversation-head", app_css)
        self.assertIn(b"-webkit-line-clamp: 2", app_css)
        self.assertIn(b'.stage.has-conversation .conversation', app_css)
        self.assertIn(b'.stage[data-state="thinking"] .hud-right', app_css)
        self.assertIn(b".compact-surface {\n  display: none", app_css)
        self.assertIn(b'error?.name === "AbortError"', app_js)
        self.assertNotIn(b"speechSynthesis", app_js)

        status, headers, visual_js = self.request("/ui/jarvis-3d.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"drawMemory", visual_js)
        self.assertIn(b"drawForge", visual_js)
        self.assertIn(b"makeCoreEntity", visual_js)
        self.assertIn(b"MEMORY CONSTELLATION", visual_js)
        self.assertIn(b"visualModeForState", visual_js)
        self.assertIn(b"AnimationMixer", visual_js)
        self.assertIn(b"20260807-voicecyan1", visual_js)
        self.assertIn(b"installCyanRemap", visual_js)
        self.assertIn(b"jarvisRedMask", visual_js)
        self.assertIn(b"BASE_FRAME_INTERVAL_MS", visual_js)
        self.assertIn(b"adaptive-lite-18fps", visual_js)
        self.assertIn(b"slowFrameWindows", visual_js)
        self.assertIn(b'renderer.setPixelRatio(1)', visual_js)
        self.assertIn(b'GPU 3D desativada', visual_js)
        self.assertIn(b"frameIntervalMs", visual_js)
        self.assertIn(b"document.hidden", visual_js)
        self.assertIn(b"X-Jarvis-Owner-Token", visual_js)

        status, headers, three_js = self.request("/ui/vendor/three.module.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertGreater(len(three_js), 1_000_000)

        status, headers, css = self.request("/ui/jarvis.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".hud-rail", css)
        self.assertIn(b".message.user.voice", css)

        status, _, favicon = self.request("/favicon.ico")
        self.assertEqual(status, 200)
        self.assertEqual(favicon, b"")

        status, headers, model = self.request("/asset/models/jarvis-humanoid.glb")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "model/gltf-binary")
        self.assertEqual(headers["Cache-Control"], "public, max-age=31536000, immutable")
        self.assertGreater(len(model), 4_000_000)
        self.assertLess(len(model), 4_500_000)

    def test_local_device_request_becomes_handoff(self):
        status, _, payload = self.json_request(
            "/command", "POST", {"command": "tirar um print da tela"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "screen_capture")
        self.assertTrue(payload["requires_local_worker"])
        self.assertTrue(payload["local_command"].startswith("./jarvis do "))
        stream = payload["event_stream"]
        self.assertEqual(stream["protocol"], "jarvis-events/1")
        self.assertEqual(stream["events"][0]["type"], "RUN_STARTED")
        self.assertEqual(stream["events"][-1]["type"], "RUN_FINISHED")
        self.assertGreaterEqual(stream["elapsed_ms"], 0)

    def test_failed_command_has_terminal_error_event(self):
        status, _, payload = self.json_request("/command", "POST", {"command": ""})
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["event_stream"]["events"][-1]["type"], "RUN_ERROR")

    def test_planning_response_has_typed_ui_card(self):
        status, _, payload = self.json_request(
            "/command", "POST", {"command": "/plan melhorar a memória"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["ui_cards"][0]["type"], "plan")
        self.assertEqual(payload["ui_cards"][0]["status"], "ready")
        self.assertGreaterEqual(len(payload["ui_cards"][0]["items"]), 3)

    def test_plain_answer_does_not_invent_ui_card(self):
        cards = MODULE.response_cards({"ok": True, "provider": "openrouter", "message": "Olá"})
        self.assertEqual(cards, [])

    def test_open_and_close_apps_route_to_explicit_computer_command(self):
        opened, open_status = MODULE.command_payload(
            {"command": "abre o Chrome pra mim"},
            local_execute=False,
        )
        closed, close_status = MODULE.command_payload(
            {"command": "fecha o Spotify"},
            local_execute=False,
        )
        self.assertEqual(open_status, 200)
        self.assertEqual(opened["intent"], "open_application")
        self.assertEqual(opened["local_command"], "./jarvis computer open 'Google Chrome'")
        self.assertEqual(close_status, 200)
        self.assertEqual(closed["intent"], "close_application")
        self.assertEqual(closed["local_command"], "./jarvis computer close Spotify")

    def test_remote_device_action_requires_owner_pairing(self):
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        with patch.dict(os.environ, env, clear=False):
            payload, status = MODULE.command_payload(
                {"command": "abre a Calculadora"},
                owner_authenticated=False,
            )
        self.assertEqual(status, 401)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["pairing_required"])
        self.assertNotIn(env["JARVIS_OWNER_TOKEN"], json.dumps(payload))

    def test_paired_remote_device_action_enters_supabase_queue(self):
        class FakeSupabaseResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps([{
                    "id": 91,
                    "action": "open_application",
                    "target": "Calculator",
                    "status": "pending",
                }]).encode("utf-8")

        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeSupabaseResponse()) as request:
                payload, status = MODULE.command_payload(
                    {"command": "abre a Calculadora"},
                    owner_authenticated=True,
                )
        self.assertEqual(status, 202)
        self.assertEqual(payload["status_real"], "device_command_queued")
        self.assertEqual(payload["job"]["id"], 91)
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.method, "POST")
        self.assertIn("/rest/v1/jarvis_device_commands", sent_request.full_url)

    def test_self_edit_routes_only_to_paired_local_worker(self):
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        with patch.dict(os.environ, env, clear=False):
            blocked, blocked_status = MODULE.command_payload(
                {"command": "melhore seus próprios scripts de diagnóstico"},
                owner_authenticated=False,
            )
            self.assertEqual(blocked_status, 401)
            self.assertTrue(blocked["pairing_required"])
            with patch.object(MODULE, "supabase_device_enqueue", return_value=({
                "ok": True,
                "intent": "self_edit",
                "status_real": "device_command_queued",
            }, 202)) as enqueue:
                payload, status = MODULE.command_payload(
                    {"command": "melhore seus próprios scripts de diagnóstico"},
                    owner_authenticated=True,
                )
        self.assertEqual(status, 202)
        self.assertEqual(payload["intent"], "self_edit")
        enqueue.assert_called_once_with("melhore seus próprios scripts de diagnóstico", "self_edit")

    def test_create_in_jarvis_and_deploy_routes_to_self_edit_worker(self):
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        command = "crie um painel de diagnóstico no jarvis, publique e faça deploy"
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE,
            "supabase_device_enqueue",
            return_value=({
                "ok": True,
                "intent": "self_edit",
                "status_real": "device_command_queued",
            }, 202),
        ) as enqueue:
            payload, status = MODULE.command_payload(
                {"command": command},
                owner_authenticated=True,
            )
        self.assertEqual(status, 202)
        self.assertEqual(payload["intent"], "self_edit")
        enqueue.assert_called_once_with(command, "self_edit")

    def test_voice_design_requires_pairing_and_routes_to_real_provider(self):
        env = {"JARVIS_OWNER_TOKEN": "owner-pairing-test-value"}
        command = "crie uma voz própria para você"
        with patch.dict(os.environ, env, clear=False):
            blocked, blocked_status = MODULE.command_payload(
                {"command": command}, owner_authenticated=False
            )
            self.assertEqual(blocked_status, 401)
            self.assertTrue(blocked["pairing_required"])
            expected = {
                "ok": True,
                "status_real": "elevenlabs_voice_created",
                "intent": "voice_design",
            }
            with patch.object(MODULE, "elevenlabs_voice_design", return_value=(expected, 201)) as design:
                payload, status = MODULE.command_payload(
                    {"command": command}, owner_authenticated=True
                )
        self.assertEqual(status, 201)
        self.assertEqual(payload["status_real"], "elevenlabs_voice_created")
        design.assert_called_once_with(command)

    def test_voice_design_creates_and_persists_returned_voice_id(self):
        class FakeJsonResponse:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps(self.payload).encode("utf-8")

        env = {
            "ELEVENLABS_API_KEY": "elevenlabs-test-key-value",
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }
        responses = [
            FakeJsonResponse({"previews": [{"generated_voice_id": "generated_voice_123"}]}),
            FakeJsonResponse({"voice_id": "created_voice_456"}),
        ]
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "supabase_request", return_value=[]
        ), patch.object(MODULE, "urlopen", side_effect=responses) as provider, patch.object(
            MODULE, "persist_active_voice", return_value={}
        ) as persist:
            payload, status = MODULE.elevenlabs_voice_design("crie uma voz própria para você")
        self.assertEqual(status, 201)
        self.assertEqual(payload["voice"]["id"], "created_voice_456")
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(provider.call_args_list[0].args[0].full_url, MODULE.ELEVENLABS_VOICE_DESIGN_URL)
        self.assertEqual(provider.call_args_list[1].args[0].full_url, MODULE.ELEVENLABS_VOICE_CREATE_URL)
        persist.assert_called_once()
        self.assertEqual(persist.call_args.args[0], "created_voice_456")

    def test_device_command_status_uses_persisted_result(self):
        class FakeSupabaseResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps([{
                    "id": 91,
                    "action": "open_application",
                    "target": "Calculator",
                    "status": "succeeded",
                    "result": "Aplicativo aberto e confirmado.",
                    "created_at": "2026-08-07T12:00:00Z",
                    "claimed_at": "2026-08-07T12:00:01Z",
                    "completed_at": "2026-08-07T12:00:02Z",
                }]).encode("utf-8")

        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeSupabaseResponse()):
                payload, status = MODULE.supabase_device_command("91")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "device_command_succeeded")
        self.assertEqual(payload["job"]["result"], "Aplicativo aberto e confirmado.")
        self.assertTrue(payload["job"]["terminal"])

    def test_pending_device_action_can_be_canceled_with_evidence(self):
        saved = [{
            "id": 91,
            "action": "open_application",
            "target": "Calculator",
            "status": "canceled",
            "completed_at": "2026-08-08T12:00:00Z",
        }]
        with patch.object(MODULE, "supabase_request", return_value=saved) as request:
            payload, status = MODULE.supabase_device_cancel("91")
        self.assertEqual(status, 200)
        self.assertEqual(payload["job"]["status"], "canceled")
        self.assertTrue(payload["job"]["terminal"])
        args, kwargs = request.call_args
        self.assertEqual(args[0], "PATCH")
        self.assertIn("status=eq.pending", kwargs["query"])
        self.assertEqual(kwargs["body"]["status"], "canceled")

    def test_device_cancel_refuses_when_job_is_no_longer_pending(self):
        with patch.object(MODULE, "supabase_request", return_value=[]):
            payload, status = MODULE.supabase_device_cancel("91")
        self.assertEqual(status, 409)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status_real"], "device_command_cancel_too_late")

    def test_status_reports_pairing_without_exposing_token(self):
        with patch.dict(os.environ, {"JARVIS_OWNER_TOKEN": "owner-pairing-test-value"}, clear=False):
            payload = MODULE.status_payload(owner_authenticated=True)
        self.assertTrue(payload["owner_pairing"]["required"])
        self.assertTrue(payload["owner_pairing"]["authenticated"])
        self.assertNotIn("owner-pairing-test-value", json.dumps(payload))

    def test_paired_personal_tools_enter_allowlisted_queue(self):
        class FakeSupabaseResponse:
            next_id = 120

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                FakeSupabaseResponse.next_id += 1
                return json.dumps([{
                    "id": FakeSupabaseResponse.next_id,
                    "status": "pending",
                }]).encode("utf-8")

        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        commands = {
            "screen_capture": "tira um print da tela",
            "storage_scan": "mostra os arquivos grandes do armazenamento",
            "message_send": 'mande mensagem para 5511999999999 "teste real"',
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(MODULE, "urlopen", side_effect=lambda *_args, **_kwargs: FakeSupabaseResponse()) as request:
                results = {
                    intent: MODULE.command_payload(
                        {"command": command},
                        owner_authenticated=True,
                    )
                    for intent, command in commands.items()
                }
        for intent, (payload, status) in results.items():
            self.assertEqual(status, 202)
            self.assertEqual(payload["intent"], intent)
            self.assertEqual(payload["status_real"], "device_command_queued")
        self.assertEqual(results["storage_scan"][0]["job"]["target"], "Downloads")
        self.assertEqual(results["message_send"][0]["job"]["target"], "…9999")
        message_request = request.call_args_list[-1].args[0]
        stored = json.loads(message_request.data.decode("utf-8"))
        self.assertEqual(stored["target"], "5511999999999")

    def test_message_queue_requires_exact_phone_and_body(self):
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        with patch.dict(os.environ, env, clear=False):
            payload, status = MODULE.command_payload(
                {"command": "mande mensagem dizendo oi"},
                owner_authenticated=True,
            )
        self.assertEqual(status, 400)
        self.assertEqual(payload["status_real"], "message_details_missing")

    def test_open_app_can_execute_local_computer_adapter(self):
        completed = MODULE.subprocess.CompletedProcess(
            args=["./jarvis", "computer", "open", "Google Chrome"],
            returncode=0,
            stdout="OK — Google Chrome aberto e confirmado.",
            stderr="",
        )
        with patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            payload, status = MODULE.command_payload(
                {"command": "abre o Chrome"},
                local_execute=True,
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "local_action_executed")
        self.assertEqual(run.call_args.args[0], completed.args)

    def test_local_device_request_can_execute_allowlisted_worker(self):
        completed = MODULE.subprocess.CompletedProcess(
            args=["./jarvis", "do", "tirar um print da tela"],
            returncode=0,
            stdout="Status real: captura concluída",
            stderr="",
        )
        with patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            payload, status = MODULE.command_payload(
                {"command": "tirar um print da tela"},
                local_execute=True,
            )
        self.assertEqual(status, 200)
        self.assertTrue(payload["executed_locally"])
        self.assertEqual(payload["status_real"], "local_action_executed")
        run.assert_called_once()

    def test_message_send_routes_to_local_worker(self):
        payload, status = MODULE.command_payload(
            {"command": "mandar mensagem para 5511999999999 dizendo teste local"},
            local_execute=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "message_send")
        self.assertTrue(payload["requires_local_worker"])

    def test_slow_mac_routes_to_real_memory_diagnostic(self):
        payload, status = MODULE.command_payload(
            {"command": "meu computador está travando, olha a memória"},
            local_execute=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "system_memory")
        self.assertEqual(payload["local_command"], "./jarvis system-memory")

    def test_explicit_jarvis_cleanup_stays_scoped(self):
        payload, status = MODULE.command_payload(
            {"command": "limpa os processos temporários do jarvis"},
            local_execute=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "system_memory")
        self.assertEqual(
            payload["local_command"],
            "./jarvis system-memory --cleanup-jarvis",
        )

    def test_remote_jarvis_cleanup_reaches_worker_with_explicit_scope(self):
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE,
            "supabase_request",
            return_value=[{"id": 91, "status": "pending"}],
        ) as request:
            payload, status = MODULE.command_payload(
                {"command": "limpa os processos temporários do jarvis"},
                owner_authenticated=True,
            )
        self.assertEqual(status, 202)
        self.assertEqual(payload["intent"], "system_memory")
        self.assertEqual(payload["job"]["target"], "jarvis-temporaries")
        self.assertEqual(request.call_args.kwargs["body"]["target"], "jarvis-temporaries")

    def test_broad_mac_cleanup_remains_diagnostic_only(self):
        payload, status = MODULE.command_payload(
            {"command": "limpa os processos do Mac"},
            local_execute=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "system_memory")
        self.assertEqual(payload["local_command"], "./jarvis system-memory")

    def test_memory_save_executes_and_opens_memory_visual(self):
        completed = MODULE.subprocess.CompletedProcess(
            args=["./jarvis", "memory-save", "o busto deve continuar na frente", "--kind", "learning"],
            returncode=0,
            stdout="Mem\u00f3ria criada: 03_MEMORIA/01_APRENDIZADOS/item.md",
            stderr="",
        )
        with patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            payload, status = MODULE.command_payload(
                {"command": "guarde na mem\u00f3ria que o busto deve continuar na frente"},
                local_execute=True,
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "memory_save")
        self.assertEqual(payload["visual_state"], "memory")
        self.assertTrue(payload["executed_locally"])
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], completed.args)

    def test_memory_save_handoff_opens_memory_visual(self):
        payload, status = MODULE.command_payload(
            {"command": "guarde na memória como preferência: respostas curtas"},
            local_execute=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "memory_save")
        self.assertEqual(payload["visual_state"], "memory")
        self.assertTrue(payload["requires_local_worker"])
        self.assertEqual(
            payload["local_command"],
            "./jarvis memory-save 'respostas curtas' --kind preference",
        )

    def test_supabase_memory_save_returns_persisted_evidence(self):
        class FakeSupabaseResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps([{
                    "id": 42,
                    "kind": "preference",
                    "content": "respostas curtas",
                    "created_at": "2026-08-07T12:00:00Z",
                }]).encode("utf-8")

        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeSupabaseResponse()) as request:
                payload, status = MODULE.command_payload({
                    "command": "guarde na memória como preferência: respostas curtas"
                })
        self.assertEqual(status, 201)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status_real"], "supabase_memory_persisted")
        self.assertEqual(payload["memory"]["id"], 42)
        self.assertNotIn("private-supabase-key", json.dumps(payload))
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.method, "POST")
        self.assertIn("/rest/v1/jarvis_memories", sent_request.full_url)
        sent_row = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(sent_row["metadata"]["schema_version"], 2)
        self.assertEqual(sent_row["metadata"]["layer"], "owner")

    def test_supabase_memory_tree_reads_real_rows(self):
        class FakeSupabaseResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps([{
                    "id": 42,
                    "kind": "learning",
                    "content": "o busto fica na frente",
                    "source": "jarvis-web",
                    "created_at": "2026-08-07T12:00:00Z",
                }]).encode("utf-8")

        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeSupabaseResponse()):
                payload = MODULE.memory_tree_payload()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["provider"], "supabase")
        self.assertTrue(payload["persistent_write"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["nodes"][0]["label"], "o busto fica na frente")
        self.assertEqual(payload["nodes"][0]["layer"], "discussion")

    def test_memory_ranking_prefers_relevance_and_owner_preferences(self):
        rows = [
            {"id": 1, "kind": "learning", "content": "usar azul no avatar", "metadata": {"layer": "project"}},
            {"id": 2, "kind": "learning", "content": "reunião amanhã às nove", "metadata": {"layer": "daily"}},
            {"id": 3, "kind": "preference", "content": "Theo prefere respostas curtas", "metadata": {"layer": "owner"}},
            {"id": 4, "kind": "decision", "content": "deploy do projeto JARVIS na Vercel", "metadata": {"layer": "project"}},
        ]
        ranked = MODULE.rank_memory_rows(rows, "como está o deploy na Vercel?", 3)
        self.assertEqual(ranked[0]["id"], 4)
        self.assertIn(3, [row["id"] for row in ranked])
        self.assertEqual(ranked[0]["layer"], "project")

    def test_memory_layer_classification(self):
        self.assertEqual(MODULE.memory_layer("prefiro respostas curtas", "preference"), "owner")
        self.assertEqual(MODULE.memory_layer("deploy do projeto na Vercel", "decision"), "project")
        self.assertEqual(MODULE.memory_layer("reunião amanhã às nove", "learning"), "daily")

    def test_proactive_pulse_returns_only_one_confirmable_matter(self):
        rows = [
            {"id": 7, "title": "Revisar apresentação", "scheduled_for": "2026-08-08T13:00:00Z"},
            {"id": 8, "title": "Segunda tarefa", "scheduled_for": "2026-08-08T14:00:00Z"},
        ]
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }
        now = datetime.fromisoformat("2026-08-08T12:00:00+00:00")
        with patch.dict(os.environ, env, clear=False), patch.object(MODULE, "supabase_agenda_rows", return_value=rows):
            payload = MODULE.proactive_pulse_payload(owner_authenticated=True, now=now)
        self.assertEqual(payload["status_real"], "proactive_pulse_has_matter")
        self.assertEqual(payload["suggestion"]["message"], "Revisar apresentação · 08/08 às 10:00")
        self.assertTrue(payload["suggestion"]["requires_confirmation"])
        self.assertFalse(payload["writes"])

    def test_proactive_pulse_stays_quiet_without_backend(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""}, clear=False):
            payload = MODULE.proactive_pulse_payload()
        self.assertIsNone(payload["suggestion"])
        self.assertEqual(payload["status_real"], "proactive_pulse_quiet")

    def test_memory_save_never_claims_success_without_file_evidence(self):
        completed = MODULE.subprocess.CompletedProcess(
            args=["./jarvis", "memory-save", "respostas curtas", "--kind", "learning"],
            returncode=0,
            stdout="Comando finalizado sem arquivo.",
            stderr="",
        )
        with patch.object(MODULE.subprocess, "run", return_value=completed):
            payload, status = MODULE.command_payload(
                {"command": "guarde na memória que respostas devem ser curtas"},
                local_execute=True,
            )
        self.assertEqual(status, 200)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status_real"], "local_action_failed")
        self.assertEqual(payload["visual_state"], "error")

    def test_unconfigured_ai_uses_deterministic_plan(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
            status, _, payload = self.json_request(
                "/command", "POST", {"command": "planeje minha semana"}
            )
        self.assertEqual(status, 200)
        self.assertFalse(payload["ai_configured"])
        self.assertGreaterEqual(len(payload["steps"]), 4)

    def test_openrouter_response_returns_to_speaking_visual(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "Resposta conectada."}}],
                }).encode("utf-8")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeResponse()) as request:
                payload, status = MODULE.assistant_response({"command": "converse comigo"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "openrouter")
        self.assertEqual(payload["visual_state"], "response")
        self.assertEqual(payload["message"], "Resposta conectada.")
        sent_request = request.call_args.args[0]
        sent_payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(sent_payload["temperature"], 0.65)
        self.assertEqual(sent_payload["max_tokens"], 900)
        system_prompt = sent_payload["messages"][0]["content"]
        self.assertIn("humor seco", system_prompt)
        self.assertIn("até três frases", system_prompt)
        self.assertIn("porcentagem de confiança somente", system_prompt)
        self.assertIn("não use rótulos burocráticos", system_prompt)
        self.assertIn("nunca diga que não possui voz", system_prompt.casefold())

    def test_openrouter_can_suggest_real_memory_without_saving_it(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "Entendido. Vou manter isso em mente."}}],
                }).encode("utf-8")

        preference = "Eu prefiro respostas curtas e diretas."
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeResponse()):
                payload, status = MODULE.assistant_response({"command": preference})
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "openrouter")
        self.assertEqual(payload["visual_state"], "memory")
        self.assertEqual(payload["memory_suggestion"], preference)
        self.assertNotIn("executed_locally", payload)

    def test_pdf_attachment_uses_official_openrouter_file_contract(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "O PDF contém um teste."}}],
                }).encode("utf-8")

        encoded = base64.b64encode(b"%PDF-1.4\ntest document").decode("ascii")
        attachment = {
            "name": "brief.pdf",
            "type": "application/pdf",
            "size": 22,
            "data_url": f"data:application/pdf;base64,{encoded}",
        }
        env = {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_ATTACHMENT_MODEL": "openrouter/free",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeResponse()) as request:
                payload, status = MODULE.command_payload({
                    "command": "resuma este documento",
                    "attachments": [attachment],
                })
        self.assertEqual(status, 200)
        self.assertEqual(payload["attachments_received"][0]["name"], "brief.pdf")
        sent = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent["model"], "openrouter/free")
        self.assertEqual(sent["messages"][-1]["content"][0], {"type": "text", "text": "resuma este documento"})
        file_part = sent["messages"][-1]["content"][1]
        self.assertEqual(file_part["type"], "file")
        self.assertEqual(file_part["file"]["filename"], "brief.pdf")
        self.assertTrue(file_part["file"]["file_data"].startswith("data:application/pdf;base64,"))
        self.assertEqual(sent["plugins"][0]["pdf"]["engine"], "cloudflare-ai")

    def test_text_attachment_with_secret_is_refused_before_provider(self):
        secret = "api_key=" + ("x" * 24)
        encoded = base64.b64encode(secret.encode("utf-8")).decode("ascii")
        payload, status = MODULE.assistant_response({
            "command": "leia o arquivo",
            "attachments": [{
                "name": "config.txt",
                "type": "text/plain",
                "data_url": f"data:text/plain;base64,{encoded}",
            }],
        })
        self.assertEqual(status, 400)
        self.assertEqual(payload["status_real"], "attachment_refused")
        self.assertNotIn(secret, json.dumps(payload))

    def test_elevenlabs_speech_returns_audio_without_exposing_key(self):
        class FakeAudioResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return b"ID3-test-audio"

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "private-test-key"}, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeAudioResponse()) as request:
                audio, status = MODULE.elevenlabs_speech({"text": "Olá, Theo."})
        self.assertEqual(status, 200)
        self.assertTrue(audio.startswith(b"ID3"))
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.headers["Xi-api-key"], "private-test-key")
        sent_payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(sent_payload["language_code"], "pt")
        self.assertEqual(sent_payload["model_id"], "eleven_flash_v2_5")
        self.assertEqual(sent_payload["voice_settings"]["stability"], 0.38)
        self.assertFalse(sent_payload["voice_settings"]["use_speaker_boost"])
        self.assertEqual(sent_payload["voice_settings"]["speed"], 1.04)

    def test_missing_elevenlabs_key_stays_text_only(self):
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}, clear=False):
            payload, status = MODULE.elevenlabs_speech({"text": "Olá, Theo."})
        self.assertEqual(status, 503)
        self.assertEqual(payload["fallback"], "text_only")

    def test_elevenlabs_quota_error_is_reported_honestly(self):
        provider_error = HTTPError("https://api.elevenlabs.io", 402, "payment required", {}, None)
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "private-test-key"}, clear=False):
            with patch.object(MODULE, "urlopen", side_effect=provider_error):
                payload, status = MODULE.elevenlabs_speech({"text": "Olá, Theo."})
        self.assertEqual(status, 502)
        self.assertEqual(payload["error_code"], "elevenlabs_quota")
        self.assertIn("sem créditos", payload["error"])
        self.assertEqual(payload["fallback"], "text_only")

    def test_agenda_routes_to_configured_n8n_webhook(self):
        class FakeN8nResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps({"message": "Evento criado na agenda."}).encode("utf-8")

        env = {"N8N_WEBHOOK_URL": "https://n8n.example.test/webhook/jarvis"}
        with patch.dict(os.environ, env, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeN8nResponse()):
                payload, status = MODULE.command_payload(
                    {"command": "adiciona reunião amanhã na agenda"}
                )
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "n8n")
        self.assertEqual(payload["message"], "Evento criado na agenda.")

    def test_agenda_uses_private_supabase_fallback_without_n8n(self):
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "N8N_WEBHOOK_URL": "",
        }
        saved = [{"id": 7, "title": "comprar ração amanhã", "status": "pending"}]
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "supabase_request", return_value=saved
        ) as request:
            payload, status = MODULE.command_payload(
                {"command": "coloca na agenda comprar ração amanhã"}
            )
        self.assertEqual(status, 201)
        self.assertEqual(payload["provider"], "supabase_agenda")
        self.assertEqual(payload["agenda"][0]["title"], "comprar ração amanhã")
        self.assertEqual(request.call_args.kwargs["table"], MODULE.SUPABASE_AGENDA_TABLE)

    def test_agenda_schedule_uses_sao_paulo_dates_and_times(self):
        now = datetime(2026, 8, 7, 14, 0, tzinfo=MODULE.ZoneInfo("America/Sao_Paulo"))
        tomorrow = MODULE.agenda_schedule("coloca na agenda reunião amanhã às 15h", now=now)
        monday = MODULE.agenda_schedule("marca revisão segunda às 09:30", now=now)
        no_date = MODULE.agenda_schedule("coloca na agenda comprar café", now=now)
        self.assertEqual(tomorrow, "2026-08-08T18:00:00Z")
        self.assertEqual(monday, "2026-08-10T12:30:00Z")
        self.assertEqual(no_date, "")

    def test_agenda_complete_updates_exact_pending_item(self):
        saved = [{
            "id": 17,
            "title": "comprar ração amanhã",
            "status": "done",
            "scheduled_for": "2026-08-08T12:00:00Z",
        }]
        with patch.object(MODULE, "supabase_request", return_value=saved) as request:
            payload, status = MODULE.supabase_agenda_command(
                "conclui a tarefa 17", "agenda_complete"
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "supabase_agenda_completed")
        self.assertEqual(request.call_args.args[0], "PATCH")
        self.assertIn("id=eq.17", request.call_args.kwargs["query"])
        self.assertEqual(request.call_args.kwargs["body"]["status"], "done")

    def test_contact_alias_is_persisted_and_resolved_for_message_queue(self):
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        contact_row = [{
            "id": 3,
            "alias": "arthur",
            "display_name": "Arthur",
            "phone": "5511999999999",
        }]
        queued_row = [{"id": 131, "status": "pending"}]
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "supabase_request", side_effect=[contact_row, queued_row]
        ) as request:
            payload, status = MODULE.command_payload(
                {"command": "manda mensagem para Arthur dizendo estou chegando"},
                owner_authenticated=True,
            )
        self.assertEqual(status, 202)
        self.assertEqual(payload["job"]["target"], "…9999")
        queued = request.call_args_list[1].kwargs["body"]
        self.assertEqual(queued["target"], "5511999999999")
        self.assertNotIn("5511999999999", json.dumps(payload))

    def test_contact_save_masks_phone_in_public_payload(self):
        saved = [{"id": 3, "alias": "arthur", "display_name": "Arthur", "phone": "5511999999999"}]
        with patch.object(MODULE, "supabase_request", return_value=saved):
            payload, status = MODULE.supabase_contact_save(
                "salva o contato Arthur 5511999999999"
            )
        self.assertEqual(status, 201)
        self.assertEqual(payload["contact"]["phone"], "…9999")
        self.assertNotIn("5511999999999", json.dumps(payload))

    def test_contact_archive_is_soft_delete_and_contact_list_filters_it(self):
        archived = [{"id": 3, "display_name": "Arthur", "alias": "arthur"}]
        with patch.object(MODULE, "supabase_request", return_value=archived) as request:
            payload, status = MODULE.supabase_contact_archive("arquiva o contato Arthur")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "supabase_contact_archived")
        self.assertIsNotNone(request.call_args.kwargs["body"]["archived_at"])
        with patch.object(MODULE, "supabase_request", return_value=[]) as list_request:
            listed, list_status = MODULE.contacts_payload(50)
        self.assertEqual(list_status, 200)
        self.assertEqual(listed["count"], 0)
        self.assertIn("archived_at=is.null", list_request.call_args.kwargs["query"])

    def test_device_command_returns_only_short_lived_signed_artifact(self):
        row = [{
            "id": 99,
            "action": "screen_capture",
            "target": "",
            "status": "succeeded",
            "result": "captura confirmada",
            "artifact_path": "theo/99-screen.png",
            "artifact_mime": "image/png",
        }]
        with patch.object(MODULE, "supabase_request", return_value=row), patch.object(
            MODULE, "signed_artifact_url", return_value="https://signed.example/preview"
        ) as signer:
            payload, status = MODULE.supabase_device_command("99")
        self.assertEqual(status, 200)
        self.assertEqual(payload["job"]["artifact_url"], "https://signed.example/preview")
        self.assertNotIn("artifact_path", payload["job"])
        signer.assert_called_once_with("theo/99-screen.png")

    def test_device_history_masks_message_target(self):
        rows = [{
            "id": 12,
            "action": "message_send",
            "target": "5511999999999",
            "status": "succeeded",
            "result": "mensagem enviada",
        }]
        with patch.object(MODULE, "supabase_request", return_value=rows):
            payload, status = MODULE.device_history_payload(8)
        self.assertEqual(status, 200)
        self.assertEqual(payload["history"][0]["target"], "…9999")
        self.assertNotIn("5511999999999", json.dumps(payload))

    def test_memory_tree_is_read_only_and_structured(self):
        status, _, payload = self.json_request("/memory-tree")
        self.assertEqual(status, 200)
        self.assertEqual(payload["visual_state"], "memory")
        self.assertFalse(payload["persistent_write"])
        self.assertIsInstance(payload["nodes"], list)
        self.assertIsInstance(payload["edges"], list)

        status, _, payload = self.json_request(
            "/command", "POST", {"command": "mostra minhas mem\u00f3rias"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["mode"], "memory")
        self.assertEqual(payload["visual_state"], "memory")

    def test_secret_like_prompt_is_refused(self):
        fake = "sk-" + "or-" + "v1-" + ("x" * 20)
        status, _, payload = self.json_request(
            "/command", "POST", {"command": f"use {fake}"}
        )
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])

    def test_vercel_rewrite_path_and_asset_traversal(self):
        vercel_config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(
            vercel_config["rewrites"][0],
            {"source": "/", "destination": "/api/index?jarvis_path=/"},
        )

        status, _, payload = self.json_request(
            "/api/index?jarvis_path=/capabilities"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["endpoint"], "GET /capabilities")

        status, _, payload = self.json_request("/asset/../../README.md")
        self.assertIn(status, {403, 404})
        self.assertFalse(payload["ok"])

        status, _, payload = self.json_request("/ui/../../README.md")
        self.assertIn(status, {403, 404})
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
