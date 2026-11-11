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
            ("Bom dia, senhor. São 10 horas e 32 da manhã, 26 graus e ensolarado, dia incrível para trabalhar. Abrindo o modo web e os seus compromissos.", False, None),
            ("Abrindo o projeto, senhor. Código aberto para todo mundo.", False, None),
            ("Entrando no modo Homem de Ferro.", False, "ferro"),
            ("dá uma breve do próximo vídeo aí pra todo mundo também", False, "sitehunter"),
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


class BomDiaTest(unittest.TestCase):
    def test_hora_e_clima_fixos_do_video(self):
        """O vídeo se passa às 10:32, seja qual for a hora da gravação."""
        self.assertIn(
            '"Bom dia, senhor. São 10 horas e 32 da manhã, 26 graus e ensolarado, dia incrível para trabalhar. '
            'Abrindo o modo web e os seus compromissos."',
            FALA_JS,
        )
        self.assertNotIn("horaFalada", FALA_JS)


class RoteiroEncenadoTest(unittest.TestCase):
    def test_roteiro_automatico_segue_a_ordem_do_video(self):
        """Depois do Homem de Ferro o resto roda sozinho, sem o app ouvir."""
        bloco = _bloco(r"const ROTEIRO_AUTO = \[", r"\n  \];")
        self.assertEqual(
            re.findall(r'\[\d+, "(\w+)"\]', bloco),
            ["web", "agenda", "github", "sitehunter"],
        )
        cena = _bloco(r"window.__jarvisHomemDeFerro = async", r"\n  \};")
        self.assertIn("seguirRoteiroAuto()", cena)

    def test_ferro_nao_recomeca_no_meio_do_roteiro(self):
        """A voz do JARVIS volta pelo microfone e casava de novo com "Homem de Ferro"."""
        despachante = _bloco(r"function iniciarCena\(chave\) \{", r"\n  \}\n\n  window.__jarvisRoteiro")
        self.assertIn('chave === "ferro" && autoRodando', despachante)
        self.assertLess(despachante.index("autoRodando"), despachante.index("cenasRodando[chave]"))
        self.assertIn("autoRodando = false", _bloco(r"parar_roteiro: \(\) =>", r"\},"))

    def test_cena_repetida_e_ignorada(self):
        self.assertIn("REPETIR_CENA_MS", FALA_JS)
        self.assertIn("estado.rodando", FALA_JS)

    """O roteiro não pode depender de rede nem de modelo."""

    def test_falas_exatas_do_pedido(self):
        self.assertNotIn("Quer que eu abra o modo web", FALA_JS)
        self.assertIn(
            "Você tem três reuniões marcadas para essa semana, senhor. Uma para amanhã, uma para sexta-feira "
            "e uma para domingo. Deseja confirmar ou saber qual é qual?",
            FALA_JS,
        )

    def test_bom_dia_no_segundo_4_da_musica(self):
        self.assertIn("ESPERA_MUSICA_FERRO_MS = 4000", FALA_JS)
        cena = _bloco(r"window.__jarvisHomemDeFerro = async", r"\n  \};")
        self.assertLess(cena.index('jarvisMusic?.postMessage("play")'), cena.index("ESPERA_MUSICA_FERRO_MS"))

    def test_video_cabe_em_um_minuto(self):
        bloco = _bloco(r"const ROTEIRO_AUTO = \[", r"\n  \];")
        esperas = sum(int(n) for n in re.findall(r'\[(\d+), "\w+"\]', bloco))
        self.assertLessEqual(esperas, 20000)

    def test_musica_abaixa_quando_ele_fala(self):
        swift = (ROOT / "11_SCRIPTS" / "jarvis_native_app.swift").read_text(encoding="utf-8")
        fala = swift[swift.index("private func speakNative"):]
        self.assertIn("abaixarMusica()", fala[:1500])

    def test_musica_local_e_nao_spotify(self):
        cena = _bloco(r"window.__jarvisHomemDeFerro = async", r"\n  \};")
        self.assertNotIn("spotify:", cena)
        self.assertNotIn("jarvisOpen", cena)

    def test_github_abre_nas_telas_2_e_3(self):
        cena = _bloco(r"window.__jarvisAbrirGithub = async", r"\n  \};")
        self.assertIn('["2", "3"]', cena)
        self.assertIn("fecharHud()", cena)
        self.assertIn("fecharSite()", cena)

    def test_web_toca_o_clipe_na_tela_do_mac_sem_abrir_o_site(self):
        cena = _bloco(r"window.__jarvisAbrirWeb = async", r"\n  \};")
        self.assertIn("jarvis:modo-web", cena)
        self.assertNotIn("jarvisOpen", cena)
        self.assertNotIn("rodadaAuto", cena)
        self.assertTrue((ROOT / "web" / "filme" / "modo-web.mp4").is_file())

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe não instalado")
    def test_clipe_web_sem_os_2s_finais(self):
        """Nos 2 s finais o dono aparece mexendo e entrega que é um vídeo."""
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(ROOT / "web" / "filme" / "modo-web.mp4")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertLess(float(proc.stdout), 15.5)

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
