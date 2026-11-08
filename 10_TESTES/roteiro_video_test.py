#!/usr/bin/env python3
"""Roteiro do vídeo: cada frase do dono tem que cair na cena certa, offline.

Extrai os gatilhos de verdade do web/fala.js e roda no Node, com as frases
como o reconhecedor entrega (minúscula com acento, ou "dobrada" sem acento).
"""

from pathlib import Path
import json
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
FALA_JS = (ROOT / "web" / "fala.js").read_text(encoding="utf-8")

HARNESS = r"""
%(resposta)s
%(gatilhos)s
%(fold)s
function cena(texto, ofertaViva) {
  for (const g of GATILHOS_FILME) {
    if (!g.teste.test(texto)) continue;
    if (g.precisaFerro && !ofertaViva) continue;
    return g.cena;
  }
  return null;
}
const casos = %(casos)s;
const saida = casos.map(([frase, oferta]) => [
  frase, oferta, cena(frase.toLowerCase(), oferta), cena(foldSpeech(frase), oferta),
]);
console.log(JSON.stringify(saida));
"""


def _bloco(inicio, fim):
    achou = re.search(inicio + r".*?" + fim, FALA_JS, re.S)
    assert achou, inicio
    return achou.group(0)


def rodar(casos):
    gatilhos = _bloco(r"const GATILHOS_FILME = \[", r"\n  \];")
    resposta = _bloco(r"const RESPOSTA_ABRIR =", r";\n")
    fold = _bloco(r"function foldSpeech\(text\) \{", r"\n  \}")
    programa = HARNESS % {
        "gatilhos": gatilhos, "resposta": resposta, "fold": fold,
        "casos": json.dumps(casos, ensure_ascii=False),
    }
    proc = subprocess.run(["node", "-e", programa], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


GITHUB = (
    "Jarvis, abre seu projeto no GitHub pra mostrar que qualquer um pode baixar você "
    "e modelar você do jeito que quiser, além do modo web que é gratuito pra todo mundo"
)


@unittest.skipUnless(shutil.which("node"), "node não instalado")
class RoteiroDoVideoTest(unittest.TestCase):
    def _esperar(self, casos):
        for frase, oferta, cru, dobrado in rodar([[f, o] for f, o, _ in casos]):
            esperada = next(e for f, o, e in casos if f == frase and o == oferta)
            self.assertEqual(cru, esperada, f"{frase!r} (acento)")
            self.assertEqual(dobrado, esperada, f"{frase!r} (sem acento)")

    def test_passo_1_homem_de_ferro(self):
        self._esperar([
            ("Jarvis, entra no modo Homem de Ferro", False, "ferro"),
            ("entra no modo homem-de-ferro", False, "ferro"),
            ("modo iron man", False, "ferro"),
        ])

    def test_passo_3_fullscreen_ou_web(self):
        self._esperar([
            ("fullscreen", True, "fullscreen"),
            ("abre o modo fullscreen", True, "fullscreen"),
            ("modo web", True, "web"),
            ("pode abrir", True, "web"),
            ("modo web", False, None),
        ])

    def test_passo_4_pedido_do_github_nao_vira_resposta_de_web(self):
        """Ele diz "modo web" no meio do pedido do GitHub: tem que abrir o GitHub."""
        self._esperar([(GITHUB, True, "github"), (GITHUB, False, "github")])

    def test_passo_5_agenda(self):
        self._esperar([("Jarvis, abre uma agenda virtual pra mim ver", False, "agenda")])

    def test_passo_6_recusa(self):
        self._esperar([
            ("Não, agora não, obrigado", False, "recusa"),
            ("agora não", False, "recusa"),
        ])

    def test_passo_7_previa_do_sitehunter(self):
        self._esperar([
            ("Jarvis, dá uma prévia do próximo vídeo", False, "sitehunter"),
            ("mostra o sitehunter", False, "sitehunter"),
        ])

    def test_conversa_comum_nao_dispara_cena(self):
        self._esperar([("que horas são", False, None), ("sim", False, None)])


class RoteiroEncenadoTest(unittest.TestCase):
    """O roteiro não pode depender de rede nem de modelo."""

    def test_falas_exatas_do_pedido(self):
        self.assertIn('"Entrando no modo Homem de Ferro."', FALA_JS)
        self.assertIn("Bom dia, senhor. Hoje o tempo está nublado, 22 graus e perfeito para trabalhar.", FALA_JS)
        self.assertIn("Quer que eu abra o modo web ou o modo fullscreen?", FALA_JS)
        self.assertIn(
            "Você tem três reuniões marcadas, uma pra segunda, uma pra quarta e uma pra quinta-feira. Deseja confirmar?",
            FALA_JS,
        )

    def test_nove_segundos_de_musica_antes_do_bom_dia(self):
        self.assertIn("ESPERA_MUSICA_FERRO_MS = 9000", FALA_JS)

    def test_musica_local_e_nao_spotify(self):
        cena = _bloco(r"window.__jarvisHomemDeFerro = async", r"\n  \};")
        self.assertIn("jarvisMusic", cena)
        self.assertNotIn("spotify:", cena)
        self.assertNotIn("jarvisOpen", cena)

    def test_github_abre_na_tela_3_e_em_silencio(self):
        cena = _bloco(r"window.__jarvisAbrirGithub = async", r"\n  \};")
        self.assertIn('tela: "3"', cena)
        self.assertNotIn("speak(", cena)

    def test_fullscreen_nao_abre_o_chrome_da_tv(self):
        cena = _bloco(r"window.__jarvisFullscreen = async", r"\n  \};")
        self.assertIn("jarvisFullscreen", cena)
        self.assertNotIn("http", cena)


if __name__ == "__main__":
    unittest.main(verbosity=2)
