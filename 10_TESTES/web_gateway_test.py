#!/usr/bin/env python3
"""Contract tests for the stdlib-only JARVIS web gateway."""

from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import importlib.util
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
        self.assertIn("n8n", payload["automations"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_cockpit_and_model_asset(self):
        status, _, html = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"JARVIS", html)
        self.assertIn(b'id="voiceButton"', html)
        self.assertIn(b'id="avatar3d"', html)
        self.assertIn(b'id="liveSurface"', html)
        self.assertIn(b'/ui/vendor/three.module.js', html)
        self.assertNotIn(b'unpkg.com', html)

        status, headers, app_js = self.request("/ui/jarvis.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"SpeechRecognition", app_js)

        status, headers, visual_js = self.request("/ui/jarvis-3d.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"drawMemory", visual_js)

        status, headers, three_js = self.request("/ui/vendor/three.module.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertGreater(len(three_js), 1_000_000)

        status, headers, css = self.request("/ui/jarvis.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".hud-rail", css)

        status, _, favicon = self.request("/favicon.ico")
        self.assertEqual(status, 200)
        self.assertEqual(favicon, b"")

        status, headers, model = self.request("/asset/models/jarvis-humanoid.glb")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "model/gltf-binary")
        self.assertGreater(len(model), 100_000)

    def test_local_device_request_becomes_handoff(self):
        status, _, payload = self.json_request(
            "/command", "POST", {"command": "tirar um print da tela"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "screen_capture")
        self.assertTrue(payload["requires_local_worker"])
        self.assertTrue(payload["local_command"].startswith("./jarvis do "))

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

    def test_memory_save_executes_and_opens_memory_visual(self):
        completed = MODULE.subprocess.CompletedProcess(
            args=["./jarvis", "do", "guarda isso na mem\u00f3ria"],
            returncode=0,
            stdout="Mem\u00f3ria criada: 03_MEMORIA/01_APRENDIZADOS/item.md",
            stderr="",
        )
        with patch.object(MODULE.subprocess, "run", return_value=completed):
            payload, status = MODULE.command_payload(
                {"command": "guarda isso na mem\u00f3ria"},
                local_execute=True,
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "memory_save")
        self.assertEqual(payload["visual_state"], "memory")
        self.assertTrue(payload["executed_locally"])

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
            with patch.object(MODULE, "urlopen", return_value=FakeResponse()):
                payload, status = MODULE.assistant_response({"command": "converse comigo"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "openrouter")
        self.assertEqual(payload["visual_state"], "response")
        self.assertEqual(payload["message"], "Resposta conectada.")

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
