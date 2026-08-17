#!/usr/bin/env python3
"""Contract tests for the JARVIS-THEO OpenRouter terminal interface."""

from contextlib import redirect_stdout
from io import StringIO
import importlib.util
from pathlib import Path
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_theo_chat",
    ROOT / "11_SCRIPTS" / "jarvis_theo_chat.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeBrain:
    def __init__(self):
        self.calls = []

    def chat(self, prompt, history=None, **kwargs):
        self.calls.append({"prompt": prompt, "history": history or []})
        return {
            "ok": True,
            "status": 200,
            "message": "Entendi o recado: reunião amanhã às 10.",
            "provider": "openrouter",
            "model": "nvidia/nemotron-3-nano-30b-a3b:free",
        }


class TheoChatTest(unittest.TestCase):
    def test_dry_run_does_not_call_openrouter(self):
        gateway = FakeBrain()
        output = StringIO()
        with redirect_stdout(output):
            code = MODULE.execute(["--dry-run", "explica isso"], gateway=gateway)
        self.assertEqual(code, 0)
        self.assertEqual(gateway.calls, [])
        text = output.getvalue()
        self.assertIn("JARVIS-THEO", text)
        self.assertIn("OpenRouter não foi chamado", text)
        self.assertIn("Pocket TTS", text)
        self.assertIn("Produção: nada alterado.", text)
        self.assertNotIn("sk-", text)

    def test_missing_key_fails_without_network(self):
        gateway = FakeBrain()
        output = StringIO()
        env = {k: v for k, v in os.environ.items() if not k.startswith("OPENROUTER")}
        with patch.object(MODULE, "secret_files", return_value=[]), \
                patch.dict(os.environ, env, clear=True), \
                redirect_stdout(output):
            code = MODULE.execute(["oi"], gateway=gateway)
        self.assertEqual(code, 1)
        self.assertEqual(gateway.calls, [])
        self.assertIn("OpenRouter não está configurado", output.getvalue())

    def test_one_shot_uses_fast_openrouter_client(self):
        brain = FakeBrain()
        output = StringIO()
        with patch.object(MODULE, "openrouter_ready", return_value=True), redirect_stdout(output):
            code = MODULE.execute(["transcreve: fala baixo"], chat_fn=brain.chat)
        self.assertEqual(code, 0)
        self.assertEqual(len(brain.calls), 1)
        self.assertIn("transcreve", brain.calls[0]["prompt"])
        self.assertIn("Entendi o recado", output.getvalue())

    def test_text_file_becomes_transcription_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recado.txt"
            path.write_text("oi theo amanha dez horas reuniao", encoding="utf-8")
            opts = MODULE.parse_args([str(path)])
        self.assertIn("Transcreva com clareza", opts["prompt"])
        self.assertIn("reuniao", opts["prompt"])
        self.assertTrue(opts["source"].endswith("recado.txt"))

    def test_load_secrets_sets_key_without_echoing_it(self):
        secret = "sk-or-v1-test-not-real"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secrets.env"
            path.write_text(f"OPENROUTER_API_KEY={secret}\n", encoding="utf-8")
            env = {}
            with patch.object(MODULE, "secret_files", return_value=[path]):
                loaded = MODULE.load_secrets(env)
        self.assertEqual(loaded, [str(path)])
        self.assertEqual(env["OPENROUTER_API_KEY"], secret)
        self.assertTrue(MODULE.openrouter_ready(env))

    def test_rejects_placeholder_openrouter_values(self):
        self.assertFalse(MODULE.looks_like_openrouter_key("Encrypted"))
        self.assertFalse(MODULE.looks_like_openrouter_key("sk-or-short"))
        self.assertTrue(MODULE.looks_like_openrouter_key("sk-or-v1-" + ("a" * 24)))

    def test_install_keys_dry_run_does_not_touch_disk(self):
        output = StringIO()
        called = []
        with redirect_stdout(output):
            code = MODULE.install_keys_from_vercel(dry_run=True, runner=lambda *a, **k: called.append(a))
        self.assertEqual(code, 0)
        self.assertEqual(called, [])
        self.assertIn("preview da instalação", output.getvalue())
        self.assertIn("OPENROUTER_", output.getvalue())

    def test_route_note_mentions_key_and_model_switch(self):
        note = MODULE.route_note({
            "openrouter_key_failover": True,
            "model": "openrouter/free",
            "model_routing": {
                "selected": "openrouter/free",
                "compatibility_fallback": True,
                "compatibility_attempts": [{"model": "a"}, {"model": "b"}],
            },
        })
        self.assertIn("reserva", note)
        self.assertIn("modelo", note)

    def test_fast_client_skips_400_and_uses_next_model(self):
        import jarvis_theo_brain as brain

        calls = []

        def poster(api_key, model, messages, timeout):
            calls.append(model)
            if model.endswith("nano-30b-a3b:free"):
                raise urllib.error.HTTPError(brain.OPENROUTER_URL, 400, "bad", {}, None)
            return {
                "model": model,
                "choices": [{"message": {"content": "ok rapido"}}],
            }

        payload = brain.chat(
            "oi",
            [],
            keys=["sk-or-v1-test-not-real-key-00000000"],
            poster=poster,
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["message"], "ok rapido")
        self.assertGreaterEqual(len(calls), 2)

    def test_logo_is_calm_pixel_mark(self):
        scripts = str(ROOT / "11_SCRIPTS")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import jarvis_theo_ui as ui
        with patch.dict(os.environ, {"JARVIS_THEO_PLAIN": "1"}, clear=False):
            rows = ui.pixel_mark()
            text = ui.banner(True, 1)
        self.assertGreaterEqual(len(rows), 12)
        self.assertLessEqual(len(rows), 20)
        joined = "\n".join(rows)
        self.assertIn("·", joined)
        self.assertIn("•", joined)
        self.assertIn("●", joined)
        self.assertNotIn("█", joined)
        self.assertIn("J · A · R · V · I · S", text)

    def test_banner_uses_official_wordmark(self):
        scripts = str(ROOT / "11_SCRIPTS")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import jarvis_theo_ui as ui
        with patch.dict(os.environ, {"JARVIS_THEO_PLAIN": "1"}, clear=False):
            text = ui.banner(True, 4)
        self.assertIn("J · A · R · V · I · S", text)
        self.assertIn("POR THEO LORENTZ PADILHA", text)
        self.assertIn("JARVIS-THEO", text)

    def test_setup_explains_other_computer(self):
        output = StringIO()
        with redirect_stdout(output):
            code = MODULE.execute(["--setup"])
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("outro computador", text.lower())
        self.assertIn("OPENROUTER_API_KEY", text)
        self.assertNotIn("sk-or-v1-d674", text)

    def test_careful_mode_for_real_improvements(self):
        import jarvis_theo_brain as brain
        self.assertTrue(brain.CAREFUL_RE.search("melhorar o deploy"))
        self.assertFalse(brain.CAREFUL_RE.search("oi jarvis"))

    def test_help_mentions_openrouter_not_codex(self):
        output = StringIO()
        with redirect_stdout(output):
            code = MODULE.execute(["--help"])
        text = output.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("OpenRouter", text)
        self.assertNotIn("opencode", text.lower())
        self.assertNotIn("codex", text.lower())
        self.assertNotIn("claude", text.lower())

    def test_local_fallback_knows_itself_and_web_intent(self):
        identity = MODULE.local_reply("quem é você")
        self.assertTrue(identity["ok"])
        self.assertIn("Theo", identity["message"])
        self.assertIn("Pocket", MODULE.local_reply("como é a sua voz")["message"])
        self.assertTrue(MODULE.wants_web("pesquise o preço do Civic 2018"))
        self.assertFalse(MODULE.wants_web("oi jarvis"))

    def test_ask_falls_back_locally_when_brain_is_blocked(self):
        def boom(_prompt, _history):
            return {"ok": False, "status": 429, "error": "OpenRouter bloqueou"}

        payload, status = MODULE.ask("quem é você", [], chat_fn=boom)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["provider"], "local_fallback")
        self.assertIn("Theo", payload["message"])


if __name__ == "__main__":
    unittest.main()
