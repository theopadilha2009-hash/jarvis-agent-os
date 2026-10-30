#!/usr/bin/env python3
"""Sets pessoais: gatilho, passos e casamento do pedido."""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import sets  # noqa: E402
import spotify_control  # noqa: E402


class GatilhoTest(unittest.TestCase):
    def test_guardar_a_frase_inteira(self):
        # Só "foco" dispararia em qualquer frase que mencionasse a palavra.
        self.assertEqual(sets.parse_trigger("estilo foco"), "estilo foco")
        self.assertEqual(sets.parse_trigger("modo trabalho"), "modo trabalho")

    def test_frase_curta_sem_prefixo_vale(self):
        self.assertEqual(sets.parse_trigger("foco"), "foco")

    def test_frase_longa_nao_e_gatilho(self):
        self.assertEqual(sets.parse_trigger("toca back in black agora por favor"), "")
        self.assertEqual(sets.parse_trigger("quero criar um set novo"), "")


class PassosTest(unittest.TestCase):
    def test_lista_completa(self):
        passos = sets.parse_steps("toca Back in Black, abre o Safari e fala a agenda")
        self.assertEqual([p["kind"] for p in passos], ["spotify", "app", "agenda"])
        self.assertEqual(passos[0]["uri"], spotify_control.BACK_IN_BLACK_URI)
        self.assertEqual(passos[1]["target"], "Safari")

    def test_pasta_e_volume(self):
        passos = sets.parse_steps("abre a pasta downloads e volume 30")
        self.assertEqual(passos[0], {"kind": "folder", "target": "downloads"})
        self.assertEqual(passos[1], {"kind": "volume", "level": 30})

    def test_tema_do_app(self):
        self.assertEqual(sets.parse_steps("muda pro claro"), [{"kind": "theme", "value": "light"}])
        self.assertEqual(sets.parse_steps("tema escuro"), [{"kind": "theme", "value": "dark"}])
        # "claro" solto não vira passo de tema.
        self.assertEqual(sets.parse_steps("abre o Slack"), [{"kind": "app", "target": "Slack"}])

    def test_descricao_do_tema(self):
        self.assertIn("claro", sets.describe_steps([{"kind": "theme", "value": "light"}]))

    def test_mudo(self):
        self.assertEqual(sets.parse_steps("põe no mudo")[0], {"kind": "volume", "level": 0})

    def test_texto_sem_passo_nao_inventa(self):
        self.assertEqual(sets.parse_steps("sei lá, qualquer coisa"), [])

    def test_descricao_falada(self):
        passos = sets.parse_steps("toca Back in Black, abre o Safari e fala a agenda")
        descricao = sets.describe_steps(passos)
        self.assertIn("tocar", descricao)
        self.assertIn("abrir o Safari", descricao)
        self.assertIn("agenda", descricao)
        self.assertTrue(descricao.count(" e ") >= 1)


class CasamentoTest(unittest.TestCase):
    SETS = [
        {"trigger": "estilo foco", "steps": [{"kind": "agenda"}]},
        {"trigger": "foco", "steps": [{"kind": "volume", "level": 0}]},
    ]

    def test_gatilho_mais_longo_vence(self):
        achado = sets.match("jarvis, estilo foco", self.SETS)
        self.assertEqual(achado["trigger"], "estilo foco")

    def test_sem_gatilho_nao_casa(self):
        self.assertIsNone(sets.match("toca back in black", self.SETS))

    def test_acento_e_caixa_nao_importam(self):
        achado = sets.match("JARVIS, ESTILO FÔCO", self.SETS)
        self.assertIsNotNone(achado)


class MemoriaTest(unittest.TestCase):
    def test_le_set_e_ignora_o_resto(self):
        rows = [
            {"id": 1, "kind": "preference", "metadata": {"action": "set", "trigger": "estilo foco",
                                                         "steps": [{"kind": "agenda"}]}},
            {"id": 2, "kind": "preference", "metadata": {"action": "set_draft", "stage": "trigger"}},
            {"id": 3, "kind": "preference", "metadata": {"action": "spotify_play", "trigger": "x",
                                                         "payload": {"uri": spotify_control.BACK_IN_BLACK_URI}}},
            {"id": 4, "kind": "learning", "metadata": {"action": "set", "trigger": "y", "steps": [{}]}},
        ]
        encontrados = sets.sets_from_memories(rows)
        self.assertEqual([s["trigger"] for s in encontrados], ["estilo foco"])
        self.assertEqual(sets.draft_from_memories(rows)["id"], 2)

    def test_set_sem_passo_nao_vale(self):
        rows = [{"id": 1, "kind": "preference", "metadata": {"action": "set", "trigger": "x", "steps": []}}]
        self.assertEqual(sets.sets_from_memories(rows), [])


class PadroesDoFluxoTest(unittest.TestCase):
    def test_pedido_de_criar(self):
        for frase in ("quero criar um set novo", "cria um modo pra mim", "novo set"):
            self.assertIsNotNone(sets.CREATE_PATTERN.search(frase), frase)

    def test_pedido_normal_nao_cria(self):
        for frase in ("toca back in black", "estilo foco"):
            self.assertIsNone(sets.CREATE_PATTERN.search(frase), frase)

    def test_cancelar(self):
        self.assertIsNotNone(sets.CANCEL_PATTERN.match("cancela"))
        self.assertIsNotNone(sets.CANCEL_PATTERN.match("deixa pra depois"))
        self.assertIsNone(sets.CANCEL_PATTERN.match("estilo foco"))


if __name__ == "__main__":
    unittest.main()
