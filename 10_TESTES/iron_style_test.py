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

    def _payload(self, agenda=None, notes=None):
        original = (
            gateway.supabase_configured,
            gateway.supabase_agenda_rows,
            gateway.supabase_notes_rows,
            gateway.supabase_request,
        )
        gateway.supabase_configured = lambda: True
        gateway.supabase_agenda_rows = lambda *_a, **_k: self.AGENDA if agenda is None else agenda
        gateway.supabase_notes_rows = lambda *_a, **_k: notes or []
        # Não enfileira nada: teste não pode tocar música no Mac.
        gateway.supabase_request = lambda *_a, **_k: [{"id": 1, "status": "pending"}]
        try:
            return gateway.iron_style_payload()[0]
        finally:
            (
                gateway.supabase_configured,
                gateway.supabase_agenda_rows,
                gateway.supabase_notes_rows,
                gateway.supabase_request,
            ) = original

    def test_agenda_anotacoes_e_pergunta_final(self):
        payload = self._payload(notes=[{"title": "Revisar contrato do cliente"}])
        falado = payload["spoken"]
        for esperado in ("criar 3 sistemas", "mandar retorno até terça", "revisar contrato do cliente"):
            self.assertIn(esperado, falado.lower())
        self.assertIn("como quer seguir hoje", falado.lower())
        self.assertIn("back in black", falado.lower())

    def test_fala_cabe_no_limite_da_voz(self):
        payload = self._payload(notes=[{"title": "Revisar contrato do cliente"}])
        self.assertLessEqual(len(payload["spoken"]), 400)

    def test_sem_agenda_avisa_limpa(self):
        falado = self._payload(agenda=[])["spoken"]
        self.assertIn("agenda limpa", falado.lower())
        self.assertIn("como quer seguir hoje", falado.lower())

    def test_sem_anotacao_nao_inventa_secao(self):
        falado = self._payload(notes=[])["spoken"]
        self.assertNotIn("anotações", falado.lower())

    def test_nao_soa_como_relatorio(self):
        falado = self._payload()["spoken"]
        for ruido in ("status_real", "03/11", "http", "worker", "supabase"):
            self.assertNotIn(ruido, falado.lower())


class ConfirmedTrackTest(unittest.TestCase):
    """O modelo já inventou URI de faixa; só toca o que veio do Theo."""

    def test_uri_inventada_pelo_modelo_nao_passa(self):
        self.assertEqual(
            gateway.confirmed_track_uri("spotify:track:4svkPL62HbvyFgf0nHFXAF", "toca uma música aí"),
            "",
        )

    def test_nome_do_catalogo_manda_na_uri(self):
        # Pedido era Back In Black; o modelo mandou Black Sabbath. Vence o catálogo.
        self.assertEqual(
            gateway.confirmed_track_uri(
                "spotify:track:4svkPL62HbvyFgf0nHFXAF", "toca a música do homem de ferro"
            ),
            spotify_control.BACK_IN_BLACK_URI,
        )

    def test_link_dito_pelo_usuario_passa(self):
        link = "https://open.spotify.com/track/2iEGj7kAwH7HAa5epwYwLB"
        self.assertEqual(
            gateway.confirmed_track_uri(spotify_control.BACK_IN_BLACK_URI, f"toca {link}"),
            spotify_control.BACK_IN_BLACK_URI,
        )

    def test_uri_que_nao_e_faixa_nao_passa(self):
        self.assertEqual(gateway.confirmed_track_uri("javascript:alert(1)", "toca isso"), "")
        self.assertEqual(gateway.confirmed_track_uri("spotify:album:abc", "toca isso"), "")


class SpokenClipTest(unittest.TestCase):
    def test_texto_curto_passa_intacto(self):
        self.assertEqual(gateway.spoken_clip("Beleza, tá feito."), "Beleza, tá feito.")

    def test_corta_no_separador_e_nao_no_meio_da_palavra(self):
        texto = "Sua agenda: " + ", ".join(f"tarefa comprida numero {i}" for i in range(12))
        cortado = gateway.spoken_clip(texto, limit=90)
        self.assertLessEqual(len(cortado), 91)
        self.assertTrue(cortado.endswith(".") or cortado.endswith("…"))
        self.assertFalse(cortado.endswith(" "))

    def test_nunca_passa_do_limite_sem_espaco(self):
        self.assertLessEqual(len(gateway.spoken_clip("x" * 400, limit=100)), 101)


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
