#!/usr/bin/env python3
"""O caminho da tela, elo por elo.

A revisão achou QUATRO elos soltos nessa cadeia e nenhum teste pegava:

  1. o handler jarvisDisplay não era registrado no WKWebView
  2. "abre o Google na TV" direto não preenchia open_display
  3. o CLI do telas.py não usava o fallback
  4. a tela nunca chegava no payload da fila do Mac

Testar as peças separadas deixou tudo verde com a feature morta. Estes testes
seguem o dado de ponta a ponta: pedido -> payload -> fila -> worker.
"""

from pathlib import Path
import json
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import index as gateway  # noqa: E402
import device_actions  # noqa: E402
import device_worker  # noqa: E402


class TelaPedidaTest(unittest.TestCase):
    def test_reconhece_as_tres_telas(self):
        casos = {
            "abre o google na tv": "tv",
            "abre o google na televisão": "tv",
            "coloca no projetor": "projetor",
            "abre no hdmi": "projetor",
            "abre na tela principal": "principal",
        }
        for frase, esperado in casos.items():
            self.assertEqual(gateway.tela_pedida(frase), esperado, frase)

    def test_pedido_sem_tela_nao_inventa(self):
        for frase in ("abre o google", "toca uma música", "que horas são"):
            self.assertEqual(gateway.tela_pedida(frase), "", frase)

    def test_tv_nao_e_confundida_com_projetor(self):
        self.assertEqual(gateway.tela_pedida("abre na tv"), "tv")
        self.assertEqual(gateway.tela_pedida("abre no projetor"), "projetor")


class PayloadDoNavegadorTest(unittest.TestCase):
    """Elo 2: o pedido direto tem que trazer a tela."""

    def _payload(self, frase):
        resultado = gateway.browser_open_payload(frase)
        if isinstance(resultado, tuple):
            return resultado[0]
        return resultado or {}

    def test_pedido_direto_traz_open_display(self):
        dados = self._payload("abre o google na tv")
        self.assertEqual(dados.get("open_display"), "tv")
        self.assertIn("na TV", dados.get("message", ""))

    def test_preposicao_certa_por_tela(self):
        self.assertIn("na TV", self._payload("abre o google na tv").get("message", ""))
        self.assertIn("no projetor", self._payload("abre o google no projetor").get("message", ""))

    def test_sem_tela_continua_como_antes(self):
        dados = self._payload("abre o google")
        self.assertEqual(dados.get("open_display"), "")
        self.assertNotIn(" na ", dados.get("message", ""))

    def test_spotify_nao_vira_aba_na_tv(self):
        """Spotify é app do Mac: pedir na TV não pode virar aba."""
        self.assertIsNone(gateway.browser_open_payload("toca spotify na tv"))


class PayloadDaFilaTest(unittest.TestCase):
    """Elo 4: a tela tem que chegar na fila que o worker consome."""

    def test_payload_json_carrega_a_tela(self):
        bruto = device_actions.payload_json("open_url", "https://x.com", tela="tv")
        self.assertEqual(json.loads(bruto).get("tela"), "tv")

    def test_worker_le_a_tela_de_volta(self):
        bruto = device_actions.payload_json("open_url", "https://x.com", tela="projetor")
        job = {"request_text": bruto}
        self.assertEqual(device_worker.job_open_display(job), "projetor")

    def test_worker_sem_tela_devolve_vazio(self):
        bruto = device_actions.payload_json("open_url", "https://x.com")
        job = {"request_text": bruto}
        self.assertEqual(device_worker.job_open_display(job), "")

    def test_url_continua_sendo_lida(self):
        bruto = device_actions.payload_json("open_url", "https://x.com/a", tela="tv")
        job = {"request_text": bruto}
        self.assertEqual(device_worker.job_open_url(job), "https://x.com/a")

    def test_gateway_e_worker_usam_o_mesmo_nome_de_campo(self):
        """Se um lado escrever 'display' e o outro ler 'tela', quebra calado."""
        fonte_gateway = (ROOT / "api" / "index.py").read_text(encoding="utf-8")
        self.assertIn('{"tela": tela}', fonte_gateway)
        fonte_worker = (ROOT / "11_SCRIPTS" / "device_worker.py").read_text(encoding="utf-8")
        self.assertIn('payload.get("tela")', fonte_worker)


class BridgeSwiftTest(unittest.TestCase):
    """Elo 1: handler tratado mas não registrado = canal morto.

    Foi o bug mais caro: o Swift tratava a mensagem, o JS testava o canal, e
    o add() nunca aconteceu. Todo o resto da cadeia ficava inalcançável.
    """

    SWIFT = (ROOT / "11_SCRIPTS" / "jarvis_native_app.swift").read_text(encoding="utf-8")
    FALA = (ROOT / "web" / "fala.js").read_text(encoding="utf-8")

    def test_handler_da_tela_esta_registrado(self):
        self.assertIn('add(self, name: "jarvisDisplay")', self.SWIFT)

    def test_todo_handler_usado_pelo_js_esta_registrado(self):
        """Contrato: cada messageHandlers.X do JS tem um add(X) no Swift."""
        usados = set(re.findall(r"messageHandlers\.(\w+)\.postMessage", self.FALA))
        self.assertTrue(usados, "nenhum handler encontrado no fala.js")
        registrados = set(re.findall(r'add\(self, name: "(\w+)"\)', self.SWIFT))
        faltando = usados - registrados - {"webkit"}
        self.assertFalse(faltando, f"handler usado no JS e não registrado no Swift: {faltando}")

    def test_js_envia_json_com_url_e_tela(self):
        """O pedido vai com a tela resolvida, não só a que veio no payload.

        Projeto do GitHub não pede tela na fala, mas abre na terceira tela do
        arranjo do dono — por isso o JS resolve o destino antes de mandar.
        """
        self.assertIn("JSON.stringify({ url: data.open_url, tela })", self.FALA)
        self.assertIn('const tela = data.open_display ||', self.FALA)

    def test_swift_roda_telas_py_sem_shell(self):
        """argv direto: nada de interpolar a URL numa linha de shell."""
        self.assertIn('proc.arguments = [script, "abrir", url, tela]', self.SWIFT)


class VersaoDoCacheTest(unittest.TestCase):
    """`/ui/*.js` vai com max-age de 1 ano e immutable.

    Sem subir o ?v=, o app nativo continua rodando o fala.js velho para
    sempre — foi assim que as correções de hoje quase não chegaram.
    """

    def test_fala_html_aponta_para_a_versao_do_meta(self):
        html = (ROOT / "web" / "fala.html").read_text(encoding="utf-8")
        meta = re.search(r'<meta name="jarvis-shell" content="([^"]+)"', html)
        self.assertIsNotNone(meta)
        versao = meta.group(1)
        self.assertIn(f"/ui/fala.js?v={versao}", html)

    def test_versao_nao_e_a_antiga(self):
        html = (ROOT / "web" / "fala.html").read_text(encoding="utf-8")
        self.assertNotIn("20261104-voz4", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)