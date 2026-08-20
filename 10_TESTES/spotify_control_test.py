#!/usr/bin/env python3
"""Contract tests for deterministic Spotify command parsing."""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
from spotify_control import command_args, control_requested, public_target  # noqa: E402


class SpotifyControlTest(unittest.TestCase):
    def test_portuguese_controls_map_to_allowlisted_arguments(self):
        cases = {
            "pause o Spotify": ["pause"],
            "próxima faixa no Spotify": ["next"],
            "volta para a música anterior": ["previous"],
            "volume do Spotify para 35": ["volume", "35"],
            "o que está tocando no Spotify": ["status"],
            "busque no Spotify Daft Punk": ["search", "Daft Punk"],
            "toque Bohemian Rhapsody no Spotify": ["search", "Bohemian Rhapsody"],
            "ative o aleatório no Spotify": ["shuffle", "on"],
            "desative a repetição no Spotify": ["repeat", "off"],
            "continue o Spotify": ["play"],
            "toque no Spotify spotify:track:4uLU6hMCjMI75M1A2tKUQC": [
                "play-uri", "spotify:track:4uLU6hMCjMI75M1A2tKUQC",
            ],
            "toca a música do homem de ferro": [
                "play-uri", "spotify:track:4svkPL62HbvyFgf0nHFXAF",
            ],
            "abre o Spotify com a música do Homem de Ferro": [
                "play-uri", "spotify:track:4svkPL62HbvyFgf0nHFXAF",
            ],
            "toque Iron Man no Spotify": [
                "play-uri", "spotify:track:4svkPL62HbvyFgf0nHFXAF",
            ],
        }
        for request, expected in cases.items():
            with self.subTest(request=request):
                self.assertTrue(control_requested(request))
                self.assertEqual(command_args(request), expected)

    def test_invalid_values_never_become_commands(self):
        self.assertIsNone(command_args("volume do Spotify para 999"))
        self.assertIsNone(command_args("busque no Spotify x; rm -rf"))
        self.assertIsNone(command_args("toque spotify:album:not-a-track no Spotify"))

    def test_public_target_never_exposes_search_or_uri(self):
        self.assertEqual(public_target(["search", "Theo Mix"]), "search")
        self.assertEqual(public_target(["play-uri", "spotify:track:4uLU6hMCjMI75M1A2tKUQC"]), "play-uri")
        self.assertEqual(public_target(["volume", "35"]), "volume 35")


if __name__ == "__main__":
    unittest.main(verbosity=2)
