#!/usr/bin/env python3
"""Modo Homem de Ferro: gatilho, faixa do catálogo e agenda que é falada."""

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
            "entrar no modo do Homem de Ferro",
            "modo do iron man",
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
    """Testa o payload de verdade, não uma cópia da mensagem."""

    AGENDA = [
        {"title": "Criar 3 sistemas", "scheduled_for": None},
        {"title": "Mandar retorno até terça", "scheduled_for": "2026-11-03T12:00:00+00:00"},
        {"title": "Postar um vídeo sexta-feira", "scheduled_for": "2026-11-06T15:00:00+00:00"},
    ]

    def _payload(self, agenda=None, notes=None, clima="17 graus e nublado"):
        original = (
            gateway.supabase_configured,
            gateway.supabase_agenda_rows,
            gateway.supabase_notes_rows,
            gateway.supabase_request,
            gateway.weather_now,
        )
        gateway.supabase_configured = lambda: True
        gateway.supabase_agenda_rows = lambda *_a, **_k: self.AGENDA if agenda is None else agenda
        gateway.supabase_notes_rows = lambda *_a, **_k: notes or []
        # Não enfileira nada e não sai para a internet: teste não toca música
        # nem depende do clima real.
        gateway.supabase_request = lambda *_a, **_k: [{"id": 1, "status": "pending"}]
        gateway.weather_now = lambda: clima
        try:
            return gateway.iron_style_payload()[0]
        finally:
            (
                gateway.supabase_configured,
                gateway.supabase_agenda_rows,
                gateway.supabase_notes_rows,
                gateway.supabase_request,
                gateway.weather_now,
            ) = original

    def test_abertura_curta_para_a_musica_entrar(self):
        payload = self._payload()
        self.assertIn("entrando no modo homem de ferro", payload["spoken"].lower())
        self.assertIn("senhor", payload["spoken"].lower())
        self.assertGreaterEqual(payload["spoken_delay_ms"], 5000)
        self.assertLess(len(payload["spoken"]), 90)

    def test_quadro_com_hora_clima_agenda_e_pergunta(self):
        payload = self._payload(notes=[{"title": "Revisar contrato do cliente"}])
        quadro = payload["spoken_later"].lower()
        self.assertIn("agora são", quadro)
        self.assertIn("hoje está 17 graus", quadro)
        self.assertIn("na agenda", quadro)
        self.assertIn("mandar retorno até terça", quadro)
        self.assertIn("suas anotações para hoje são", quadro)
        self.assertIn("revisar contrato do cliente", quadro)
        self.assertIn("abra alguma coisa", quadro)

    def test_cada_fala_cabe_no_limite_da_voz(self):
        payload = self._payload(notes=[{"title": "Revisar contrato do cliente"}])
        self.assertLessEqual(len(payload["spoken"]), 400)
        self.assertLessEqual(len(payload["spoken_later"]), 400)

    def test_sem_agenda_avisa_limpa(self):
        quadro = self._payload(agenda=[])["spoken_later"].lower()
        self.assertIn("agenda limpa", quadro)

    def test_sem_anotacao_nao_inventa_secao(self):
        self.assertNotIn("anotações", self._payload(notes=[])["spoken_later"].lower())

    def test_sem_clima_nao_quebra_a_frase(self):
        quadro = self._payload(clima="")["spoken_later"].lower()
        self.assertNotIn("lá fora", quadro)
        self.assertIn("agora são", quadro)

    def test_nao_soa_como_relatorio(self):
        payload = self._payload()
        for ruido in ("status_real", "03/11", "http", "worker", "supabase"):
            self.assertNotIn(ruido, (payload["spoken"] + " " + payload["spoken_later"]).lower())


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
        self.assertEqual(spotify_control.BACK_IN_BLACK_URI, "spotify:track:08mG3Y1vljYA6bvDt4Wqkj")


if __name__ == "__main__":
    unittest.main()
