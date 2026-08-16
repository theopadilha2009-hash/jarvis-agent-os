#!/usr/bin/env python3
"""Contract tests for the local JARVIS voice server."""

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
    def __init__(self, name, result=None, error=None, natural=True):
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
    def test_parser_defaults_to_pocket_portuguese(self):
        args = MODULE.build_parser().parse_args([])
        self.assertEqual(args.engine, "auto")
        self.assertEqual(args.language, "portuguese")
        self.assertEqual(args.lsd_decode_steps, 1)

    def test_pocket_requires_reference(self):
        args = MODULE.build_parser().parse_args(["--engine", "pocket"])
        with self.assertRaisesRegex(RuntimeError, "exige --reference"):
            MODULE.build_engine(args)

    def test_fallback_promotes_working_engine(self):
        primary = FakeEngine("pocket-tts", error=RuntimeError("offline"))
        fallback = FakeEngine("piper", result=b"wav", natural=False)
        engine = MODULE.FallbackEngine([primary, fallback])
        self.assertEqual(engine.synthesize("oi", {}), b"wav")
        self.assertEqual(engine.name, "piper")
        self.assertEqual(engine.engines[0].name, "piper")


if __name__ == "__main__":
    unittest.main()
