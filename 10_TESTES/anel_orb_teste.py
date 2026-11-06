"""O anel de fala em volta do orbe precisa existir nos dois modos.

O dono pediu o orbe no meio com a fala em volta, "até mesmo no minimizado e no
normal". O HTML e o JS do anel já existiam, mas o CSS não — então o anel nunca
apareceu em lugar nenhum. Este teste falha se o estilo sumir de novo.
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FALA_CSS = RAIZ / "web" / "fala.css"
FALA_HTML = RAIZ / "web" / "fala.html"
FALA_JS = RAIZ / "web" / "fala.js"


class AnelOrbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = FALA_CSS.read_text(encoding="utf-8")
        cls.html = FALA_HTML.read_text(encoding="utf-8")
        cls.js = FALA_JS.read_text(encoding="utf-8")

    def test_html_tem_o_palco_e_o_anel(self):
        self.assertIn('id="orbStage"', self.html)
        self.assertIn('id="orbRing"', self.html)
        self.assertIn("textPath", self.html)

    def test_css_estiliza_o_anel(self):
        """Sem estas regras o anel fica invisível, como estava."""
        self.assertIn(".orb-ring", self.css)
        self.assertIn(".orb-ring-text", self.css)
        self.assertIn(".orb-stage", self.css)

    def test_anel_aparece_quando_ha_fala(self):
        self.assertIn(".orb-stage.has-ring .orb-ring", self.css)
        self.assertIn("opacity: 1", self.css)

    def test_anel_existe_no_modo_minimizado(self):
        """O modo minimizado é html.idle-orb; o anel precisa acompanhar."""
        self.assertRegex(
            self.css,
            r"html\.idle-orb[^{]*\.orb-stage",
            "o anel não tem regra para o modo minimizado",
        )

    def test_anel_existe_no_modo_normal(self):
        """No modo normal o palco tem tamanho próprio."""
        self.assertRegex(self.css, r"\.orb-stage\s*\{[^}]*width")

    def test_js_pinta_o_anel(self):
        self.assertIn("function paintRing", self.js)
        self.assertIn("has-ring", self.js)
        self.assertIn("is-speaking", self.js)

    def test_js_limpa_o_anel_quando_cala(self):
        """Anel vazio não pode ficar girando na tela."""
        self.assertIn('paintRing("", false)', self.js)

    def test_respeita_movimento_reduzido(self):
        self.assertIn("prefers-reduced-motion", self.css)


if __name__ == "__main__":
    unittest.main()