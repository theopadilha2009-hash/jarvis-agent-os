#!/usr/bin/env python3
"""Telas: achar a TV pelo apelido e não confundir com o projetor."""

import json
import os
from pathlib import Path
import sys
import tempfile
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


class NumeroDaTelaTest(unittest.TestCase):
    """O dono fala "tela 1/2/3": TV, MacBook e a terceira, nessa ordem."""

    def _achar(self, apelido, config=None):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "telas.json"
            if config is not None:
                caminho.write_text(json.dumps(config), encoding="utf-8")
            with patch.dict(os.environ, {"JARVIS_TELAS_CONFIG": str(caminho)}), \
                    patch.object(telas, "listar", return_value=TELAS_REAIS):
                return telas.encontrar(apelido)

    def test_config_mapeia_numero_para_nome(self):
        config = {"1": "SAMSUNG", "2": "Built-in", "3": "HDMI"}
        self.assertEqual(self._achar("1", config)["nome"], "SAMSUNG")
        self.assertIn("Built-in", self._achar("tela 2", config)["nome"])
        self.assertEqual(self._achar("tela3", config)["nome"], "HDMI")

    def test_sem_config_vale_a_posicao_da_esquerda_para_a_direita(self):
        self.assertIn("Built-in", self._achar("1")["nome"])
        self.assertEqual(self._achar("2")["nome"], "SAMSUNG")
        self.assertEqual(self._achar("3")["nome"], "HDMI")

    def test_numero_fora_do_arranjo_nao_inventa_tela(self):
        self.assertIsNone(self._achar("4"))

    def test_tela_configurada_e_desconectada_nao_cai_na_posicao(self):
        self.assertIsNone(self._achar("3", {"3": "Projector X"}))

    def test_config_quebrada_cai_na_posicao(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "telas.json"
            caminho.write_text("{não é json", encoding="utf-8")
            with patch.dict(os.environ, {"JARVIS_TELAS_CONFIG": str(caminho)}), \
                    patch.object(telas, "listar", return_value=TELAS_REAIS):
                self.assertEqual(telas.encontrar("2")["nome"], "SAMSUNG")


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


class InjecaoAppleScriptTest(unittest.TestCase):
    """A URL entra num script AppleScript entre aspas.

    Sem escape, uma aspa fecha o literal e o resto vira COMANDO:
    `https://x/a" & (do shell script "...") & "` executa shell. Foi provado
    num osascript real antes de corrigir.
    """

    def test_aspa_vira_texto(self):
        escape = telas._applescript_literal('a"b')
        self.assertEqual(escape, 'a\\"b')

    def test_barra_antes_da_aspa(self):
        """Ordem importa: escapar aspas primeiro deixaria a barra sozinha."""
        self.assertEqual(telas._applescript_literal("a\\b"), "a\\\\b")

    def test_payload_de_injecao_fica_inofensivo(self):
        url = 'https://x.com/a" & (do shell script "touch /tmp/PWNED") & "'
        escape = telas._applescript_literal(url)
        # Nenhuma aspa crua sobra: todas viraram \"
        self.assertNotIn('"', escape.replace('\\"', ""))

    def test_quebra_de_linha_e_removida(self):
        self.assertEqual(telas._applescript_literal("a\nb"), "a b")
        self.assertEqual(telas._applescript_literal("a\r\nb"), "a  b")

    def test_url_normal_nao_muda(self):
        url = "https://www.google.com/search?q=cafe"
        self.assertEqual(telas._applescript_literal(url), url)


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


class ChromeIsoladoTest(unittest.TestCase):
    """A janela nasce na tela certa sem Acessibilidade (que a reinstalação zera)."""

    def test_posiciona_pela_linha_de_comando(self):
        samsung = TELAS_REAIS[2]
        chamadas = []

        def falso(argv, timeout=15):
            chamadas.append(argv)
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch.object(telas, "_rodar", side_effect=falso), \
                patch.object(telas.os, "makedirs"):
            ok, msg = telas._abrir_na_tela("https://github.com/x/y", samsung)
        self.assertTrue(ok, msg)
        self.assertEqual(len(chamadas), 1, "não pode cair no System Events")
        argv = chamadas[0]
        self.assertEqual(argv[0], "open")
        self.assertIn("--window-position=1440,0", argv)
        self.assertIn("--window-size=1920,1080", argv)
        self.assertIn("--app=https://github.com/x/y", argv)
        self.assertIn("--disable-features=Translate", argv)

    def test_so_abre_http(self):
        ok, _ = telas._abrir_chrome_isolado("file:///etc/passwd", TELAS_REAIS[2])
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)