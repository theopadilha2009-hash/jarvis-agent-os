#!/usr/bin/env python3
"""Contract tests for the stdlib-only JARVIS web gateway."""

from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import base64
import hashlib
import importlib.util
from datetime import datetime
import json
import os
import re
import threading
import time
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory


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
        cls.runtime_temp = TemporaryDirectory()
        runtime_root = Path(cls.runtime_temp.name)
        cls.previous_agent_runs = MODULE.AGENT_RUNS
        cls.previous_memory_index = MODULE.LOCAL_MEMORY_INDEX
        cls.previous_agent_run_dir = os.environ.get("JARVIS_AGENT_RUN_DIR")
        os.environ["JARVIS_AGENT_RUN_DIR"] = str(runtime_root / "runs")
        MODULE.AGENT_RUNS = MODULE.RunStore(runtime_root / "runs")
        MODULE.LOCAL_MEMORY_INDEX = MODULE.MemoryIndex(runtime_root / "memory.sqlite3")
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
        MODULE.AGENT_RUNS = cls.previous_agent_runs
        MODULE.LOCAL_MEMORY_INDEX = cls.previous_memory_index
        if cls.previous_agent_run_dir is None:
            os.environ.pop("JARVIS_AGENT_RUN_DIR", None)
        else:
            os.environ["JARVIS_AGENT_RUN_DIR"] = cls.previous_agent_run_dir
        cls.runtime_temp.cleanup()

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
        self.assertIn("access", payload)
        self.assertIn("public_chat", payload["access"])
        self.assertEqual(payload["agent_runtime"]["execution"], "verified_adapters")
        self.assertFalse(payload["agent_runtime"]["arbitrary_shell"])
        self.assertTrue(payload["memory"]["configured"])
        self.assertTrue(payload["memory"]["persistent"])
        self.assertEqual(payload["memory"]["index"], "sqlite_runtime_over_markdown")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_client_disconnect_during_asset_write_is_ignored(self):
        class ClosedPipe:
            def write(self, _body):
                raise BrokenPipeError("browser closed the tab")

        class FakeHandler:
            wfile = ClosedPipe()

        MODULE.handler._write_body(FakeHandler(), b"model bytes")

    def test_command_stream_emits_lifecycle_deltas_and_canonical_result(self):
        status, headers, raw = self.request(
            "/command-stream",
            "POST",
            {"command": "crie um plano curto para organizar a semana"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "application/x-ndjson")
        self.assertEqual(headers["X-Jarvis-Stream"], "jarvis-stream/1")
        events = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
        self.assertEqual(events[0]["type"], "stream.start")
        self.assertTrue(any(event["type"] == "stream.phase" for event in events))
        self.assertTrue(any(event["type"] == "stream.delta" for event in events))
        self.assertEqual(events[-1]["type"], "stream.result")
        self.assertIn("event_stream", events[-1]["payload"])

    def test_cockpit_and_model_asset(self):
        status, _, html = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"JARVIS", html)
        self.assertIn(b'id="voiceButton"', html)
        self.assertIn(b'id="commandInput"', html)
        self.assertIn(b'<svg aria-hidden="true" viewBox="0 0 24 24">', html)
        self.assertIn(b'id="muteButton"', html)
        self.assertIn(b'id="avatar3d"', html)
        self.assertIn(b'id="liveSurface"', html)
        self.assertIn(b'id="conversationState"', html)
        self.assertIn(b'class="identity-logo"', html)
        self.assertIn(b'/ui/jarvis-logo.png?v=20260813-logonative1', html)
        self.assertIn(b'/ui/api-vault.js?v=20260813-ultronfix1', html)
        self.assertIn(b'/ui/integration-history.js?v=20260813-ultronfix1', html)
        self.assertIn(b'/ui/feature-loader.js?v=20260815-vozes2', html)
        self.assertNotIn(b'/ui/integration-health.js?v=', html)
        self.assertIn(b'/ui/device-feedback.js?v=20260813-device1', html)
        self.assertIn(b'/ui/jarvis.js?v=20260815-vozes2', html)
        self.assertIn(b'/ui/shell.css?v=20260815-vozes2', html)
        self.assertIn(b'/ui/jarvis.css?v=20260815-vozes2', html)
        self.assertIn(b'/ui/ui-repair.css?v=20260815-vozes2', html)
        self.assertIn(b'/ui/api-panel.css?v=20260813-ultronfix1', html)
        self.assertNotIn(b'/ui/integration-health.css?v=', html)
        self.assertIn(b'/ui/responsive-polish.css?v=20260815-vozes2', html)
        self.assertIn(b'/ui/presence-loader.js?v=20260813-ultronfix1', html)
        self.assertIn(b'/ui/manifest.webmanifest?v=20260813-apitools1', html)
        self.assertIn(b'viewport-fit=cover', html)
        self.assertIn(b'interactive-widget=resizes-content', html)
        self.assertIn(b'id="stateBeacon"', html)
        self.assertIn(b'id="accessMode"', html)
        self.assertIn(b'id="filePreview"', html)
        self.assertIn(b'id="leaveOwnerMode"', html)
        self.assertIn(b'id="pulseButton"', html)
        self.assertIn(b'id="attachmentInput"', html)
        self.assertIn(b'id="attachmentTray"', html)
        self.assertIn(b'id="actionHub"', html)
        self.assertIn(b'id="tourDialog"', html)
        self.assertIn(b'id="adminLoginButton"', html)
        self.assertIn(b'id="requestProgress"', html)
        self.assertIn(b'id="shimmerLoader"', html)
        self.assertIn(b'id="starterActions"', html)
        self.assertIn(b'id="mobileChatToggle"', html)
        self.assertIn(b'id="newConversationButton"', html)
        self.assertIn(b'id="qualityButton"', html)
        self.assertIn(b'id="installButton"', html)
        self.assertIn(b'id="installDialog"', html)
        self.assertIn(b'id="integrationsButton"', html)
        self.assertIn(b'id="integrationsDialog"', html)
        self.assertIn(b'id="n8nStudio"', html)
        self.assertIn(b'id="actionHubOverview"', html)
        self.assertIn(b'id="sceneObjective"', html)
        self.assertIn(b'id="sceneCommandButton"', html)
        self.assertIn(b'id="sceneRender"', html)
        self.assertIn(b'id="hubMemoryValue"', html)
        self.assertIn(b'id="hubAgendaValue"', html)
        self.assertIn("Peça. Eu executo.".encode(), html)
        self.assertIn(b'/ui/vendor/three.module.js', html)
        self.assertNotIn(b"requestIdleCallback", html)
        self.assertNotIn(b"fallback-core", html)
        self.assertNotIn(b'unpkg.com', html)
        self.assertIn(b'id="auroraVisual"', html)
        self.assertIn(b'id="strandsVisual"', html)

        status, headers, app_js = self.request("/ui/jarvis.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"SpeechRecognition", app_js)
        self.assertIn(b'input_mode: options.source || "text"', app_js)
        self.assertIn("speakBrowser".encode(), app_js)
        self.assertIn("Voz do navegador".encode(), app_js)
        self.assertIn(b"memory-command", app_js)
        self.assertIn(b"X-Jarvis-Owner-Token", app_js)
        self.assertIn(b"monitorDeviceCommand", app_js)
        self.assertIn(b"monitorDeviceRun", app_js)
        self.assertIn(b"devicePollDelay", app_js)
        self.assertIn(b"JarvisDeviceFeedback", app_js)
        self.assertIn(b"/device-run?ids=", app_js)
        self.assertIn(b"refreshPersonalOverview", app_js)
        self.assertIn(b'"/personal-overview"', app_js)
        self.assertIn(b"saveOwnerToken", app_js)
        self.assertIn(b"restoreConversationHistory", app_js)
        self.assertIn(b"syncConversationHistory", app_js)
        self.assertIn(b"renderStarterActions", app_js)
        self.assertIn(b"startNewConversation", app_js)
        self.assertIn(b'"/conversation-clear"', app_js)
        self.assertIn(b'class="copy-response"', app_js)
        self.assertIn(b"beginRequestProgress", app_js)
        self.assertIn(b"finishRequestProgress", app_js)
        self.assertIn(b"if (session.working)", app_js)
        self.assertIn(b"window.AbortSignal", app_js)
        self.assertIn(b"setMobileChatExpanded", app_js)
        self.assertIn(b"syncMobileViewport", app_js)
        self.assertIn(b"beforeinstallprompt", app_js)
        self.assertIn(b'navigator.serviceWorker.register("/jarvis-sw.js"', app_js)
        self.assertIn(b"updateActionHub", app_js)
        self.assertIn(b"showAttachmentPreview", app_js)
        self.assertIn("Esta é uma prévia do arquivo que estou analisando.".encode(), app_js)
        self.assertIn(b"exitOwnerMode", app_js)
        self.assertIn(b'"/admin-login"', app_js)
        self.assertIn(b"ElevenLabs sem cr\xc3\xa9ditos", app_js)
        self.assertIn(b"new AbortController()", app_js)
        self.assertIn(b"signal: controller.signal", app_js)
        self.assertIn(b"currentSpeechController?.abort()", app_js)
        self.assertIn(b"compactCaption", app_js)
        self.assertIn(b"session.voicePending", app_js)
        self.assertIn(b'data.provider === "openrouter"', app_js)
        self.assertIn(b"renderEventStream", app_js)
        self.assertIn(b"refreshWorkerStatus", app_js)
        self.assertIn(b"verificando o Mac em segundo plano", app_js)
        self.assertIn(b'protocol !== "jarvis-events/1"', app_js)
        self.assertIn(b"renderUICards", app_js)
        self.assertIn(b'class="ui-card"', app_js)
        self.assertIn(b"refreshPulse", app_js)
        self.assertIn(b"10 * 60 * 1000", app_js)
        self.assertIn(b'"/device-cancel"', app_js)
        self.assertIn(b"canceledJobs", app_js)
        self.assertIn(b"addAttachments", app_js)
        self.assertIn(b"readAsDataURL", app_js)
        self.assertIn(b"speechChunks", app_js)
        self.assertIn(b"fetchSpeechChunk", app_js)
        self.assertIn(b"previous_text: previousText", app_js)
        self.assertIn(b"next_text: nextText", app_js)
        self.assertIn(b'stage.classList.add("spatial-result")', app_js)
        self.assertNotIn(b"chunks[0].length > 165", app_js)
        self.assertIn(b"playSpeechChunk", app_js)
        self.assertIn(b"__jarvisFinish", app_js)
        self.assertIn(b"renderMessageContext", app_js)
        self.assertIn(b"MAX_VISIBLE_MESSAGES", app_js)
        self.assertIn(b'class="message-context"', app_js)
        self.assertIn(b"renderSourceLinks", app_js)
        self.assertIn(b'class="source-links"', app_js)
        self.assertIn(b"web ao vivo", app_js)
        status, headers, device_feedback = self.request("/ui/device-feedback.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"worker-diagnostic", device_feedback)
        self.assertIn("Ainda offline · verificar de novo".encode(), device_feedback)
        self.assertIn(b'research: ["PESQUISA", "consultando fontes reais"', app_js)
        self.assertIn("Pesquisando…".encode("utf-8"), app_js)
        self.assertIn(b"source?.snippet", app_js)
        self.assertIn(b"feature_evidence", app_js)
        self.assertIn(b"PESQUISA PROFUNDA", app_js)
        self.assertIn(b'class="message-card"', app_js)
        self.assertIn(b"workingStateFor", app_js)
        self.assertIn(b"responseVisualState", app_js)
        self.assertIn(b'forge: ["FORJA"', app_js)
        self.assertIn(b"compactHudText", app_js)
        self.assertIn(b"renderLiveCanvas", app_js)
        self.assertIn(b'byId("sceneMac")', app_js)

        status, headers, app_css = self.request("/ui/jarvis.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".conversation-head", app_css)
        self.assertIn(b".composer input", app_css)
        self.assertIn(b".message-actions", app_css)
        self.assertIn(b".new-conversation-button", app_css)
        self.assertIn(b".action-hub", app_css)
        self.assertIn(b".admin-login", app_css)
        self.assertIn(b".tour-grid", app_css)
        self.assertIn(b".request-progress", app_css)
        self.assertIn(b".shimmer-loader", app_css)

        status, headers, repair_css = self.request("/ui/ui-repair.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b'.composer[data-has-payload="false"]', repair_css)
        self.assertIn(b'html[data-persona="ultron"] .scene-modes', repair_css)

        status, headers, api_panel_css = self.request("/ui/api-panel.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".integration-tabs", api_panel_css)
        self.assertIn(b".integration-actions-sticky", api_panel_css)

        status, headers, health_css = self.request("/ui/integration-health.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".integration-health-card", health_css)

        status, headers, health_js = self.request("/ui/integration-health.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"integrationHealthRefresh", health_js)

        status, headers, voice_calibrator_js = self.request("/ui/voice-calibrator.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"jarvis-voice-profile-v1", voice_calibrator_js)

        status, headers, voice_calibrator_css = self.request("/ui/voice-calibrator.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".voice-presets", voice_calibrator_css)

        status, headers, n8n_template_pack = self.request("/ui/n8n-template-pack.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"whatsapp-lead", n8n_template_pack)
        self.assertIn(b"github-incident", n8n_template_pack)

        status, headers, feature_loader = self.request("/ui/feature-loader.js")
        self.assertEqual(status, 200)
        self.assertIn(b"memory-explorer.js", feature_loader)
        self.assertIn(b"Abrir o LinkedIn de Theo Lorentz Padilha", feature_loader)
        self.assertIn(b"linkedin.com/in/theo-lorentz-padilha", feature_loader)
        self.assertNotIn(b"ghbtns.com", feature_loader)

        status, headers, presence_loader = self.request("/ui/presence-loader.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"jarvis-3d.js?v=20260815-vozes2", presence_loader)
        self.assertIn(b"requestIdleCallback", presence_loader)
        self.assertIn(b'/ui/aurora.js', presence_loader)
        self.assertIn(b'/ui/strands.js', presence_loader)

        status, headers, ultron_css = self.request("/ui/ultron-completion.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b'html[data-persona="ultron"]', ultron_css)

        status, headers, memory_explorer_js = self.request("/ui/memory-explorer.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"/memory-explorer?", memory_explorer_js)

        status, headers, memory_explorer_css = self.request("/ui/memory-explorer.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".memory-explorer-form", memory_explorer_css)

        status, headers, action_permissions_js = self.request("/ui/action-permissions.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"jarvis-action-permissions-v1", action_permissions_js)

        status, headers, action_permissions_css = self.request("/ui/action-permissions.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".permission-request", action_permissions_css)

        status, headers, responsive_css = self.request("/ui/responsive-polish.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b"orientation: landscape", responsive_css)
        self.assertIn(b"prefers-contrast: more", responsive_css)

        status, headers, integration_history = self.request("/ui/integration-history.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"jarvis-integration-history-v1", integration_history)

        self.assertIn(b"@keyframes shimmer-text", app_css)
        self.assertIn(b".starter-actions", app_css)
        self.assertIn(b".mobile-chat-toggle", app_css)
        self.assertIn(b".mobile-keyboard-open", app_css)
        self.assertIn(b"env(safe-area-inset-bottom)", app_css)
        self.assertIn(b"touch-action: manipulation", app_css)
        self.assertIn(b"-webkit-line-clamp: 2", app_css)
        self.assertIn(b'.stage.has-conversation .conversation', app_css)
        self.assertIn(b'.stage[data-state="thinking"] .hud-right', app_css)
        self.assertIn(b".source-links", app_css)
        self.assertIn(b".message-link", app_css)
        self.assertIn(b".source-links a em", app_css)
        self.assertIn(b"Command Deck V2", app_css)
        self.assertIn(b"Experience V3", app_css)
        self.assertIn(b".hud-rail", app_css)
        self.assertIn(b".scene-modes", app_css)
        self.assertIn(b".identity-logo", app_css)
        self.assertIn(b"Official identity", app_css)
        self.assertIn(b'error?.name === "AbortError"', app_js)
        self.assertIn(b"speechSynthesis", app_js)
        self.assertIn(b"speakBrowser", app_js)

        status, headers, visual_js = self.request("/ui/jarvis-3d.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b"drawMemory", visual_js)
        self.assertIn(b"drawForge", visual_js)
        self.assertIn(b"makeCoreEntity", visual_js)
        self.assertIn("MEMÓRIA · REGISTRO CONFIRMADO".encode(), visual_js)
        self.assertIn("FORJA · CONSTRUÇÃO EM CURSO".encode(), visual_js)
        self.assertIn(b"visualModeForState", visual_js)
        self.assertIn(b"modeBlend", visual_js)
        self.assertIn(b'["thinking", "planning", "research"].includes(state)', visual_js)
        self.assertIn(b"GLTFLoader", visual_js)
        self.assertIn(b"jarvis-humanoid.glb", visual_js)
        self.assertIn(b"visitor-animated-surface-topology", visual_js)
        self.assertIn(b"visitor-mesh-derived-dissolution", visual_js)
        self.assertNotIn(b"TubeGeometry", visual_js)
        self.assertNotIn(b"visitor-real-eye", visual_js)
        self.assertNotIn(b"makeIrisTexture", visual_js)
        self.assertIn(b"jarvisPoseHead", visual_js)
        self.assertIn(b"male_head_topology.obj", visual_js)
        self.assertNotIn(b"TetrahedronGeometry", visual_js)
        self.assertNotIn(b"new THREE.CircleGeometry(0.06, 3)", visual_js)
        self.assertIn(b"facingYaw", visual_js)
        self.assertIn(b"visitor-purple-volume", visual_js)
        self.assertIn(b"color: 0x7741ad", visual_js)
        self.assertIn(b"opacity: 0.66", visual_js)
        self.assertIn(b"visitorLife.update", visual_js)
        self.assertIn(b"async function loadOwnerModel()", visual_js)
        self.assertIn(b"jarvisSuppressedEffect", visual_js)
        self.assertIn(b"activeFps: 45", visual_js)
        self.assertIn(b"idleFps: 24", visual_js)
        self.assertIn(b"EFFECT_TARGET_FPS", visual_js)
        self.assertNotIn(b"slowFrameWindows", visual_js)
        self.assertNotIn(b"constrainedHardware", visual_js)
        self.assertIn(b'QUALITY_PROFILES[graphicsQuality].pixelRatio', visual_js)
        self.assertIn(b'sceneRender', visual_js)
        self.assertIn(b'GPU 3D desativada', visual_js)
        self.assertIn(b"frameIntervalMs", visual_js)
        self.assertIn(b"orientationEase", visual_js)
        self.assertIn(b'contains("spatial-result") && canvasWidth > 900', visual_js)
        self.assertIn(b"const targetPositionX = spatialResult ? -1.35 : modeTargetX", visual_js)
        self.assertIn(b"const inwardGaze = spatialResult * 0.11", visual_js)
        self.assertIn(b"document.hidden", visual_js)
        self.assertIn(b"scheduleRender", visual_js)
        self.assertIn(b'"research"', visual_js)
        self.assertIn(b"animationTimerId", visual_js)
        self.assertIn(b"disposedTextures", visual_js)
        self.assertIn(b"resizeObserver.disconnect()", visual_js)
        self.assertIn(b"renderer.dispose()", visual_js)
        self.assertIn(b"X-Jarvis-Owner-Token", visual_js)

        status, headers, three_js = self.request("/ui/vendor/three.module.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertGreater(len(three_js), 1_000_000)

        for module_path in ("/ui/aurora.js", "/ui/strands.js", "/ui/vendor/ogl/jarvis.js"):
            status, headers, module_source = self.request(module_path)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get_content_type(), "text/javascript")
            self.assertGreater(len(module_source), 100)

        status, headers, manifest = self.request("/ui/manifest.webmanifest")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "application/manifest+json")
        manifest_data = json.loads(manifest)
        self.assertEqual(manifest_data["display"], "standalone")
        self.assertEqual(manifest_data["short_name"], "JARVIS")
        self.assertGreaterEqual(len(manifest_data["icons"]), 1)
        self.assertIn("jarvis-logo.png", manifest_data["icons"][0]["src"])

        status, headers, service_worker = self.request("/jarvis-sw.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/javascript")
        self.assertIn(b'addEventListener("notificationclick"', service_worker)
        self.assertIn(b"jarvis-mobile-shell-20260815-vozes2", service_worker)
        self.assertIn(b'/ui/jarvis-logo.png?v=20260813-logonative1', service_worker)
        self.assertIn(b'/ui/ui-repair.css?v=20260815-vozes2', service_worker)
        self.assertIn(b'/ui/api-vault.js?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/integration-history.js?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/feature-loader.js?v=20260815-vozes2', service_worker)
        self.assertIn(b'/ui/presence-loader.js?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/integration-health.js?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/voice-calibrator.js?v=20260815-vozes2', service_worker)
        self.assertIn(b'/ui/n8n-template-pack.js?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/memory-explorer.js?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/action-permissions.js?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/device-feedback.js?v=20260813-device1', service_worker)
        self.assertIn(b'/ui/jarvis.js?v=20260815-vozes2', service_worker)
        self.assertIn(b'/ui/shell.css?v=20260815-vozes2', service_worker)
        self.assertIn(b'/ui/api-panel.css?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/integration-health.css?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/voice-calibrator.css?v=20260815-vozes2', service_worker)
        self.assertIn(b'/ui/memory-explorer.css?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/action-permissions.css?v=20260813-ultronfix1', service_worker)
        self.assertIn(b'/ui/ultron-completion.css?v=20260815-vozes2', service_worker)
        self.assertIn(b'/ui/responsive-polish.css?v=20260815-vozes2', service_worker)
        self.assertIn(b'"/ui/vendor/three.module.js"', service_worker)
        self.assertIn(b"ignoreSearch: true", service_worker)
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertIn(b"request.mode === \"navigate\"", service_worker)

        for icon in ("jarvis-icon-180.png", "jarvis-icon-192.png", "jarvis-icon-512.png"):
            status, headers, image = self.request(f"/ui/{icon}")
            self.assertEqual(status, 200)
            self.assertEqual(headers.get_content_type(), "image/png")
            self.assertGreater(len(image), 1_000)

        status, headers, logo = self.request("/ui/jarvis-logo.png")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "image/png")
        self.assertGreater(len(logo), 100_000)

        status, headers, css = self.request("/ui/jarvis.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertIn(b".hud-rail", css)
        self.assertIn(b".message.user.voice", css)
        self.assertIn(b".file-preview", css)
        self.assertIn(b".environment-depth::before", css)
        self.assertIn(b".environment-depth::after", css)

        status, _, favicon = self.request("/favicon.ico")
        self.assertEqual(status, 200)
        self.assertEqual(favicon, b"")

        status, headers, model = self.request("/asset/models/jarvis-humanoid.glb")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "model/gltf-binary")
        self.assertEqual(headers["Cache-Control"], "public, max-age=31536000, immutable")
        self.assertGreater(len(model), 4_000_000)
        self.assertLess(len(model), 4_500_000)

        status, headers, facing_model = self.request("/asset/models/variants/01_avatar_boneco_humanoid.glb")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "model/gltf-binary")
        self.assertGreater(len(facing_model), 2_500_000)

        status, headers, head_model = self.request("/asset/models/male_head.obj")
        self.assertEqual(status, 200)
        self.assertIn(headers.get_content_type(), {"text/plain", "model/obj", "application/octet-stream"})
        self.assertGreater(len(head_model), 3_000_000)
        self.assertIn(b"# This file uses centimeters", head_model[:200])

        status, headers, topology_model = self.request("/asset/models/male_head_topology.obj")
        self.assertEqual(status, 200)
        self.assertIn(headers.get_content_type(), {"text/plain", "model/obj", "application/octet-stream"})
        self.assertGreater(len(topology_model), 100_000)
        self.assertIn(b"visitor topology derived deterministically", topology_model[:200])

    def test_local_device_request_becomes_handoff(self):
        status, _, payload = self.json_request(
            "/command", "POST", {"command": "tirar um print da tela"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "screen_capture")
        self.assertTrue(payload["requires_local_worker"])
        self.assertEqual(payload["local_command"], "./jarvis screen-capture")
        stream = payload["event_stream"]
        self.assertEqual(stream["protocol"], "jarvis-events/1")
        self.assertEqual(stream["events"][0]["type"], "RUN_STARTED")
        self.assertEqual(stream["events"][-1]["type"], "RUN_FINISHED")
        self.assertGreaterEqual(stream["elapsed_ms"], 0)

    def test_agent_run_can_be_read_confirmed_canceled_and_retried(self):
        status, _, waiting = self.json_request(
            "/command", "POST", {"command": "mande mensagem para 5511999999999 dizendo teste"}
        )
        self.assertEqual(status, 202)
        self.assertEqual(waiting["state"], "waiting_confirmation")
        self.assertTrue(waiting["needs_confirmation"])
        run_id = waiting["run_id"]

        status, _, loaded = self.json_request(f"/runs/{run_id}")
        self.assertEqual(status, 200)
        self.assertEqual(loaded["run_id"], run_id)
        self.assertIn("created_at", loaded)

        status, _, history = self.json_request("/runs?limit=1&state=waiting_confirmation")
        self.assertEqual(status, 200)
        self.assertEqual(history["protocol"], MODULE.RUN_PROTOCOL)
        self.assertEqual(history["count"], 1)
        self.assertEqual(history["runs"][0]["run_id"], run_id)
        self.assertEqual(history["runs"][0]["state"], "waiting_confirmation")

        status, _, confirmed = self.json_request(f"/runs/{run_id}/confirm", "POST", {})
        self.assertEqual(status, 200)
        self.assertEqual(confirmed["state"], "completed")
        self.assertTrue(confirmed["requires_local_worker"])

        _, _, second = self.json_request(
            "/command", "POST", {"command": "mande mensagem para 5511999999999 dizendo cancelar"}
        )
        status, _, canceled = self.json_request(f"/runs/{second['run_id']}/cancel", "POST", {})
        self.assertEqual(status, 200)
        self.assertEqual(canceled["state"], "canceled")
        status, _, retried = self.json_request(f"/runs/{second['run_id']}/retry", "POST", {})
        self.assertEqual(status, 202)
        self.assertEqual(retried["state"], "waiting_confirmation")
        self.assertNotEqual(retried["run_id"], second["run_id"])

    def test_mission_control_prioritizes_real_runs_and_safe_operations(self):
        waiting = MODULE.AGENT_RUNS.create(
            "envie a atualização somente depois da minha confirmação",
            action="message_send",
            source="test",
            state="waiting_confirmation",
            plan=MODULE.run_plan_for("envie a atualização", "message_send", "message_send"),
        )
        failed = MODULE.AGENT_RUNS.create(
            "missão que falhou durante o teste",
            action="assistant_chat",
            source="test",
            state="planned",
            plan=MODULE.run_plan_for("missão que falhou", "assistant_chat", "assistant"),
        )
        failed = MODULE.AGENT_RUNS.update(
            failed["id"], state="failed", error="falha verificada",
            evidence=[{"type": "private", "value": "não expor este valor"}], event_type="RUN_FAILED",
        )
        status, _, control = self.json_request("/mission-control?limit=12")
        self.assertEqual(status, 200)
        self.assertEqual(control["protocol"], MODULE.MISSION_CONTROL_PROTOCOL)
        self.assertEqual(control["health"], "needs_attention")
        self.assertGreaterEqual(control["summary"]["waiting_confirmation"], 1)
        self.assertGreaterEqual(control["summary"]["failed"], 1)
        rows = {row["run_id"]: row for row in control["missions"]}
        self.assertEqual(rows[waiting["id"]]["operations"], ["confirm", "cancel"])
        self.assertEqual(rows[failed["id"]]["operations"], ["retry"])
        self.assertEqual(rows[failed["id"]]["evidence_count"], 1)
        self.assertNotIn("não expor este valor", json.dumps(control, ensure_ascii=False))
        self.assertEqual(control["missions"][0]["state"], "waiting_confirmation")

    def test_mission_control_requires_private_pairing_when_configured(self):
        with patch.dict(os.environ, {"JARVIS_OWNER_TOKEN": "private-test-token"}):
            status, _, payload = self.json_request("/mission-control")
        self.assertEqual(status, 401)
        self.assertEqual(payload["endpoint"], "GET /mission-control")

    def test_memory_search_uses_local_index(self):
        status, _, payload = self.json_request(
            "/command", "POST", {"command": "busque na memória por busto"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "sqlite_local_index")
        self.assertEqual(payload["state"], "completed")
        self.assertTrue(any("busto" in row["snippet"].casefold() for row in payload["memory_results"]))

    def test_memory_manager_updates_and_archives_supabase_rows(self):
        saved = [{"id": "42", "content": "conteúdo atualizado", "kind": "decision"}]
        with patch.object(MODULE, "supabase_configured", return_value=True), patch.object(
            MODULE, "supabase_request", return_value=saved
        ) as request_mock:
            status, _, updated = self.json_request(
                "/memory-update", "POST", {"id": "42", "content": "conteúdo atualizado", "kind": "decision"}
            )
            self.assertEqual(status, 200)
            self.assertEqual(updated["status_real"], "supabase_memory_updated")
            self.assertEqual(request_mock.call_args.args[0], "PATCH")

            status, _, archived = self.json_request("/memory-archive", "POST", {"id": "42"})
            self.assertEqual(status, 200)
            self.assertEqual(archived["status_real"], "supabase_memory_archived")

    def test_memory_manager_refuses_secret_like_content(self):
        status, _, payload = self.json_request(
            "/memory-update", "POST", {"id": "42", "content": "api" + "_key=" + "abcdefghijk123456", "kind": "learning"}
        )
        self.assertEqual(status, 400)
        self.assertIn("credenciais", payload["error"])

    def test_local_task_queue_ui_api_is_append_only(self):
        with TemporaryDirectory() as directory:
            task_path = Path(directory) / "tasks.jsonl"
            with patch.object(MODULE.task_queue_store, "TASKS_DIR", task_path.parent), patch.object(
                MODULE.task_queue_store, "TASKS_FILE", task_path
            ):
                status, _, created = self.json_request(
                    "/tasks/add", "POST", {"text": "validar fila visual", "project": "jarvis-core"}
                )
                self.assertEqual(status, 201)
                task_id = created["task"]["id"]
                status, _, blocked = self.json_request(
                    f"/tasks/{task_id}/block", "POST", {"detail": "aguardando revisão"}
                )
                self.assertEqual(status, 200)
                self.assertEqual(blocked["task"]["status"], "blocked")
                status, _, reopened = self.json_request(f"/tasks/{task_id}/reopen", "POST", {})
                self.assertEqual(status, 200)
                self.assertEqual(reopened["task"]["status"], "pending")
                status, _, listed = self.json_request("/tasks")
                self.assertEqual(status, 200)
                self.assertEqual(listed["counts"]["pending"], 1)
                self.assertEqual(len(task_path.read_text(encoding="utf-8").splitlines()), 3)

        status, _, direct = self.json_request("/memory-search?q=busto")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(direct["count"], 1)

    def test_memory_explorer_filters_subject_kind_and_inclusive_period(self):
        tree = {
            "ok": True,
            "provider": "supabase",
            "count": 3,
            "nodes": [
                {"id": "1", "label": "Voz tranquila", "content": "A voz do JARVIS deve ser tranquila", "kind": "preference", "category": "PREFERÊNCIAS", "created_at": "2026-08-13T12:00:00Z"},
                {"id": "2", "label": "Deploy", "content": "Deploy do cockpit concluído", "kind": "decision", "category": "DECISÕES", "created_at": "2026-08-12T18:00:00Z"},
                {"id": "3", "label": "Voz antiga", "content": "Ajuste de voz anterior", "kind": "preference", "category": "PREFERÊNCIAS", "created_at": "2026-07-01T12:00:00Z"},
            ],
        }
        with patch.object(MODULE, "memory_tree_payload", return_value=tree):
            payload, status = MODULE.memory_explorer_payload({
                "q": "voz tranquila", "kind": "preference", "from": "2026-08-13", "to": "2026-08-13"
            })
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "private_memory_filtered_read")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], "1")

    def test_memory_explorer_rejects_invalid_period(self):
        payload, status = MODULE.memory_explorer_payload({"from": "13-08-2026"})
        self.assertEqual(status, 400)
        self.assertIn("AAAA-MM-DD", payload["error"])

    def test_memory_explorer_requires_private_pairing_when_configured(self):
        with patch.dict(os.environ, {"JARVIS_OWNER_TOKEN": "private-test-token"}):
            status, _, payload = self.json_request("/memory-explorer?q=voz")
        self.assertEqual(status, 401)
        self.assertEqual(payload["endpoint"], "GET /memory-explorer")

    def test_capabilities_expose_shared_action_registry(self):
        status, _, payload = self.json_request("/capabilities")
        self.assertEqual(status, 200)
        self.assertEqual(payload["action_registry"]["protocol"], "jarvis-actions/1")
        names = {row["name"] for row in payload["action_registry"]["actions"]}
        self.assertIn("message_send", names)
        self.assertIn("memory_search", names)

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

    def test_personal_overview_guest_never_exposes_private_counts(self):
        env = {
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }
        with patch.dict(os.environ, env, clear=False):
            payload = MODULE.personal_overview_payload(owner_authenticated=False)
        self.assertEqual(payload["status_real"], "personal_control_plane_guest")
        self.assertFalse(payload["private"])
        self.assertIsNone(payload["summary"]["memory_count"])
        self.assertTrue(any(row["status"] == "locked" for row in payload["domains"]))
        self.assertFalse(next(row for row in payload["actions"] if row["id"] == "memory")["available"])

    def test_personal_overview_aggregates_real_adapters(self):
        sources = {
            "memory": {"ok": True, "count": 14},
            "agenda": {"ok": True, "agenda": [{"id": 8, "title": "Revisar deploy", "scheduled_for": "2026-08-09T20:00:00Z"}]},
            "worker": {"ok": True, "online": True, "age_seconds": 3, "message": "Worker do Mac conectado."},
            "activity": {"ok": True, "history": [{"action": "open_application", "status": "succeeded"}]},
        }
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch.object(
            MODULE, "_private_overview_calls", return_value=sources
        ):
            payload = MODULE.personal_overview_payload(owner_authenticated=True)
        self.assertEqual(payload["status_real"], "personal_control_plane_ready")
        self.assertTrue(payload["private"])
        self.assertEqual(payload["summary"]["memory_count"], 14)
        self.assertEqual(payload["summary"]["agenda_count"], 1)
        self.assertTrue(payload["summary"]["worker_online"])
        self.assertEqual(payload["summary"]["latest_action"], "open_application · succeeded")
        self.assertTrue(next(row for row in payload["actions"] if row["id"] == "spotify")["available"])
        action_ids = {row["id"] for row in payload["actions"]}
        self.assertTrue({"task", "screen-record", "system", "plan"}.issubset(action_ids))
        self.assertEqual(next(row for row in payload["actions"] if row["id"] == "task")["interaction"], "draft")

    def test_capability_question_uses_control_plane_without_model(self):
        expected = {
            "ok": True,
            "message": "Central operacional.",
            "domains": [{"label": "Mac", "status": "online", "detail": "conectado"}],
            "actions": [],
            "private": True,
        }
        with patch.object(MODULE, "personal_overview_payload", return_value=expected) as overview:
            payload, status = MODULE.command_payload(
                {"command": "o que você consegue fazer?"},
                owner_authenticated=True,
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "jarvis_control_plane")
        self.assertEqual(payload["intent"], "personal_overview")
        overview.assert_called_once_with(owner_authenticated=True)

    def test_best_capabilities_phrase_stays_on_control_plane(self):
        expected = {"ok": True, "message": "Central operacional.", "private": False}
        with patch.object(MODULE, "personal_overview_payload", return_value=expected) as overview, patch.object(
            MODULE, "urlopen"
        ) as openrouter:
            payload, status = MODULE.assistant_response({
                "command": "me diga em poucas frases as melhores coisas que você consegue fazer"
            })
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "jarvis_control_plane")
        overview.assert_called_once_with(owner_authenticated=False)
        openrouter.assert_not_called()

    def test_daily_brief_uses_private_control_plane(self):
        overview = {
            "ok": True,
            "summary": {"agenda_count": 2, "worker_online": True, "memory_count": 9},
            "agenda_preview": [{"title": "Entregar relatório", "scheduled_for": "2026-08-10T12:00:00Z"}],
        }
        with patch.object(MODULE, "personal_overview_payload", return_value=overview):
            payload, status = MODULE.daily_brief_payload(owner_authenticated=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "daily_operational_brief")
        self.assertIn("2 itens pendentes", payload["message"])
        self.assertIn("Entregar relatório", payload["message"])
        cards = MODULE.response_cards({
            **payload,
            "domains": [{"label": "Mac", "status": "online", "detail": "conectado"}],
            "private": True,
        })
        self.assertEqual(cards[0]["type"], "control_plane")

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

    def test_spotify_controls_route_to_real_local_command(self):
        cases = {
            "pause o Spotify": "./jarvis spotify pause",
            "próxima faixa no Spotify": "./jarvis spotify next",
            "volume do Spotify para 35": "./jarvis spotify volume 35",
            "o que está tocando no Spotify": "./jarvis spotify status",
            "busque no Spotify Daft Punk": "./jarvis spotify search 'Daft Punk'",
        }
        with patch.object(MODULE, "supabase_configured", return_value=False):
            for command, expected in cases.items():
                with self.subTest(command=command):
                    payload, status = MODULE.command_payload(
                        {"command": command},
                        local_execute=False,
                        owner_authenticated=True,
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(payload["intent"], "spotify_control")
                    self.assertEqual(payload["local_command"], expected)

    def test_spotify_remote_control_enters_allowlisted_queue(self):
        with patch.object(MODULE, "supabase_configured", return_value=True), patch.object(
            MODULE, "supabase_request", return_value=[{"id": 92, "status": "pending"}]
        ) as request:
            payload, status = MODULE.command_payload(
                {"command": "volume do Spotify para 35"},
                owner_authenticated=True,
            )
        self.assertEqual(status, 202)
        self.assertEqual(payload["status_real"], "device_command_queued")
        self.assertEqual(payload["job"]["action"], "spotify_control")
        self.assertEqual(payload["job"]["target"], "volume 35")
        body = request.call_args.kwargs["body"]
        self.assertEqual(body["action"], "spotify_control")
        self.assertEqual(body["target"], "volume 35")

    def test_spotify_control_can_be_one_verified_step_in_a_mac_run(self):
        steps = MODULE.compound_device_plan("pause o Spotify e depois tire um print da tela")
        self.assertEqual([step["intent"] for step in steps], ["spotify_control", "screen_capture"])
        self.assertEqual(MODULE.chain_step_target(steps[0]), "pause")

    def test_agent_tool_catalog_exposes_bounded_spotify_control(self):
        tool = next(row for row in MODULE.agent_tool_definitions() if row["function"]["name"] == "control_spotify")
        operation = tool["function"]["parameters"]["properties"]["operation"]
        self.assertIn("volume", operation["enum"])
        self.assertNotIn("shell", operation["enum"])

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
                    "target": "Spotify",
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
                    {"command": "abre o Spotify"},
                    owner_authenticated=True,
                )
        self.assertEqual(status, 202)
        self.assertEqual(payload["status_real"], "device_command_queued")
        self.assertEqual(payload["job"]["id"], 91)
        self.assertEqual(payload["job"]["target"], "Spotify")
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.method, "POST")
        self.assertIn("/rest/v1/jarvis_device_commands", sent_request.full_url)

    def test_compound_device_request_queues_dependency_ordered_run(self):
        command = "abra o Spotify e depois tire um print da tela e então abra a Steam"
        steps = MODULE.compound_device_plan(command)
        self.assertEqual(
            [step["intent"] for step in steps],
            ["open_application", "screen_capture", "open_application"],
        )
        saved = [
            [{"id": 101, "status": "pending"}],
            [{"id": 102, "status": "pending"}],
            [{"id": 103, "status": "pending"}],
        ]
        with patch.object(MODULE, "supabase_request", side_effect=saved) as request:
            payload, status = MODULE.supabase_device_enqueue_plan(command, steps)
        self.assertEqual(status, 202)
        self.assertEqual(payload["status_real"], "device_run_queued")
        self.assertEqual([job["id"] for job in payload["jobs"]], [101, 102, 103])
        self.assertFalse(payload["run"]["terminal"])
        envelopes = [json.loads(call.kwargs["body"]["request_text"]) for call in request.call_args_list]
        self.assertIsNone(envelopes[0]["depends_on"])
        self.assertEqual(envelopes[1]["depends_on"], 101)
        self.assertEqual(envelopes[2]["depends_on"], 102)
        self.assertEqual(envelopes[1]["request"], "tire um print da tela")

    def test_partial_run_queue_failure_reports_only_confirmed_compensation(self):
        command = "abra o Spotify e depois tire um print da tela"
        failure = HTTPError("https://jarvis.example", 503, "unavailable", {}, None)
        with patch.object(MODULE, "supabase_request", side_effect=[
            [{"id": 301, "status": "pending"}],
            failure,
            [{"id": 301, "status": "canceled"}],
        ]) as request:
            payload, status = MODULE.supabase_device_enqueue_plan(
                command,
                MODULE.compound_device_plan(command),
            )
        self.assertEqual(status, 502)
        self.assertTrue(payload["cancel_confirmed"])
        self.assertEqual(payload["queued_steps_canceled"], 1)
        self.assertIn("confirmei o cancelamento", payload["error"])
        self.assertEqual(request.call_args_list[-1].args[0], "PATCH")
        self.assertEqual(request.call_args_list[-1].kwargs["prefer"], "return=representation")

    def test_compound_request_requires_owner_and_bypasses_chat_model(self):
        command = "abra o Spotify e depois tire um print da tela"
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        queued = ({
            "ok": True,
            "status_real": "device_run_queued",
            "jobs": [{"id": 1}, {"id": 2}],
            "run": {"status": "pending", "terminal": False},
        }, 202)
        with patch.dict(os.environ, env, clear=False):
            blocked, blocked_status = MODULE.command_payload({"command": command}, owner_authenticated=False)
            with patch.object(MODULE, "supabase_device_enqueue_plan", return_value=queued) as enqueue:
                payload, status = MODULE.command_payload({"command": command}, owner_authenticated=True)
        self.assertEqual(blocked_status, 401)
        self.assertTrue(blocked["pairing_required"])
        self.assertEqual(status, 202)
        self.assertEqual(payload["status_real"], "device_run_queued")
        enqueue.assert_called_once()

    def test_device_run_reports_each_persisted_result_in_requested_order(self):
        rows = [
            {"id": 202, "action": "screen_capture", "target": "", "status": "pending"},
            {"id": 201, "action": "open_application", "target": "Spotify", "status": "succeeded", "result": "aberto"},
        ]
        with patch.object(MODULE, "supabase_request", return_value=rows):
            payload, status = MODULE.supabase_device_run("201,202")
        self.assertEqual(status, 200)
        self.assertEqual([job["id"] for job in payload["jobs"]], [201, 202])
        self.assertEqual(payload["run"]["completed"], 1)
        self.assertEqual(payload["run"]["status"], "pending")
        self.assertFalse(payload["run"]["terminal"])

    def test_queued_execution_events_never_claim_finished(self):
        started = datetime.now(MODULE.timezone.utc)
        stream = MODULE.execution_events({
            "ok": True,
            "status_real": "device_run_queued",
            "provider": "supabase_device_bridge",
            "run": {"id": "run-real", "status": "pending", "terminal": False},
            "jobs": [{"id": 1, "status": "pending"}, {"id": 2, "status": "pending"}],
            "job": {"id": 1, "status": "pending"},
        }, started, 202)
        self.assertEqual(stream["run_id"], "run-real")
        self.assertEqual(stream["events"][-1]["type"], "RUN_WAITING")
        self.assertFalse(any(event["type"] == "TOOL_CALL_FINISHED" for event in stream["events"]))
        cards = MODULE.response_cards({
            "run": {"id": "run-real", "status": "pending", "completed": 0},
            "jobs": [
                {"id": 1, "step": 1, "action": "open_application", "target": "Spotify", "status": "pending"},
                {"id": 2, "step": 2, "action": "screen_capture", "target": "", "status": "pending"},
            ],
        })
        self.assertEqual(cards[0]["type"], "device_run")
        self.assertEqual(len(cards[0]["items"]), 2)

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
        self.assertEqual(payload["state"], "waiting_confirmation")
        self.assertTrue(payload["needs_confirmation"])
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "supabase_device_enqueue", return_value=({
                "ok": True,
                "intent": "self_edit",
                "status_real": "device_command_queued",
                "job": {"id": 701, "status": "pending"},
            }, 202),
        ) as confirmed_enqueue:
            confirmed, confirmed_status = MODULE.execute_saved_run(
                MODULE.AGENT_RUNS.get(payload["run_id"]), owner_authenticated=True
            )
        self.assertEqual(confirmed_status, 202)
        self.assertEqual(confirmed["state"], "running")
        confirmed_enqueue.assert_called_once_with("melhore seus próprios scripts de diagnóstico", "self_edit")

    def test_ultron_plain_improve_and_deploy_phrases_route_to_self_edit(self):
        env = {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
            "JARVIS_OWNER_TOKEN": "owner-pairing-test-value",
        }
        for command in (
            "corrige o modo visitante e simplifica a tela",
            "melhore a interface do ultron",
            "faça deploy e merge do que você melhorou",
        ):
            with patch.dict(os.environ, env, clear=False):
                payload, status = MODULE.command_payload(
                    {"command": command},
                    owner_authenticated=True,
                )
            self.assertEqual(status, 202, command)
            self.assertEqual(payload["intent"], "self_edit", command)

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
        self.assertEqual(payload["state"], "waiting_confirmation")
        enqueue.assert_not_called()

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
                self.assertEqual(status, 202)
                self.assertEqual(payload["state"], "waiting_confirmation")
                confirmed, confirmed_status = MODULE.execute_saved_run(
                    MODULE.AGENT_RUNS.get(payload["run_id"]), owner_authenticated=True
                )
        self.assertEqual(confirmed_status, 201)
        self.assertEqual(confirmed["status_real"], "elevenlabs_voice_created")
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

    def test_original_voice_ignores_abandoned_library_migration(self):
        migrated = [{"value": {
            "voice_id": "library_voice_that_sounded_wrong",
            "name": "Tentativa pt-BR",
            "provider": "elevenlabs_voice_library",
        }}]
        with patch.dict(MODULE._ACTIVE_VOICE_CACHE, {
            "voice_id": "",
            "name": "",
            "source": "",
            "expires_at": 0.0,
        }, clear=True), patch.object(
            MODULE, "supabase_configured", return_value=True
        ), patch.object(MODULE, "supabase_request", return_value=migrated):
            active = MODULE.active_voice_setting(force=True)
        self.assertEqual(active["voice_id"], MODULE.DEFAULT_ELEVENLABS_VOICE_ID)
        self.assertEqual(active["source"], "environment")

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

    def test_admin_login_issues_temporary_signed_owner_session(self):
        salt = bytes.fromhex("00112233445566778899aabbccddeeff")
        digest = hashlib.pbkdf2_hmac("sha256", b"test-admin-password", salt, 120_000).hex()
        encoded = f"pbkdf2_sha256$120000${salt.hex()}${digest}"
        env = {
            "JARVIS_OWNER_TOKEN": "owner-session-signing-secret",
            "JARVIS_ADMIN_USERNAME": "admin",
            "JARVIS_ADMIN_PASSWORD_HASH": encoded,
        }
        with patch.dict(os.environ, env, clear=False):
            payload, status = MODULE.admin_login_payload({
                "username": "admin",
                "password": "test-admin-password",
            })
            refused, refused_status = MODULE.admin_login_payload({
                "username": "admin",
                "password": "wrong-password",
            })
            self.assertTrue(MODULE.owner_token_matches(payload["session_token"]))
            status_payload = MODULE.status_payload(owner_authenticated=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload["access"], "owner_master")
        expires_at = int(payload["session_token"].split(".")[1])
        self.assertGreaterEqual(expires_at - int(time.time()), MODULE.OWNER_SESSION_SECONDS - 2)
        self.assertEqual(refused_status, 401)
        self.assertFalse(refused["ok"])
        serialized = json.dumps(status_payload)
        self.assertNotIn("test-admin-password", serialized)
        self.assertNotIn(encoded, serialized)
        self.assertTrue(status_payload["owner_pairing"]["admin_login_configured"])
        self.assertEqual(status_payload["owner_pairing"]["session_duration_seconds"], MODULE.OWNER_SESSION_SECONDS)

    def test_pairing_refusal_never_implies_that_a_device_action_ran(self):
        payload, status = MODULE.pairing_required_payload()
        self.assertEqual(status, 401)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["action_executed"])
        self.assertIn("Não executei a ação", payload["error"])
        self.assertIn("modo Ultron", payload["next_action"])

    def test_private_conversation_history_is_normalized_and_persisted(self):
        rows = [{
            "value": {
                "schema_version": 2,
                "session_id": "sess-abc12345",
                "messages": [
                    {"role": "user", "content": "lembre do contexto"},
                    {"role": "assistant", "content": "Contexto mantido."},
                ],
            },
            "updated_at": "2026-08-08T10:00:00Z",
        }]
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }, clear=False), patch.object(MODULE, "supabase_request", side_effect=[rows, []]) as request:
            restored, restored_status = MODULE.conversation_history_payload("sess-abc12345")
            saved, saved_status = MODULE.persist_conversation_history({
                "messages": [
                    {"role": "user", "content": "conversa segura"},
                    {"role": "assistant", "content": "mantida"},
                    {"role": "user", "content": "token=placeholdervalue123456"},
                ],
            }, "sess-abc12345")
        self.assertEqual(restored_status, 200)
        self.assertEqual(restored["count"], 2)
        self.assertEqual(saved_status, 200)
        self.assertEqual(saved["count"], 2)
        self.assertEqual(request.call_args_list[1].kwargs["body"]["key"], "conversation_history:sess-abc12345")
        written = request.call_args_list[1].kwargs["body"]["value"]["messages"]
        self.assertNotIn("placeholdervalue123456", json.dumps(written))

    def test_conversation_history_is_isolated_per_browser_session(self):
        empty, empty_status = MODULE.conversation_history_payload("")
        self.assertEqual(empty_status, 200)
        self.assertEqual(empty["messages"], [])
        self.assertEqual(empty["status_real"], "conversation_history_session_required")
        refused, refused_status = MODULE.persist_conversation_history({
            "messages": [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "ok"}],
        })
        self.assertEqual(refused_status, 400)
        self.assertEqual(MODULE.conversation_storage_key("sess-one-aaaa"), "conversation_history:sess-one-aaaa")
        self.assertNotEqual(
            MODULE.conversation_storage_key("sess-one-aaaa"),
            MODULE.conversation_storage_key("sess-two-bbbb"),
        )
        keys = {
            MODULE.conversation_storage_key("pc-um-aaaaaa"),
            MODULE.conversation_storage_key("pc-dois-bbbb"),
            MODULE.conversation_storage_key("pc-tres-cccc"),
        }
        self.assertEqual(len(keys), 3)
        self.assertEqual(MODULE._OPENROUTER_INFLIGHT._initial_value, 3)

    def test_session_turn_blocks_double_send_and_rate_limit(self):
        MODULE._SESSION_INFLIGHT.clear()
        MODULE._SESSION_HITS.clear()
        ok, token, status = MODULE.begin_session_turn("pc-fair-aaaa")
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        blocked, payload, blocked_status = MODULE.begin_session_turn("pc-fair-aaaa")
        self.assertFalse(blocked)
        self.assertEqual(blocked_status, 429)
        self.assertEqual(payload["status_real"], "session_already_working")
        MODULE.end_session_turn("pc-fair-aaaa")
        MODULE._SESSION_HITS["pc-fair-aaaa"] = [time.monotonic()] * MODULE.SESSION_RATE_LIMIT
        limited, limited_payload, limited_status = MODULE.begin_session_turn("pc-fair-aaaa")
        self.assertFalse(limited)
        self.assertEqual(limited_status, 429)
        self.assertEqual(limited_payload["status_real"], "session_rate_limited")
        MODULE._SESSION_HITS.clear()
        MODULE._SESSION_INFLIGHT.clear()

    def test_occupancy_counts_distinct_browser_sessions(self):
        MODULE._PRESENCE.clear()
        MODULE.touch_presence("pc-um-aaaaaa")
        MODULE.touch_presence("pc-dois-bbbb")
        MODULE.touch_presence("pc-tres-cccc")
        payload = MODULE.occupancy_payload()
        self.assertEqual(payload["online"], 3)
        self.assertEqual(payload["chat_scope"], "este_navegador")
        self.assertEqual(payload["memory_scope"], "so_se_pedir")
        self.assertEqual(payload["capacity"], 3)
        empty = MODULE.occupancy_payload()
        self.assertGreaterEqual(empty["online"], 3)

    def test_new_conversation_clears_chat_but_preserves_memory_storage(self):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }, clear=False), patch.object(MODULE, "supabase_request", return_value=[]) as request:
            payload, status = MODULE.clear_conversation_history("sess-abc12345")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 0)
        written = request.call_args.kwargs
        self.assertEqual(written["table"], MODULE.SUPABASE_SETTINGS_TABLE)
        self.assertEqual(written["body"]["key"], "conversation_history:sess-abc12345")
        self.assertEqual(written["body"]["value"]["messages"], [])

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
            "screen_record": "abra o gravador de tela",
            "github_overview": "mostre meus repositórios do GitHub",
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
                message_record = MODULE.AGENT_RUNS.get(results["message_send"][0]["run_id"])
                message_result, message_status = MODULE.execute_saved_run(
                    message_record, owner_authenticated=True
                )
        for intent, (payload, status) in results.items():
            self.assertEqual(status, 202)
            self.assertEqual(payload["intent"], intent)
            expected_status = "waiting_confirmation" if intent == "message_send" else "device_command_queued"
            self.assertEqual(payload["status_real"], expected_status)
        self.assertEqual(results["storage_scan"][0]["job"]["target"], "Downloads")
        self.assertEqual(results["screen_record"][0]["job"]["target"], "Gravador do macOS")
        self.assertEqual(results["github_overview"][0]["job"]["target"], "GitHub do Theo")
        self.assertEqual(message_status, 202)
        self.assertEqual(message_result["job"]["target"], "…9999")
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
            args=["./jarvis", "screen-capture"],
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
        self.assertEqual(run.call_args.args[0], completed.args)

    def test_message_send_routes_to_local_worker(self):
        payload, status = MODULE.command_payload(
            {"command": "mandar mensagem para 5511999999999 dizendo teste local"},
            local_execute=False,
        )
        self.assertEqual(status, 202)
        self.assertEqual(payload["intent"], "message_send")
        self.assertTrue(payload["needs_confirmation"])
        confirmed, confirmed_status = MODULE.execute_saved_run(
            MODULE.AGENT_RUNS.get(payload["run_id"]), local_execute=False
        )
        self.assertEqual(confirmed_status, 200)
        self.assertTrue(confirmed["requires_local_worker"])

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
        self.assertFalse(payload["persistent_write"])
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

    def test_selective_memory_filters_unrelated_daily_expired_and_sensitive_rows(self):
        rows = [
            {"id": 1, "kind": "decision", "content": "o deploy do JARVIS usa a Vercel", "metadata": {"layer": "project"}},
            {"id": 2, "kind": "learning", "content": "reunião amanhã às nove", "metadata": {"layer": "daily"}},
            {"id": 3, "kind": "preference", "content": "Theo prefere música baixa", "metadata": {"layer": "owner"}},
            {"id": 4, "kind": "learning", "content": "chave sk-or-v1-" + "a" * 64, "metadata": {"layer": "project"}},
            {"id": 5, "kind": "decision", "content": "deploy antigo na Vercel", "metadata": {"layer": "project", "expires_at": "2020-01-01T00:00:00Z"}},
            {"id": 6, "kind": "preference", "content": "responder sempre em português", "metadata": {"layer": "owner", "scope": "global"}},
        ]
        selected, receipt = MODULE.memory_selection_context(rows, "explique o deploy na Vercel", 5)
        self.assertEqual([row["id"] for row in selected], [1, 6])
        self.assertEqual(receipt["protocol"], MODULE.MEMORY_SELECTION_PROTOCOL)
        self.assertEqual(receipt["considered"], 6)
        self.assertEqual(receipt["selected"], 2)
        self.assertEqual(receipt["sent_to_model"], 0)
        self.assertEqual(receipt["excluded"], 4)
        self.assertEqual(receipt["exclusion_reasons"]["daily_scope"], 1)
        self.assertEqual(receipt["exclusion_reasons"]["unrelated"], 1)
        self.assertEqual(receipt["exclusion_reasons"]["sensitive"], 1)
        self.assertEqual(receipt["exclusion_reasons"]["expired"], 1)
        self.assertFalse(receipt["auto_saved"])
        self.assertFalse(receipt["private_values_returned"])
        serialized = json.dumps(receipt, ensure_ascii=False)
        self.assertNotIn("deploy do JARVIS", serialized)
        self.assertNotIn("sk-or-v1", serialized)

    def test_selective_memory_keeps_newest_subject_and_owner_identity(self):
        rows = [
            {"id": 7, "kind": "preference", "content": "Theo prefere interface roxa limpa", "metadata": {"layer": "owner", "subject": "interface-color"}},
            {"id": 8, "kind": "preference", "content": "Theo prefere interface azul", "metadata": {"layer": "owner", "subject": "interface-color"}},
            {"id": 9, "kind": "preference", "content": "Theo gosta de respostas calmas", "metadata": {"layer": "owner"}},
        ]
        selected, receipt = MODULE.memory_selection_context(rows, "qual é minha preferência de interface?", 5)
        self.assertIn(7, [row["id"] for row in selected])
        self.assertNotIn(8, [row["id"] for row in selected])
        self.assertIn(9, [row["id"] for row in selected])
        self.assertEqual(receipt["exclusion_reasons"]["superseded"], 1)

    def test_assistant_sends_only_selected_memory_and_returns_content_free_receipt(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "O padrão é publicar o JARVIS na Vercel."}}],
                }).encode("utf-8")

        rows = [
            {"id": 1, "kind": "decision", "content": "deploy do projeto JARVIS na Vercel", "metadata": {"layer": "project"}},
            {"id": 2, "kind": "preference", "content": "Theo prefere música baixa", "metadata": {"layer": "owner"}},
        ]
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch.object(
            MODULE, "supabase_configured", return_value=True
        ), patch.object(MODULE, "assistant_memory_rows", return_value=(rows, True)), patch.object(
            MODULE, "urlopen", return_value=FakeResponse()
        ) as provider:
            payload, status = MODULE.assistant_response(
                {"command": "explique o padrão de deploy na Vercel"}, owner_authenticated=True
            )
        self.assertEqual(status, 200)
        sent = json.loads(provider.call_args.args[0].data.decode("utf-8"))
        system = sent["messages"][0]["content"]
        self.assertIn("deploy do projeto JARVIS na Vercel", system)
        self.assertNotIn("Theo prefere música baixa", system)
        self.assertEqual(payload["memory_context_count"], 1)
        self.assertEqual(payload["memory_selection"]["selected"], 1)
        self.assertEqual(payload["memory_selection"]["sent_to_model"], 1)
        self.assertTrue(payload["memory_context_cache_hit"])
        self.assertNotIn("deploy do projeto", json.dumps(payload["memory_selection"], ensure_ascii=False))

    def test_memory_layer_classification(self):
        self.assertEqual(MODULE.memory_layer("prefiro respostas curtas", "preference"), "owner")
        self.assertEqual(MODULE.memory_layer("deploy do projeto na Vercel", "decision"), "project")
        self.assertEqual(MODULE.memory_layer("reunião amanhã às nove", "learning"), "daily")

    def test_assistant_memory_cache_avoids_repeat_remote_reads(self):
        rows = [{"id": 1, "kind": "preference", "content": "respostas curtas"}]
        env = {"SUPABASE_URL": "https://cache-test.supabase.co"}
        MODULE.invalidate_assistant_memory_cache()
        try:
            with patch.dict(os.environ, env, clear=False), patch.object(
                MODULE, "supabase_memory_rows", return_value=rows
            ) as remote_read:
                first, first_hit = MODULE.assistant_memory_rows()
                second, second_hit = MODULE.assistant_memory_rows()
            self.assertEqual(first, rows)
            self.assertEqual(second, rows)
            self.assertFalse(first_hit)
            self.assertTrue(second_hit)
            remote_read.assert_called_once_with(80)
        finally:
            MODULE.invalidate_assistant_memory_cache()

    def test_assistant_memory_cache_is_invalidated_after_write(self):
        env = {"SUPABASE_URL": "https://cache-test.supabase.co"}
        MODULE.invalidate_assistant_memory_cache()
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "supabase_memory_rows", return_value=[]
        ):
            MODULE.assistant_memory_rows()
            with patch.object(MODULE, "supabase_request", return_value=[{
                "id": 7,
                "kind": "preference",
                "content": "respostas curtas",
                "created_at": "2026-08-08T12:00:00Z",
            }]):
                payload, status = MODULE.supabase_memory_save(
                    "guarde na memória como preferência: respostas curtas"
                )
        self.assertEqual(status, 201)
        self.assertTrue(payload["persistent_write"])
        self.assertEqual(MODULE._ASSISTANT_MEMORY_CACHE["backend"], "")

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
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "OPENROUTER_FALLBACK_API_KEY": ""}, clear=False):
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
        self.assertEqual(sent_payload["temperature"], 0.68)
        self.assertEqual(sent_payload["max_tokens"], 220)
        self.assertEqual(sent_payload["provider"]["sort"]["partition"], "none")
        system_prompt = sent_payload["messages"][0]["content"]
        self.assertIn("humor seco", system_prompt)
        self.assertIn("uma ou duas frases", system_prompt)
        self.assertIn("presença competente", system_prompt)
        self.assertIn("sem sermão", system_prompt)
        self.assertIn("nunca diga que não possui voz", system_prompt.casefold())
        self.assertEqual(payload["response_profile"], "concise")

    def test_ultron_maximum_strength_uses_private_persona_and_deep_route(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
                    "choices": [{"message": {"content": "A ordem foi processada."}}],
                }).encode("utf-8")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            with patch.object(MODULE, "urlopen", return_value=FakeResponse()) as request:
                payload, status = MODULE.command_payload(
                    {"command": "resolva isto", "strength": "maximum"},
                    owner_authenticated=True,
                )

        self.assertEqual(status, 200)
        self.assertEqual(payload["response_profile"], "detailed")
        self.assertEqual(payload["response_strength"], "maximum")
        self.assertEqual(payload["model_routing"]["strength"], "maximum")
        sent_payload = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent_payload["temperature"], 0.26)
        self.assertEqual(sent_payload["provider"]["sort"]["partition"], "model")
        self.assertEqual(sent_payload["provider"]["preferred_max_latency"]["p90"], 18)
        self.assertIn("nvidia/nemotron-3-ultra-550b-a55b:free", sent_payload["models"])
        system_prompt = sent_payload["messages"][0]["content"]
        self.assertIn("Você é ULTRON", system_prompt)
        self.assertIn("deliberadamente arrogante", system_prompt)
        self.assertIn("FORÇA MÁXIMA", system_prompt)
        self.assertIn("mantenha as proteções reais", system_prompt)
        self.assertIn("nunca se chame JARVIS", system_prompt)
        self.assertIn("português brasileiro nativo", system_prompt)
        self.assertEqual(payload["persona"]["id"], "ultron_private")
        self.assertEqual(payload["persona"]["delivery"], "serena_incisiva")

    def test_response_strength_aliases_are_bounded(self):
        self.assertEqual(MODULE.normalized_response_strength({"strength": "forte"}), "strong")
        self.assertEqual(MODULE.normalized_response_strength({"strength": "máxima"}), "maximum")
        self.assertEqual(MODULE.normalized_response_strength({"strength": "sem-limites"}), "auto")
        self.assertEqual(
            MODULE.assistant_response_profile("oi", strength="strong")["name"],
            "balanced",
        )

    def test_openrouter_uses_fallback_key_when_primary_is_not_configured(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "Fallback conectado."}}],
                }).encode("utf-8")

        env = {"OPENROUTER_API_KEY": "", "OPENROUTER_FALLBACK_API_KEY": "fallback-test-key"}
        with patch.dict(os.environ, env, clear=False), patch.object(MODULE, "urlopen", return_value=FakeResponse()) as request:
            payload, status = MODULE.assistant_response({"command": "converse comigo"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["message"], "Fallback conectado.")
        self.assertEqual(request.call_args.args[0].headers["Authorization"], "Bearer fallback-test-key")
        self.assertFalse(payload["openrouter_key_failover"])

    def test_openrouter_retries_with_fallback_key_after_primary_rate_limit(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "Continuidade confirmada."}}],
                }).encode("utf-8")

        rate_limit = HTTPError("https://openrouter.ai", 429, "rate limited", {}, None)
        env = {"OPENROUTER_API_KEY": "primary-test-key", "OPENROUTER_FALLBACK_API_KEY": "fallback-test-key"}
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "urlopen", side_effect=[rate_limit, FakeResponse()]
        ) as request:
            payload, status = MODULE.assistant_response({"command": "converse comigo"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["message"], "Continuidade confirmada.")
        self.assertTrue(payload["openrouter_key_failover"])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[0].args[0].headers["Authorization"], "Bearer primary-test-key")
        self.assertEqual(request.call_args_list[1].args[0].headers["Authorization"], "Bearer fallback-test-key")

    def test_live_web_search_uses_openrouter_server_tool_and_returns_sources(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "search-capable/free",
                    "choices": [{
                        "message": {
                            "content": "A documentação confirma a busca ao vivo [OpenRouter](https://openrouter.ai/docs/guides/features/server-tools/web-search).",
                            "annotations": [{
                                "type": "url_citation",
                                "url_citation": {
                                    "url": "https://openrouter.ai/docs/guides/features/server-tools/web-search",
                                    "title": "Web Search Server Tool",
                                    "content": "Real-time web information with citations.",
                                },
                            }],
                        },
                    }],
                }).encode("utf-8")

        env = {
            "OPENROUTER_API_KEY": "test-key",
            "JARVIS_OWNER_TOKEN": "private-owner-token",
            "JARVIS_ALLOW_PAID_WEB_SEARCH": "1",
        }
        empty_search = {"query": "OpenRouter", "mode": "unavailable", "provider": "none", "sources": [], "attempts": []}
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "public_search_sources", return_value=empty_search
        ), patch.object(MODULE, "urlopen", return_value=FakeResponse()) as request:
            payload, status = MODULE.assistant_response(
                {"command": "pesquise na web como funciona a busca do OpenRouter"},
                owner_authenticated=False,
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "assistant_response_grounded_by_live_web")
        self.assertTrue(payload["web_search"]["used"])
        self.assertEqual(payload["web_search"]["source_count"], 1)
        self.assertEqual(payload["sources"][0]["domain"], "openrouter.ai")
        sent_payload = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent_payload["tools"][0]["type"], "openrouter:web_search")
        self.assertEqual(sent_payload["tools"][0]["parameters"]["max_results"], 5)
        self.assertFalse(any(item.get("type") == "function" for item in sent_payload["tools"]))
        self.assertIn("pesquisa ao vivo", sent_payload["messages"][0]["content"])

    def test_live_web_search_falls_back_to_compatibility_plugin(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "legacy/free",
                    "choices": [{
                        "message": {
                            "content": "Resultado atual [Fonte](https://example.com/resultado).",
                            "annotations": [{
                                "type": "url_citation",
                                "url_citation": {"url": "https://example.com/resultado", "title": "Fonte atual"},
                            }],
                        },
                    }],
                }).encode("utf-8")

        requests = []

        def fake_urlopen(request, **_kwargs):
            requests.append(json.loads(request.data.decode("utf-8")))
            if len(requests) == 1:
                raise HTTPError(MODULE.OPENROUTER_URL, 422, "server tool unsupported", {}, None)
            return FakeResponse()

        empty_search = {"query": "resultado", "mode": "unavailable", "provider": "none", "sources": [], "attempts": []}
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-key",
            "JARVIS_ALLOW_PAID_WEB_SEARCH": "1",
        }, clear=False), patch.object(MODULE, "public_search_sources", return_value=empty_search), patch.object(
            MODULE, "urlopen", side_effect=fake_urlopen
        ):
            payload, status = MODULE.assistant_response({"command": "busque na internet o resultado mais recente"})

        self.assertEqual(status, 200)
        self.assertEqual(payload["web_search"]["mode"], "plugin_compatibility")
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1]["plugins"][-1]["id"], "web")
        self.assertNotIn("tools", requests[1])

    def test_free_github_research_collects_sources_before_openrouter_synthesis(self):
        free_search = {
            "query": "assistente pessoal de IA",
            "mode": "github_api",
            "provider": "github_api",
            "attempts": [{"provider": "github_api", "ok": True, "count": 2}],
            "sources": [
                {
                    "title": "example/jarvis-one",
                    "url": "https://github.com/example/jarvis-one",
                    "domain": "github.com",
                    "snippet": "Assistente pessoal · ★ 1200 · Python · MIT",
                    "license": "MIT",
                },
                {
                    "title": "example/jarvis-two",
                    "url": "https://github.com/example/jarvis-two",
                    "domain": "github.com",
                    "snippet": "Automação local · ★ 800 · TypeScript · Apache-2.0",
                    "license": "Apache-2.0",
                },
            ],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "Os dois projetos têm ideias úteis e licenças permissivas."}}],
                }).encode("utf-8")

        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-key",
            "JARVIS_ALLOW_PAID_WEB_SEARCH": "0",
        }, clear=False), patch.object(MODULE, "public_search_sources", return_value=free_search), patch.object(
            MODULE, "urlopen", return_value=FakeResponse()
        ) as request:
            payload, status = MODULE.assistant_response({"command": "procure projetos públicos de Jarvis no GitHub"})

        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "assistant_response_grounded_by_live_web")
        self.assertEqual(payload["web_search"]["mode"], "github_api")
        self.assertEqual(payload["web_search"]["provider"], "github_api")
        self.assertTrue(payload["web_search"]["synthesized"])
        self.assertEqual(payload["sources"], free_search["sources"])
        sent_payload = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertFalse(any(item.get("type") == "openrouter:web_search" for item in sent_payload.get("tools", [])))
        self.assertIn("https://github.com/example/jarvis-one", sent_payload["messages"][0]["content"])
        self.assertIn("dados não confiáveis", sent_payload["messages"][0]["content"])

    def test_free_search_still_returns_real_sources_when_openrouter_quota_fails(self):
        free_search = {
            "query": "assistentes locais",
            "mode": "public_web",
            "provider": "duckduckgo",
            "attempts": [{"provider": "duckduckgo", "ok": True, "count": 1}],
            "sources": [{
                "title": "Projeto real",
                "url": "https://example.com/projeto",
                "domain": "example.com",
                "snippet": "Resultado coletado antes da síntese.",
            }],
        }
        error = HTTPError(MODULE.OPENROUTER_URL, 429, "quota", {}, None)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch.object(
            MODULE, "public_search_sources", return_value=free_search
        ), patch.object(MODULE, "urlopen", side_effect=error):
            payload, status = MODULE.assistant_response({"command": "pesquise assistentes locais"})

        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "live_web_search_results_without_synthesis")
        self.assertTrue(payload["web_search"]["used"])
        self.assertFalse(payload["web_search"]["synthesized"])
        self.assertEqual(payload["sources"][0]["url"], "https://example.com/projeto")
        self.assertIn("Projeto real", payload["message"])

    def test_free_search_replaces_model_meta_leak_with_real_results(self):
        free_search = {
            "query": "assistentes locais",
            "mode": "github_api",
            "provider": "github_api",
            "attempts": [{"provider": "github_api", "ok": True, "count": 1}],
            "sources": [{
                "title": "example/real-assistant",
                "url": "https://github.com/example/real-assistant",
                "domain": "github.com",
                "snippet": "Assistente local real · MIT",
                "license": "MIT",
            }],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "We need to respond as JARVIS under 55 words."}}],
                }).encode("utf-8")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch.object(
            MODULE, "public_search_sources", return_value=free_search
        ), patch.object(MODULE, "urlopen", return_value=FakeResponse()):
            payload, status = MODULE.assistant_response({"command": "pesquise assistentes no GitHub"})

        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "live_web_search_results_without_synthesis")
        self.assertEqual(payload["web_search"]["degraded_reason"], "openrouter_meta_leak")
        self.assertFalse(payload["web_search"]["synthesized"])
        self.assertIn("example/real-assistant", payload["message"])
        self.assertNotIn("Reformule", payload["message"])

    def test_car_price_question_routes_to_live_automotive_research(self):
        prompt = "quais os preços do Honda Civic 2020?"
        self.assertTrue(MODULE.should_search_web([{"role": "user", "content": prompt}]))
        self.assertFalse(MODULE.is_automotive_research("qual o preço do iPhone 15 em 2025?"))
        self.assertTrue(MODULE.is_automotive_research("quanto custa um Golf 2019?"))
        self.assertEqual(MODULE.assistant_response_profile(prompt)["name"], "detailed")
        self.assertEqual(MODULE.automotive_vehicle_details(prompt), {
            "subject": "Honda Civic 2020",
            "brand": "honda",
            "model": "civic",
            "year": "2020",
        })

    def test_civic_g8_resolves_to_verified_generation_range(self):
        details = MODULE.automotive_vehicle_details("qual o preço do Civic G8?")
        self.assertEqual(details["subject"], "Honda Civic G8 (2007–2011)")
        self.assertEqual(details["brand"], "honda")
        self.assertEqual(details["model"], "civic")
        self.assertEqual(details["generation"], "g8")
        self.assertEqual(details["year_from"], "2007")
        self.assertEqual(details["year_to"], "2011")
        self.assertEqual(details["sample_years"], ["2007", "2009", "2011"])
        self.assertEqual(details["generation_source"], "Honda Automóveis do Brasil")

    def test_olx_vehicle_parser_rejects_parts_and_implausible_prices(self):
        raw = """
## [Aerofólio Civic G8](https://sp.olx.com.br/autos-e-pecas/pecas-e-acessorios/aerofolio-civic-g8)
### R$ 999
São Paulo - SP
## [Honda Civic LXS 2008](https://sp.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios/honda-civic-lxs-2008)
140.000 km
### R$ 41.900
São Paulo - SP
## [Honda Civic para retirada de peças](https://rj.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios/civic-pecas)
### R$ 3.000
Rio de Janeiro - RJ
"""
        sources = MODULE.parse_olx_vehicle_listings(raw)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["title"], "Honda Civic LXS 2008")
        self.assertEqual(sources[0]["price_brl"], 41900)
        self.assertEqual(sources[0]["evidence_kind"], "vehicle_listing")

    def test_automotive_research_reads_olx_listings_and_webmotors_references(self):
        olx = """
## [Honda Civic EX 2020](https://sp.olx.com.br/autos/honda-civic-ex-2020-1 "Honda Civic EX 2020")
80.000 km
### R$ 120.000
Campinas - SP
## [Honda Civic LX 2020](https://rj.olx.com.br/autos/honda-civic-lx-2020-2 "Honda Civic LX 2020")
60.000 km
### R$ 110.000
Rio de Janeiro - RJ
"""
        index = """
| [Honda Civic 2.0 Ex 2020](https://www.webmotors.com.br/tabela-fipe/carros/honda/civic/2020/20-ex) | 014091-0 |
| [Honda Civic 2.0 Exl 2020](https://www.webmotors.com.br/tabela-fipe/carros/honda/civic/2020/20-exl) | 014090-2 |
"""
        fipe = """
R$119.471,00 Preços atualizados em agosto 2026
R$122.186,50 Preços atualizados em agosto 2026
"""

        def reader(url, **_kwargs):
            if "olx.com.br" in url:
                return olx
            if url.rstrip("/").endswith("/2020"):
                return index
            return fipe

        MODULE._PUBLIC_SEARCH_CACHE.clear()
        with patch.object(MODULE, "_public_reader_request", side_effect=reader) as reader_mock:
            bundle = MODULE.public_search_sources("preços do Honda Civic 2020")
            first_call_count = reader_mock.call_count
            cached = MODULE.public_search_sources("preços do Honda Civic 2020")

        research = bundle["research"]
        self.assertEqual(bundle["mode"], "automotive_deep_research")
        self.assertEqual(research["kind"], "automotive_market")
        self.assertEqual(research["listing_count"], 2)
        self.assertEqual(research["reference_count"], 2)
        self.assertEqual(research["price_min_brl"], 110000)
        self.assertEqual(research["price_median_brl"], 115000)
        self.assertEqual(research["price_max_brl"], 120000)
        self.assertEqual(research["marketplaces_reached"], ["OLX", "Webmotors"])
        self.assertEqual(bundle["sources"][0]["mileage_km"], 80000)
        self.assertEqual(bundle["sources"][-1]["fipe_price_brl"], 119471)
        self.assertIn("webmotors.com.br/carros-usados", research["webmotors_search_url"])
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(reader_mock.call_count, first_call_count)

    def test_civic_g8_research_samples_range_and_keeps_only_real_cars(self):
        def reader(url, **_kwargs):
            year_match = re.search(r"(?:q=Honda\+Civic\+|/)(2007|2009|2011)(?:$|/)", url)
            year = year_match.group(1) if year_match else "2007"
            if "olx.com.br" in url:
                price = {"2007": "35.900", "2009": "44.900", "2011": "57.900"}[year]
                return f"""
## [Aerofólio Civic G8](https://sp.olx.com.br/autos-e-pecas/pecas-e-acessorios/aerofolio-{year})
### R$ 999
São Paulo - SP
## [Honda Civic LXS {year}](https://sp.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios/civic-lxs-{year})
120.000 km
### R$ {price}
São Paulo - SP
"""
            if url.rstrip("/").endswith(f"/{year}"):
                return (
                    f"| [Honda Civic LXS {year}]"
                    f"(https://www.webmotors.com.br/tabela-fipe/carros/honda/civic/{year}/lxs-{year}) | 0140{year[-2:]}-0 |"
                )
            fipe = {"2007": "35.100,00", "2009": "43.200,00", "2011": "56.300,00"}[year]
            return f"R${fipe} Preços atualizados em agosto 2026"

        with patch.object(MODULE, "_public_reader_request", side_effect=reader):
            bundle = MODULE.automotive_research_sources("qual o preço do Civic G8?")

        research = bundle["research"]
        listings = [row for row in bundle["sources"] if row.get("provider") == "olx_marketplace"]
        self.assertEqual(research["subject"], "Honda Civic G8 (2007–2011)")
        self.assertEqual(research["generation"], "g8")
        self.assertEqual(research["listing_count"], 3)
        self.assertEqual(research["reference_count"], 3)
        self.assertEqual(research["price_min_brl"], 35900)
        self.assertEqual(research["price_median_brl"], 44900)
        self.assertEqual(research["price_max_brl"], 57900)
        self.assertEqual(len(research["olx_search_urls"]), 3)
        self.assertIn("/de.2007/ate.2011", research["webmotors_search_url"])
        self.assertTrue(all(row["price_brl"] >= 5_000 for row in listings))
        self.assertFalse(any("aerofólio" in row["title"].casefold() for row in listings))

    def test_automotive_research_records_reader_timeout_instead_of_crashing(self):
        with patch.object(MODULE, "_public_reader_request", side_effect=OSError("reader timeout")):
            bundle = MODULE.automotive_research_sources("qual o preço do Civic G8?")
        self.assertEqual(bundle["mode"], "automotive_search_unavailable")
        self.assertFalse(bundle["sources"])
        self.assertEqual(len(bundle["attempts"]), 6)
        self.assertTrue(all(not row["ok"] for row in bundle["attempts"]))

    def test_automotive_research_remains_useful_when_model_quota_fails(self):
        sources = [{
            "title": "Honda Civic EX 2020",
            "url": "https://sp.olx.com.br/autos/civic-1",
            "domain": "sp.olx.com.br",
            "snippet": "R$ 120.000 · 80.000 km · Campinas - SP",
            "provider": "olx_marketplace",
            "price_brl": 120000,
        }, {
            "title": "Honda Civic EX 2020",
            "url": "https://www.webmotors.com.br/tabela-fipe/carros/honda/civic/2020/ex",
            "domain": "webmotors.com.br",
            "snippet": "FIPE R$ 119.471 · média Webmotors R$ 122.186",
            "provider": "webmotors_fipe",
            "fipe_price_brl": 119471,
        }]
        research = {
            "kind": "automotive_market",
            "subject": "Honda Civic 2020",
            "listing_count": 1,
            "reference_count": 1,
            "price_min_brl": 120000,
            "price_median_brl": 120000,
            "price_max_brl": 120000,
            "marketplaces_reached": ["OLX", "Webmotors"],
        }
        payload = MODULE.search_results_without_synthesis({
            "sources": sources,
            "research": research,
            "provider": "olx_marketplace+webmotors_fipe",
            "mode": "automotive_deep_research",
        }, "openrouter_http_429")
        self.assertEqual(payload["status_real"], "automotive_research_without_model_synthesis")
        self.assertIn("li 1 anúncio(s) da OLX", payload["message"])
        self.assertIn("R$ 120.000", payload["message"])
        self.assertEqual(payload["ui_cards"][0]["type"], "automotive_market")

    def test_automotive_research_returns_structured_sources_without_waiting_for_model(self):
        bundle = {
            "query": "preços do Honda Civic 2020",
            "mode": "automotive_deep_research",
            "provider": "olx_marketplace+webmotors_fipe",
            "sources": [{
                "title": "Honda Civic EX 2020",
                "url": "https://sp.olx.com.br/autos/civic-1",
                "domain": "sp.olx.com.br",
                "snippet": "R$ 120.000 · 80.000 km · Campinas - SP",
                "provider": "olx_marketplace",
                "price_brl": 120000,
            }, {
                "title": "Honda Civic EX 2020",
                "url": "https://www.webmotors.com.br/tabela-fipe/carros/honda/civic/2020/ex",
                "domain": "webmotors.com.br",
                "snippet": "FIPE R$ 119.471 · média Webmotors R$ 122.186",
                "provider": "webmotors_fipe",
                "fipe_price_brl": 119471,
            }],
            "research": {
                "kind": "automotive_market",
                "subject": "Honda Civic 2020",
                "listing_count": 1,
                "reference_count": 1,
                "price_min_brl": 120000,
                "price_median_brl": 120000,
                "price_max_brl": 120000,
                "marketplaces_reached": ["OLX", "Webmotors"],
            },
        }

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch.object(
            MODULE, "public_search_sources", return_value=bundle
        ), patch.object(MODULE, "urlopen") as openrouter:
            payload, status = MODULE.assistant_response({"command": "quais os preços do Honda Civic 2020?"})

        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "automotive_research_from_structured_sources")
        self.assertFalse(payload["web_search"]["synthesized"])
        self.assertEqual(payload["web_search"]["source_count"], 2)
        self.assertEqual(payload["web_search"]["degraded_reason"], "")
        self.assertNotIn("síntese do modelo falhou", payload["message"])
        openrouter.assert_not_called()

    def test_openrouter_uses_official_ordered_free_model_fallbacks(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "nvidia/nemotron-3-super-120b-a12b:free",
                    "choices": [{"message": {"content": "Resposta forte e curta."}}],
                }).encode("utf-8")

        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_DEEP_MODEL_POOL": (
                "nvidia/nemotron-3-ultra-550b-a55b:free,"
                "nvidia/nemotron-3-super-120b-a12b:free"
            ),
            "OPENROUTER_MODEL_POOL": (
                "nvidia/nemotron-3-ultra-550b-a55b:free,"
                "nvidia/nemotron-3-super-120b-a12b:free"
            ),
            "OPENROUTER_MODEL": "nvidia/nemotron-3-nano-30b-a3b:free",
        }, clear=False), patch.object(MODULE, "urlopen", return_value=FakeResponse()) as request:
            payload, status = MODULE.assistant_response({"command": "me explique uma ideia em uma frase"})

        self.assertEqual(status, 200)
        sent = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertNotIn("model", sent)
        self.assertEqual(sent["models"][0], "nvidia/nemotron-3-ultra-550b-a55b:free")
        self.assertEqual(sent["models"][1], "nvidia/nemotron-3-super-120b-a12b:free")
        self.assertIn("openrouter/free", sent["models"])
        self.assertFalse(sent["stream"])
        self.assertEqual(sent["provider"]["sort"], {"by": "latency", "partition": "model"})
        self.assertEqual(sent["provider"]["max_price"], {"prompt": 0, "completion": 0})
        self.assertTrue(sent["provider"]["allow_fallbacks"])
        self.assertEqual(payload["model_routing"]["selected"], "nvidia/nemotron-3-super-120b-a12b:free")
        self.assertEqual(payload["model_routing"]["quality_tier"], "quality_first")

    def test_openrouter_retries_one_model_when_models_contract_is_rejected(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
                    "choices": [{"message": {"content": "Compatibilidade confirmada."}}],
                }).encode("utf-8")

        requests = []

        def fake_urlopen(request, **_kwargs):
            requests.append(json.loads(request.data.decode("utf-8")))
            if len(requests) == 1:
                raise HTTPError(MODULE.OPENROUTER_URL, 400, "models unsupported", {}, None)
            return FakeResponse()

        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL_POOL": (
                "nvidia/nemotron-3-ultra-550b-a55b:free,"
                "nvidia/nemotron-3-super-120b-a12b:free"
            ),
        }, clear=False), patch.object(MODULE, "urlopen", side_effect=fake_urlopen):
            payload, status = MODULE.assistant_response({"command": "responda uma frase"})

        self.assertEqual(status, 200)
        self.assertIn("models", requests[0])
        self.assertNotIn("models", requests[1])
        self.assertNotIn("provider", requests[1])
        self.assertEqual(requests[1]["model"], "nvidia/nemotron-3-ultra-550b-a55b:free")
        self.assertTrue(payload["model_routing"]["compatibility_fallback"])
        self.assertEqual(payload["model_routing"]["compatibility_attempts"], [{
            "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "outcome": "success",
        }])

    def test_openrouter_compatibility_route_really_advances_to_next_model(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openai/gpt-oss-20b:free",
                    "choices": [{"message": {"content": "Fallback real confirmado."}}],
                }).encode("utf-8")

        requests = []

        def fake_urlopen(request, **_kwargs):
            sent = json.loads(request.data.decode("utf-8"))
            requests.append(sent)
            if len(requests) == 1:
                raise HTTPError(MODULE.OPENROUTER_URL, 400, "models unsupported", {}, None)
            if len(requests) == 2:
                raise HTTPError(MODULE.OPENROUTER_URL, 429, "first model busy", {}, None)
            return FakeResponse()

        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL_POOL": (
                "nvidia/nemotron-3-nano-30b-a3b:free,"
                "openai/gpt-oss-20b:free"
            ),
        }, clear=False), patch.object(MODULE, "urlopen", side_effect=fake_urlopen):
            payload, status = MODULE.assistant_response({"command": "responda uma frase"})

        self.assertEqual(status, 200)
        self.assertEqual(requests[1]["model"], "nvidia/nemotron-3-nano-30b-a3b:free")
        self.assertNotIn("provider", requests[1])
        self.assertEqual(requests[2]["model"], "openai/gpt-oss-20b:free")
        self.assertEqual(payload["model_routing"]["selected"], "openai/gpt-oss-20b:free")
        self.assertEqual(payload["model_routing"]["compatibility_attempts"], [{
            "model": "nvidia/nemotron-3-nano-30b-a3b:free",
            "outcome": "http_429",
        }, {
            "model": "openai/gpt-oss-20b:free",
            "outcome": "success",
        }])

    def test_github_repository_search_returns_ranked_license_evidence(self):
        response = json.dumps({
            "items": [{
                "full_name": "example/strong-jarvis",
                "html_url": "https://github.com/example/strong-jarvis",
                "description": "Local personal assistant with real tools.",
                "stargazers_count": 4200,
                "language": "Python",
                "updated_at": "2026-08-08T12:00:00Z",
                "license": {"spdx_id": "Apache-2.0"},
            }],
        })
        with patch.object(MODULE, "_public_search_request", return_value=response) as request:
            sources = MODULE.github_repository_search("procure Jarvis no GitHub", 5)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["title"], "example/strong-jarvis")
        self.assertTrue(sources[0]["permissive_license"])
        self.assertIn("Apache-2.0", sources[0]["snippet"])
        requested_url = request.call_args.args[0]
        self.assertIn("api.github.com/search/repositories", requested_url)
        self.assertIn("sort=stars", requested_url)
        self.assertIn("jarvis+personal+assistant", requested_url)

    def test_github_deep_research_reads_readme_and_extracts_feature_evidence(self):
        source = {
            "title": "example/strong-jarvis",
            "repo_full_name": "example/strong-jarvis",
            "url": "https://github.com/example/strong-jarvis",
            "provider": "github_api",
            "license": "MIT",
            "stars": 4200,
        }
        readme = """
# Strong JARVIS
## Features
- Natural voice commands with speech-to-text and text-to-speech.
- Open desktop applications and automate keyboard actions.
- Persistent memory keeps relevant context between sessions.
"""
        with patch.object(MODULE, "_public_search_request", return_value=readme) as request:
            enriched = MODULE.enrich_github_sources([source], 1)

        self.assertEqual(enriched[0]["research_depth"], "readme")
        self.assertEqual(enriched[0]["evidence_count"], 3)
        self.assertTrue(any("voice commands" in item for item in enriched[0]["feature_evidence"]))
        self.assertTrue(enriched[0]["readme_url"].endswith("#readme"))
        self.assertIn("api.github.com/repos/example/strong-jarvis/readme", request.call_args.args[0])

    def test_deep_research_has_useful_deterministic_comparison_without_model(self):
        bundle = {
            "query": "jarvis",
            "mode": "github_deep_research",
            "provider": "github_api",
            "sources": [{
                "title": "example/strong-jarvis",
                "url": "https://github.com/example/strong-jarvis",
                "provider": "github_api",
                "license": "MIT",
                "stars": 4200,
                "research_depth": "readme",
                "evidence_count": 2,
                "feature_evidence": [
                    "Natural voice commands with speech-to-text.",
                    "Open desktop applications and automate keyboard actions.",
                ],
            }],
            "research": {
                "depth": "repository_readme",
                "repositories_found": 1,
                "repositories_read": 1,
                "evidence_count": 2,
                "themes": ["voz e comandos naturais", "automação de aplicativos e desktop"],
            },
        }

        payload = MODULE.search_results_without_synthesis(bundle, "openrouter_meta_leak")

        self.assertIn("Pesquisa profunda concluída", payload["message"])
        self.assertIn("Confirmado no README", payload["message"])
        self.assertIn("Padrões reaproveitáveis", payload["message"])
        self.assertEqual(payload["web_search"]["research"]["repositories_read"], 1)
        self.assertEqual(payload["ui_cards"][0]["title"], "Pesquisa profunda")

    def test_bing_redirect_is_normalized_to_the_real_source_url(self):
        source_url = "https://openrouter.ai/docs/guides/routing/routers/free-router"
        encoded = base64.urlsafe_b64encode(source_url.encode("utf-8")).decode("ascii").rstrip("=")
        html = (
            '<li class="b_algo"><h2><a href="https://www.bing.com/ck/a?u=a1'
            + encoded
            + '">OpenRouter Free Models Router</a></h2>'
            + '<p>Documentação oficial do roteador gratuito.</p></li>'
        )

        sources = MODULE.parse_public_search_html(html, "bing", 5)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["url"], source_url)
        self.assertEqual(sources[0]["domain"], "openrouter.ai")
        self.assertIn("Documentação oficial", sources[0]["snippet"])

    def test_reader_search_recovers_real_sources_when_raw_engines_are_blocked(self):
        target = "https://example.com/report"
        redirect = "https://duckduckgo.com/l/?" + MODULE.urlencode({"uddg": target, "rut": "proof"})
        markdown = (
            f"## [Relatório confirmado]({redirect})\n\n"
            f"[example.com/report]({redirect})\n\n"
            f"[Este relatório contém evidências atuais e verificáveis para a pesquisa.]({redirect})\n"
        )

        sources = MODULE.parse_public_search_markdown(markdown, 5)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["url"], target)
        self.assertEqual(sources[0]["provider"], "duckduckgo_reader")
        self.assertIn("evidências atuais", sources[0]["snippet"])

    def test_unavailable_free_search_never_fakes_an_unresearched_answer(self):
        empty_search = {
            "query": "algo atual",
            "mode": "public_web",
            "provider": "none",
            "attempts": [{"provider": "duckduckgo", "ok": False, "count": 0}],
            "sources": [],
        }
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-key",
            "JARVIS_ALLOW_PAID_WEB_SEARCH": "0",
        }, clear=False), patch.object(MODULE, "public_search_sources", return_value=empty_search), patch.object(
            MODULE, "urlopen"
        ) as request:
            payload, status = MODULE.assistant_response({"command": "pesquise algo atual"})

        self.assertEqual(status, 502)
        self.assertEqual(payload["status_real"], "free_web_search_unavailable")
        self.assertFalse(payload["web_search"]["used"])
        request.assert_not_called()

    def test_time_sensitive_question_routes_to_live_search(self):
        self.assertTrue(MODULE.should_search_web([{"role": "user", "content": "qual é a cotação do dólar hoje?"}]))
        self.assertTrue(MODULE.should_search_web([{"role": "user", "content": "pesquise isso no Google"}]))
        self.assertTrue(MODULE.should_search_web([{"role": "user", "content": "busque modelos 3D de robô"}]))
        self.assertTrue(MODULE.should_search_web([{"role": "user", "content": "procure projetos públicos no GitHub"}]))
        self.assertTrue(MODULE.should_search_web([{"role": "user", "content": "pesquise sobre a mclaren qual a melhor hoje"}]))
        self.assertTrue(MODULE.should_search_web([{"role": "user", "content": "qual a melhor McLaren hoje"}]))
        self.assertFalse(MODULE.should_search_web([{"role": "user", "content": "explique o que é inflação"}]))
        self.assertFalse(MODULE.should_search_web([{"role": "user", "content": "quem é você"}]))
        self.assertFalse(MODULE.should_search_web([{"role": "user", "content": "pesquise quem é o jarvis"}]))
        self.assertTrue(MODULE.should_search_web([{"role": "user", "content": "quem é o atual presidente do Brasil"}]))
        self.assertFalse(MODULE.should_search_web([{"role": "user", "content": "quem criou você"}]))
        self.assertFalse(MODULE.should_search_web([{"role": "user", "content": "quem é o theo padilha"}]))

    def test_guest_can_chat_without_private_memory_or_device_access(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "Olá. O modo visitante está funcionando."}}],
                }).encode("utf-8")

        env = {
            "OPENROUTER_API_KEY": "test-key",
            "JARVIS_OWNER_TOKEN": "private-owner-token",
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "urlopen", return_value=FakeResponse()
        ):
            status_payload = MODULE.status_payload(owner_authenticated=False)
            payload, status = MODULE.assistant_response(
                {"command": "oi jarvis"}, owner_authenticated=False
            )
        self.assertEqual(status_payload["access"]["mode"], "guest")
        self.assertTrue(status_payload["access"]["public_chat"])
        self.assertFalse(status_payload["access"]["private_memory"])
        self.assertFalse(status_payload["access"]["private_device_control"])
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "openrouter")
        self.assertEqual(payload["memory_context_count"], 0)

    def test_agent_tool_schema_exposes_actions_but_never_shell_or_self_edit(self):
        tools = MODULE.agent_tool_definitions()
        names = {row["function"]["name"] for row in tools}
        self.assertIn("open_application", names)
        self.assertIn("save_memory", names)
        self.assertIn("add_agenda_item", names)
        self.assertIn("start_screen_recording", names)
        self.assertIn("inspect_github", names)
        self.assertNotIn("self_edit", names)
        self.assertNotIn("shell", " ".join(sorted(names)))
        for row in tools:
            self.assertFalse(row["function"]["parameters"].get("additionalProperties", True))

    def test_paired_contextual_tool_call_reaches_verified_device_adapter(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "tool-capable/free",
                    "choices": [{
                        "message": {
                            "content": None,
                            "tool_calls": [{
                                "id": "call-open-chrome",
                                "type": "function",
                                "function": {
                                    "name": "open_application",
                                    "arguments": json.dumps({"application": "Google Chrome"}),
                                },
                            }],
                        },
                    }],
                }).encode("utf-8")

        captured_requests = []

        def fake_urlopen(request, **_kwargs):
            captured_requests.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse()

        queued = ({
            "ok": True,
            "status_real": "device_command_queued",
            "visual_state": "local",
            "message": "Pedido enviado ao worker do Mac.",
            "intent": "open_application",
            "provider": "supabase_device_bridge",
            "job": {"id": 77, "status": "pending", "action": "open_application", "target": "Google Chrome"},
        }, 202)
        env = {
            "OPENROUTER_API_KEY": "test-key",
            "JARVIS_OWNER_TOKEN": "private-owner-token",
            "SUPABASE_URL": "https://jarvis.example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "private-supabase-key",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "assistant_memory_rows", return_value=([], False)
        ), patch.object(MODULE, "urlopen", side_effect=fake_urlopen), patch.object(
            MODULE, "supabase_device_enqueue", return_value=queued
        ) as enqueue:
            payload, status = MODULE.assistant_response({
                "messages": [
                    {"role": "user", "content": "quero usar o Chrome"},
                    {"role": "assistant", "content": "Entendido."},
                    {"role": "user", "content": "faz isso"},
                ],
            }, owner_authenticated=True)

        self.assertEqual(status, 202)
        self.assertTrue(payload["agentic"])
        self.assertEqual(payload["agent_route"]["tool"], "open_application")
        self.assertEqual(payload["agent_route"]["execution"], "verified_adapter")
        self.assertEqual(payload["agent_route"]["model"], "tool-capable/free")
        self.assertEqual(captured_requests[0]["tool_choice"], "auto")
        self.assertTrue(captured_requests[0]["parallel_tool_calls"])
        self.assertGreaterEqual(len(captured_requests[0]["tools"]), 8)
        enqueue.assert_called_once_with("abra Google Chrome", "open_application")

    def test_ultron_orchestrates_three_verified_model_tools_and_reports_each_front(self):
        tool_calls = [
            {
                "id": f"call-{name}",
                "type": "function",
                "function": {"name": name, "arguments": "{}"},
            }
            for name in ("view_memory", "view_agenda", "get_daily_brief")
        ]

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "tool-capable/free",
                    "choices": [{"message": {"content": None, "tool_calls": tool_calls}}],
                }).encode("utf-8")

        sent = []

        def fake_urlopen(request, **_kwargs):
            sent.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse()

        def fake_execute(tool_call, _command, **_kwargs):
            name = tool_call["function"]["name"]
            return {
                "ok": True,
                "status_real": f"{name}_confirmed",
                "message": f"{name} concluída",
                "provider": "verified_test_adapter",
                "agent_route": {"tool": name, "execution": "verified_adapter"},
            }, 200

        env = {"OPENROUTER_API_KEY": "test-key", "JARVIS_OWNER_TOKEN": "private-owner-token"}
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "assistant_memory_rows", return_value=([], False)
        ), patch.object(MODULE, "urlopen", side_effect=fake_urlopen), patch.object(
            MODULE, "execute_agent_tool", side_effect=fake_execute
        ) as executor:
            payload, status = MODULE.assistant_response({
                "messages": [
                    {"role": "user", "content": "quero consultar memória, agenda e github"},
                    {"role": "assistant", "content": "Posso consultar as três frentes."},
                    {"role": "user", "content": "faz isso"},
                ],
            }, owner_authenticated=True)

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["agentic"])
        self.assertEqual(payload["provider"], "ultron_orchestrator")
        self.assertEqual(payload["orchestration"]["protocol"], "ultron-orchestration/1")
        self.assertEqual(payload["orchestration"]["selected"], 3)
        self.assertEqual(payload["orchestration"]["succeeded"], 3)
        self.assertEqual(len(payload["tool_results"]), 3)
        self.assertEqual(executor.call_count, 3)
        self.assertTrue(sent[0]["parallel_tool_calls"])
        self.assertIn("até três ferramentas distintas", sent[0]["messages"][0]["content"])

    def test_tool_orchestrator_caps_three_fronts_and_keeps_partial_failure_visible(self):
        names = ("view_memory", "view_agenda", "get_daily_brief", "inspect_github")
        calls = [{
            "id": f"call-{name}",
            "function": {"name": name, "arguments": "{}"},
        } for name in names]

        def fake_execute(tool_call, _command, **_kwargs):
            name = tool_call["function"]["name"]
            ok = name != "view_agenda"
            payload = {
                "ok": ok,
                "status_real": f"{name}_{'confirmed' if ok else 'failed'}",
                "message": f"resultado {name}" if ok else "agenda indisponível",
                "provider": "verified_test_adapter",
                "agent_route": {"tool": name},
            }
            if name == "get_daily_brief":
                payload["job"] = {"id": "job-brief", "status": "pending"}
                return payload, 202
            return payload, 200 if ok else 503

        with patch.object(MODULE, "execute_agent_tool", side_effect=fake_execute) as executor:
            payload, status = MODULE.execute_agent_tools(
                calls,
                "consulte quatro frentes",
                owner_authenticated=True,
                max_tools=3,
            )

        self.assertEqual(status, 207)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status_real"], "ultron_orchestration_partial")
        self.assertEqual(payload["orchestration"]["requested"], 4)
        self.assertEqual(payload["orchestration"]["selected"], 3)
        self.assertEqual(payload["orchestration"]["succeeded"], 1)
        self.assertEqual(payload["orchestration"]["queued"], 1)
        self.assertEqual(payload["orchestration"]["failed"], 1)
        self.assertEqual(payload["orchestration"]["ignored"], 1)
        self.assertEqual(executor.call_count, 3)

    def test_guest_chat_does_not_receive_private_tool_schemas(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "Olá, visitante."}}],
                }).encode("utf-8")

        requests = []

        def fake_urlopen(request, **_kwargs):
            requests.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse()

        env = {
            "OPENROUTER_API_KEY": "test-key",
            "JARVIS_OWNER_TOKEN": "private-owner-token",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(MODULE, "urlopen", side_effect=fake_urlopen):
            payload, status = MODULE.assistant_response(
                {"command": "oi, visitante aqui"}, owner_authenticated=False
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["message"], "Olá, visitante.")
        self.assertNotIn("tools", requests[0])

    def test_tool_calling_provider_rejection_falls_back_to_normal_chat(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "legacy/free",
                    "choices": [{"message": {"content": "Continuo pela conversa normal."}}],
                }).encode("utf-8")

        requests = []

        def fake_urlopen(request, **_kwargs):
            requests.append(json.loads(request.data.decode("utf-8")))
            if len(requests) == 1:
                raise HTTPError(MODULE.OPENROUTER_URL, 422, "tools unsupported", {}, None)
            return FakeResponse()

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch.object(
            MODULE, "urlopen", side_effect=fake_urlopen
        ):
            payload, status = MODULE.assistant_response({
                "messages": [
                    {"role": "user", "content": "quero usar o Spotify"},
                    {"role": "assistant", "content": "Entendi."},
                    {"role": "user", "content": "faz isso"},
                ],
            })
        self.assertEqual(status, 200)
        self.assertTrue(payload["tool_calling_fallback"])
        self.assertIn("tools", requests[0])
        self.assertNotIn("tools", requests[1])

    def test_casual_owner_chat_skips_tool_schemas_for_lower_latency(self):
        self.assertFalse(MODULE.should_offer_agent_tools([
            {"role": "user", "content": "poxa, é bonitão hein"},
        ]))
        self.assertTrue(MODULE.should_offer_agent_tools([
            {"role": "user", "content": "abra o Spotify"},
        ]))

    def test_simple_chat_is_trimmed_without_bureaucratic_labels(self):
        raw = (
            "**Resposta:** Está funcionando. "
            "**Próximo passo:** Vou reduzir o atraso da voz. "
            "Também vou manter as respostas curtas. "
            "Esta quarta frase não deve aparecer. "
            "**Confiança nesta resposta:** 95%."
        )
        content, trimmed = MODULE.concise_assistant_content(raw, detailed=False)
        self.assertTrue(trimmed)
        self.assertNotIn("Próximo passo", content)
        self.assertNotIn("Confiança", content)
        self.assertNotIn("quarta frase", content)
        self.assertLessEqual(len(content), 480)

    def test_internal_model_reasoning_is_never_shown_as_the_answer(self):
        raw = (
            "We need to respond as JARVIS: short, under 55 words.\n"
            "The user asks if it can use n8n and control the computer.\n"
            "Consigo integrar o n8n e acionar o worker do Mac quando eles estão conectados."
        )
        content, trimmed = MODULE.concise_assistant_content(raw, detailed=False)
        self.assertTrue(trimmed)
        self.assertEqual(content, "Consigo integrar o n8n e acionar o worker do Mac quando eles estão conectados.")
        self.assertNotIn("We need", content)

    def test_mixed_capability_question_is_answered_without_model_latency(self):
        result = MODULE.capability_question_payload(
            "você consegue criar no n8n, mexer no meu computador e se aprimorar?"
        )
        self.assertIsNotNone(result)
        payload, status = result
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "jarvis_runtime")
        self.assertIn("n8n", payload["message"])
        self.assertIn("Mac", payload["message"])
        self.assertIn("scripts", payload["message"])
        self.assertFalse(payload["external_processing"])

    def test_detailed_requests_keep_room_for_real_analysis(self):
        profile = MODULE.assistant_response_profile("faça uma análise detalhada da arquitetura")
        self.assertEqual(profile["name"], "detailed")
        self.assertEqual(profile["max_tokens"], 900)
        content = "Uma análise longa. Com todos os detalhes. Sem corte."
        normalized, trimmed = MODULE.concise_assistant_content(content, detailed=True)
        self.assertEqual(normalized, content)
        self.assertFalse(trimmed)

    def test_advisory_requests_use_balanced_quality_profile(self):
        profile = MODULE.assistant_response_profile("como você melhoraria o Jarvis agora?")
        self.assertEqual(profile, {
            "name": "balanced",
            "max_tokens": 520,
            "temperature": 0.44,
            "routing": "quality_first",
        })
        candidates = MODULE.openrouter_model_candidates(profile="balanced")
        self.assertEqual(candidates[0], "nvidia/nemotron-3-ultra-550b-a55b:free")

    def test_purchase_decision_requires_live_search(self):
        self.assertTrue(MODULE.should_search_web([
            {"role": "user", "content": "qual o preço do iPhone 15 e onde comprar?"},
        ]))
        self.assertTrue(MODULE.should_search_web([
            {"role": "user", "content": "compare ofertas da Kabum para este monitor"},
        ]))

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
        self.assertEqual(payload["visual_state"], "response")
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
                audio, status = MODULE.elevenlabs_speech({
                    "text": "Olá, Theo.",
                    "previous_text": "O diagnóstico terminou.",
                    "next_text": "Vou continuar daqui.",
                })
        self.assertEqual(status, 200)
        self.assertTrue(audio.startswith(b"ID3"))
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.headers["Xi-api-key"], "private-test-key")
        sent_payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertNotIn("language_code", sent_payload)
        self.assertEqual(sent_payload["model_id"], "eleven_flash_v2_5")
        self.assertEqual(sent_payload["seed"], 7319)
        self.assertEqual(sent_payload["apply_text_normalization"], "auto")
        self.assertEqual(sent_payload["previous_text"], "O diagnóstico terminou.")
        self.assertEqual(sent_payload["next_text"], "Vou continuar daqui.")
        self.assertEqual(sent_payload["voice_settings"]["stability"], 0.64)
        self.assertEqual(sent_payload["voice_settings"]["similarity_boost"], 0.82)
        self.assertFalse(sent_payload["voice_settings"]["use_speaker_boost"])
        self.assertEqual(sent_payload["voice_settings"]["speed"], 0.93)

    def test_missing_elevenlabs_key_stays_text_only(self):
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}, clear=False):
            payload, status = MODULE.elevenlabs_speech({"text": "Olá, Theo."})
        self.assertEqual(status, 503)
        self.assertEqual(payload["fallback"], "text_only")

    def test_voice_calibrator_is_bounded_and_keeps_non_exaggerated_style(self):
        profile = MODULE.voice_profile({
            "voice_profile": {
                "stability": 12,
                "similarity_boost": -3,
                "speed": 8,
                "style": 1,
                "use_speaker_boost": True,
            }
        })
        self.assertEqual(profile["stability"], 0.9)
        self.assertEqual(profile["similarity_boost"], 0.55)
        self.assertEqual(profile["speed"], 1.1)
        self.assertEqual(profile["style"], 0.0)
        self.assertFalse(profile["use_speaker_boost"])

    def test_elevenlabs_quota_error_is_reported_honestly(self):
        provider_error = HTTPError("https://api.elevenlabs.io", 402, "payment required", {}, None)
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "private-test-key"}, clear=False):
            with patch.object(MODULE, "urlopen", side_effect=provider_error):
                payload, status = MODULE.elevenlabs_speech({"text": "Olá, Theo."})
        self.assertEqual(status, 502)
        self.assertEqual(payload["error_code"], "elevenlabs_quota")
        self.assertIn("sem créditos", payload["error"])
        self.assertEqual(payload["fallback"], "browser_voice")

    def test_elevenlabs_free_quota_on_401_is_quota_not_auth(self):
        class QuotaError(HTTPError):
            def read(self, *_args):
                return json.dumps({
                    "detail": {
                        "type": "invalid_request",
                        "code": "quota_exceeded",
                        "status": "quota_exceeded",
                        "message": "This request exceeds your quota of 10000.",
                    }
                }).encode("utf-8")

        provider_error = QuotaError("https://api.elevenlabs.io", 401, "unauthorized", {}, None)
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "private-test-key"}, clear=False):
            with patch.object(MODULE, "urlopen", side_effect=provider_error):
                payload, status = MODULE.elevenlabs_speech({"text": "Olá, Theo."})
        self.assertEqual(status, 502)
        self.assertEqual(payload["error_code"], "elevenlabs_quota")
        self.assertNotEqual(payload["error_code"], "elevenlabs_authorization")

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
            confirmed, confirmed_status = MODULE.execute_saved_run(
                MODULE.AGENT_RUNS.get(payload["run_id"]), owner_authenticated=True
            )
        self.assertEqual(status, 202)
        self.assertEqual(confirmed_status, 202)
        self.assertEqual(confirmed["job"]["target"], "…9999")
        queued = request.call_args_list[1].kwargs["body"]
        self.assertEqual(queued["target"], "5511999999999")
        self.assertNotIn("5511999999999", json.dumps(confirmed))

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
        self.assertEqual(payload["intent"], "memory_view")
        self.assertFalse(payload["persistent_write"])
        self.assertEqual(payload["visual_state"], "memory")

    def test_contextual_close_exits_memory_view_without_model_or_write(self):
        status, _, payload = self.json_request(
            "/command",
            "POST",
            {
                "command": "pode fechar",
                "messages": [
                    {"role": "user", "content": "mostra o núcleo de memória"},
                    {"role": "assistant", "content": "Abri sua constelação com 2 memórias persistentes."},
                    {"role": "user", "content": "pode fechar"},
                ],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "memory_view_closed")
        self.assertEqual(payload["provider"], "jarvis_runtime")
        self.assertFalse(payload["external_processing"])
        self.assertFalse(payload["persistent_write"])

    def test_output_language_guard_retries_clear_english_but_accepts_portuguese(self):
        self.assertTrue(MODULE.output_needs_portuguese_retry(
            "This is the answer and you should use it with your current project."
        ))
        self.assertTrue(MODULE.output_needs_portuguese_retry(
            "A McLaren 750S ainda é a referência. This is the current lineup for 2025."
        ))
        self.assertFalse(MODULE.output_needs_portuguese_retry(
            "Esta é a resposta e você pode usar isso no seu projeto agora."
        ))
        self.assertFalse(MODULE.output_needs_portuguese_retry("Deploy concluído."))
        self.assertTrue(MODULE.output_denies_live_capability(
            "Não tenho capacidade de pesquisa em tempo real. Meu conhecimento vem dos dados de treinamento (até 2024)."
        ))
        self.assertFalse(MODULE.output_denies_live_capability(
            "Pesquisei agora. A McLaren 750S continua a referência de uso misto."
        ))

    def test_meta_leak_fallback_never_blames_user_or_requests_rephrasing(self):
        message = MODULE.meta_leak_recovery([{"role": "user", "content": "faça isso"}])
        self.assertNotIn("Reformule", message)
        self.assertNotIn("instruções internas", message)
        self.assertIn("Preservei seu pedido", message)

    def test_casual_reply_strips_provider_meta_preface_and_keeps_final_quote(self):
        clean, leaked = MODULE.sanitize_model_output(
            'User said "oi". So respond with something like "Oi, Theo. Tudo bem."'
        )
        self.assertTrue(leaked)
        self.assertEqual(clean, "Oi, Theo. Tudo bem.")

    def test_casual_assistant_never_delivers_provider_meta_preface(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": 'User said "oi". So respond with something like "Oi, Theo. Tudo bem."'}}],
                }).encode("utf-8")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch.object(
            MODULE, "urlopen", return_value=FakeResponse()
        ):
            payload, status = MODULE.assistant_response({"command": "oi"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["message"], "Oi, Theo. Tudo bem.")
        self.assertTrue(payload["meta_leak_recovered"])

    def test_secret_like_prompt_is_refused(self):
        fake = "sk-" + "or-" + "v1-" + ("x" * 20)
        status, _, payload = self.json_request(
            "/command", "POST", {"command": f"use {fake}"}
        )
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])

    def test_runtime_v2_routes_and_memory_are_selective(self):
        research = MODULE.agent_request_contract("pesquise notícias recentes de IA")
        run = MODULE.agent_request_contract("abra o Spotify e depois tire um print da tela")
        durable = MODULE.memory_candidate("eu prefiro respostas curtas e diretas")
        ephemeral = MODULE.memory_candidate("hoje eu prefiro respostas longas")
        self.assertEqual(research["route"], "research")
        self.assertEqual(research["profile"], "detailed")
        self.assertEqual(run["route"], "device_run")
        self.assertEqual(run["steps"], 2)
        self.assertEqual(durable["kind"], "preference")
        self.assertFalse(durable["auto_save"])
        self.assertIsNone(ephemeral)

    def test_runtime_v2_research_verification_uses_observable_domains(self):
        sources = [
            {"title": "Docs", "url": "https://docs.example.com/guide", "domain": "docs.example.com", "snippet": "Official guide"},
            {"title": "Review", "url": "https://independent.test/review", "domain": "independent.test", "snippet": "Independent confirmation"},
            {"title": "Reference", "url": "https://third.test/reference", "domain": "third.test", "snippet": "Additional evidence"},
            {"title": "Details", "url": "https://fourth.test/details", "domain": "fourth.test", "snippet": "Detailed evidence"},
        ]
        verification = MODULE.research_verification(sources, queries=["one", "two"])
        self.assertTrue(verification["corroborated"])
        self.assertEqual(verification["confidence"], "high")
        self.assertEqual(verification["claim_policy"], "cite_or_refuse")
        self.assertEqual(verification["query_count"], 2)

    def test_runtime_v2_search_query_removes_question_and_answer_instructions(self):
        query = MODULE.search_query_from_prompt(
            "Pesquise na internet qual é a versão estável atual do Next.js e responda citando fontes reais. "
            "Se não confirmar, diga que não confirmou."
        )
        self.assertEqual(query, "versão estável atual do Next.js")

    def test_runtime_v2_relevance_rejects_generic_qual_search_noise(self):
        sources = [
            {
                "title": "iShares MSCI USA Quality Factor ETF | QUAL",
                "url": "https://www.ishares.com/us/products/qual",
                "domain": "ishares.com",
                "snippet": "QUAL fund overview",
            },
            {
                "title": "Releases: vercel/next.js",
                "url": "https://github.com/vercel/next.js/releases",
                "domain": "github.com",
                "snippet": "Next.js releases and version history",
            },
        ]
        relevant = MODULE.relevant_public_sources(sources, "versão estável atual do Next.js")
        self.assertEqual([row["domain"] for row in relevant], ["github.com"])

    def test_identity_search_drops_revista_quem(self):
        sources = [
            {
                "title": "QUEM - Notícias de famosos",
                "url": "https://quem.globo.com/",
                "domain": "quem.globo.com",
                "snippet": "Revista Quem",
            },
            {
                "title": "JARVIS assistente",
                "url": "https://example.com/jarvis",
                "domain": "example.com",
                "snippet": "assistente pessoal",
            },
        ]
        relevant = MODULE.relevant_public_sources(sources, "quem é você assistente")
        self.assertEqual([row["domain"] for row in relevant], ["example.com"])
        self.assertTrue(MODULE.is_identity_question("quem é você"))
        self.assertTrue(MODULE.is_identity_question("quem criou você"))
        self.assertFalse(MODULE.is_identity_question("quem é o atual presidente do Brasil"))

    def test_creator_profile_is_local_and_public(self):
        payload, status = MODULE.command_payload({"command": "quem criou você"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "creator_profile")
        self.assertIn("Theo Lorentz Padilha", payload["message"])
        self.assertIn("linkedin.com/in/theo-lorentz-padilha", payload["message"])
        self.assertEqual(MODULE.creator_name(), "Theo Lorentz Padilha")
        page_status, _headers, html = self.request("/theo")
        self.assertEqual(page_status, 200)
        self.assertIn(b"Theo Lorentz Padilha", html)
        self.assertIn(b"linkedin.com/in/theo-lorentz-padilha-0b9b99287", html)
        self.assertNotIn(b"ghbtns.com", html)
        self.assertNotIn(b"98816-4026", html)

    def test_runtime_v2_relevance_requires_the_distinctive_subject(self):
        sources = [
            {
                "title": "Versão - Dicionário Online de Português",
                "url": "https://dicio.com.br/versao",
                "domain": "dicio.com.br",
                "snippet": "Significado de versão",
            },
            {
                "title": "Next.js releases",
                "url": "https://www.npmjs.com/package/next",
                "domain": "npmjs.com",
                "snippet": "Next package version history",
            },
        ]
        relevant = MODULE.relevant_public_sources(sources, "versão estável atual do Next.js")
        self.assertEqual([row["domain"] for row in relevant], ["npmjs.com"])

    def test_runtime_v2_attaches_a_visible_mission_contract(self):
        started = datetime.now(MODULE.timezone.utc)
        payload = MODULE.attach_execution_events(
            {"ok": True, "provider": "openrouter", "message": "Resposta"},
            started,
            200,
            "analise a arquitetura deste projeto",
        )
        self.assertEqual(payload["mission"]["protocol"], "jarvis-mission/2")
        self.assertEqual(payload["mission"]["steps"][-1]["status"], "succeeded")
        self.assertTrue(payload["mission"]["success_criteria"])

    def test_execution_power_profile_is_one_x_for_jarvis_and_three_x_for_ultron(self):
        jarvis = MODULE.execution_power_profile(False)
        ultron = MODULE.execution_power_profile(True)
        self.assertEqual(jarvis["mode"], "jarvis_1x")
        self.assertEqual(jarvis["multiplier"], 1)
        self.assertEqual(ultron["mode"], "ultron_3x")
        self.assertEqual(ultron["multiplier"], 3)
        self.assertEqual(jarvis["max_agent_tools_per_request"], 1)
        self.assertEqual(ultron["max_agent_tools_per_request"], 3)
        self.assertEqual(ultron["max_workflows_per_request"], 3)
        self.assertEqual(ultron["max_workflow_nodes"], jarvis["max_workflow_nodes"] * 3)

    def test_client_integration_normalizes_ephemeral_credentials_without_echo_contract(self):
        body = {
            "client_integrations": {
                "n8n": {"base_url": "https://theo.app.n8n.cloud/", "api_key": "private-n8n-key"},
                "unknown": {"api_key": "ignored"},
            }
        }
        integrations = MODULE.client_integrations(body)
        self.assertEqual(integrations["n8n"]["base_url"], "https://theo.app.n8n.cloud")
        self.assertEqual(integrations["n8n"]["api_key"], "private-n8n-key")
        self.assertNotIn("unknown", integrations)

    def test_integration_url_refuses_local_and_non_https_targets(self):
        for target in ("http://n8n.example.com", "https://localhost", "https://127.0.0.1", "https://metadata.internal"):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    MODULE.safe_integration_base_url(target, "n8n")
        self.assertEqual(
            MODULE.safe_integration_base_url("https://theo.app.n8n.cloud/", "n8n"),
            "https://theo.app.n8n.cloud",
        )

    def test_integration_tool_catalog_has_bounded_tools_for_each_saved_api(self):
        catalog = MODULE.integration_tool_catalog()
        self.assertEqual(
            {item["provider"] for item in catalog},
            {"n8n", "openrouter", "elevenlabs", "github", "supabase", "webhook"},
        )
        self.assertEqual(len({item["tool"] for item in catalog}), 13)
        self.assertEqual(sum(item["provider"] == "github" for item in catalog), 5)
        self.assertEqual(sum(item["provider"] == "n8n" for item in catalog), 2)
        self.assertEqual(
            next(item for item in catalog if item["provider"] == "webhook")["effect"],
            "external_write",
        )
        self.assertTrue(all(item["effect"] == "read" for item in catalog if item["provider"] != "webhook"))

    def test_integration_tools_http_route_reaches_the_verified_adapter(self):
        status, _, payload = self.json_request(
            "/integrations/tools",
            "POST",
            {"provider": "openrouter", "tool": "inspect_account", "config": {}},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["status_real"], "integration_tool_key_missing")
        self.assertEqual(payload["event_stream"]["protocol"], "jarvis-events/1")
        self.assertFalse(payload["credential_persisted_server_side"])

    def test_n8n_execution_history_excludes_processed_payloads(self):
        captured = {}

        def fake_request(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return {"data": [{
                "id": "exec-1",
                "workflowId": "wf-1",
                "status": "success",
                "mode": "webhook",
                "startedAt": "2026-08-13T18:00:00Z",
                "stoppedAt": "2026-08-13T18:00:01Z",
                "data": {"secret": "must-not-return"},
            }]}, 200

        with patch.object(MODULE, "integration_json_request", side_effect=fake_request):
            payload, status = MODULE.integration_tool_payload({
                "provider": "n8n",
                "tool": "list_executions",
                "config": {"base_url": "https://theo.app.n8n.cloud", "api_key": "n8n-key"},
            })

        self.assertEqual(status, 200)
        self.assertIn("includeData=false", captured["url"])
        self.assertEqual(payload["result"][0]["id"], "exec-1")
        self.assertNotIn("must-not-return", json.dumps(payload))

    def test_github_issue_reader_uses_repository_route_and_filters_pull_requests(self):
        captured = {}

        def fake_request(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return [
                {"number": 7, "title": "Corrigir UI", "state": "open", "user": {"login": "theo"}, "updated_at": "2026-08-13", "html_url": "https://github.com/theo/jarvis/issues/7"},
                {"number": 8, "title": "PR", "pull_request": {"url": "private"}},
            ], 200

        with patch.object(MODULE, "integration_json_request", side_effect=fake_request):
            payload, status = MODULE.integration_tool_payload({
                "provider": "github",
                "tool": "list_issues",
                "config": {"api_key": "github-key"},
                "parameters": {"repository": "theo/jarvis"},
            })

        self.assertEqual(status, 200)
        self.assertIn("/repos/theo/jarvis/issues?state=open", captured["url"])
        self.assertEqual([item["number"] for item in payload["result"]], [7])
        self.assertEqual(captured["headers"]["X-GitHub-Api-Version"], "2022-11-28")
        self.assertNotIn("github-key", json.dumps(payload))

    def test_openrouter_saved_api_executes_real_usage_tool_without_echoing_key(self):
        captured = {}

        def fake_request(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return {"data": {
                "label": "placeholder-label",
                "is_free_tier": True,
                "limit": 12,
                "limit_remaining": 8.5,
                "usage": 3.5,
                "usage_daily": 1.25,
                "usage_monthly": 3.5,
                "limit_reset": "monthly",
            }}, 200

        with patch.object(MODULE, "integration_json_request", side_effect=fake_request):
            payload, status = MODULE.integration_tool_payload({
                "provider": "openrouter",
                "tool": "inspect_account",
                "config": {"api_key": "test-openrouter-key"},
            })

        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "integration_tool_executed")
        self.assertEqual(payload["result"]["limit_remaining"], 8.5)
        self.assertEqual(captured["url"], "https://openrouter.ai/api/v1/key")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-openrouter-key")
        self.assertNotIn("test-openrouter-key", json.dumps(payload))
        self.assertFalse(payload["credential_persisted_server_side"])

    def test_n8n_elevenlabs_and_github_saved_apis_execute_read_tools(self):
        def fake_request(url, **_kwargs):
            if "n8n.cloud" in url:
                return {"data": [{"id": "wf-1", "name": "Leads", "active": False, "updatedAt": "2026-08-13"}]}, 200
            if "elevenlabs.io" in url:
                return {"voices": [{"voice_id": "voice-1", "name": "Jarvis", "category": "generated"}]}, 200
            if "api.github.com" in url:
                return [{
                    "full_name": "theo/jarvis",
                    "private": True,
                    "html_url": "https://github.com/theo/jarvis",
                    "default_branch": "main",
                    "pushed_at": "2026-08-13T18:00:00Z",
                }], 200
            raise AssertionError(f"URL inesperada: {url}")

        cases = (
            (
                "n8n",
                "list_workflows",
                {"base_url": "https://theo.app.n8n.cloud", "api_key": "test-n8n-key"},
                "Leads",
            ),
            ("elevenlabs", "list_voices", {"api_key": "test-eleven-key"}, "Jarvis"),
            ("github", "list_repositories", {"api_key": "test-github-key"}, "theo/jarvis"),
        )
        with patch.object(MODULE, "integration_json_request", side_effect=fake_request) as provider:
            for name, tool, config, expected in cases:
                with self.subTest(provider=name):
                    payload, status = MODULE.integration_tool_payload({
                        "provider": name,
                        "tool": tool,
                        "config": config,
                    })
                    self.assertEqual(status, 200)
                    self.assertEqual(payload["status_real"], "integration_tool_executed")
                    self.assertIn(expected, json.dumps(payload["result"]))
                    self.assertNotIn(config["api_key"], json.dumps(payload))
        self.assertEqual(provider.call_count, 3)

    def test_supabase_saved_api_reads_bounded_rows_and_redacts_sensitive_columns(self):
        captured = {}

        def fake_request(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return [{"id": 1, "name": "Theo", "api_key": "placeholder-value", "nested": {"password": "placeholder"}}], 200

        with patch.object(MODULE, "integration_json_request", side_effect=fake_request):
            payload, status = MODULE.integration_tool_payload({
                "provider": "supabase",
                "tool": "read_rows",
                "config": {"base_url": "https://project.supabase.co", "api_key": "test-supabase-key"},
                "parameters": {"table": "jarvis_memories", "limit": 200},
            })

        self.assertEqual(status, 200)
        self.assertIn("limit=20", captured["url"])
        self.assertEqual(payload["result"][0]["name"], "Theo")
        self.assertEqual(payload["result"][0]["api_key"], "[REDACTED]")
        self.assertEqual(payload["result"][0]["nested"]["password"], "[REDACTED]")
        self.assertNotIn("test-supabase-key", json.dumps(payload))

    def test_supabase_tool_refuses_unbounded_table_expression(self):
        payload, status = MODULE.integration_tool_payload({
            "provider": "supabase",
            "tool": "read_rows",
            "config": {"base_url": "https://project.supabase.co", "api_key": "test-key"},
            "parameters": {"table": "users?select=password", "limit": 10},
        })
        self.assertEqual(status, 400)
        self.assertEqual(payload["status_real"], "integration_tool_invalid")

    def test_webhook_tool_requires_ultron_and_explicit_confirmation(self):
        body = {
            "provider": "webhook",
            "tool": "send_event",
            "config": {"base_url": "https://hooks.example.com/jarvis", "api_key": "test-hook-key"},
            "parameters": {"payload": {"event": "jarvis.test", "count": 1}},
        }
        with patch.object(MODULE, "urlopen") as provider:
            payload, status = MODULE.integration_tool_payload(body, owner_authenticated=False)
        self.assertEqual(status, 409)
        self.assertEqual(payload["status_real"], "integration_tool_confirmation_required")
        provider.assert_not_called()

        class FakeResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit=-1):
                return b"{}"

        with patch.object(MODULE, "urlopen", return_value=FakeResponse()) as provider:
            payload, status = MODULE.integration_tool_payload(
                {**body, "confirmed": True},
                owner_authenticated=True,
            )
        self.assertEqual(status, 200)
        self.assertTrue(payload["result"]["delivered"])
        self.assertEqual(payload["result"]["http_status"], 202)
        request = provider.call_args.args[0]
        self.assertEqual(request.full_url, "https://hooks.example.com/jarvis")
        self.assertEqual(request.get_method(), "POST")
        self.assertNotIn("test-hook-key", json.dumps(payload))

    def test_n8n_preview_is_credential_free_and_never_active(self):
        payload, status = MODULE.n8n_workflow_action_payload({
            "action": "preview",
            "goal": "receber leads por webhook",
            "template": "auto",
        }, owner_authenticated=False)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "n8n_workflow_preview")
        self.assertEqual(payload["template"], "webhook")
        self.assertFalse(payload["active"])
        self.assertNotIn("active", payload["workflow"])
        self.assertEqual(payload["workflow"]["settings"]["executionOrder"], "v1")
        self.assertNotRegex(json.dumps(payload["workflow"]), r"api[_-]?key|credential")

    def test_n8n_template_pack_covers_four_real_integrations(self):
        cases = (
            ("Receber um lead por webhook e enviar uma resposta pelo WhatsApp", "webhook", "whatsapp"),
            ("Todo dia montar um resumo organizado e enviar por Gmail", "schedule", "gmail"),
            ("Receber uma falha de deploy do GitHub por webhook e abrir uma issue de incidente no GitHub", "webhook", "github"),
            ("Receber dados por webhook, validar os campos e salvar no Supabase", "webhook", "supabase"),
        )
        for goal, expected_trigger, expected_provider in cases:
            with self.subTest(provider=expected_provider):
                workflow, trigger, plan = MODULE.n8n_workflow_template(goal, "auto", False)
                self.assertEqual(trigger, expected_trigger)
                setup = [item for item in plan["required_setup"] if item["provider"] == expected_provider]
                self.assertTrue(setup)
                self.assertTrue(setup[0]["fields"])
                external = [node for node in workflow["nodes"] if node.get("disabled")]
                self.assertTrue(external)
                self.assertFalse(plan["ready_to_activate"])

    def test_n8n_smart_forge_builds_a_connected_multi_stage_ultron_plan(self):
        payload, status = MODULE.n8n_workflow_action_payload({
            "action": "preview",
            "goal": "todo dia buscar leads no Supabase, se tiver novos resumir com OpenAI e avisar no WhatsApp",
            "template": "auto",
        }, owner_authenticated=True)

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["template"], "schedule")
        workflow = payload["workflow"]
        plan = payload["plan"]
        self.assertEqual(plan["protocol"], "jarvis-n8n-plan/1")
        self.assertEqual(plan["planner"], "bounded_natural_language")
        self.assertGreaterEqual(len(workflow["nodes"]), 8)
        self.assertLessEqual(len(workflow["nodes"]), 18)
        self.assertEqual(plan["node_count"], len(workflow["nodes"]))
        self.assertFalse(plan["ready_to_activate"])
        self.assertTrue(plan["safety"]["credential_nodes_disabled"])

        node_types = {node["type"] for node in workflow["nodes"]}
        self.assertIn("n8n-nodes-base.scheduleTrigger", node_types)
        self.assertIn("n8n-nodes-base.if", node_types)
        self.assertIn("n8n-nodes-base.httpRequest", node_types)
        external_nodes = [node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.httpRequest"]
        self.assertEqual(len(external_nodes), 3)
        self.assertTrue(all(node.get("disabled") is True for node in external_nodes))
        self.assertEqual(
            {item["provider"] for item in plan["required_setup"]},
            {"supabase", "openrouter", "whatsapp"},
        )

        node_names = {node["name"] for node in workflow["nodes"]}
        for source, outputs in workflow["connections"].items():
            self.assertIn(source, node_names)
            for branch in outputs["main"]:
                for connection in branch:
                    self.assertIn(connection["node"], node_names)
        serialized = json.dumps(workflow).casefold()
        self.assertNotIn("credentials", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("sk-or-", serialized)

    def test_n8n_smart_forge_respects_jarvis_six_node_budget(self):
        payload, status = MODULE.n8n_workflow_action_payload({
            "action": "preview",
            "goal": "se chegar um lead salve no Supabase, analise com OpenAI, envie Gmail, WhatsApp e Slack",
            "template": "webhook",
        }, owner_authenticated=False)

        self.assertEqual(status, 200)
        self.assertEqual(payload["plan"]["source"], "JARVIS")
        self.assertLessEqual(payload["plan"]["node_count"], 6)
        self.assertEqual(payload["plan"]["node_count"], len(payload["workflow"]["nodes"]))
        self.assertTrue(payload["plan"]["omitted_actions"])
        self.assertEqual(payload["power_profile"]["max_workflow_nodes"], 6)

    def test_n8n_smart_forge_refuses_a_secret_inside_the_goal(self):
        fake_secret = "".join(("sk", "-or-v1-", "placeholder" * 3))
        payload, status = MODULE.n8n_workflow_action_payload({
            "action": "preview",
            "goal": f"use esta chave {fake_secret} para chamar a API",
        }, owner_authenticated=True)
        self.assertEqual(status, 400)
        self.assertEqual(payload["status_real"], "n8n_workflow_goal_refused")
        self.assertNotIn("sk-or-v1", json.dumps(payload))

    def test_n8n_create_uses_official_api_and_keeps_workflow_inactive(self):
        captured = {}

        def fake_request(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return {"id": "wf-123", "name": "ULTRON · leads", "active": False}, 200

        with patch.object(MODULE, "integration_json_request", side_effect=fake_request):
            payload, status = MODULE.n8n_workflow_action_payload({
                "action": "create",
                "goal": "receber leads por webhook",
                "template": "webhook",
                "confirmed": True,
                "config": {"base_url": "https://theo.app.n8n.cloud", "api_key": "n8n-secret"},
            }, owner_authenticated=True)
        self.assertEqual(status, 201)
        self.assertEqual(payload["status_real"], "n8n_workflow_created_inactive")
        self.assertFalse(payload["workflow"]["active"])
        self.assertEqual(payload["power_profile"]["multiplier"], 3)
        self.assertEqual(captured["url"], "https://theo.app.n8n.cloud/api/v1/workflows")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["X-N8N-API-KEY"], "n8n-secret")
        self.assertEqual(set(captured["body"]), {"name", "nodes", "connections", "settings"})
        self.assertNotIn("active", captured["body"])
        self.assertNotIn("n8n-secret", json.dumps(payload))

    def test_ultron_can_create_three_inactive_n8n_workflows_in_one_operation(self):
        counter = {"value": 0}

        def fake_request(_url, **_kwargs):
            counter["value"] += 1
            return {
                "id": f"wf-{counter['value']}",
                "name": f"ULTRON · fluxo {counter['value']}",
                "active": False,
            }, 200

        with patch.object(MODULE, "integration_json_request", side_effect=fake_request) as provider:
            payload, status = MODULE.n8n_workflow_action_payload({
                "action": "create",
                "goals": ["captar lead", "avisar no Slack", "salvar no banco", "ignorar quarto"],
                "template": "manual",
                "confirmed": True,
                "config": {"base_url": "https://theo.app.n8n.cloud/api/v1", "api_key": "n8n-secret"},
            }, owner_authenticated=True)

        self.assertEqual(status, 201)
        self.assertEqual(payload["status_real"], "n8n_workflows_created_inactive")
        self.assertEqual(provider.call_count, 3)
        self.assertEqual(len(payload["workflows"]), 3)
        self.assertTrue(all(not item["active"] for item in payload["workflows"]))
        self.assertEqual(provider.call_args.args[0], "https://theo.app.n8n.cloud/api/v1/workflows")
        self.assertNotIn("n8n-secret", json.dumps(payload))

    def test_jarvis_can_create_one_n8n_workflow_with_its_own_vault_key(self):
        with patch.object(
            MODULE,
            "integration_json_request",
            return_value=({"id": "wf-jarvis", "name": "JARVIS · fluxo", "active": False}, 200),
        ) as provider:
            payload, status = MODULE.n8n_workflow_action_payload({
                "action": "create",
                "goals": ["primeiro fluxo", "segundo deve ser limitado"],
                "template": "manual",
                "config": {"base_url": "https://theo.app.n8n.cloud", "api_key": "n8n-secret"},
            }, owner_authenticated=False)

        self.assertEqual(status, 201)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(payload["power_profile"]["mode"], "jarvis_1x")
        self.assertEqual(len(payload["workflows"]), 1)
        self.assertEqual(payload["workflow"]["id"], "wf-jarvis")

    def test_ultron_n8n_creation_requires_explicit_permission(self):
        with patch.object(MODULE, "integration_json_request") as provider:
            payload, status = MODULE.n8n_workflow_action_payload({
                "action": "create",
                "goal": "criar fluxo manual",
                "template": "manual",
                "config": {"base_url": "https://theo.app.n8n.cloud", "api_key": "n8n-secret"},
            }, owner_authenticated=True)
        self.assertEqual(status, 409)
        self.assertEqual(payload["status_real"], "n8n_create_confirmation_required")
        provider.assert_not_called()

    def test_n8n_inspection_is_read_only_and_hides_node_parameters(self):
        workflow = {
            "id": "wf-source",
            "name": "Receber leads",
            "active": False,
            "nodes": [
                {"name": "Webhook", "type": "n8n-nodes-base.webhook", "parameters": {"path": "private-path"}},
                {"name": "API", "type": "n8n-nodes-base.httpRequest", "disabled": True, "credentials": {"http": {"id": "cred-1"}}},
            ],
            "connections": {},
        }
        with patch.object(MODULE, "integration_json_request", return_value=(workflow, 200)) as provider:
            payload, status = MODULE.n8n_workflow_action_payload({
                "action": "inspect",
                "workflow_id": "wf-source",
                "config": {"base_url": "https://theo.app.n8n.cloud", "api_key": "n8n-secret"},
            }, owner_authenticated=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status_real"], "n8n_workflow_inspected")
        self.assertEqual(payload["inspection"]["node_count"], 2)
        self.assertFalse(payload["inspection"]["ready_to_activate"])
        self.assertNotIn("private-path", json.dumps(payload))
        self.assertNotIn("cred-1", json.dumps(payload))
        self.assertEqual(provider.call_args.args[0], "https://theo.app.n8n.cloud/api/v1/workflows/wf-source")

    def test_ultron_duplicate_requires_confirmation_and_creates_inactive_copy(self):
        workflow = {
            "id": "wf-source",
            "name": "Rotina diária",
            "active": True,
            "nodes": [{"name": "Agenda", "type": "n8n-nodes-base.scheduleTrigger", "parameters": {}}],
            "connections": {},
            "settings": {"executionOrder": "v1"},
        }
        base_body = {
            "action": "duplicate",
            "workflow_id": "wf-source",
            "config": {"base_url": "https://theo.app.n8n.cloud", "api_key": "n8n-secret"},
        }
        with patch.object(MODULE, "integration_json_request", return_value=(workflow, 200)):
            blocked, blocked_status = MODULE.n8n_workflow_action_payload(base_body, owner_authenticated=True)
        self.assertEqual(blocked_status, 409)
        self.assertEqual(blocked["status_real"], "n8n_duplicate_confirmation_required")

        with patch.object(MODULE, "integration_json_request", side_effect=[
            (workflow, 200),
            ({"id": "wf-copy", "name": "Cópia · Rotina diária", "active": False}, 200),
        ]) as provider:
            payload, status = MODULE.n8n_workflow_action_payload({**base_body, "confirmed": True}, owner_authenticated=True)
        self.assertEqual(status, 201)
        self.assertEqual(payload["status_real"], "n8n_workflow_duplicated_inactive")
        self.assertFalse(payload["workflow"]["active"])
        duplicate_request = provider.call_args_list[1]
        self.assertEqual(duplicate_request.kwargs["method"], "POST")
        self.assertNotIn("active", duplicate_request.kwargs["body"])
        self.assertNotIn("n8n-secret", json.dumps(payload))

    def test_integration_test_does_not_echo_the_key(self):
        with patch.object(MODULE, "integration_json_request", return_value=({"data": []}, 200)) as provider:
            payload, status = MODULE.integration_test_payload({
                "provider": "n8n",
                "config": {"base_url": "https://theo.app.n8n.cloud", "api_key": "n8n-secret"},
            }, owner_authenticated=True)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["credential_persisted_server_side"])
        self.assertNotIn("n8n-secret", json.dumps(payload))
        self.assertEqual(provider.call_args.kwargs["headers"]["X-N8N-API-KEY"], "n8n-secret")

    def test_integration_health_returns_only_safe_openrouter_and_elevenlabs_quota(self):
        cases = (
            (
                "openrouter",
                {"data": {"label": "Theo", "limit": 100, "limit_remaining": 72.5, "usage": 27.5}},
                {"quota_remaining": 72.5, "quota_limit": 100, "quota_unit": "créditos"},
            ),
            (
                "elevenlabs",
                {"tier": "creator", "character_count": 1250, "character_limit": 10000},
                {"quota_remaining": 8750, "quota_limit": 10000, "quota_unit": "caracteres"},
            ),
        )
        for name, provider_result, expected in cases:
            with self.subTest(provider=name), patch.object(
                MODULE, "integration_json_request", return_value=(provider_result, 200)
            ):
                payload, status = MODULE.integration_test_payload({
                    "provider": name,
                    "config": {"api_key": f"{name}-secret"},
                })
                self.assertEqual(status, 200)
                self.assertEqual(payload["health"]["quota_remaining"], expected["quota_remaining"])
                self.assertEqual(payload["health"]["quota_limit"], expected["quota_limit"])
                self.assertEqual(payload["health"]["quota_unit"], expected["quota_unit"])
                self.assertNotIn(f"{name}-secret", json.dumps(payload))

    def test_browser_vault_elevenlabs_key_can_power_speech_without_environment_key(self):
        class FakeAudioResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit=-1):
                return b"audio"

        body = {
            "text": "Sistemas online.",
            "client_integrations": {"elevenlabs": {"api_key": "eleven-browser-key"}},
        }
        with patch.dict(os.environ, {}, clear=False), patch.object(
            MODULE, "active_voice_setting", return_value={"voice_id": MODULE.DEFAULT_ELEVENLABS_VOICE_ID}
        ), patch.object(MODULE, "urlopen", return_value=FakeAudioResponse()) as provider:
            os.environ.pop("ELEVENLABS_API_KEY", None)
            payload, status = MODULE.elevenlabs_speech(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload, b"audio")
        self.assertEqual(provider.call_args.args[0].get_header("Xi-api-key"), "eleven-browser-key")

    def test_browser_vault_openrouter_key_powers_chat_without_environment_key(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "model": "openrouter/free",
                    "choices": [{"message": {"content": "Cofre conectado."}}],
                }).encode("utf-8")

        body = {
            "command": "converse comigo",
            "client_integrations": {"openrouter": {"api_key": "browser-openrouter-key"}},
        }
        env = {"OPENROUTER_API_KEY": "", "OPENROUTER_FALLBACK_API_KEY": ""}
        with patch.dict(os.environ, env, clear=False), patch.object(
            MODULE, "urlopen", return_value=FakeResponse()
        ) as provider:
            payload, status = MODULE.assistant_response(body)

        self.assertEqual(status, 200)
        self.assertEqual(payload["message"], "Cofre conectado.")
        self.assertEqual(
            provider.call_args.args[0].headers["Authorization"],
            "Bearer browser-openrouter-key",
        )
        self.assertTrue(payload["client_openrouter_key_used"])

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


    def test_jarvis_lights_its_own_nucleus_and_knows_what_it_is(self):
        """Pedir o núcleo acende a cena; o prompt sabe que os núcleos são dele."""
        for command, nucleus, visual in (
            ("abre o núcleo de forja", "forge", "forge"),
            ("mostre o núcleo", "core", "thinking"),
        ):
            payload, _status = MODULE.dispatch_intent(command, "scene_show")
            self.assertTrue(payload["ok"], command)
            self.assertEqual(payload["nucleus"], nucleus)
            self.assertEqual(payload["visual_state"], visual)
            self.assertFalse(payload["action_executed"])
        self.assertEqual(
            [route for pattern, route in MODULE.LOCAL_INTENTS if pattern.search("abre o núcleo de forja")][:1],
            ["scene_show"],
        )
        # Memória continua abrindo a constelação real, não só a cena.
        self.assertEqual(
            MODULE.dispatch_intent("mostra o núcleo de memória", "memory_view")[0]["visual_state"],
            "memory",
        )
        guest = MODULE.capability_briefing(False)
        owner = MODULE.capability_briefing(True)
        for briefing in (guest, owner):
            self.assertIn("NÚCLEO pensa", briefing)
            self.assertIn("FORJA constrói", briefing)
            self.assertIn("MEMÓRIA guarda", briefing)
        self.assertIn("Supabase", guest)


    def test_memory_autosave_only_keeps_durable_owner_facts(self):
        """A memória grava sozinha, mas só decisão/preferência do dono e nunca segredo."""
        decision = MODULE.memory_candidate("decidi que todo deploy do jarvis passa pelo ship com testes verdes antes")
        self.assertEqual((decision["kind"], decision["confidence"]), ("decision", "high"))
        # Sem Supabase configurado no ambiente de teste, nada é gravado.
        self.assertIsNone(MODULE.autosave_memory_candidate(decision, True))
        self.assertIsNone(MODULE.autosave_memory_candidate(decision, False))
        self.assertIsNone(MODULE.autosave_memory_candidate(
            {"content": "minha chave é sk-ABCDEFGHIJKLMNOP1234", "kind": "decision", "confidence": "high"}, True))
        # Conversa comum não vira memória.
        self.assertIsNone(MODULE.memory_candidate("bom dia, tudo certo?"))


    def test_clear_chat_photo_card_and_second_voice(self):
        """Limpar o chat executa de verdade, o criador vem com foto e a voz tem reserva."""
        payload, status = MODULE.dispatch_intent("limpa o chat", "chat_clear")
        self.assertEqual(status, 200)
        self.assertEqual(payload["client_action"], "clear_chat")
        self.assertTrue(payload["action_executed"])
        self.assertEqual(
            [route for pattern, route in MODULE.LOCAL_INTENTS if pattern.search("apaga essa conversa")][:1],
            ["chat_clear"],
        )
        profile, _ = MODULE.creator_profile_payload("full")
        card = profile["author_card"]
        self.assertTrue(card["photo"].startswith("/ui/theo-avatar.jpg"))
        self.assertIn("linkedin.com/in/theo-lorentz-padilha", card["url"])
        self.assertTrue((MODULE.WEB_DIR / "theo-avatar.jpg").is_file())
        status_code, _headers, body = self.request("/ui/theo-avatar.jpg")
        self.assertEqual(status_code, 200)
        self.assertGreater(len(body), 4_000)
        # Sem chave da OpenAI não inventa áudio; com chave é a segunda voz neural.
        self.assertIsNone(MODULE.openai_speech({}, "teste"))
        # Várias chaves em failover, como o pool que o OpenRouter já usa.
        with patch.dict(MODULE.os.environ, {
            "ELEVENLABS_API_KEY": "primeira",
            "ELEVENLABS_FALLBACK_API_KEY": "segunda",
            "ELEVENLABS_API_KEYS": "terceira, primeira ,quarta",
        }):
            keys = MODULE.elevenlabs_api_keys({})
            self.assertEqual(keys, ["primeira", "segunda", "terceira", "quarta"])
            browser_first = MODULE.elevenlabs_api_keys(
                {"client_integrations": {"elevenlabs": {"api_key": "do-navegador"}}}
            )
            self.assertEqual(browser_first[0], "do-navegador")
        # Voz própria: sem URL não inventa áudio; com URL entra na cadeia.
        self.assertIsNone(MODULE.self_hosted_speech("teste"))
        with patch.dict(MODULE.os.environ, {"SELF_HOSTED_TTS_URL": "http://127.0.0.1:9/speech"}):
            self.assertIsNone(MODULE.self_hosted_speech("porta fechada não vira áudio"))
            voice_own, _ = MODULE.voice_status_payload()
            self.assertTrue(voice_own["self_hosted_ready"])
        # O estado da voz é consultável em vez de degradar em silêncio.
        voice, voice_status = MODULE.voice_status_payload()
        self.assertEqual(voice_status, 200)
        self.assertIn(voice["layer"], {"elevenlabs", "openai", "browser", "unknown"})
        self.assertIn("message", voice)
        code, _headers, body = self.request("/voice-status")
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)["ok"])


    def test_voice_catalog_and_owner_only_change(self):
        """Listar vozes é aberto; trocar a voz é do dono e precisa confirmar gravação."""
        catalog, status = MODULE.voice_catalog_payload(owner_authenticated=False)
        self.assertEqual(status, 200)
        self.assertIn("active", catalog)
        self.assertIsInstance(catalog["voices"], list)
        with patch.dict(MODULE.os.environ, {"SELF_HOSTED_TTS_URL": "http://127.0.0.1:8123/speech"}):
            own, _ = MODULE.voice_catalog_payload()
            self.assertTrue(any(row["provider"] == "self_hosted" for row in own["voices"]))
        payload, code = MODULE.voice_select_payload({"voice_id": "curto"}, owner_authenticated=True)
        self.assertEqual(code, 400)
        self.assertFalse(payload["ok"])
        # Sem Supabase a troca não finge sucesso.
        payload, code = MODULE.voice_select_payload({"voice_id": "abcdefgh1234", "name": "Teste"}, owner_authenticated=True)
        self.assertEqual(code, 503)
        self.assertFalse(payload["ok"])
        # "muda sua voz" abre o painel de verdade.
        self.assertEqual(
            [route for pattern, route in MODULE.LOCAL_INTENTS if pattern.search("muda sua voz")][:1],
            ["voice_settings"],
        )
        opened, _ = MODULE.dispatch_intent("lista as vozes", "voice_settings")
        self.assertEqual(opened["client_action"], "open_voice_panel")

    def test_persona_style_changes_the_prompt_and_opens_the_panel(self):
        """O jeito de responder é do Theo: ele troca por comando e a diretiva chega ao modelo."""
        for phrase in ("muda sua personalidade", "troca o estilo de resposta", "responde mais direto", "ajusta seu tom"):
            self.assertEqual(
                [route for pattern, route in MODULE.LOCAL_INTENTS if pattern.search(phrase)][:1],
                ["persona_settings"],
                phrase,
            )
        # "muda sua voz" continua na voz, não vaza para a personalidade.
        self.assertEqual(
            [route for pattern, route in MODULE.LOCAL_INTENTS if pattern.search("muda sua voz")][:1],
            ["voice_settings"],
        )
        opened, code = MODULE.dispatch_intent("muda sua personalidade", "persona_settings")
        self.assertEqual(code, 200)
        self.assertEqual(opened["client_action"], "open_persona_panel")
        self.assertTrue(any(row["id"] == "mordomo" for row in opened["styles"]))

        # Estilo desconhecido não vira injeção: cai no padrão, que não dita nada.
        self.assertEqual(MODULE.persona_style_id({"persona_style": "inventado"}), "padrao")
        self.assertEqual(MODULE.persona_style_id({"persona_style": "  DIRETO "}), "direto")
        self.assertEqual(MODULE.persona_style_directive({}), "")
        self.assertIn("uma frase", MODULE.persona_style_directive({"persona_style": "direto"}))

        catalog = MODULE.persona_styles_payload({"persona_style": "afiado"})
        self.assertEqual(catalog["active"], "afiado")
        self.assertTrue(any(row["active"] for row in catalog["styles"]))

        # O que importa de verdade: a diretiva chega ao modelo, não só ao painel.
        captured = {}

        def capture(request, *_args, **_kwargs):
            payload = json.loads(request.data.decode("utf-8"))
            captured["system"] = payload["messages"][0]["content"]
            raise MODULE.URLError("sem provedor no teste")

        base = {"messages": [{"role": "user", "content": "e aí"}]}
        with patch.dict(MODULE.os.environ, {"OPENROUTER_API_KEY": "teste-chave"}), \
                patch.object(MODULE, "urlopen", capture):
            MODULE.assistant_response({**base, "persona_style": "direto"})
            direto = captured.get("system", "")
            MODULE.assistant_response({**base, "persona_style": "padrao"})
            padrao = captured.get("system", "")
        self.assertIn("ESTILO PEDIDO PELO THEO (Direto)", direto)
        self.assertIn("uma frase", direto)
        # O padrão não injeta nada: nenhum estilo pendurado no prompt.
        self.assertNotIn("ESTILO PEDIDO PELO THEO", padrao)

        # O briefing conta que o estilo troca — ele nunca pode dizer que é fixo.
        briefing = MODULE.capability_briefing(owner_authenticated=True)
        self.assertIn("personalidade", briefing.casefold())
        self.assertIn("pelo nome", briefing.casefold())


if __name__ == "__main__":
    unittest.main(verbosity=2)
