#!/usr/bin/env python3
"""Persona: o modo conciso precisa caber o fato E o comentário seco."""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
import index as gateway  # noqa: E402


class PersonaVoiceContractTest(unittest.TestCase):
    def test_dono_recebe_o_contrato_completo(self):
        contrato = gateway.persona_voice_contract(True).lower()
        for marca in ("mordomo", "humor", "senhor", "nunca faz"):
            self.assertIn(marca, contrato)

    def test_visitante_nao_herda_a_intimidade_do_dono(self):
        dono = gateway.persona_voice_contract(True)
        visita = gateway.persona_voice_contract(False)
        self.assertNotEqual(dono, visita)
        self.assertIn("visita", visita.lower())
        self.assertNotIn("visita", dono.lower())

    def test_contrato_nao_e_uma_lista_de_proibicoes(self):
        """O prompt precisa de presença, não só de 'não faça'."""
        contrato = gateway.persona_voice_contract(True).lower()
        self.assertGreater(contrato.count("\n- "), 10)


class ConciseBudgetTest(unittest.TestCase):
    def test_fato_mais_comentario_sobrevive_ao_corte(self):
        """Quatro frases: a última é o humor, e ela não pode sumir."""
        texto = (
            "O deploy passou. Os 492 testes continuam verdes. "
            "O domínio já serve a versão nova. Levou vinte minutos; a parte difícil foi descobrir o alias."
        )
        saida, _ = gateway.concise_assistant_content(texto)
        self.assertIn("levou vinte minutos", saida.lower())

    def test_texto_longo_ainda_e_cortado(self):
        texto = " ".join(f"Esta é a frase numero {i} do teste." for i in range(40))
        saida, _ = gateway.concise_assistant_content(texto)
        self.assertLessEqual(len(saida), gateway.CONCISE_MAX_CHARS)
        self.assertTrue(saida.endswith(".") or saida.endswith("…"))

    def test_corte_nao_para_no_meio_da_palavra(self):
        texto = ("palavra " * 300).strip()
        saida, _ = gateway.concise_assistant_content(texto)
        self.assertFalse(saida.rstrip(".").endswith("palavr"))

    def test_detalhado_nao_e_tocado(self):
        texto = " ".join(f"Frase {i}." for i in range(30))
        saida, _ = gateway.concise_assistant_content(texto, detailed=True)
        self.assertEqual(saida, texto)

    def test_ruido_de_relatorio_continua_sendo_removido(self):
        texto = "Resposta: o deploy passou. Confiança nesta resposta: alta."
        saida, _ = gateway.concise_assistant_content(texto)
        self.assertNotIn("confiança nesta resposta", saida.lower())


class TemperatureTest(unittest.TestCase):
    def test_conciso_nao_improvisa(self):
        """Precisão vence criatividade: nome de faixa errado quebra a confiança."""
        perfil = gateway.assistant_response_profile("oi")
        self.assertEqual(perfil["name"], "concise")
        self.assertLessEqual(perfil["temperature"], 0.5)


class IronToneTest(unittest.TestCase):
    AGENDA = [
        {"title": "Mandar retorno até terça", "scheduled_for": "2026-11-03T12:00:00+00:00"},
        {"title": "Postar um vídeo sexta-feira", "scheduled_for": "2026-11-06T15:00:00+00:00"},
        {"title": "Criar 3 sistemas", "scheduled_for": None},
        {"title": "Revisar proposta do cliente", "scheduled_for": None},
        {"title": "Comprar café", "scheduled_for": None},
    ]

    def _quadro(self, agenda=None):
        original = (
            gateway.supabase_configured,
            gateway.supabase_agenda_rows,
            gateway.supabase_notes_rows,
            gateway.supabase_request,
            gateway.weather_now,
        )
        gateway.supabase_configured = lambda: True
        gateway.supabase_agenda_rows = lambda *_a, **_k: self.AGENDA if agenda is None else agenda
        gateway.supabase_notes_rows = lambda *_a, **_k: []
        gateway.supabase_request = lambda *_a, **_k: [{"id": 1, "status": "pending"}]
        gateway.weather_now = lambda: "22 graus e nublado"
        try:
            return gateway.iron_style_payload()[0]
        finally:
            (
                gateway.supabase_configured,
                gateway.supabase_agenda_rows,
                gateway.supabase_notes_rows,
                gateway.supabase_request,
                gateway.weather_now,
            ) = original

    def test_agenda_longa_anuncia_o_resto_em_vez_de_sumir(self):
        partes = " ".join(self._quadro()["spoken_parts"]).lower()
        self.assertIn("mais", partes)
        # Lê três e conta o resto: cinco itens viram três + "mais duas coisas".
        self.assertIn("mais duas coisas", partes)

    def test_pergunta_final_sempre_presente(self):
        partes = self._quadro()["spoken_parts"]
        self.assertIn("abra alguma coisa", partes[-1].lower())

    def test_agenda_vazia_tem_humor_em_vez_de_robotica(self):
        partes = " ".join(self._quadro(agenda=[])["spoken_parts"]).lower()
        self.assertIn("agenda limpa", partes)
        self.assertNotIn("nada pendente", partes)

    def test_sem_anotacao_nao_vira_linha_de_sistema(self):
        partes = " ".join(self._quadro()["spoken_parts"]).lower()
        self.assertNotIn("nenhuma anotação", partes)

    def test_cada_parte_cabe_na_voz(self):
        for parte in self._quadro()["spoken_parts"]:
            self.assertLessEqual(len(parte), 320, parte)


if __name__ == "__main__":
    unittest.main(verbosity=2)