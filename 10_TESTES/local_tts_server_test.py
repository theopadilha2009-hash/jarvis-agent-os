#!/usr/bin/env python3
"""Contract tests for the local JARVIS TTS engine selector."""

from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_local_tts",
    ROOT / "11_SCRIPTS" / "local_tts_server.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeEngine(MODULE.VoiceEngine):
    def __init__(self, name, result=None, error=None, natural=False):
        self.name = name
        self.model_name = name + "-model"
        self.sample_rate = 24000
        self.device = "cpu"
        self.natural_audio = natural
        self.result = result
        self.error = error

    def synthesize(self, text, options):
        if self.error:
            raise self.error
        return self.result or text.encode("utf-8")


class LocalTtsServerTest(unittest.TestCase):
    def test_fallback_promotes_working_engine(self):
        primary = FakeEngine("chatterbox-v3", error=RuntimeError("offline"), natural=True)
        fallback = FakeEngine("piper", result=b"wav")
        engine = MODULE.FallbackEngine([primary, fallback])

        self.assertEqual(engine.synthesize("oi", {}), b"wav")
        self.assertEqual(engine.name, "piper")
        self.assertEqual(engine.engines[0].name, "piper")

    def test_bounded_clamps_generation_controls(self):
        self.assertEqual(MODULE._bounded({"cfg_weight": 2}, "cfg_weight", 0.35, 0, 1), 1)
        self.assertEqual(MODULE._bounded({"cfg_weight": -1}, "cfg_weight", 0.35, 0, 1), 0)
        self.assertEqual(MODULE._bounded({"cfg_weight": "x"}, "cfg_weight", 0.35, 0, 1), 0.35)

    def test_parser_keeps_legacy_piper_voice_optional(self):
        parser = MODULE.build_parser()
        args = parser.parse_args(["--engine", "piper", "--voice", "/tmp/cadu.onnx"])
        self.assertEqual(args.engine, "piper")
        self.assertEqual(args.voice, "/tmp/cadu.onnx")
        self.assertEqual(args.language, "pt")


if __name__ == "__main__":
    unittest.main()
