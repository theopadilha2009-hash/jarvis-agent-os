"""O engine de áudio não pode travar por causa do dispositivo de saída virtual.

Teste real: com o iMobie (driver virtual) como saída padrão, o
``AVAudioEngine.start()`` trava para sempre — e trava a main thread, então nem
o retry roda e o JARVIS fica surdo. O app precisa (a) apontar a saída do engine
para a placa de som do Mac e (b) chamar ``start()`` fora da main thread com
timeout, para poder se recuperar.

Este teste lê o Swift e falha se alguém remover qualquer uma das duas defesas.
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SWIFT = RAIZ / "11_SCRIPTS" / "jarvis_native_app.swift"


class SaidaVirtualTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codigo = SWIFT.read_text(encoding="utf-8")

    def test_importa_coreaudio(self):
        """Sem CoreAudio não há como descobrir nem trocar o dispositivo."""
        self.assertIn("import CoreAudio", self.codigo)

    def test_forca_saida_para_o_hardware(self):
        """Antes de instalar o tap, a saída precisa apontar para a placa real."""
        self.assertIn("fixarSaidaParaHardware()", self.codigo)
        self.assertIn("setDeviceID(placa)", self.codigo)

    def test_start_do_engine_tem_timeout(self):
        """start() travado na main thread congela o app inteiro."""
        self.assertIn("startEngineComGuarda()", self.codigo)
        trecho = self.codigo[self.codigo.find("private func startEngineComGuarda"):]
        self.assertIn("semaforo.wait(timeout:", trecho)
        self.assertIn("engine.stop()", trecho)

    def test_start_nao_roda_na_main_thread(self):
        """O start real precisa sair da main para o timeout ter efeito."""
        trecho = self.codigo[self.codigo.find("private func startEngineComGuarda"):]
        self.assertIn("DispatchQueue.global", trecho)

    def test_mic_chama_a_guarda_e_nao_o_start_direto(self):
        """startMic não pode voltar a chamar try engine.start() na main."""
        inicio = self.codigo.find("private func startMic(to analyzerFormat")
        fim = self.codigo.find("private func startEngineComGuarda")
        self.assertGreater(inicio, 0)
        self.assertGreater(fim, inicio)
        trecho = self.codigo[inicio:fim]
        self.assertNotIn("try engine.start()", trecho)

    def test_saida_padrao_e_lida_do_sistema(self):
        """O log precisa registrar qual era o padrão antes de trocar."""
        self.assertIn("saidaPadraoDoMac()", self.codigo)
        self.assertIn("kAudioHardwarePropertyDefaultOutputDevice", self.codigo)


if __name__ == "__main__":
    unittest.main()