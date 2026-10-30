#!/usr/bin/env python3
"""Preferências ensinadas falando: "quando eu pedir X, bota essa"."""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import preferences  # noqa: E402
import spotify_control  # noqa: E402


LINK = "https://open.spotify.com/intl-pt/track/2iEGj7kAwH7HAa5epwYwLB?si=31c1ce569492445d"
URI = "spotify:track:2iEGj7kAwH7HAa5epwYwLB"


class ParseTeachingTest(unittest.TestCase):
    def test_quando_eu_pedir_com_link(self):
        rule = preferences.parse_teaching(
            f"quando eu te pedir a música do Homem de Ferro, bota essa aqui {LINK}"
        )
        self.assertEqual(rule, {"trigger": "homem de ferro", "action": "spotify_play", "payload": {"uri": URI}})

    def test_sem_virgula_o_reconhecimento_de_fala_engole(self):
        rule = preferences.parse_teaching(
            f"quando eu falar música do homem de ferro bota essa {LINK}"
        )
        self.assertIsNotNone(rule)
        self.assertEqual(rule["trigger"], "homem de ferro")
        self.assertEqual(rule["payload"]["uri"], URI)

    def test_frase_do_tipo_e_essa(self):
        rule = preferences.parse_teaching(f"a música do homem de ferro é essa aqui: {LINK}")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["trigger"], "homem de ferro")

    def test_uri_direta_tambem_vale(self):
        rule = preferences.parse_teaching(f"quando eu pedir música do homem de ferro toca {URI}")
        self.assertEqual(rule["payload"]["uri"], URI)

    def test_pedido_normal_nao_e_ensino(self):
        for text in (
            "toca back in black",
            "quando eu pedir a música do homem de ferro",
            "abre o spotify",
            "quando eu pedir o relatório da semana, manda no whatsapp",
        ):
            self.assertIsNone(preferences.parse_teaching(text), text)


class TriggerKeyTest(unittest.TestCase):
    def test_tira_o_enfite_da_frase(self):
        self.assertEqual(preferences.trigger_key("a música do Homem de Ferro"), "homem de ferro")
        self.assertEqual(preferences.trigger_key("Homem de Ferro"), "homem de ferro")

    def test_acento_e_caixa_nao_importam(self):
        self.assertEqual(preferences.trigger_key("MÚSICA DO AC/DC"), "ac/dc")


class LearnedUriTest(unittest.TestCase):
    def test_gatilho_mais_longo_vence(self):
        rules = [
            {"trigger": "homem de ferro", "payload": {"uri": "spotify:track:AAAAAAAAAAAA"}},
            {"trigger": "musica do homem de ferro", "payload": {"uri": "spotify:track:BBBBBBBBBBBB"}},
        ]
        self.assertEqual(
            preferences.learned_uri("toca a música do homem de ferro", rules),
            "spotify:track:BBBBBBBBBBBB",
        )

    def test_sem_regra_nao_casa(self):
        self.assertEqual(preferences.learned_uri("toca back in black", []), "")

    def test_regra_com_uri_invalida_e_ignorada(self):
        rules = [{"trigger": "homem de ferro", "payload": {"uri": "javascript:alert(1)"}}]
        self.assertEqual(preferences.learned_uri("toca homem de ferro", rules), "")


class RulesFromMemoriesTest(unittest.TestCase):
    def test_so_preferencia_de_spotify_vira_regra(self):
        rows = [
            {"kind": "preference", "metadata": {"trigger": "homem de ferro", "action": "spotify_play",
                                                "payload": {"uri": URI}}},
            {"kind": "preference", "metadata": {"trigger": "outra coisa", "action": "outra_acao"}},
            {"kind": "learning", "metadata": {"trigger": "homem de ferro", "action": "spotify_play",
                                              "payload": {"uri": URI}}},
            {"kind": "preference", "metadata": "texto solto"},
        ]
        self.assertEqual(preferences.rules_from_memories(rows), [{"trigger": "homem de ferro", "payload": {"uri": URI}}])


class LearnedCatalogTest(unittest.TestCase):
    def tearDown(self):
        spotify_control.set_learned_tracks([])

    def test_preferencia_aprendida_vence_o_catalogo_fixo(self):
        outra = "spotify:track:ZZZZZZZZZZZZ"
        spotify_control.set_learned_tracks([{"trigger": "homem de ferro", "payload": {"uri": outra}}])
        self.assertEqual(spotify_control.command_args("toca a música do homem de ferro"), ["play-uri", outra])

    def test_sem_preferencia_o_catalogo_fixo_responde(self):
        spotify_control.set_learned_tracks([])
        self.assertEqual(
            spotify_control.command_args("toca a música do homem de ferro"),
            ["play-uri", spotify_control.BACK_IN_BLACK_URI],
        )

    def test_uri_invalida_nao_entra_no_catalogo(self):
        spotify_control.set_learned_tracks([{"trigger": "x", "payload": {"uri": "spotify:album:abc"}}])
        self.assertEqual(spotify_control.learned_tracks(), {})


if __name__ == "__main__":
    unittest.main()
