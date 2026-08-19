#!/usr/bin/env python3
"""Static UI, accessibility and loading-budget regression checks."""

from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
INDEX = WEB / "index.html"
CSS = WEB / "jarvis.css"
UI_REPAIR_CSS = WEB / "ui-repair.css"
API_PANEL_CSS = WEB / "api-panel.css"
RESPONSIVE_POLISH_CSS = WEB / "responsive-polish.css"
SHELL_CSS = WEB / "shell.css"
INTEGRATION_HEALTH_CSS = WEB / "integration-health.css"
LOGO = WEB / "jarvis-logo.png"
APP_JS = WEB / "jarvis.js"
API_VAULT_JS = WEB / "api-vault.js"
INTEGRATION_HISTORY_JS = WEB / "integration-history.js"
INTEGRATION_HEALTH_JS = WEB / "integration-health.js"
VOICE_CALIBRATOR_JS = WEB / "voice-calibrator.js"
VOICE_CALIBRATOR_CSS = WEB / "voice-calibrator.css"
N8N_TEMPLATE_PACK_JS = WEB / "n8n-template-pack.js"
FEATURE_LOADER_JS = WEB / "feature-loader.js"
PRESENCE_LOADER_JS = WEB / "presence-loader.js"
ULTRON_COMPLETION_CSS = WEB / "ultron-completion.css"
MEMORY_EXPLORER_JS = WEB / "memory-explorer.js"
MEMORY_EXPLORER_CSS = WEB / "memory-explorer.css"
ACTION_PERMISSIONS_JS = WEB / "action-permissions.js"
ACTION_PERMISSIONS_CSS = WEB / "action-permissions.css"
MISSION_CONTROL_JS = WEB / "mission-control.js"
MISSION_CONTROL_CSS = WEB / "mission-control.css"
VOICE_PACING_JS = WEB / "voice-pacing.js"
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
        cls.ui_repair_css = UI_REPAIR_CSS.read_text(encoding="utf-8")
        cls.shell_css = SHELL_CSS.read_text(encoding="utf-8")
        cls.api_panel_css = API_PANEL_CSS.read_text(encoding="utf-8")
        cls.app_js = APP_JS.read_text(encoding="utf-8")
        cls.api_vault_js = API_VAULT_JS.read_text(encoding="utf-8")
        cls.mission_control_js = MISSION_CONTROL_JS.read_text(encoding="utf-8")
        cls.mission_control_css = MISSION_CONTROL_CSS.read_text(encoding="utf-8")
        cls.voice_pacing_js = VOICE_PACING_JS.read_text(encoding="utf-8")
        cls.presence_js = PRESENCE_JS.read_text(encoding="utf-8")
        cls.presence_loader_js = PRESENCE_LOADER_JS.read_text(encoding="utf-8")
        cls.feature_loader_js = FEATURE_LOADER_JS.read_text(encoding="utf-8")
        cls.ultron_completion_css = ULTRON_COMPLETION_CSS.read_text(encoding="utf-8")
        cls.parser = CockpitParser()
        cls.parser.feed(cls.html)

    def test_first_party_javascript_parses(self):
        """Um await fora de async derruba o cockpit inteiro. Exige parse real."""
        node = shutil.which("node")
        if not node:
            self.skipTest("node não está no PATH")
        scripts = [
            path for path in WEB.rglob("*.js")
            if "vendor" not in path.parts
        ]
        self.assertGreaterEqual(len(scripts), 8)
        failures = []
        for path in sorted(scripts):
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                failures.append(f"{path.relative_to(ROOT)}: {(result.stderr or result.stdout).strip()}")
        self.assertEqual(failures, [], "JavaScript inválido:\n" + "\n".join(failures))

    def test_ids_are_unique(self):
        duplicates = sorted({item for item in self.parser.ids if self.parser.ids.count(item) > 1})
        self.assertEqual(duplicates, [], f"IDs duplicados: {duplicates}")

    def test_dialogs_have_valid_accessible_titles(self):
        known_ids = set(self.parser.ids)
        dialogs = [attrs for tag, attrs in self.parser.elements if tag == "dialog"]
        self.assertEqual(len(dialogs), 6)
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

    def test_composer_uses_one_whatsapp_style_voice_or_send_action(self):
        self.assertIn('class="strength-gauge"', self.html)
        self.assertIn('class="strength-gauge-needle"', self.html)
        self.assertIn("grid-template-columns: 40px 56px 46px minmax(0, 1fr)", self.shell_css)
        self.assertIn('.composer[data-has-payload="false"] .send-button', self.ui_repair_css)
        self.assertIn('.composer[data-has-payload="true"] .voice-button', self.ui_repair_css)
        self.assertIn('content: "➤"', self.ui_repair_css)
        self.assertIn("function syncComposerAction()", self.app_js)
        self.assertIn('input.addEventListener("input", () => {', self.app_js)
        self.assertIn("syncComposerAction();", self.app_js)
        self.assertIn("syncComposerHeight();", self.app_js)
        self.assertNotIn("grid-template-columns: 46px 40px minmax(0, 1fr) auto;", self.css)
        self.assertIn('sendButton.textContent = "Enviar";', self.app_js)
        self.assertIn('sendButton.toggleAttribute("aria-busy", value)', self.app_js)

    def test_api_vault_and_n8n_forge_are_real_controls(self):
        dynamic_ids = {
            "memoryExplorerDialog", "memoryExplorerMount",
            "actionPermissionsDialog", "actionPermissionsMount",
        }
        for element_id in (
            "integrationsButton",
            "integrationsDialog",
            "integrationProviderList",
            "integrationSaveButton",
            "integrationTestButton",
            "integrationRemoveButton",
            "integrationToolbox",
            "integrationToolFields",
            "integrationToolRunButton",
            "integrationToolResult",
            "integrationToolSelect",
            "integrationHistoryClear",
            "integrationHistoryList",
            "integrationTabs",
            "integrationConnectionPanel",
            "integrationToolsPanel",
            "integrationWorkflowsPanel",
            "integrationHealthPanel",
            "integrationHealthMount",
            "voiceTuningButton",
            "voiceTuningDialog",
            "voiceTuningMount",
            "n8nStudio",
            "n8nWorkflowMap",
            "n8nTemplateGallery",
            "n8nWorkflowList",
            "n8nWorkflowSummary",
            "memoryExplorerButton",
            "memoryExplorerDialog",
            "memoryExplorerMount",
            "actionPermissionsButton",
            "actionPermissionsDialog",
            "actionPermissionsMount",
            "n8nPreviewButton",
            "n8nCreateButton",
        ):
            source = self.feature_loader_js if element_id in dynamic_ids else self.html
            self.assertIn(f'"{element_id}"', source)
        self.assertIn("AES-GCM", self.api_vault_js)
        self.assertIn("false,", self.api_vault_js)
        self.assertIn("indexedDB", self.api_vault_js)
        self.assertIn("client_integrations: clientIntegrations", self.app_js)
        self.assertIn('request("/integrations/test"', self.app_js)
        self.assertIn('request("/integrations/tools"', self.app_js)
        self.assertIn('request("/integrations/n8n/workflows"', self.app_js)
        self.assertIn("integration-toolbox", self.api_panel_css)
        self.assertIn("external_write", self.app_js)
        self.assertIn('document.createElement("article")', self.app_js)
        self.assertIn("n8n-map-node", self.api_panel_css)
        self.assertIn("n8n-map-connector", self.api_panel_css)
        self.assertIn("n8n-template-gallery", self.api_panel_css)
        self.assertIn("n8n-workflow-row", self.api_panel_css)
        template_pack = N8N_TEMPLATE_PACK_JS.read_text(encoding="utf-8")
        self.assertIn('id: "whatsapp-lead"', template_pack)
        self.assertIn('id: "gmail-digest"', template_pack)
        self.assertIn('id: "github-incident"', template_pack)
        self.assertIn('id: "supabase-intake"', template_pack)
        self.assertIn('data-integration-tab="workflows"', self.html)
        self.assertIn('inspect.dataset.n8nWorkflowAction = "inspect"', self.app_js)
        self.assertIn('duplicate.dataset.n8nWorkflowAction = "duplicate"', self.app_js)
        self.assertIn('authorize("automation"', self.app_js)
        self.assertIn('authorize("outbound"', self.app_js)
        self.assertIn("ULTRON · 3×", self.app_js)
        self.assertIn('data-integration-tab="connection"', self.html)
        self.assertIn('data-integration-tab="tools"', self.html)
        self.assertIn('data-integration-tab="workflows"', self.html)
        self.assertIn('data-integration-tab="health"', self.html)
        self.assertIn("window.JarvisIntegrationTabs", self.api_vault_js)
        self.assertIn("ArrowRight", self.api_vault_js)
        self.assertIn("integration-actions-sticky", self.api_panel_css)
        self.assertIn("currentIntegrationTool", self.app_js)
        self.assertIn("recordIntegrationActivity", self.app_js)
        self.assertIn("jarvis-integration-history-v1", INTEGRATION_HISTORY_JS.read_text(encoding="utf-8"))
        self.assertIn("integration-history-row", self.api_panel_css)
        health_js = INTEGRATION_HEALTH_JS.read_text(encoding="utf-8")
        self.assertIn("integrationHealthRefresh", health_js)
        self.assertIn("quotaLabel", health_js)
        self.assertIn("latency_ms", health_js)
        self.assertIn("last_failure", health_js)
        self.assertIn("integration-health-card", INTEGRATION_HEALTH_CSS.read_text(encoding="utf-8"))
        voice_calibrator = VOICE_CALIBRATOR_JS.read_text(encoding="utf-8")
        self.assertIn("jarvis-voice-profile-v1", voice_calibrator)
        self.assertIn('label: "Sério"', voice_calibrator)
        self.assertIn('label: "Tranquilo"', voice_calibrator)
        self.assertIn('data-voice-setting="speed"', voice_calibrator)
        self.assertIn("sem aplicar pitch artificial", voice_calibrator)
        self.assertIn("voice_profile: window.JarvisVoiceCalibrator?.profile()", self.app_js)
        self.assertIn("voice-calibrator.js?v=20260815-vozes2", INTEGRATION_HISTORY_JS.read_text(encoding="utf-8"))
        self.assertIn("n8n-template-pack.js?v=20260813-ultronfix1", INTEGRATION_HISTORY_JS.read_text(encoding="utf-8"))
        memory_explorer = MEMORY_EXPLORER_JS.read_text(encoding="utf-8")
        self.assertIn('name="q"', memory_explorer)
        self.assertIn('name="kind"', memory_explorer)
        self.assertIn('name="from"', memory_explorer)
        self.assertIn('name="to"', memory_explorer)
        feature_loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")
        self.assertIn("memory-explorer.js?v=20260813-ultronfix1", feature_loader)
        self.assertIn("action-permissions.js?v=20260813-ultronfix1", feature_loader)
        self.assertIn("linkedin.com/in/theo-lorentz-padilha", feature_loader)
        self.assertNotIn("ghbtns.com", feature_loader)
        self.assertIn("screenUnavailable", feature_loader)
        self.assertIn("devicePollDelay", self.app_js)
        self.assertIn("worker_offline", self.app_js)
        device_feedback = (ROOT / "web" / "device-feedback.js").read_text(encoding="utf-8")
        self.assertIn("Ainda offline · verificar de novo", device_feedback)
        self.assertIn("worker-diagnostic", device_feedback)
        action_permissions = ACTION_PERMISSIONS_JS.read_text(encoding="utf-8")
        self.assertIn("jarvis-action-permissions-v1", action_permissions)
        self.assertIn("Permitir uma vez", action_permissions)
        self.assertIn("Liberar nesta sessão", action_permissions)
        self.assertIn("Não existe “permitir para sempre”", action_permissions)

    def test_startup_assets_stay_within_budget(self):
        critical_bytes = sum(path.stat().st_size for path in (INDEX, CSS, APP_JS))
        self.assertLess(critical_bytes, 294 * 1024, f"Carga crítica cresceu para {critical_bytes} bytes")
        self.assertLess(API_VAULT_JS.stat().st_size, 8 * 1024)
        self.assertLess(INTEGRATION_HISTORY_JS.stat().st_size, 5 * 1024)
        self.assertLess(INTEGRATION_HEALTH_JS.stat().st_size, 7 * 1024)
        self.assertLess(INTEGRATION_HEALTH_CSS.stat().st_size, 4 * 1024)
        # O calibrador virou também o seletor de vozes; segue sob demanda, fora do arranque.
        self.assertLess(VOICE_CALIBRATOR_JS.stat().st_size, 12 * 1024)
        self.assertLess(VOICE_CALIBRATOR_CSS.stat().st_size, 6 * 1024)
        self.assertLess(N8N_TEMPLATE_PACK_JS.stat().st_size, 5 * 1024)
        self.assertLess(FEATURE_LOADER_JS.stat().st_size, 5 * 1024)
        self.assertLess(PRESENCE_LOADER_JS.stat().st_size, 3 * 1024)
        self.assertLess(ULTRON_COMPLETION_CSS.stat().st_size, 7 * 1024)
        self.assertLess(MEMORY_EXPLORER_JS.stat().st_size, 8 * 1024)
        self.assertLess(MEMORY_EXPLORER_CSS.stat().st_size, 4 * 1024)
        self.assertLess(ACTION_PERMISSIONS_JS.stat().st_size, 8 * 1024)
        self.assertLess(ACTION_PERMISSIONS_CSS.stat().st_size, 4 * 1024)
        self.assertLess(UI_REPAIR_CSS.stat().st_size, 12 * 1024)
        self.assertLess(API_PANEL_CSS.stat().st_size, 20 * 1024)
        self.assertLess(RESPONSIVE_POLISH_CSS.stat().st_size, 12 * 1024)
        self.assertLess(SHELL_CSS.stat().st_size, 9 * 1024)
        self.assertLess(PRESENCE_JS.stat().st_size, 64 * 1024)
        self.assertLess(THREE_JS.stat().st_size, 1400 * 1024)

    def test_mission_control_is_lazy_real_and_operator_controlled(self):
        self.assertIn("Missões <kbd>⌘K</kbd>", self.html)
        self.assertIn('import("/ui/mission-control.js?v=20260813-missions1")', self.api_vault_js)
        self.assertIn('request("/mission-control?limit=12")', self.mission_control_js)
        self.assertIn("jarvis-mission-control/1", self.mission_control_js)
        self.assertIn("data-mission-operation", self.mission_control_js)
        self.assertIn("window.confirm", self.mission_control_js)
        self.assertIn("mission-control-row", self.mission_control_css)
        self.assertIn("prefers-reduced-motion", self.mission_control_css)
        self.assertLess(MISSION_CONTROL_JS.stat().st_size, 16 * 1024)
        self.assertLess(MISSION_CONTROL_CSS.stat().st_size, 8 * 1024)

    def test_living_voice_preserves_voice_and_prefetches_natural_lead(self):
        self.assertIn('import("/ui/voice-pacing.js?v=20260813-voice2")', self.api_vault_js)
        self.assertIn("requestIdleCallback", self.api_vault_js)
        self.assertIn("jarvis-voice-pacing/2", self.voice_pacing_js)
        self.assertIn("FIRST_TARGET = 128", self.voice_pacing_js)
        self.assertIn("MAX_CHUNKS = 4", self.voice_pacing_js)
        self.assertIn("naturalCut", self.voice_pacing_js)
        self.assertIn("window.JarvisVoicePacing?.chunks", self.app_js)
        self.assertIn("prepared = index + 1 < chunks.length", self.app_js)
        self.assertIn("previous_text: previousText", self.app_js)
        self.assertIn("next_text: nextText", self.app_js)
        self.assertIn("voiceFirstAudioMs", self.app_js)
        self.assertIn('`ElevenLabs · voz em ${session.voiceFirstAudioMs} ms`', self.app_js)
        self.assertIn('? 100\n        : ["research", "planning"].includes(workingState) ? 600 : 280', self.app_js)
        self.assertLess(VOICE_PACING_JS.stat().st_size, 6 * 1024)

    def test_selective_memory_receipt_stays_inside_real_details(self):
        self.assertIn("data.memory_selection?.selected", self.app_js)
        self.assertIn("memórias relevantes", self.app_js)

    def test_3d_is_lazy_quality_controlled_and_fully_pauses(self):
        self.assertIn('presence-loader.js?v=20260813-ultronfix1', self.html)
        self.assertIn('import("/ui/jarvis-3d.js?v=20260815-vozes2")', self.presence_loader_js)
        self.assertIn("always: true", self.presence_js)
        self.assertIn("requestIdleCallback", self.presence_loader_js)
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
        self.assertGreaterEqual(self.html.count("20260813-apitools1"), 1)
        self.assertNotIn("chatfix", self.html)
        self.assertGreaterEqual(self.html.count("20260815-vozes2"), 3)
        self.assertGreaterEqual(self.html.count("20260817-move1") + self.html.count("20260818-login2"), 3)
        self.assertIn("20260818-login2", self.html)
        self.assertIn("welcomeLogin", self.html)
        self.assertIn("script interrompido", self.html)
        self.assertIn("local-voice.js", self.html)
        self.assertGreaterEqual(self.html.count("20260813-ultronfix1"), 3)

    def test_ultron_completion_removes_purple_controls_and_canvas_palette(self):
        self.assertIn('html[data-persona="ultron"]', self.ultron_completion_css)
        self.assertIn(".send-button", self.ultron_completion_css)
        self.assertIn(".memory-search-button", self.ultron_completion_css)
        self.assertIn(".integration-tabs button[aria-selected=\"true\"]", self.ultron_completion_css)
        self.assertIn('document.documentElement.dataset.persona === "ultron"', self.presence_js)
        self.assertIn('"rgba(239,68,68,', self.presence_js)
        self.assertIn("wireMaterial.color.setHex(ultron ? (options.ultronWire ?? 0xef4444)", self.presence_js)
        self.assertIn("soulMaterial.color.setHex(ultron ? (options.ultronSoul ?? 0xf87171)", self.presence_js)
        # As miniaturas também viram vermelhas no Ultron: nada de roxo/laranja/ciano.
        self.assertIn("ultronSoul", self.presence_js)
        self.assertNotIn("if (!always) {", self.presence_js)
        self.assertIn('html[data-persona="ultron"] .nucleus-legend span', self.ultron_completion_css)
        self.assertIn('html[data-persona="ultron"] .conversation-move', self.ultron_completion_css)
        self.assertIn("background: linear-gradient(145deg, #ef4444, #991b1b)", self.ui_repair_css)

    def test_final_responsive_guardrails_cover_real_viewports(self):
        css = RESPONSIVE_POLISH_CSS.read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 1280px) and (min-width: 941px)", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn("@media (max-width: 520px)", css)
        self.assertIn("@media (max-width: 370px)", css)
        self.assertIn("@media (max-height: 650px) and (orientation: landscape)", css)
        self.assertIn("env(safe-area-inset-right)", css)
        self.assertIn("prefers-contrast: more", css)
        self.assertIn("prefers-reduced-transparency: reduce", css)
        self.assertIn(".integration-history-row time { grid-column: 2; }", css)
        self.assertNotIn(".avatar canvas", css)

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
        self.assertIn('["#2E1065", "#7C3AED", "#A855F7"]', self.presence_loader_js)
        self.assertIn('["#6D28D9", "#A855F7", "#C084FC"]', self.presence_loader_js)
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
        self.assertNotIn('id="ultronLaughter"', self.html)
        self.assertNotIn("scheduleUltronLaughter", self.app_js)
        self.assertNotIn("HAHAHA", self.app_js)
        self.assertIn('id="conversationResize"', self.html)
        self.assertIn('id="conversationMove"', self.html)
        self.assertIn("CHAT_RECT_KEY", self.app_js)
        self.assertIn("speakBrowser", self.app_js)
        self.assertIn("nucleus-pulse", self.ui_repair_css)
        self.assertIn("shell.css", self.html)
        self.assertIn("dataset.placed", self.app_js)
        self.assertIn("nucleus-legend", self.html)
        self.assertIn('id="conversationOccupancy"', self.html)
        self.assertIn("jarvis-conversation-local", self.app_js)
        self.assertIn("renderOccupancy", self.app_js)
        self.assertIn("na fila", self.app_js)
        self.assertIn("__copy_bug_report__", self.app_js)
        self.assertIn("BUG JARVIS (visitante)", self.app_js)
        self.assertIn("Sair do Ultron", self.app_js)
        self.assertIn("access-swap", self.html)
        self.assertIn("identityCreator", self.html)
        self.assertIn('id="macDownloadButton"', self.html)
        self.assertIn('href="/download/mac"', self.html)
        self.assertIn("creator-seal.js", self.html)
        self.assertIn("VGhlbyBMb3JlbnR6IFBhZGlsaGE=", self.app_js)
        self.assertIn("Quem te criou?", self.app_js)
        self.assertIn("jarvis-owner-last-active", self.app_js)
        self.assertIn("expireIdleOwnerSession", self.app_js)
        self.assertIn("rememberLoginEnabled", self.app_js)
        self.assertIn("jarvis-remember-login-v1", self.app_js)
        self.assertIn("clamp(340px, 62vh, 620px)", self.shell_css)
        self.assertIn(".scene-telemetry", self.shell_css)
        self.assertIn(".author-link", self.shell_css)
        self.assertIn("Melhorar você", self.app_js)
        self.assertIn("hidden", self.html)
        self.assertIn('<textarea id="commandInput"', self.html)
        self.assertIn('id="strengthButton"', self.html)
        self.assertIn('id="identityAssistantName"', self.html)
        self.assertIn('id="conversationAssistantName"', self.html)
        self.assertIn('html[data-persona="ultron"]', self.css)
        self.assertIn("--cyan: #ef4444", self.css)
        self.assertIn("#240307", self.presence_loader_js)
        self.assertIn("#EF4444", self.presence_loader_js)
        self.assertIn('document.documentElement.dataset.persona = ultron ? "ultron" : "jarvis"', self.app_js)
        self.assertIn("strength: session.paired && session.strength === \"auto\" ? \"strong\" : session.strength", self.app_js)
        self.assertIn('"jarvis-response-strength"', self.app_js)
        self.assertIn("function signalUltron", self.app_js)
        self.assertIn("X-Jarvis-Conversation-Id", self.app_js)
        self.assertIn('authorLink.className = "author-link"', self.feature_loader_js)
        self.assertNotIn("ghbtns.com", self.feature_loader_js)
        self.assertIn('data.persona?.id === "ultron_private"', self.app_js)
        self.assertIn("@keyframes ultron-target-lock", self.css)
        self.assertIn('html[data-persona="ultron"] .message-context', self.ui_repair_css)
        self.assertIn('html[data-persona="ultron"] .message-actions .speak-command', self.ui_repair_css)
        self.assertIn('html[data-persona="ultron"] .composer input', self.ui_repair_css)
        self.assertIn('html[data-persona="ultron"] .scene-modes > span', self.ui_repair_css)
        self.assertIn(".scene-modes > button > span", self.ui_repair_css)
        self.assertIn("const OWNER_RED = 0xef3340", self.presence_js)
        self.assertIn("ultron-red-identity-v1", self.presence_js)
        self.assertNotIn("modo master", self.html.casefold())
        self.assertNotIn("modo master", self.app_js.casefold())

    def test_identity_logo_blends_without_dark_square(self):
        logo = LOGO.read_bytes()
        self.assertEqual(logo[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn(logo[25], {4, 6}, "Logo precisa ter canal alpha nativo")
        self.assertIn("mix-blend-mode: normal", self.ui_repair_css)
        self.assertNotIn("logo-filter.svg", self.html + self.ui_repair_css)
        self.assertIn("border-color: transparent", self.ui_repair_css)
        self.assertIn("background: transparent", self.ui_repair_css)

    def test_only_the_shell_owns_the_chat_window_geometry(self):
        """Regressão do pulo de altura: uma camada só define a janela do chat."""
        geometry = {
            "position", "left", "right", "top", "bottom", "width", "height",
            "max-height", "min-height", "transform",
            "grid-template-rows", "grid-template-columns", "grid-row", "grid-column",
        }
        window_selector = re.compile(r"\.(?:conversation|composer)(?![\w:-])")
        offenders = []
        for path in sorted(p for p in WEB.glob("*.css") if p.name != "shell.css"):
            text = re.sub(r"/\*.*?\*/", " ", path.read_text(encoding="utf-8"), flags=re.S)
            for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
                if not window_selector.search(selector):
                    continue
                for declaration in body.split(";"):
                    prop = declaration.split(":")[0].strip().lower()
                    if prop in geometry:
                        offenders.append(f"{path.name}: {' '.join(selector.split())} -> {prop}")
        self.assertEqual(offenders, [], f"Geometria da janela fora de shell.css: {offenders}")
        self.assertFalse((WEB / "shell-final.css").exists(), "shell-final.css foi consolidado em shell.css")
        self.assertNotIn("shell-final.css", self.html)

    def test_chat_window_is_a_real_window_without_height_jump(self):
        self.assertIn("position: fixed", self.shell_css)
        for edge in ("n", "s", "e", "w", "ne", "nw", "se", "sw"):
            self.assertIn(f'.conversation-edges [data-edge="{edge}"]', self.shell_css)
            self.assertIn(f'data-edge="{edge}"', self.html)
        self.assertIn(".conversation-head {", self.shell_css)
        self.assertIn("cursor: grab", self.shell_css)
        self.assertIn(">arrastar</button>", self.html)
        self.assertIn('href="/download/mac"', self.html)
        self.assertIn("setPointerCapture", self.app_js)
        self.assertIn("response.status >= 500 && attempt === 0", self.app_js)
        self.assertIn('placeholder="Escreva ou fale comigo"', self.html)
        self.assertIn(".composer textarea::-webkit-scrollbar", self.shell_css)
        self.assertIn("scrollbar-width: none", self.shell_css)
        self.assertIn(".composer .attachment-button { grid-column: 1; grid-row: 1; }", self.shell_css)
        self.assertIn(".composer .strength-button { grid-column: 2; grid-row: 1;", self.shell_css)
        self.assertIn(".composer .voice-button,\n.composer .send-button {", self.shell_css)
        self.assertIn("Math.min(120, Math.max(50, input.scrollHeight))", self.app_js)

    def test_chat_window_opens_tall_and_drops_the_squashed_saved_rect(self):
        """A janela salva antes da v2 abria 720x240; a chave nova descarta isso."""
        self.assertIn('const CHAT_RECT_KEY = "jarvis-chat-rect-v4"', self.app_js)
        self.assertIn('localStorage.removeItem("jarvis-chat-rect")', self.html)
        self.assertIn('localStorage.getItem("jarvis-chat-rect-v4")', self.html)
        self.assertIn('localStorage.removeItem("jarvis-chat-rect-v3")', self.html)
        self.assertIn('localStorage.removeItem("jarvis-chat-rect-v2")', self.html)
        self.assertNotIn("jarvis-chat-height", self.app_js)
        self.assertIn("const minH = 340", self.app_js)
        self.assertIn("Math.max(440, Math.round(window.innerHeight * 0.66))", self.app_js)
        # Nasce como painel à direita, com o busto e os núcleos livres à esquerda.
        self.assertIn("window.innerWidth - width - 28", self.app_js)

    def test_mini_nuclei_are_anchored_to_the_legend(self):
        """Núcleo, Forja e Memória: cada nome encosta na sua própria miniatura."""
        self.assertIn("placeMiniNuclei", self.presence_js)
        self.assertIn("camera.updateMatrixWorld(true)", self.presence_js)
        self.assertIn("--nucleus-x", self.presence_js)
        self.assertIn("--nucleus-y", self.presence_js)
        self.assertIn(".nucleus-legend span", self.shell_css)
        self.assertIn("left: var(--nucleus-x", self.shell_css)
        # A legenda vive dentro do canvas 3D, senão o offset do .avatar desalinha.
        avatar = self.html.split('id="avatar3d"', 1)[1].split("</div>", 1)[0]
        self.assertIn("nucleus-legend", avatar)
        # Sem baseY os três colapsam na mesma altura do busto.
        self.assertIn("group.userData.baseY", self.presence_js)
        # Forja e Memória são os visuais reais daqueles modos, não esferas.
        self.assertIn("drawForge(thumbContext", self.presence_js)
        self.assertIn("drawMemory(thumbContext", self.presence_js)
        self.assertIn("nucleusSlots.push", self.presence_js)
        # Miniatura tem camada própria, na frente do busto.
        self.assertIn('makeEffectCanvas("nuclei", "2")', self.presence_js)
        # E não espera o busto de 3 MB para aparecer.
        self.assertIn("thumbnailTicker = requestAnimationFrame", self.presence_js)
        # Telemetria viva: o núcleo acende no evento real dele.
        self.assertIn("jarvis-nucleus-pulse", self.presence_js)
        self.assertIn("jarvis-nucleus-pulse", self.app_js)
        self.assertIn("function nucleusForResult", self.app_js)
        self.assertIn("pulseForWorkingState(workingState)", self.app_js)

    def test_jarvis_greets_when_theo_comes_back(self):
        """Voltou depois de um tempo longe: ele abre a conversa sozinho, uma vez."""
        self.assertIn("function greetOnArrival", self.app_js)
        self.assertIn("ARRIVAL_AWAY_MS = 25 * 60 * 1000", self.app_js)
        self.assertIn("ARRIVAL_COOLDOWN_MS = 60 * 60 * 1000", self.app_js)
        self.assertIn('localStorage.getItem(ARRIVAL_KEY', self.app_js)
        self.assertIn('document.addEventListener("visibilitychange"', self.app_js)
        # Dono recebe o brief real; visitante recebe só a saudação.
        self.assertIn('sendCommand("me dê um resumo operacional do meu dia", { source: "arrival" })', self.app_js)
        self.assertIn("watchArrival();", self.app_js)
        # O worker abre o cockpit com ?arrival=worker; aí a saudação é imediata.
        self.assertIn('params.get("arrival")', self.app_js)
        self.assertIn("greetOnArrival({ requested: true, reason: arrival, silent })", self.app_js)
        # A aba não repete o que o alto-falante do Mac já disse.
        self.assertIn('params.get("spoken") === "1"', self.app_js)
        self.assertIn("if (!silent) speak(welcome)", self.app_js)

    def test_voice_never_falls_back_to_the_flat_default(self):
        """ElevenLabs sem crédito não pode devolver a voz robótica padrão."""
        self.assertIn("VOZ RESERVA", self.app_js)
        self.assertIn("premium|enhanced|siri|neural", self.app_js)
        self.assertIn('data.client_action === "clear_chat"', self.app_js)
        self.assertIn("startNewConversation({ force: true })", self.app_js)
        self.assertNotIn("await startNewConversation", self.app_js)
        self.assertIn('data?.client_action === "clear_chat"', self.app_js)
        self.assertIn('id="crownButton"', self.html)
        self.assertIn('id="signupButton"', self.html)
        self.assertIn('id="welcomeLogin"', self.html)
        self.assertIn('id="rememberLogin"', self.html)
        self.assertIn("Entrar com login e senha", self.html)
        self.assertIn('id="signupTerms"', self.html)
        self.assertIn('accepted_terms', self.app_js)
        self.assertIn('id="accountsDialog"', self.html)
        self.assertIn('data.client_action === "open_code_mode"', self.app_js)
        self.assertIn("[data-scene-mode]", self.app_js)
        self.assertIn("Pocket TTS", self.app_js)
        self.assertIn("JarvisLocalVoice", self.app_js)
        self.assertIn("speakBlob", self.app_js)
        self.assertIn("pending_accounts", self.app_js)
        self.assertIn("formatSeen", self.app_js)
        self.assertIn(".author-card", self.shell_css)
        self.assertIn("author-card", self.app_js)
        self.assertIn("announceVoiceDowngrade", self.app_js)
        # Painel de vozes: listar, trocar e adicionar.
        calibrator = VOICE_CALIBRATOR_JS.read_text(encoding="utf-8")
        self.assertIn("async function loadVoices", calibrator)
        self.assertIn("async function selectVoice", calibrator)
        self.assertIn('api("/voices")', calibrator)
        self.assertIn('api("/voice-select"', calibrator)
        self.assertIn('data.client_action === "open_voice_panel"', self.app_js)
        self.assertIn("Bem-vindo, Theo", self.app_js)
        # Chamar pelo nome, para JARVIS e ULTRON.
        self.assertIn("const WAKE_WORD", self.app_js)
        self.assertIn("installWakeWord", self.app_js)
        self.assertIn("JarvisWakeWord", self.app_js)
        self.assertIn("voiceWakeToggle", calibrator)
        # Chamar tem que ser instantâneo: depois de acordar, a frase seguinte
        # vira comando no MESMO microfone — parar e reabrir custava segundos.
        self.assertIn("commandUntil", self.app_js)
        self.assertNotIn("commandRecognition.start()", self.app_js)
        # Resultados parciais repetem o trecho; sem trava, o comando dispara duas vezes.
        self.assertIn("lastFired", self.app_js)
        self.assertIn('command: "Te ouvindo', self.app_js)
        self.assertIn('.wake-indicator[data-state="command"]', self.ultron_completion_css)
        # Timbre da voz própria sai do mesmo painel.
        self.assertIn('data-voice-setting="pitch"', calibrator)
        self.assertIn('data-voice-setting="tempo"', calibrator)
        # A voz do navegador nunca pode ser feminina por acaso.
        self.assertIn("FEMALE_VOICES", self.app_js)
        self.assertIn("MALE_VOICES", self.app_js)
        self.assertIn('request("/voice-status")', self.app_js)
        self.assertNotIn("group.position.y = 0.02 + Math.sin", self.presence_js)

    def test_api_vault_editor_has_a_bounded_scroll_surface(self):
        self.assertIn(".integrations-dialog[open]", self.ui_repair_css)
        self.assertIn("grid-template-rows: auto minmax(0, 1fr)", self.ui_repair_css)
        self.assertIn(".integration-provider-list,\n  .integration-editor", self.ui_repair_css)
        self.assertIn("overscroll-behavior: contain", self.ui_repair_css)


if __name__ == "__main__":
    unittest.main()
