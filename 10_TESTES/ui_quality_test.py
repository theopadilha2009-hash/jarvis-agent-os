#!/usr/bin/env python3
"""Static UI, accessibility and loading-budget regression checks."""

from html.parser import HTMLParser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
INDEX = WEB / "index.html"
CSS = WEB / "jarvis.css"
APP_JS = WEB / "jarvis.js"
API_VAULT_JS = WEB / "api-vault.js"
PRESENCE_JS = WEB / "jarvis-3d.js"
STRANDS_JS = WEB / "strands.js"
AURORA_JS = WEB / "aurora.js"
THREE_JS = WEB / "vendor" / "three.module.js"


class CockpitParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.elements = []
        self.buttons = []
        self._button_stack = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.elements.append((tag, attributes))
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        if tag == "button":
            self.buttons.append({"attrs": attributes, "text": []})
            self._button_stack.append(len(self.buttons) - 1)

    def handle_endtag(self, tag):
        if tag == "button" and self._button_stack:
            self._button_stack.pop()

    def handle_data(self, data):
        if self._button_stack:
            self.buttons[self._button_stack[-1]]["text"].append(data)


class UIQualityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")
        cls.app_js = APP_JS.read_text(encoding="utf-8")
        cls.api_vault_js = API_VAULT_JS.read_text(encoding="utf-8")
        cls.presence_js = PRESENCE_JS.read_text(encoding="utf-8")
        cls.parser = CockpitParser()
        cls.parser.feed(cls.html)

    def test_ids_are_unique(self):
        duplicates = sorted({item for item in self.parser.ids if self.parser.ids.count(item) > 1})
        self.assertEqual(duplicates, [], f"IDs duplicados: {duplicates}")

    def test_dialogs_have_valid_accessible_titles(self):
        known_ids = set(self.parser.ids)
        dialogs = [attrs for tag, attrs in self.parser.elements if tag == "dialog"]
        self.assertEqual(len(dialogs), 4)
        for dialog in dialogs:
            label_id = dialog.get("aria-labelledby")
            self.assertTrue(label_id, f"Dialog sem aria-labelledby: {dialog.get('id')}")
            self.assertIn(label_id, known_ids, f"Título ausente para dialog: {dialog.get('id')}")

    def test_form_controls_and_buttons_have_accessible_names(self):
        label_targets = {
            attrs.get("for")
            for tag, attrs in self.parser.elements
            if tag == "label" and attrs.get("for")
        }
        unnamed_controls = []
        for tag, attrs in self.parser.elements:
            if tag not in {"input", "select", "textarea"}:
                continue
            if "hidden" in attrs or attrs.get("type") == "hidden":
                continue
            if not (attrs.get("aria-label") or attrs.get("aria-labelledby") or attrs.get("id") in label_targets):
                unnamed_controls.append(attrs.get("id") or tag)
        self.assertEqual(unnamed_controls, [], f"Controles sem nome: {unnamed_controls}")

        unnamed_buttons = []
        for button in self.parser.buttons:
            text = " ".join("".join(button["text"]).split())
            attrs = button["attrs"]
            if not (text or attrs.get("aria-label") or attrs.get("aria-labelledby")):
                unnamed_buttons.append(attrs.get("id") or "button")
        self.assertEqual(unnamed_buttons, [], f"Botões sem nome: {unnamed_buttons}")

    def test_keyboard_landmark_focus_and_motion_contract(self):
        self.assertIn('<a class="skip-link" href="#commandInput">', self.html)
        self.assertIn('<main class="stage"', self.html)
        self.assertIn(":focus-visible", self.css)
        self.assertIn(".skip-link:focus", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)

    def test_responsive_layout_contract(self):
        for breakpoint in (900, 720, 350):
            self.assertIn(f"@media (max-width: {breakpoint}px)", self.css)
        for selector in (
            ".conversation",
            ".composer",
            ".action-hub",
            ".tour-dialog",
            ".install-dialog",
            ".dialog-grid",
        ):
            self.assertIn(selector, self.css)
        self.assertIn("min-height: 44px", self.css)

    def test_composer_keeps_five_controls_inline_with_gauge_strength(self):
        self.assertIn('class="strength-gauge"', self.html)
        self.assertIn('class="strength-gauge-needle"', self.html)
        self.assertIn("minmax(150px, 1fr) 58px 76px", self.css)
        self.assertNotIn("grid-template-columns: 46px 40px minmax(0, 1fr) auto;", self.css)
        self.assertIn('sendButton.textContent = "Enviar";', self.app_js)
        self.assertIn('sendButton.toggleAttribute("aria-busy", value)', self.app_js)

    def test_api_vault_and_n8n_forge_are_real_controls(self):
        for element_id in (
            "integrationsButton",
            "integrationsDialog",
            "integrationProviderList",
            "integrationSaveButton",
            "integrationTestButton",
            "integrationRemoveButton",
            "n8nStudio",
            "n8nWorkflowMap",
            "n8nWorkflowSummary",
            "n8nPreviewButton",
            "n8nCreateButton",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("AES-GCM", self.api_vault_js)
        self.assertIn("false,", self.api_vault_js)
        self.assertIn("indexedDB", self.api_vault_js)
        self.assertIn("client_integrations: clientIntegrations", self.app_js)
        self.assertIn('request("/integrations/test"', self.app_js)
        self.assertIn('request("/integrations/n8n/workflows"', self.app_js)
        self.assertIn('document.createElement("article")', self.app_js)
        self.assertIn("n8n-map-node", self.css)
        self.assertIn("n8n-map-connector", self.css)
        self.assertIn("ULTRON · 3×", self.app_js)

    def test_startup_assets_stay_within_budget(self):
        critical_bytes = sum(path.stat().st_size for path in (INDEX, CSS, APP_JS))
        self.assertLess(critical_bytes, 250 * 1024, f"Carga crítica cresceu para {critical_bytes} bytes")
        self.assertLess(API_VAULT_JS.stat().st_size, 8 * 1024)
        self.assertLess(PRESENCE_JS.stat().st_size, 64 * 1024)
        self.assertLess(THREE_JS.stat().st_size, 1400 * 1024)

    def test_3d_is_lazy_quality_controlled_and_fully_pauses(self):
        self.assertIn('import("/ui/jarvis-3d.js?v=20260813-smartforge1")', self.html)
        self.assertIn("requestIdleCallback", self.html)
        self.assertIn("activeFps: 45", self.presence_js)
        self.assertIn("idleFps: 24", self.presence_js)
        self.assertIn("pixelRatio: 1.25", self.presence_js)
        self.assertIn("activeFps: 30, idleFps: 18, pixelRatio: 1", self.presence_js)
        self.assertIn("activeFps: 20, idleFps: 10, pixelRatio: 0.75", self.presence_js)
        self.assertIn("document.hidden", self.presence_js)
        self.assertIn("if (!reducedMotion) scheduleRender(frameIntervalMs)", self.presence_js)
        self.assertNotIn("constrainedHardware", self.presence_js)
        self.assertNotIn("slowFrameWindows", self.presence_js)

    def test_all_shell_assets_share_space_cache_version(self):
        self.assertNotIn("20260812-v9", self.html)
        self.assertGreaterEqual(self.html.count("20260813-smartforge1"), 10)

    def test_purple_brand_and_bust_contract(self):
        self.assertIn("jarvis-logo.png", self.html)
        self.assertIn("--cyan: #a855f7", self.css)
        self.assertIn("visitor-purple-volume", self.presence_js)
        self.assertNotIn("visitor-real-eye-", self.presence_js)
        self.assertIn("visitor-animated-surface-topology", self.presence_js)
        self.assertIn("visitor-mesh-derived-dissolution", self.presence_js)
        self.assertNotIn("TubeGeometry", self.presence_js)
        self.assertIn("jarvisPoseHead", self.presence_js)
        self.assertNotIn("makeIrisTexture", self.presence_js)
        self.assertIn("* 9.2", self.presence_js)
        self.assertIn('stage.classList.contains("spatial-result")', self.presence_js)
        self.assertIn("const targetPositionX = spatialResult ? -1.35 : modeTargetX", self.presence_js)
        self.assertIn("const inwardGaze = spatialResult * 0.11", self.presence_js)
        self.assertIn("--ink: #130824", self.css)
        self.assertIn("opacity: 0.86", self.css)
        self.assertIn('window.addEventListener("jarvis-voice-level", onVoiceLevel)', self.presence_js)
        self.assertIn("jarvis-humanoid.glb", self.presence_js)
        self.assertIn("ownerModel.visible = isOwner", self.presence_js)
        self.assertIn('id="auroraVisual"', self.html)
        self.assertIn('id="strandsVisual"', self.html)
        self.assertIn(".aurora-visual", self.css)
        self.assertIn(".strands-visual", self.css)
        self.assertIn('["#2E1065", "#7C3AED", "#A855F7"]', self.html)
        self.assertIn('["#6D28D9", "#A855F7", "#C084FC"]', self.html)
        self.assertTrue(AURORA_JS.is_file())
        self.assertTrue(STRANDS_JS.is_file())
        self.assertIn('window.addEventListener("jarvis-voice-level", onVoiceLevel)', STRANDS_JS.read_text(encoding="utf-8"))
        for legacy_accent in ("#2563eb", "#60a5fa", "#49c7dc", "#71ddeb", "#9beeff"):
            self.assertNotIn(legacy_accent, self.css.lower())
        self.assertNotIn("TetrahedronGeometry", self.presence_js)

    def test_clarity_pass_has_luminous_surfaces_and_tactile_controls(self):
        self.assertIn("Clarity pass", self.css)
        self.assertIn("linear-gradient(135deg, #9333ea", self.css)
        self.assertIn(".message.voice-status", self.css)
        self.assertIn("border-left: 2px solid #c084fc", self.css)
        self.assertIn(".message-actions .speak-command", self.css)
        self.assertIn("border-radius: 8px", self.css)
        self.assertIn(".shimmer-label", self.css)
        self.assertIn("background: transparent", self.css)
        self.assertIn("grid-template-rows: 34px 16px", self.css)

    def test_ultron_mode_has_distinct_identity_environment_and_strength_control(self):
        self.assertIn('id="ultronLaughter"', self.html)
        self.assertIn('id="strengthButton"', self.html)
        self.assertIn('id="identityAssistantName"', self.html)
        self.assertIn('id="conversationAssistantName"', self.html)
        self.assertIn('html[data-persona="ultron"]', self.css)
        self.assertIn("@keyframes ultron-laugh-drift", self.css)
        self.assertIn("--cyan: #ef4444", self.css)
        self.assertIn("#240307", self.html)
        self.assertIn("#EF4444", self.html)
        self.assertIn('document.documentElement.dataset.persona = ultron ? "ultron" : "jarvis"', self.app_js)
        self.assertIn('strength: session.strength', self.app_js)
        self.assertIn('"jarvis-response-strength"', self.app_js)
        self.assertIn("scheduleUltronLaughter", self.app_js)
        self.assertIn("const OWNER_RED = 0xef3340", self.presence_js)
        self.assertIn("ultron-red-identity-v1", self.presence_js)
        self.assertNotIn("modo master", self.html.casefold())
        self.assertNotIn("modo master", self.app_js.casefold())


if __name__ == "__main__":
    unittest.main()
