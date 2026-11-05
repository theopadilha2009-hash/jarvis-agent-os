#!/usr/bin/env python3
"""Modo leve: o JARVIS tem que abrir inteiro num Chromebook de escola."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LEVE_JS = ROOT / "web" / "leve.js"
SW_JS = ROOT / "web" / "jarvis-sw.js"
INDEX_HTML = ROOT / "web" / "index.html"


class LeveModuleTest(unittest.TestCase):
    def test_modulo_existe(self):
        self.assertTrue(LEVE_JS.is_file(), "web/leve.js não existe")

    def test_detecta_aparelho_fraco_por_varios_sinais(self):
        """Nenhum sinal sozinho é confiável: Chromebook mente sobre RAM."""
        codigo = LEVE_JS.read_text(encoding="utf-8")
        for sinal in (
            "hardwareConcurrency",
            "deviceMemory",
            "saveData",
            "effectiveType",
            "prefers-reduced-motion",
            "?leve=1",
        ):
            self.assertIn(sinal, codigo, sinal)

    def test_webgl_por_software_conta_como_fraco(self):
        """SwiftShader roda WebGL no papel e congela a aba."""
        codigo = LEVE_JS.read_text(encoding="utf-8").lower()
        self.assertIn("swiftshader", codigo)

    def test_forca_ligar_e_desligar(self):
        codigo = LEVE_JS.read_text(encoding="utf-8")
        self.assertIn("?leve=1", codigo)
        self.assertIn("?leve=0", codigo)

    def test_escolha_fica_gravada(self):
        codigo = LEVE_JS.read_text(encoding="utf-8")
        self.assertIn("localStorage", codigo)

    def test_falha_de_storage_nao_quebra(self):
        """Chromebook de escola bloqueia localStorage em aba anônima."""
        codigo = LEVE_JS.read_text(encoding="utf-8")
        self.assertRegex(codigo, r"try\s*\{[\s\S]*?localStorage")


class ServiceWorkerLeveTest(unittest.TestCase):
    def test_three_js_saiu_do_precache(self):
        """652K de three.js no install travava o primeiro uso no Chromebook."""
        texto = SW_JS.read_text(encoding="utf-8")
        shell = texto[texto.index("const SHELL"):texto.index("];", texto.index("const SHELL"))]
        # Só as entradas contam: o comentário que explica a remoção cita o nome.
        entradas = re.findall(r'"(/ui/[^"]+)"', shell)
        self.assertFalse(
            [e for e in entradas if "three.module.js" in e],
            "three.module.js voltou ao precache",
        )

    def test_precache_ficou_abaixo_de_1mb(self):
        texto = SW_JS.read_text(encoding="utf-8")
        inicio = texto.index("const SHELL")
        shell = texto[inicio:texto.index("];", inicio)]
        total = 0
        for caminho in re.findall(r'"(/ui/[^"?]+)', shell):
            arquivo = ROOT / "web" / caminho.replace("/ui/", "")
            if arquivo.is_file():
                total += arquivo.stat().st_size
        self.assertLess(total, 1024 * 1024, f"precache em {total/1024:.0f}K")


class EntradaLeveTest(unittest.TestCase):
    def test_index_carrega_o_leve_antes_de_tudo(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("leve.js", html)
        pos_leve = html.index("leve.js")
        for pesado in ("presence-loader.js", "jarvis.js"):
            if pesado in html:
                self.assertLess(pos_leve, html.index(pesado), pesado)


if __name__ == "__main__":
    unittest.main(verbosity=2)