#!/usr/bin/env python3
"""Roteamento dos pedidos em linguagem natural (spotify, agenda, semana)."""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
from ask_router import detect_intent, _next_command_for  # noqa: E402
from spotify_control import BACK_IN_BLACK_URI, command_args, resolve_track  # noqa: E402


class SpotifyIntentTest(unittest.TestCase):
    def test_abrir_spotify_nao_vira_projeto(self):
        self.assertEqual(detect_intent("abre o spotify"), "spotify_control")

    def test_composto_abre_e_toca(self):
        text = "abre o spotify e toca AC/DC - Back In Black"
        self.assertEqual(detect_intent(text), "spotify_control")
        self.assertEqual(
            command_args(text),
            ["play-uri", BACK_IN_BLACK_URI],
        )

    def test_toca_faixa_do_catalogo(self):
        self.assertEqual(detect_intent("toca back in black"), "spotify_control")

    def test_volume_do_spotify_nao_vira_volume_do_sistema(self):
        self.assertEqual(detect_intent("volume do spotify para 30"), "spotify_control")

    def test_catalogo_resolve_back_in_black(self):
        uri, name = resolve_track("AC/DC - Back In Black")
        self.assertEqual(uri, BACK_IN_BLACK_URI)
        self.assertEqual(name, "back in black")

    def test_homem_de_ferro_e_back_in_black(self):
        # Preferência do Theo (2026-10-30): "música do Homem de Ferro" é a do
        # Iron Man 2, não o Iron Man do Black Sabbath.
        iron, _ = resolve_track("homem de ferro")
        back, _ = resolve_track("back in black")
        self.assertEqual(iron, BACK_IN_BLACK_URI)
        self.assertEqual(iron, back)


class AgendaIntentTest(unittest.TestCase):
    def test_pergunta_sobre_agenda_nao_grava(self):
        for text in ("o que tenho na agenda", "me mostra a agenda", "minha agenda?"):
            self.assertEqual(detect_intent(text), "agenda_view", text)

    def test_escrita_de_agenda_grava(self):
        for text in (
            "coloca amanhã revisar LS na agenda",
            "adiciona revisar LS na agenda",
            "anota que sexta às 14h eu preciso postar um vídeo",
        ):
            self.assertEqual(detect_intent(text), "agenda_note", text)

    def test_agenda_view_nao_gera_agenda_add(self):
        cmd, _str, _safety, _dry = _next_command_for(
            "agenda_view", "", "o que tenho na agenda", None
        )
        self.assertEqual(cmd, ["./jarvis", "agenda"])
        self.assertNotIn("agenda-add", cmd)


class WeeklyReportIntentTest(unittest.TestCase):
    def test_relatorio_da_semana(self):
        for text in (
            "me dá o relatório da semana",
            "o que tenho pra fazer?",
            "minha semana",
        ):
            self.assertEqual(detect_intent(text), "weekly_report", text)

    def test_relatorio_vira_comando_week(self):
        cmd, _str, _safety, _dry = _next_command_for(
            "weekly_report", "", "me dá o relatório da semana", None
        )
        self.assertEqual(cmd, ["./jarvis", "week", "--days", "7"])


class RegressionTest(unittest.TestCase):
    def test_frases_antigas_continuam_no_lugar(self):
        self.assertEqual(
            detect_intent("abre oficina e corrige bug da agenda"), "project_fix"
        )
        self.assertEqual(detect_intent("adiciona feature no projeto gc"), "project_fix")
        self.assertEqual(detect_intent("bug da agenda"), "unclear")


if __name__ == "__main__":
    unittest.main()
