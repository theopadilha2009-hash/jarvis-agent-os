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
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MODULE.handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

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
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_cockpit_and_model_asset(self):
        status, _, html = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"JARVIS", html)

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

    def test_unconfigured_ai_uses_deterministic_plan(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
            status, _, payload = self.json_request(
                "/command", "POST", {"command": "planeje minha semana"}
            )
        self.assertEqual(status, 200)
        self.assertFalse(payload["ai_configured"])
        self.assertGreaterEqual(len(payload["steps"]), 4)

    def test_secret_like_prompt_is_refused(self):
        fake = "sk-" + "or-" + "v1-" + ("x" * 20)
        status, _, payload = self.json_request(
            "/command", "POST", {"command": f"use {fake}"}
        )
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])

    def test_vercel_rewrite_path_and_asset_traversal(self):
        status, _, payload = self.json_request(
            "/api/index?jarvis_path=/capabilities"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["endpoint"], "GET /capabilities")

        status, _, payload = self.json_request("/asset/../../README.md")
        self.assertIn(status, {403, 404})
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
