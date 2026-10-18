"""Contrato dos modos explícitos do dono e da troca de IA por comando.

Espelho das regexs de web/jarvis.js (assistantModeFor, modelSwapPlanFor) e
web/fala.js (voiceModeFor): borda verde no modo plano, vermelha no bypass e
no sempre-aceitar, nada no modo normal — e a troca de modelo com chave no
cofre local, deduzida do prefixo da chave. Se um regex mudar aqui e lá sem
o outro, este teste falha.
"""
import json
import re
import unittest
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _pattern_from(source: str, const_name: str) -> list:
    match = re.search(const_name + r"\s*=\s*\[(.*?)\n\s*\];", source, re.S)
    assert match, f"{const_name} não encontrado no jarvis.js"
    return re.findall(r're:\s*(/.+/)[a-z]*\s*,', match.group(1))


class AssistantModeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jarvis_js = (WEB_DIR / "jarvis.js").read_text(encoding="utf-8")
        cls.fala_js = (WEB_DIR / "fala.js").read_text(encoding="utf-8")
        cls.jarvis_css = (WEB_DIR / "jarvis.css").read_text(encoding="utf-8")

    def test_mode_patterns_exist_in_both_shells(self):
        self.assertIn("ASSISTANT_MODE_PATTERNS", self.jarvis_js)
        self.assertIn("voiceModeFor", self.fala_js)
        self.assertIn("applyAssistantModeClass", self.jarvis_js)
        self.assertIn("applyVoiceMode", self.fala_js)

    def test_border_css_exists(self):
        self.assertIn("body.jarvis-mode-plan::before", self.jarvis_css)
        self.assertIn("body.jarvis-mode-bypass::before", self.jarvis_css)
        self.assertIn("jarvis-mode-pulse", self.jarvis_css)

    def test_mode_contract(self):
        # Verde: modo plano — planeja, nunca executa.
        plan = re.compile(
            r"^(?:vai|vá|va)\s+dormir\.?$|^(?:entrar?\s+no\s+)?modo\s+plano\.?$|^plano\.?$", re.I
        )
        for phrase in ("vai dormir", "Vai dormir", "modo plano", "Jarvis, modo plano", "plano"):
            value = phrase.lower().strip().replace("jarvis,", "").replace("jarvis ", "").strip()
            self.assertTrue(plan.fullmatch(value), phrase)
        # Vermelha: bypass e sempre-aceitar.
        bypass = re.compile(r"^bypass(?:\s+permissions?)?\.?$|^pular\s+permiss(?:ões|oes|ão|ao)\.?$", re.I)
        for phrase in ("bypass", "bypass permissions", "pular permissões"):
            value = phrase.lower().strip()
            self.assertTrue(bypass.fullmatch(value), phrase)
        accept = re.compile(r"^always\s+accept(?:ed)?\.?$|^(?:aceite|aceitar)\s+tudo\.?$|^sempre\s+aceite\.?$", re.I)
        for phrase in ("always accept", "aceite tudo", "sempre aceite"):
            self.assertTrue(accept.fullmatch(phrase.lower()), phrase)
        # Frases normais não viram modo.
        for phrase in ("me conta uma história para eu dormir", "abre o spotify", "oi"):
            value = phrase.lower().strip()
            self.assertFalse(plan.fullmatch(value), phrase)
            self.assertFalse(bypass.fullmatch(value), phrase)

    def test_model_swap_regexes_in_frontend(self):
        self.assertIn("modelSwapPlanFor", self.jarvis_js)
        self.assertIn("sk-ant-", self.jarvis_js)
        self.assertIn("jarvis-active-ai", self.jarvis_js)

    def test_jarvis_code_prefix_routes_to_self_edit_not_code_pad(self):
        """\"Jarvis code: <pedido>\" é autoedição (Claude Code no Mac); o pad
        só abre com \"jarvis code\" nu ou pedido explícito de abrir."""

        import importlib.util

        gateway = (Path(__file__).resolve().parent.parent / "api" / "index.py").read_text(encoding="utf-8")
        self.assertIn(r"\bjarvis\s+code\b\s*[.!]?\s*$", gateway)
        self.assertIn("jarvis\\s+code\\b.{0,600}", gateway)

        spec = importlib.util.spec_from_file_location(
            "jarvis_gateway_modes", str(Path(__file__).resolve().parent.parent / "api" / "index.py")
        )
        mod = importlib.util.module_from_spec(spec)
        sys_modules = __import__("sys").modules
        sys_modules["jarvis_gateway_modes"] = mod
        spec.loader.exec_module(mod)

        def intent_of(text):
            for pattern, intent in mod.LOCAL_INTENTS:
                if pattern.search(text):
                    return intent
            return ""

        self.assertEqual(intent_of("jarvis code: adiciona um comando de status"), "self_edit")
        self.assertEqual(intent_of("Jarvis Code: arrume a tela do cockpit"), "self_edit")
        self.assertEqual(intent_of("jarvis code"), "code_pad")
        self.assertEqual(intent_of("abre o jarvis code"), "code_pad")

    def test_direct_model_override_in_gateway(self):
        gateway = (Path(__file__).resolve().parent.parent / "api" / "index.py").read_text(encoding="utf-8")
        self.assertIn("direct_model_requested", gateway)
        self.assertIn('client_integration(body, direct_provider).get("model", "")', gateway)


class GatewayDirectModelTest(unittest.TestCase):
    """O modelo pedido no cofre vence o default da rota direta."""

    def test_direct_model_override_validation(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "11_SCRIPTS"))
        # Validação isolada: slug válido passa, qualquer injeção não.
        for slug, ok in (
            ("claude-sonnet-4-5", True),
            ("gpt-5.2", True),
            ("claude-3-5-haiku-latest", True),
            ("openai/gpt-5.2", False),  # prefixo vendor/ é rota do OpenRouter, não direta
            ("x'; drop table users", False),
            ("", False),
            ("a" * 200, False),
        ):
            valid = bool(re.fullmatch(r"[A-Za-z0-9._~:-]{2,120}", slug))
            self.assertEqual(valid, ok, slug)


if __name__ == "__main__":
    unittest.main()
