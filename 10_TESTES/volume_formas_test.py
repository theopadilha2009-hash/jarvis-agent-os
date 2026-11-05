#!/usr/bin/env python3
"""Todas as formas de pedir volume têm que dar o mesmo número.

O dono fala de vários jeitos: "bota no 60", "bota em 50%", "abaixa o volume",
"volume 30". Antes só algumas casavam e o resto ia para o modelo — que não
tem como mexer no som do Mac.
"""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import device_actions  # noqa: E402


class FormasDePedirTest(unittest.TestCase):
    def test_formas_com_numero(self):
        casos = {
            "bota no 60": 60,
            "botar no 30": 30,
            "bota no 3": 3,
            "bota no 5": 5,
            "bota em 50%": 50,
            "bota em 30%": 30,
            "coloca em 25": 25,
            "coloca no 40": 40,
            "põe no 15": 15,
            "poe no 8": 8,
            "deixa em 20": 20,
            "ajusta para 45": 45,
            "muda para 12": 12,
            "volume 70": 70,
            "volume no 33": 33,
            "volume em 90%": 90,
        }
        for frase, esperado in casos.items():
            self.assertEqual(device_actions._volume_level_from_short_form(frase), esperado, frase)

    def test_com_saudacao_na_frente(self):
        self.assertEqual(device_actions._volume_level_from_short_form("Jarvis, bota no 60"), 60)
        self.assertEqual(device_actions._volume_level_from_short_form("jarvis bota em 50%"), 50)

    def test_extremos(self):
        self.assertEqual(device_actions._volume_level_from_short_form("bota no 0"), 0)
        self.assertEqual(device_actions._volume_level_from_short_form("bota no 100"), 100)

    def test_fora_da_faixa_nao_vira_numero(self):
        """150% não é volume: melhor não mexer do que cravar 100 calado."""
        self.assertIsNone(device_actions._volume_level_from_short_form("bota no 150"))
        self.assertIsNone(device_actions._volume_level_from_short_form("bota no 999"))

    def test_mudo_e_maximo(self):
        self.assertEqual(device_actions._volume_level_from_short_form("põe no mudo"), 0)
        self.assertEqual(device_actions._volume_level_from_short_form("muta"), 0)
        self.assertEqual(device_actions._volume_level_from_short_form("volume no máximo"), 100)

    def test_direcao_sem_numero_nao_inventa_valor(self):
        """"aumenta o volume" depende do volume atual — quem resolve é o
        dispatcher local, não este parser."""
        for frase in ("aumenta o volume", "abaixa o volume", "diminui o volume", "sobe o som"):
            self.assertIsNone(device_actions._volume_level_from_short_form(frase), frase)

    def test_conversa_comum_nao_vira_volume(self):
        for frase in (
            "bota a música do homem de ferro",
            "coloca o vídeo na TV",
            "volume da voz dele tá baixo",
            "quanto é 60 vezes 3",
        ):
            self.assertIsNone(device_actions._volume_level_from_short_form(frase), frase)


if __name__ == "__main__":
    unittest.main(verbosity=2)