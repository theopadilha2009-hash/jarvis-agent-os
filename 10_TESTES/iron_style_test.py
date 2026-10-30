#!/usr/bin/env python3
"""Modo Homem de Ferro: gatilho, faixa do catálogo e agenda que é falada."""

from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import index as gateway  # noqa: E402
import spotify_control  # noqa: E402


def spoken_reply(text):
    """Espelha spokenReply() de web/fala.js: só as 2 primeiras frases."""
    clip = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clip:
        return ""
    parts = re.findall(r"[^.!?…]+[.!?…]*\s*", clip) or [clip]
    return "".join(parts[:2]).strip()[:300].strip()


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
    def test_data_em_palavras(self):
        self.assertEqual(gateway.spoken_date("2026-11-03T12:00:00+00:00"), "3 de novembro")
        self.assertEqual(gateway.spoken_date("2026-12-25T09:00:00+00:00"), "25 de dezembro")

    def test_data_invalida_nao_quebra(self):
        self.assertEqual(gateway.spoken_date("amanhã"), "")
        self.assertEqual(gateway.spoken_date(""), "")

    def test_item_vira_fala_corrida(self):
        rows = [
            {"title": "Mandar retorno até terça", "scheduled_for": "2026-11-03T12:00:00+00:00"},
            {"title": "Criar 3 sistemas", "scheduled_for": None},
        ]
        self.assertEqual(
            gateway.agenda_spoken_summary(rows),
            ["mandar retorno até terça, dia 3 de novembro", "criar 3 sistemas"],
        )

    def test_lista_falada_usa_e_antes_do_ultimo(self):
        self.assertEqual(gateway.spoken_list(["a", "b", "c"]), "a, b e c")
        self.assertEqual(gateway.spoken_list(["a"]), "a")
        self.assertEqual(gateway.spoken_list([]), "")

    def test_limite_e_linhas_vazias(self):
        rows = [{"title": f"t{i}"} for i in range(10)] + [{"title": ""}]
        self.assertEqual(len(gateway.agenda_spoken_summary(rows, limit=3)), 3)


class IronStyleMessageTest(unittest.TestCase):
    """O que o app fala é só as 2 primeiras frases — a agenda tem que caber."""

    def _message(self, rows):
        items = gateway.agenda_spoken_summary(rows)
        if items:
            return (
                "Beleza, modo Homem de Ferro ligado e Back in Black tocando. "
                f"Sua agenda: {gateway.spoken_list(items)}."
            )
        return (
            "Beleza, modo Homem de Ferro ligado e Back in Black tocando. "
            "Agenda limpa, nada pendente."
        )

    def test_agenda_sobrevive_ao_corte_de_duas_frases(self):
        rows = [
            {"title": "Criar 3 sistemas", "scheduled_for": None},
            {"title": "Mandar retorno até terça", "scheduled_for": "2026-11-03T12:00:00+00:00"},
            {"title": "Postar um vídeo sexta-feira", "scheduled_for": "2026-11-06T15:00:00+00:00"},
        ]
        falado = spoken_reply(self._message(rows))
        for esperado in ("criar 3 sistemas", "mandar retorno até terça", "postar um vídeo sexta-feira"):
            self.assertIn(esperado, falado.lower())
        self.assertIn("back in black", falado.lower())

    def test_sem_agenda_avisa_limpa(self):
        falado = spoken_reply(self._message([]))
        self.assertIn("agenda limpa", falado.lower())

    def test_nao_soa_como_relatorio(self):
        falado = self._message([{"title": "Criar 3 sistemas", "scheduled_for": None}])
        for ruido in ("status_real", "03/11", "http", "worker", "supabase"):
            self.assertNotIn(ruido, falado.lower())


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
