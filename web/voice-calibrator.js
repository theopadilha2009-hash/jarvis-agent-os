"use strict";

window.JarvisVoiceCalibrator = (() => {
  const STORAGE_KEY = "jarvis-voice-profile-v1";
  const PRESETS = Object.freeze({
    natural: { label: "Natural", stability: 0.64, similarity_boost: 0.82, speed: 0.93 },
    serious: { label: "Sério", stability: 0.74, similarity_boost: 0.86, speed: 0.89 },
    calm: { label: "Tranquilo", stability: 0.80, similarity_boost: 0.80, speed: 0.86 },
    direct: { label: "Direto", stability: 0.58, similarity_boost: 0.84, speed: 1.00 },
  });
  let state = load();

  if (!document.querySelector("link[data-jarvis-voice-calibrator]")) {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/ui/voice-calibrator.css?v=20260813-voicecal1";
    stylesheet.dataset.jarvisVoiceCalibrator = "true";
    document.head.appendChild(stylesheet);
  }

  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved && (PRESETS[saved.preset] || saved.preset === "custom")) return { ...PRESETS.natural, ...saved };
    } catch { /* perfil padrão */ }
    return { preset: "natural", ...PRESETS.natural };
  }

  function profile() {
    return {
      preset: state.preset,
      stability: Number(state.stability),
      similarity_boost: Number(state.similarity_boost),
      speed: Number(state.speed),
    };
  }

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile())); } catch { /* sessão atual */ }
  }

  function valueLabel(name, value) {
    if (name === "speed") return `${Number(value).toFixed(2)}×`;
    return `${Math.round(Number(value) * 100)}%`;
  }

  function sync() {
    document.querySelectorAll("[data-voice-preset]").forEach((button) => {
      button.dataset.active = String(button.dataset.voicePreset === state.preset);
    });
    document.querySelectorAll("[data-voice-setting]").forEach((input) => {
      input.value = state[input.dataset.voiceSetting];
      const output = document.querySelector(`[data-voice-output="${input.dataset.voiceSetting}"]`);
      if (output) output.textContent = valueLabel(input.dataset.voiceSetting, input.value);
    });
    const current = document.getElementById("voicePresetCurrent");
    if (current) current.textContent = PRESETS[state.preset]?.label || "Personalizado";
  }

  function mount() {
    const target = document.getElementById("voiceTuningMount");
    if (!target || target.dataset.ready) return;
    target.dataset.ready = "true";
    target.innerHTML = `
      <div class="dialog-head voice-calibrator-head"><span><small>ENTREGA DA VOZ</small><b>Calibrador</b></span><button id="voiceTuningClose" type="button" aria-label="Fechar calibrador">×</button></div>
      <section class="voice-calibrator-body">
        <div class="voice-preset-head"><span><small>PERFIL ATUAL</small><strong id="voicePresetCurrent">Natural</strong></span><p>O tom muda a entrega da voz, sem aplicar pitch artificial.</p></div>
        <div class="voice-presets" aria-label="Tom da voz">
          ${Object.entries(PRESETS).map(([id, item]) => `<button type="button" data-voice-preset="${id}">${item.label}</button>`).join("")}
        </div>
        <div class="voice-sliders">
          <label><span>Seriedade <output data-voice-output="stability"></output></span><input type="range" min="0.35" max="0.90" step="0.01" data-voice-setting="stability"></label>
          <label><span>Presença <output data-voice-output="similarity_boost"></output></span><input type="range" min="0.55" max="0.95" step="0.01" data-voice-setting="similarity_boost"></label>
          <label><span>Velocidade <output data-voice-output="speed"></output></span><input type="range" min="0.75" max="1.10" step="0.01" data-voice-setting="speed"></label>
        </div>
        <div class="voice-calibrator-actions"><button id="voiceResetButton" type="button">Restaurar natural</button><button id="voicePreviewButton" type="button">Ouvir teste</button></div>
        <p class="voice-calibrator-note" id="voiceCalibratorNote">As escolhas ficam somente neste dispositivo e valem a partir da próxima fala.</p>
      </section>`;
    target.querySelectorAll("[data-voice-preset]").forEach((button) => button.addEventListener("click", () => {
      state = { preset: button.dataset.voicePreset, ...PRESETS[button.dataset.voicePreset] };
      save();
      sync();
    }));
    target.querySelectorAll("[data-voice-setting]").forEach((input) => input.addEventListener("input", () => {
      state[input.dataset.voiceSetting] = Number(input.value);
      state.preset = "custom";
      save();
      sync();
    }));
    document.getElementById("voiceResetButton").addEventListener("click", () => {
      state = { preset: "natural", ...PRESETS.natural };
      save();
      sync();
    });
    document.getElementById("voicePreviewButton").addEventListener("click", () => {
      document.getElementById("voiceCalibratorNote").textContent = "Preparando uma amostra com o perfil atual…";
      window.JarvisVoicePreview?.();
    });
    document.getElementById("voiceTuningClose").addEventListener("click", close);
    sync();
  }

  function open() {
    mount();
    document.getElementById("voiceTuningDialog")?.showModal();
  }

  function close() { document.getElementById("voiceTuningDialog")?.close(); }

  document.getElementById("voiceTuningButton")?.addEventListener("click", open);
  open();
  return Object.freeze({ profile });
})();
