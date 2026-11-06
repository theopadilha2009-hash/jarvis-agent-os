"""A voz precisa ter pausa curta e volume acima da música.

Duas queixas medidas, não supostas:

1. "as pausas ficam um pouco demoradas e muito brancas" — cada frase trazia
   825ms de silêncio no fim. Três frases somavam ~2,5s de pausa muda.
2. "música fica mais alto que a voz" — a voz saía a -17,3 dBFS e ficava só
   2,7 dB acima de uma música em volume médio. Abaixo de 6 dB ela soa
   abafada.

O filtro de áudio é verificado pelo número, não pelo ouvido.
"""

import importlib.util
import re
import struct
import unittest
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TTS = RAIZ / "11_SCRIPTS" / "local_tts_server.py"


def carregar_tts():
    spec = importlib.util.spec_from_file_location("tts_local", TTS)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def wav_de_teste(amostras):
    """Monta um WAV PCM 16 bits mono com as amostras dadas."""
    corpo = struct.pack(f"<{len(amostras)}h", *amostras)
    cabecalho = (
        b"RIFF" + struct.pack("<I", 36 + len(corpo)) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 24000, 48000, 2, 16)
        + b"data" + struct.pack("<I", len(corpo))
    )
    return cabecalho + corpo


class SilencioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tts = carregar_tts()

    def test_corta_silencio_do_fim(self):
        """Silêncio longo no fim é o que soa como pausa branca."""
        fala = [8000 if i % 20 < 10 else -8000 for i in range(24000)]
        muda = [0] * 24000
        audio = self.tts.apara_silencio(wav_de_teste(fala + muda))
        w = wave.open(__import__("io").BytesIO(audio), "rb")
        n = w.getnframes()
        w.close()
        # ~1s de fala + 1s de silêncio = 2s. Cortado, tem que sobrar ~1s.
        self.assertLess(n, 24000 * 1.2, "o silêncio do fim não foi cortado")
        self.assertGreater(n, 24000 * 0.9, "cortou fala junto")

    def test_nao_corta_o_silencio_do_meio(self):
        """Pausa dentro da frase é ritmo: não se toca nela."""
        comeco = [8000] * 4000
        meio = [0] * 8000
        fim = [8000] * 4000
        audio = self.tts.apara_silencio(wav_de_teste(comeco + meio + fim))
        w = wave.open(__import__("io").BytesIO(audio), "rb")
        n = w.getnframes()
        w.close()
        self.assertGreater(n, 15000, "a pausa do meio foi cortada")

    def test_audio_todo_mudo_nao_quebra(self):
        audio = self.tts.apara_silencio(wav_de_teste([0] * 1000))
        self.assertTrue(audio)


class VolumeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codigo = TTS.read_text(encoding="utf-8")

    def test_loudness_em_menos_14(self):
        """-18 LUFS ficava abafado atrás da música."""
        casamento = re.search(r"loudnorm=I=(-?\d+)", self.codigo)
        self.assertIsNotNone(casamento, "o loudnorm sumiu do servidor de voz")
        self.assertLessEqual(int(casamento.group(1)), -14)

    def test_tem_compressor(self):
        """Sem compressor as sílabas fracas somem atrás da música."""
        self.assertIn("acompressor", self.codigo)

    def test_pico_nao_estoura(self):
        """TP acima de -1 dBFS corta no alto-falante."""
        casamento = re.search(r"TP=(-[\d.]+)", self.codigo)
        self.assertIsNotNone(casamento)
        self.assertLessEqual(float(casamento.group(1)), -1.0)


if __name__ == "__main__":
    unittest.main()