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


class ParseGeneralTeachingTest(unittest.TestCase):
    def test_ensino_que_nao_e_faixa(self):
        note = preferences.parse_general_teaching(
            "quando eu te pedir o relatório da semana, manda no whatsapp em texto"
        )
        self.assertEqual(note["trigger"], "relatorio da semana")
        self.assertEqual(note["action"], "note")
        self.assertEqual(note["instruction"], "manda no whatsapp em texto")

    def test_jeito_de_falar_tambem_entra(self):
        note = preferences.parse_general_teaching(
            "quando eu pedir resumo do dia, responde curto e sem emoji"
        )
        self.assertEqual(note["trigger"], "resumo do dia")
        self.assertEqual(note["instruction"], "responde curto e sem emoji")

    def test_sem_virgula_nao_da_pra_separar(self):
        self.assertIsNone(
            preferences.parse_general_teaching("quando eu pedir o relatório da semana manda no zap")
        )

    def test_pedido_normal_nao_vira_preferencia(self):
        for text in ("toca back in black", "abre o spotify", "anota que amanhã tenho reunião"):
            self.assertIsNone(preferences.parse_general_teaching(text), text)


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


class RunRulesTest(unittest.TestCase):
    def test_so_regra_executavel_entra(self):
        rows = [
            {"kind": "preference", "metadata": {"trigger": "navegador do trabalho",
                                                "action": "run", "command": "abre o Safari"}},
            {"kind": "preference", "metadata": {"trigger": "resumo", "action": "note",
                                                "instruction": "responde curto"}},
        ]
        self.assertEqual(
            preferences.run_rules_from_memories(rows),
            [{"trigger": "navegador do trabalho", "command": "abre o Safari"}],
        )

    def test_pedido_casa_com_o_gatilho_ensinado(self):
        rules = [{"trigger": "navegador do trabalho", "command": "abre o Safari"}]
        self.assertEqual(
            preferences.learned_command("abre o navegador do trabalho", rules),
            ("abre o Safari", "navegador do trabalho"),
        )

    def test_sem_gatilho_nao_reescreve(self):
        rules = [{"trigger": "navegador do trabalho", "command": "abre o Safari"}]
        self.assertEqual(preferences.learned_command("abre o Slack", rules), ("", ""))

    def test_gatilho_mais_longo_vence_na_reescrita(self):
        rules = [
            {"trigger": "trabalho", "command": "abre o Slack"},
            {"trigger": "navegador do trabalho", "command": "abre o Safari"},
        ]
        self.assertEqual(
            preferences.learned_command("abre o navegador do trabalho", rules)[0],
            "abre o Safari",
        )


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
