"""Pedir "abre a agenda" precisa abrir a agenda.

O dono vai falar exatamente isso no vídeo. O padrão só aceitava
ver/mostra/lista/consulta, então "abre a agenda" não casava com nada, caía no
modelo e o painel não abria. Este teste cobre as formas que ele realmente usa
e garante que pedir o SiteHunter NÃO abra a agenda.
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GATEWAY = RAIZ / "api" / "index.py"

def padroes_da_agenda():
    """Todos os padrões reais do gateway — nunca uma cópia que pode divergir.

    Há mais de um: um para "o que eu tenho hoje" e outro para "abre a agenda".
    O pedido basta casar com qualquer um deles.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("jarvis_gateway", GATEWAY)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    achados = [p for p, intent in modulo.LOCAL_INTENTS if intent == "agenda_view"]
    if not achados:
        raise AssertionError("o gateway não tem mais o intent agenda_view")
    return achados


def casa_agenda(frase, padroes):
    return any(p.search(frase) for p in padroes)


class AgendaIntentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.padroes = padroes_da_agenda()

    def test_formas_de_pedir_a_agenda(self):
        """Todas as maneiras naturais de pedir, incluindo 'abre'."""
        for frase in [
            "abre a agenda",
            "abre minha agenda",
            "abre a agenda lá pra deixar certinho",
            "abrir agenda",
            "abre aí a agenda",
            "pode abrir minha agenda",
            "mostra minha agenda",
            "minha agenda",
            "ver minha agenda",
            "quais são meus compromissos",
            # "calendário" é o mesmo painel: só o Google sai da UI, e só
            # quando o dono pede isso explicitamente.
            "abre o calendário",
            "meu calendário",
        ]:
            with self.subTest(frase=frase):
                self.assertTrue(casa_agenda(frase, self.padroes), frase)

    def test_outros_pedidos_nao_abrem_a_agenda(self):
        """Abrir o SiteHunter é outra coisa: não pode cair na agenda."""
        for frase in [
            "abre o sitehunter",
            "mostra o site hunter",
            "abre o spotify",
            "qual a previsão do tempo",
        ]:
            with self.subTest(frase=frase):
                self.assertFalse(casa_agenda(frase, self.padroes), frase)

    def test_gateway_marca_client_action(self):
        """O app só abre o painel se o servidor mandar client_action."""
        texto = GATEWAY.read_text(encoding="utf-8")
        self.assertIn('"client_action": "agenda"', texto)

    def test_app_abre_o_painel_nessa_acao(self):
        js = (RAIZ / "web" / "fala.js").read_text(encoding="utf-8")
        self.assertIn('data.client_action === "agenda"', js)
        self.assertIn("abrirHud()", js)

    def test_agenda_e_calendario_nao_vao_pro_google(self):
        """A agenda mora na UI do JARVIS, não numa aba do Google.

        O dono pediu explicitamente: só vai pro Google quando ele disser
        "abre no Google". Antes, "calendário" abria o Google Calendar, e
        pedir a agenda virava uma aba em vez do painel.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location("jarvis_gateway", GATEWAY)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        for padrao, url, rotulo in modulo.WEB_OPEN_TARGETS:
            if "calendar.google.com" not in url:
                continue
            for frase in ["abre a agenda", "minha agenda", "abre o calendário",
                          "mostra o calendário", "ver a agenda"]:
                with self.subTest(frase=frase):
                    self.assertIsNone(padrao.search(frase),
                                      f"{frase!r} não pode abrir {rotulo}")


if __name__ == "__main__":
    unittest.main()