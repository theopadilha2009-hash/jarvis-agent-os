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
        cls.presence_js = PRESENCE_JS.read_text(encoding="utf-8")
        cls.parser = CockpitParser()
        cls.parser.feed(cls.html)

    def test_ids_are_unique(self):
        duplicates = sorted({item for item in self.parser.ids if self.parser.ids.count(item) > 1})
        self.assertEqual(duplicates, [], f"IDs duplicados: {duplicates}")

    def test_dialogs_have_valid_accessible_titles(self):
        known_ids = set(self.parser.ids)
        dialogs = [attrs for tag, attrs in self.parser.elements if tag == "dialog"]
        self.assertEqual(len(dialogs), 3)
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

    def test_startup_assets_stay_within_budget(self):
        critical_bytes = sum(path.stat().st_size for path in (INDEX, CSS, APP_JS))
        self.assertLess(critical_bytes, 220 * 1024, f"Carga crítica cresceu para {critical_bytes} bytes")
        self.assertLess(PRESENCE_JS.stat().st_size, 64 * 1024)
        self.assertLess(THREE_JS.stat().st_size, 1400 * 1024)

    def test_3d_is_lazy_quality_controlled_and_fully_pauses(self):
        self.assertIn('import("/ui/jarvis-3d.js?v=20260813-human6")', self.html)
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
        self.assertGreaterEqual(self.html.count("20260813-human6"), 9)

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


if __name__ == "__main__":
    unittest.main()
