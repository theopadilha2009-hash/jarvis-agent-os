#!/usr/bin/env python3
"""Pocket TTS no servidor local: config, reuse em memória, fallback, texto íntegro."""

from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.request import Request, urlopen
import importlib.util
import json
import sys
import threading
import unittest
import wave
from io import BytesIO


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_local_tts_server",
    ROOT / "11_SCRIPTS" / "local_tts_server.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PHRASE_A = (
    "Boa noite, Theo. Todos os sistemas estão operacionais. "
    "Estou pronto para auxiliá-lo."
)
PHRASE_B = "Theo, encontrei uma atualização no sistema. Posso verificar os detalhes para você."
PHRASE_C = "Theo, o deploy do GitHub terminou e o Supabase está conectado."


def silent_wav(sample_rate=24_000, frames=240) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


class FakeModel:
    def __init__(self):
        self.sample_rate = 24_000
        self.generate_calls = []

    def generate_audio(self, state, text, copy_state=True):
        self.generate_calls.append({"state": state, "text": text, "copy_state": copy_state})
        return silent_wav(self.sample_rate)


class FakePiper:
    def __init__(self):
        self.calls = []

    def synthesize_wav(self, text, handle):
        self.calls.append(text)
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(22_050)
        handle.writeframes(b"\x00\x00" * 80)


class LocalTtsServerTest(unittest.TestCase):
    def test_voice_config_resolves_from_home_lock_and_env(self):
        with TemporaryDirectory() as folder:
            lock_dir = Path(folder) / "Library" / "Application Support" / "JARVIS" / "voice-lock"
            lock_dir.mkdir(parents=True)
            (lock_dir / "VOICE_CONFIG.txt").write_text(
                "JARVIS VOICE LOCK\n"
                "Python=3.11\n"
                "Pocket-TTS=2.1.0\n"
                "Language=portuguese\n"
                "Voice=bill_boerst\n",
                encoding="utf-8",
            )
            resolved = MODULE.resolve_voice_config(environ={}, home=folder)
            self.assertEqual(resolved["engine"], "auto")
            self.assertEqual(resolved["language"], "portuguese")
            self.assertEqual(resolved["voice"], "bill_boerst")
            self.assertEqual(resolved["ultron_voice"], "javert")
            self.assertFalse(resolved["voice"].endswith(".wav"))

            overridden = MODULE.resolve_voice_config(
                environ={
                    "JARVIS_TTS_ENGINE": "pocket-tts",
                    "JARVIS_TTS_LANGUAGE": "portuguese",
                    "JARVIS_TTS_VOICE": "bill_boerst",
                    "HOME": folder,
                },
                home=folder,
            )
            self.assertEqual(overridden["engine"], "pocket_tts")
            self.assertEqual(overridden["language"], "portuguese")
            self.assertEqual(overridden["voice"], "bill_boerst")

    def test_pocket_generate_uses_catalog_voice_and_full_text(self):
        loads = []
        model = FakeModel()

        def loader(language):
            loads.append(("model", language))
            return model

        def state_loader(loaded, voice):
            loads.append(("state", voice, loaded is model))
            return {"voice": voice}

        runtime = MODULE.PocketRuntime("portuguese", "bill_boerst", loader=loader, state_loader=state_loader)
        audio = runtime.generate(PHRASE_A)
        self.assertTrue(audio.startswith(b"RIFF"))
        self.assertGreater(len(audio), 44)
        self.assertEqual(loads, [("model", "portuguese"), ("state", "bill_boerst", True)])
        self.assertEqual(model.generate_calls[0]["text"], PHRASE_A)
        self.assertEqual(model.generate_calls[0]["state"], {"voice": "bill_boerst"})
        self.assertTrue(model.generate_calls[0]["copy_state"])

    def test_second_synthesis_reuses_loaded_model_and_voice_state(self):
        loads = []
        model = FakeModel()

        def loader(language):
            loads.append(("model", language))
            return model

        def state_loader(_model, voice):
            loads.append(("state", voice))
            return {"voice": voice}

        runtime = MODULE.PocketRuntime("portuguese", "bill_boerst", loader=loader, state_loader=state_loader)
        first = runtime.generate(PHRASE_A)
        second = runtime.generate(PHRASE_B)
        self.assertTrue(first.startswith(b"RIFF"))
        self.assertTrue(second.startswith(b"RIFF"))
        self.assertEqual(loads, [("model", "portuguese"), ("state", "bill_boerst")])
        self.assertEqual(runtime.load_calls, 1)
        self.assertEqual(runtime.state_load_calls, 1)
        self.assertEqual([row["text"] for row in model.generate_calls], [PHRASE_A, PHRASE_B])

    def test_pocket_failure_falls_back_to_piper_without_crash(self):
        class Boom:
            def generate(self, text):
                raise RuntimeError("pocket ausente")

        piper = FakePiper()
        result = MODULE.synthesize_speech(PHRASE_C, pocket=Boom(), piper=piper, piper_opts={"raw": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["engine"], "piper")
        self.assertTrue(result["audio"].startswith(b"RIFF"))
        self.assertEqual(piper.calls, [PHRASE_C])

        failed = MODULE.synthesize_speech(PHRASE_C, pocket=Boom(), piper=None)
        self.assertFalse(failed["ok"])
        self.assertIn("pocket ausente", failed["error"])

    def test_speech_handler_returns_audio_and_keeps_text_intact(self):
        loads = []
        model = FakeModel()

        def loader(language):
            loads.append(("model", language))
            return model

        def state_loader(_model, voice):
            loads.append(("state", voice))
            return {"voice": voice}

        runtime = MODULE.PocketRuntime("portuguese", "bill_boerst", loader=loader, state_loader=state_loader)
        runtime.load()
        args = MODULE.build_parser().parse_args(["--engine", "pocket_tts", "--language", "portuguese", "--tts-voice", "bill_boerst"])
        config = {"engine": "pocket_tts", "language": "portuguese", "voice": "bill_boerst"}
        server = ThreadingHTTPServer(("127.0.0.1", 0), MODULE.make_handler(args, runtime, None, 24_000, config))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            spoken = []
            for phrase in (PHRASE_A, PHRASE_B, PHRASE_C):
                request = Request(
                    f"http://127.0.0.1:{port}/speech",
                    data=json.dumps({"text": phrase}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    body = response.read()
                    spoken.append(phrase)
                    self.assertEqual(response.status, 200)
                    self.assertTrue(body.startswith(b"RIFF"))
                    self.assertGreater(len(body), 44)
            self.assertEqual(spoken, [PHRASE_A, PHRASE_B, PHRASE_C])
            self.assertEqual(loads, [("model", "portuguese"), ("state", "bill_boerst")])
            self.assertEqual([row["text"] for row in model.generate_calls], [PHRASE_A, PHRASE_B, PHRASE_C])

            preflight = Request(
                f"http://127.0.0.1:{port}/speech",
                method="OPTIONS",
                headers={
                    "Origin": "https://jarvis-theo.vercel.app",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Private-Network": "true",
                },
            )
            with urlopen(preflight, timeout=5) as response:
                self.assertIn(response.status, {200, 204})
                self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
                self.assertEqual(response.headers.get("Access-Control-Allow-Private-Network"), "true")
                self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods") or "")
        finally:
            server.shutdown()
            server.server_close()

    def test_spoken_text_is_not_rewritten_before_generate(self):
        model = FakeModel()
        runtime = MODULE.PocketRuntime(
            "portuguese",
            "bill_boerst",
            loader=lambda _language: model,
            state_loader=lambda _model, voice: {"voice": voice},
        )
        result = MODULE.synthesize_speech(PHRASE_A, pocket=runtime, piper=None)
        self.assertTrue(result["ok"])
        self.assertEqual(model.generate_calls[0]["text"], PHRASE_A)
        self.assertNotIn("--voice", model.generate_calls[0]["text"])

    def test_default_catalog_is_portuguese_male_not_english_bill(self):
        empty = MODULE.resolve_voice_config(environ={}, home="/tmp/jarvis-no-voice-lock-test")
        self.assertEqual(empty["voice"], "rafael")
        self.assertEqual(empty["ultron_voice"], "javert")
        self.assertEqual(empty["edge_jarvis"], "pt-BR-AntonioNeural")
        self.assertEqual(empty["edge_ultron"], "pt-BR-AntonioNeural")
        jarvis = MODULE.resolve_request_voices({}, empty)
        ultron = MODULE.resolve_request_voices({"persona": "ultron"}, empty)
        self.assertEqual(jarvis["pocket"], "rafael")
        self.assertEqual(jarvis["edge"], "pt-BR-AntonioNeural")
        self.assertEqual(ultron["pocket"], "javert")
        self.assertEqual(ultron["edge"], "pt-BR-AntonioNeural")
        self.assertNotEqual(jarvis["edge_pitch"], ultron["edge_pitch"])

    def test_ultron_persona_uses_second_pocket_voice_state(self):
        model = FakeModel()
        runtime = MODULE.PocketRuntime(
            "portuguese",
            "rafael",
            extra_voices=["javert"],
            loader=lambda _language: model,
            state_loader=lambda _model, voice: {"voice": voice},
        )
        runtime.generate("Olá, Theo.", voice="rafael")
        runtime.generate("Ordem recebida.", voice="javert")
        self.assertEqual(runtime.load_calls, 1)
        self.assertEqual(runtime.state_load_calls, 2)
        self.assertEqual([row["state"]["voice"] for row in model.generate_calls], ["rafael", "javert"])

    def test_edge_missing_module_fails_soft(self):
        with patch.dict(sys.modules, {"edge_tts": None}):
            failed = MODULE.synthesize_edge("teste", "pt-BR-AntonioNeural")
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["engine"], "edge")

    def test_agent_restarts_only_on_crash(self):
        args = MODULE.build_parser().parse_args(["--engine", "pocket_tts", "--host", "127.0.0.1", "--port", "8123"])
        config = {
            "engine": "pocket_tts",
            "language": "portuguese",
            "voice": "rafael",
            "ultron_voice": "javert",
        }
        payload = MODULE.agent_payload(args, config)
        self.assertEqual(payload["KeepAlive"], {"SuccessfulExit": False})
        self.assertNotEqual(payload.get("ProcessType"), "Background")
        self.assertTrue(payload["RunAtLoad"])
        self.assertTrue(MODULE.ExclusiveHTTPServer.allow_reuse_address)

    def test_pocket_adult_timbre_keeps_wav_or_original(self):
        raw = silent_wav()
        with patch.object(MODULE.shutil, "which", return_value=None):
            self.assertEqual(MODULE.apply_pocket_adult(raw, 24_000), raw)
        self.assertIn("_SPEECH_LOCK", MODULE.__dict__)
        source = (ROOT / "11_SCRIPTS" / "local_tts_server.py").read_text(encoding="utf-8")
        self.assertIn("timeout=4.0", source)
        self.assertIn("with _SPEECH_LOCK:", source)
        self.assertIn("0.96", MODULE.POCKET_ADULT)

    def test_warmup_and_short_speech_cache(self):
        MODULE._SPEECH_CACHE.clear()
        model = FakeModel()
        runtime = MODULE.PocketRuntime(
            "portuguese",
            "rafael",
            loader=lambda _language: model,
            state_loader=lambda _model, voice: {"voice": voice},
        )
        MODULE.warmup_runtime(runtime, "rafael")
        self.assertEqual([row["text"] for row in model.generate_calls], ["ok"])

        args = MODULE.build_parser().parse_args(["--engine", "pocket_tts", "--language", "portuguese", "--tts-voice", "rafael"])
        config = {"engine": "pocket_tts", "language": "portuguese", "voice": "rafael"}
        server = ThreadingHTTPServer(("127.0.0.1", 0), MODULE.make_handler(args, runtime, None, 24_000, config))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            for _ in range(2):
                request = Request(
                    f"http://127.0.0.1:{port}/speech",
                    data=json.dumps({"text": "Aberto"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(response.read().startswith(b"RIFF"))
            self.assertEqual([row["text"] for row in model.generate_calls], ["ok", "Aberto"])
        finally:
            server.shutdown()
            server.server_close()
        MODULE._SPEECH_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
