#!/usr/bin/env python3
"""Frases do dia a dia: volume, agenda de hoje, disco, memória e lembretes."""

from pathlib import Path
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import index as gateway  # noqa: E402
import device_actions  # noqa: E402


class VolumeCurtoTest(unittest.TestCase):
    def test_formas_de_casa(self):
        casos = {
            "põe no mudo": 0,
            "coloca no mudo": 0,
            "muta": 0,
            "volume 30": 30,
            "volume para 45": 45,
            "volume no máximo": 100,
        }
        for frase, esperado in casos.items():
            with self.subTest(frase=frase):
                self.assertEqual(device_actions.volume_level(frase), esperado)
                self.assertEqual(gateway.command_intent(frase), "volume_set")

    def test_nao_sequestra_assunto_de_volume(self):
        # "volume" fora de pedido de aparelho não vira comando.
        self.assertIsNone(device_actions.volume_level("volume de vendas cresceu 30%"))
        self.assertNotEqual(gateway.command_intent("o volume de vendas cresceu 30%"), "volume_set")

    def test_volume_fora_da_faixa_nao_passa(self):
        self.assertIsNone(device_actions.volume_level("volume 300"))


class IntentsDoDiaTest(unittest.TestCase):
    def test_agenda_de_hoje(self):
        for frase in ("o que eu tenho pra hoje", "o que tenho amanhã", "o que eu tenho essa semana"):
            self.assertEqual(gateway.command_intent(frase), "agenda_view", frase)

    def test_disco_e_memoria(self):
        self.assertEqual(gateway.command_intent("quanto espaço livre"), "storage_scan")
        self.assertEqual(gateway.command_intent("quanto de memória o mac tem"), "system_memory")

    def test_pedido_de_musica_continua_musica(self):
        self.assertEqual(gateway.command_intent("toca back in black"), "spotify_control")


class LembreteTest(unittest.TestCase):
    def test_texto_antes_do_prazo(self):
        # A ordem natural em português: o pedido primeiro, o prazo depois.
        lembrete = gateway.parse_reminder_request("me lembra de ligar pro Arthur amanhã às 9h")
        self.assertIsNotNone(lembrete)
        self.assertEqual(lembrete["text"], "ligar pro Arthur")
        self.assertTrue(lembrete["due"].endswith("T09:00:00"))

    def test_hora_sem_minutos(self):
        lembrete = gateway.parse_reminder_request("me lembra de pagar o boleto hoje às 18h")
        self.assertIsNotNone(lembrete)
        self.assertEqual(lembrete["text"], "pagar o boleto")

    def test_texto_depois_do_prazo(self):
        lembrete = gateway.parse_reminder_request("me lembra em 20 minutos de tomar água")
        self.assertIsNotNone(lembrete)
        self.assertEqual(lembrete["text"], "tomar água")

    def test_amanha_nao_vira_hoje(self):
        # 20h de amanhã é amanhã, mesmo que 20h ainda não tenha passado hoje.
        lembrete = gateway.parse_reminder_request("me lembra amanhã às 20h de mandar o relatório")
        amanha = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86_400))
        self.assertTrue(lembrete["due"].startswith(amanha), lembrete["due"])

    def test_prazo_sem_pedido_e_recusado(self):
        self.assertIsNone(gateway.parse_reminder_request("me lembra daqui a 2 horas"))

    def test_sem_prazo_e_recusado(self):
        self.assertIsNone(gateway.parse_reminder_request("me lembra de ligar pro Arthur"))


if __name__ == "__main__":
    unittest.main()
