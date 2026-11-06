"""O aviso de "atualização disponível" tem que sumir depois de atualizar.

O dono relatou que o botão Atualizar não sumia. A causa não era o botão: a
versão estava escrita à mão no ``fala.js`` e ficou para trás do ``fala.html``
que o gateway lê em ``/status``. O cliente sempre se achava velho e o aviso
voltava para sempre.

Este teste garante que o JS lê a versão do próprio documento, em vez de
guardar uma cópia que pode dessincronizar.
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FALA_JS = RAIZ / "web" / "fala.js"
FALA_HTML = RAIZ / "web" / "fala.html"


class AvisoAtualizarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = FALA_JS.read_text(encoding="utf-8")
        cls.html = FALA_HTML.read_text(encoding="utf-8")

    def test_js_le_a_versao_do_meta(self):
        """A fonte da verdade é o <meta jarvis-shell> do HTML."""
        self.assertIn('meta[name="jarvis-shell"]', self.js)

    def test_versao_nao_e_uma_string_fixa(self):
        """Uma constante literal foi exatamente o que dessincronizou."""
        casamento = re.search(r"const SHELL_VERSION = (.+?);", self.js, re.S)
        self.assertIsNotNone(casamento, "SHELL_VERSION sumiu do fala.js")
        corpo = casamento.group(1)
        # Pode ter um literal como fallback, mas não pode SER só o literal.
        self.assertTrue(
            "querySelector" in corpo or "function" in corpo,
            "SHELL_VERSION voltou a ser uma string fixa — o aviso não some",
        )

    def test_html_tem_o_meta(self):
        """Sem o meta, o JS não tem de onde ler a versão."""
        self.assertRegex(self.html, r'<meta name="jarvis-shell" content="[^"]+"')

    def test_meta_e_o_que_o_gateway_le(self):
        """O gateway extrai a versão com esta regex exata."""
        self.assertIn("jarvis-sw", (RAIZ / "api" / "index.py").read_text(encoding="utf-8"))
        gateway = (RAIZ / "api" / "index.py").read_text(encoding="utf-8")
        self.assertIn(r'jarvis-shell"\s+content="([^"]+)"', gateway)

    def test_aviso_some_quando_versao_bate(self):
        """A condição de 'desatualizado' é comparação direta; igual = some."""
        self.assertIn("live !== SHELL_VERSION", self.js)
        self.assertIn("toast.hidden = !stale", self.js)


if __name__ == "__main__":
    unittest.main()