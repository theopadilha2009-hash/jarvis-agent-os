#!/usr/bin/env python3
"""O WAV que o Pocket devolve vem com tamanho de streaming.

Ele escreve 0xFFFFFFFF em "RIFF size" e em "data size" porque não sabe o
total até terminar. O `afplay` ignora e toca; navegador e player que
confiam no cabeçalho calculam 89 mil segundos e cortam ou recusam.
"""

from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
from local_tts_server import fix_wav_sizes  # noqa: E402


def wav(amostras: bytes, riff=0xFFFFFFFF, data=0xFFFFFFFF) -> bytes:
    """WAV mínimo: 44 bytes de cabeçalho + amostras."""
    cabecalho = bytearray(b"RIFF")
    cabecalho += struct.pack("<I", riff)
    cabecalho += b"WAVEfmt "
    cabecalho += struct.pack("<IHHIIHH", 16, 1, 1, 24000, 48000, 2, 16)
    cabecalho += b"data"
    cabecalho += struct.pack("<I", data)
    return bytes(cabecalho) + amostras


def tamanhos(dados: bytes):
    riff = struct.unpack("<I", dados[4:8])[0]
    i = dados.find(b"data")
    return riff, struct.unpack("<I", dados[i + 4 : i + 8])[0]


class FixWavSizesTest(unittest.TestCase):
    def test_corrige_os_dois_campos(self):
        amostras = b"\x00\x01" * 4800  # 0.2s a 24kHz
        original = wav(amostras)
        corrigido = fix_wav_sizes(original)
        riff, data = tamanhos(corrigido)
        self.assertEqual(riff, len(corrigido) - 8)
        self.assertEqual(data, len(amostras))

    def test_audio_nao_e_tocado(self):
        """Só oito bytes mudam: os dois tamanhos. O som é o mesmo."""
        amostras = b"\x10\x20" * 1000
        original = wav(amostras)
        corrigido = fix_wav_sizes(original)
        self.assertEqual(len(corrigido), len(original))
        self.assertEqual(corrigido[44:], original[44:], "amostras alteradas")
        diferentes = [i for i in range(44) if corrigido[i] != original[i]]
        self.assertEqual(len(diferentes), 8, f"mudou demais: {diferentes}")

    def test_wav_ja_correto_fica_igual(self):
        amostras = b"\x05\x06" * 500
        pronto = wav(amostras, riff=44 + len(amostras) - 8, data=len(amostras))
        self.assertEqual(fix_wav_sizes(pronto), pronto)

    def test_mp3_nao_e_mexido(self):
        mp3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 100
        self.assertEqual(fix_wav_sizes(mp3), mp3)

    def test_lixo_curto_nao_quebra(self):
        self.assertEqual(fix_wav_sizes(b"RIFF"), b"RIFF")
        self.assertEqual(fix_wav_sizes(b""), b"")

    def test_riff_sem_chunk_data_nao_quebra(self):
        quebrado = b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE" + b"\x00" * 60
        resultado = fix_wav_sizes(quebrado)
        self.assertEqual(resultado, quebrado)


if __name__ == "__main__":
    unittest.main(verbosity=2)