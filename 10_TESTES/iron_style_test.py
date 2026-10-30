#!/usr/bin/env python3
"""Modo Homem de Ferro: gatilho, faixa do catálogo e agenda falada."""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import index as gateway  # noqa: E402
import spotify_control  # noqa: E402


class IronStyleTriggerTest(unittest.TestCase):
    def test_formas_de_pedir(self):
        for frase in (
            "jarvis estilo homem de ferro",
            "jarvis, modo Homem de Ferro",
            "vibe stark",
            "modo iron man",
        ):
            self.assertIsNotNone(gateway.IRON_STYLE_PATTERN.search(frase), frase)

    def test_pedido_normal_nao_dispara(self):
        for frase in ("toca back in black", "abre o spotify", "estilo de código"):
            self.assertIsNone(gateway.IRON_STYLE_PATTERN.search(frase), frase)


class AgendaSummaryTest(unittest.TestCase):
    def test_ordem_e_dia_da_semana(self):
        rows = [
            {"title": "Mandar retorno até terça", "scheduled_for": "2026-11-03T12:00:00+00:00"},
            {"title": "Criar 3 sistemas", "scheduled_for": None},
        ]
        items = gateway.agenda_spoken_summary(rows)
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0].startswith("Mandar retorno até terça"))
        self.assertIn("03/11", items[0])
        self.assertEqual(items[1], "Criar 3 sistemas")

    def test_limite_e_linhas_vazias(self):
        rows = [{"title": f"t{i}"} for i in range(10)] + [{"title": ""}]
        self.assertEqual(len(gateway.agenda_spoken_summary(rows, limit=3)), 3)

    def test_data_invalida_nao_quebra(self):
        items = gateway.agenda_spoken_summary([{"title": "x", "scheduled_for": "amanhã"}])
        self.assertEqual(items, ["x"])


class IronStylePayloadTest(unittest.TestCase):
    def test_sem_supabase_nao_promete_musica(self):
        original = gateway.supabase_configured
        gateway.supabase_configured = lambda: False
        try:
            payload, status = gateway.iron_style_payload()
        finally:
            gateway.supabase_configured = original
        self.assertEqual(status, 503)
        self.assertFalse(payload["ok"])

    def test_faixa_do_modo_e_back_in_black(self):
        # O modo não passa pelo modelo: a URI é sempre a do catálogo.
        self.assertEqual(spotify_control.BACK_IN_BLACK_URI, "spotify:track:2iEGj7kAwH7HAa5epwYwLB")


if __name__ == "__main__":
    unittest.main()
