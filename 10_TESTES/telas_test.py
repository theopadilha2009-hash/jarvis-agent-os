#!/usr/bin/env python3
"""Telas: achar a TV pelo apelido e não confundir com o projetor."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import telas  # noqa: E402


# O arranjo real desta máquina, em pontos (topo-esquerda, como o System
# Events usa). A integrada é Retina: 2560x1600 físicos = 1440x900 pontos.
TELAS_REAIS = [
    {"indice": 0, "nome": "Built-in Retina Display", "x": 0, "y": 0, "largura": 1440, "altura": 900},
    {"indice": 1, "nome": "HDMI", "x": 3360, "y": 96, "largura": 1280, "altura": 720},
    {"indice": 2, "nome": "SAMSUNG", "x": 1440, "y": 0, "largura": 1920, "altura": 1080},
]


class ApelidosTest(unittest.TestCase):
    def _com_telas(self, apelido):
        with patch.object(telas, "listar", return_value=TELAS_REAIS):
            return telas.encontrar(apelido)

    def test_tv_e_samsung(self):
        for apelido in ("tv", "TV", "samsung", "SAMSUNG", "televisao", "televisão"):
            tela = self._com_telas(apelido)
            self.assertIsNotNone(tela, apelido)
            self.assertEqual(tela["nome"], "SAMSUNG", apelido)

    def test_projetor_e_hdmi(self):
        for apelido in ("projetor", "hdmi", "HDMI", "vx", "vx pro"):
            tela = self._com_telas(apelido)
            self.assertIsNotNone(tela, apelido)
            self.assertEqual(tela["nome"], "HDMI", apelido)

    def test_principal_e_a_integrada(self):
        for apelido in ("principal", "macbook", "notebook", "retina", "integrada"):
            tela = self._com_telas(apelido)
            self.assertIsNotNone(tela, apelido)
            self.assertIn("Built-in", tela["nome"], apelido)

    def test_tv_nao_e_confundida_com_projetor(self):
        """O erro caro: mandar o Google para o projetor achando que é a TV."""
        self.assertEqual(self._com_telas("tv")["nome"], "SAMSUNG")
        self.assertEqual(self._com_telas("projetor")["nome"], "HDMI")

    def test_apelido_desconhecido_nao_inventa_tela(self):
        self.assertIsNone(self._com_telas("xyz"))
        self.assertIsNone(self._com_telas(""))

    def test_sem_telas_nao_quebra(self):
        with patch.object(telas, "listar", return_value=[]):
            self.assertIsNone(telas.encontrar("tv"))


class CoordenadasTest(unittest.TestCase):
    def test_coordenadas_sao_topo_esquerda(self):
        """NSScreen dá y negativo para a TV; CGDisplayBounds dá 0. Usar o
        primeiro mandava a janela para fora da tela."""
        for tela in TELAS_REAIS:
            self.assertGreaterEqual(tela["y"], 0, tela["nome"])

    def test_tv_comeca_onde_a_integrada_termina(self):
        integrada = next(t for t in TELAS_REAIS if "Built-in" in t["nome"])
        tv = next(t for t in TELAS_REAIS if t["nome"] == "SAMSUNG")
        self.assertEqual(tv["x"], integrada["x"] + integrada["largura"])


class AbrirNaTelaTest(unittest.TestCase):
    def test_tela_inexistente_devolve_erro_claro(self):
        with patch.object(telas, "listar", return_value=TELAS_REAIS):
            ok, mensagem = telas.abrir_na_tela("https://www.google.com", "xyz")
        self.assertFalse(ok)
        self.assertIn("Não achei", mensagem)
        # A mensagem lista o que existe, para o dono corrigir o pedido.
        self.assertIn("SAMSUNG", mensagem)

    def test_sem_tela_pedida_nao_move_nada(self):
        """Sem apelido, o comportamento antigo (navegador normal) continua."""
        with patch.object(telas, "listar", return_value=TELAS_REAIS):
            ok, _ = telas.abrir_na_tela("https://www.google.com", "")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)