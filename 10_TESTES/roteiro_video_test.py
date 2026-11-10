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
            ("pode abrir no web", True, "web"),
            ("abre no modo web, Jarvis", True, "web"),
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

    def test_saidas_da_musica_e_do_fullscreen(self):
        self._esperar([
            ("para a música", False, "parar_musica"),
            ("Jarvis, fecha o mp3", False, "parar_musica"),
            ("desliga a música", False, "parar_musica"),
            ("cancela o roteiro", False, "parar_roteiro"),
            ("fecha o fullscreen", False, "sair_fullscreen"),
            ("sai da tela cheia", False, "sair_fullscreen"),
            ("tela cheia", False, "fullscreen"),
        ])

    def test_fala_do_proprio_jarvis_nao_para_nada(self):
        """O eco da fala dele não pode desligar a música nem a tela."""
        self._esperar([
            ("Bom dia, senhor. Hoje o tempo está nublado, 22 graus e perfeito para trabalhar.", False, None),
            ("Entrando no modo Homem de Ferro.", False, "ferro"),
        ])

    def test_conversa_comum_nao_dispara_cena(self):
        self._esperar([("que horas são", False, None), ("sim", False, None)])


@unittest.skipUnless(shutil.which("node"), "node não instalado")
class NomeDoJarvisTest(unittest.TestCase):
    """O reconhecedor erra o nome; o app não pode ficar surdo a ele."""

    def test_variantes_do_reconhecedor(self):
        alt = re.search(r'const WAKE_ALT = "(.*?)";', FALA_JS).group(1)
        programa = (
            f'const r = new RegExp("\\\\b(?:" + "{alt}" + ")\\\\b");'
            'console.log(JSON.stringify(process.argv.slice(1).map(t => r.test(t))));'
        )
        frases = ["jarvis", "ja vis", "jarbas", "gervais", "jarves", "jarvius", "ola", "ja vi", "ja visto"]
        proc = subprocess.run(["node", "-e", programa, *frases], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), [True] * 6 + [False] * 3)


@unittest.skipUnless(shutil.which("node"), "node não instalado")
class HoraDoBomDiaTest(unittest.TestCase):
    def _fala(self, hora, minuto):
        funcoes = _bloco(r"function horaFalada\(agora\) \{", r"\n  \}\n  function bomDiaFerro.*?\n  \}")
        programa = funcoes + f"\nconsole.log(bomDiaFerro(new Date(2026, 10, 10, {hora}, {minuto})));"
        proc = subprocess.run(["node", "-e", programa], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def test_manha_diz_a_hora_do_mac(self):
        fala = self._fala(10, 42)
        self.assertTrue(fala.startswith("Bom dia, senhor. Hoje o tempo está nublado, são 10 horas e 42 da manhã, 22 graus"), fala)
        self.assertTrue(fala.endswith("Quer que eu abra o modo web ou o modo fullscreen?"))

    def test_hora_cheia_e_outros_periodos(self):
        self.assertIn("são 3 horas da tarde,", self._fala(15, 0))
        self.assertIn("é 1 hora e 5 da madrugada,", self._fala(1, 5))
        self.assertTrue(self._fala(20, 30).startswith("Boa noite, senhor."))
        self.assertIn("são 12 horas da tarde,", self._fala(12, 0))


class RoteiroEncenadoTest(unittest.TestCase):
    def test_roteiro_automatico_segue_a_ordem_do_video(self):
        """Depois do Homem de Ferro o resto roda sozinho, sem o app ouvir."""
        bloco = _bloco(r"const ROTEIRO_AUTO = \[", r"\n  \];")
        self.assertEqual(
            re.findall(r'\[\d+, "(\w+)"\]', bloco),
            ["web", "github", "agenda", "recusa", "sitehunter"],
        )
        cena = _bloco(r"window.__jarvisHomemDeFerro = async", r"\n  \};")
        self.assertIn("seguirRoteiroAuto()", cena)

    def test_cena_repetida_e_ignorada(self):
        self.assertIn("REPETIR_CENA_MS", FALA_JS)
        self.assertIn("estado.rodando", FALA_JS)

    """O roteiro não pode depender de rede nem de modelo."""

    def test_falas_exatas_do_pedido(self):
        self.assertIn('"Entrando no modo Homem de Ferro."', FALA_JS)
        self.assertIn("Hoje o tempo está nublado, ${horaFalada(agora)}, 22 graus e perfeito para trabalhar.", FALA_JS)
        self.assertIn("Quer que eu abra o modo web ou o modo fullscreen?", FALA_JS)
        self.assertIn(
            "Você tem três reuniões marcadas para essa semana, senhor. Uma para amanhã, uma para sexta-feira "
            "e uma para domingo. Deseja confirmar ou saber qual é qual?",
            FALA_JS,
        )

    def test_nove_segundos_de_musica_antes_do_bom_dia(self):
        self.assertIn("ESPERA_MUSICA_FERRO_MS = 9000", FALA_JS)

    def test_musica_local_e_nao_spotify(self):
        cena = _bloco(r"window.__jarvisHomemDeFerro = async", r"\n  \};")
        self.assertIn("jarvisMusic", cena)
        self.assertNotIn("spotify:", cena)
        self.assertNotIn("jarvisOpen", cena)

    def test_github_abre_na_tela_central_e_avisa(self):
        cena = _bloco(r"window.__jarvisAbrirGithub = async", r"\n  \};")
        self.assertIn('tela: "1"', cena)
        self.assertIn("Abrindo meu projeto na tela central", cena)

    def test_web_toca_o_clipe_na_tela_do_mac_sem_abrir_o_site(self):
        cena = _bloco(r"window.__jarvisAbrirWeb = async", r"\n  \};")
        self.assertIn("jarvis:modo-web", cena)
        self.assertNotIn("jarvisOpen", cena)
        self.assertNotIn("rodadaAuto", cena)
        self.assertTrue((ROOT / "web" / "filme" / "modo-web.mp4").is_file())

    def test_previa_do_proximo_video_vai_para_a_tela_3(self):
        cena = _bloco(r"window.__jarvisSiteHunter = async", r"\n  \};")
        self.assertIn('tela: "3"', cena)
        self.assertIn("PREVIA_PROXIMO_VIDEO", cena)
        self.assertIn("fecharSite()", cena)
        self.assertIn("/ui/filme/sitehunter.png", FALA_JS)

    def test_agenda_do_filme_fica_roxa_por_cima_do_clipe(self):
        css = (ROOT / "web" / "fala.css").read_text(encoding="utf-8")
        regra = re.search(r"html\.modo-ferro \.hud \{(.*?)\}", css, re.S)
        self.assertIsNotNone(regra)
        self.assertIn("--glow: 168, 85, 247", regra.group(1))
        self.assertIn("z-index: 80", regra.group(1))

    def test_fullscreen_nao_abre_o_chrome_da_tv(self):
        cena = _bloco(r"window.__jarvisFullscreen = async", r"\n  \};")
        self.assertIn("jarvisFullscreen", cena)
        self.assertNotIn("http", cena)


if __name__ == "__main__":
    unittest.main(verbosity=2)
