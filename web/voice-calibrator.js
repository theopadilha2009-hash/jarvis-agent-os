"use strict";

window.JarvisVoiceCalibrator = (() => {
  const STORAGE_KEY = "jarvis-voice-profile-v1";
  const PRESETS = Object.freeze({
    natural: { label: "Natural", stability: 0.64, similarity_boost: 0.82, speed: 0.93, pitch: 0.92, tempo: 1.04 },
    serious: { label: "Sério", stability: 0.74, similarity_boost: 0.86, speed: 0.89, pitch: 0.88, tempo: 1.08 },
    calm: { label: "Tranquilo", stability: 0.80, similarity_boost: 0.80, speed: 0.86, pitch: 0.90, tempo: 1.06 },
    direct: { label: "Direto", stability: 0.58, similarity_boost: 0.84, speed: 1.00, pitch: 0.94, tempo: 1.02 },
    command: { label: "Comando", stability: 0.78, similarity_boost: 0.88, speed: 0.88, pitch: 0.82, tempo: 1.14 },
  });
  let state = load();

  if (!document.querySelector("link[data-jarvis-voice-calibrator]")) {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/ui/voice-calibrator.css?v=20260815-vozes2";
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
      // Timbre da voz própria: grave e ritmo, aplicados no servidor local.
      pitch: Number(state.pitch ?? 0.92),
      tempo: Number(state.tempo ?? 1.04),
    };
  }

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile())); } catch { /* sessão atual */ }
  }

  function valueLabel(name, value) {
    if (name === "speed" || name === "tempo") return `${Number(value).toFixed(2)}×`;
    if (name === "pitch") return `${Number(value).toFixed(2)}× grave`;
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
          <label><span>Gravidade <output data-voice-output="pitch"></output></span><input type="range" min="0.70" max="1.10" step="0.01" data-voice-setting="pitch"></label>
          <label><span>Cadência <output data-voice-output="tempo"></output></span><input type="range" min="0.80" max="1.40" step="0.01" data-voice-setting="tempo"></label>
        </div>
        <div class="voice-picker">
          <div class="voice-picker-head"><span><small>VOZ ATIVA</small><strong id="voiceActiveName">carregando…</strong></span><button id="voiceReloadButton" type="button">Atualizar</button></div>
          <div class="voice-list" id="voiceList" aria-live="polite"><p class="voice-empty">Buscando vozes disponíveis…</p></div>
          <form class="voice-add" id="voiceAddForm">
            <input id="voiceAddId" type="text" placeholder="Voice ID da ElevenLabs" aria-label="Voice ID" autocomplete="off">
            <input id="voiceAddName" type="text" placeholder="Nome" aria-label="Nome da voz" autocomplete="off">
            <button type="submit">Adicionar</button>
          </form>
        </div>
        <label class="voice-wake"><input type="checkbox" id="voiceWakeToggle"><span><b>Atender pelo nome</b><small>"fala jarvis", "e aí ultron" e variações, com o microfone sempre pronto.</small></span></label>
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
    document.getElementById("voiceReloadButton").addEventListener("click", () => loadVoices(true));
    const wake = document.getElementById("voiceWakeToggle");
    wake.checked = window.JarvisWakeWord ? window.JarvisWakeWord.enabled() : true;
    wake.addEventListener("change", () => {
      window.JarvisWakeWord?.set(wake.checked);
      note(wake.checked ? "Pode me chamar pelo nome." : "Só respondo ao botão do microfone agora.");
    });
    document.getElementById("voiceAddForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const id = document.getElementById("voiceAddId").value.trim();
      const name = document.getElementById("voiceAddName").value.trim() || "Voz adicionada";
      if (id) selectVoice(id, name);
    });
    sync();
    loadVoices();
  }

  async function api(path, options) {
    const token = (() => {
      try { return localStorage.getItem("jarvis-owner-token-v1") || ""; } catch { return ""; }
    })();
    const headers = { "Content-Type": "application/json" };
    if (token) headers["X-Jarvis-Owner-Token"] = token;
    const response = await fetch(path, { headers, ...options });
    return response.json().catch(() => ({ ok: false, error: "Resposta inválida." }));
  }

  function note(text) {
    const target = document.getElementById("voiceCalibratorNote");
    if (target) target.textContent = text;
  }

  async function selectVoice(voiceId, name) {
    note(`Trocando para ${name}…`);
    try {
      const data = await api("/voice-select", { method: "POST", body: JSON.stringify({ voice_id: voiceId, name }) });
      note(data.ok ? data.message : (data.error || "A troca de voz não foi confirmada."));
      if (data.ok) loadVoices(true);
    } catch {
      note("Não consegui falar com o servidor para trocar a voz.");
    }
  }

  async function loadVoices(force = false) {
    const list = document.getElementById("voiceList");
    if (!list) return;
    if (force) list.innerHTML = '<p class="voice-empty">Atualizando…</p>';
    try {
      const data = await api("/voices");
      const active = document.getElementById("voiceActiveName");
      if (active) active.textContent = data.active?.name || "padrão";
      const rows = Array.isArray(data.voices) ? data.voices : [];
      if (!rows.length) {
        list.innerHTML = '<p class="voice-empty">Nenhuma voz disponível: configure a ElevenLabs, a OpenAI ou a voz própria.</p>';
        return;
      }
      list.innerHTML = rows.map((voice) => `
        <button type="button" class="voice-row" data-voice-id="${voice.id}" data-voice-name="${(voice.name || "").replace(/"/g, "&quot;")}" data-active="${Boolean(voice.active)}" ${data.can_change ? "" : "disabled"}>
          <span><b>${voice.name || "Voz"}</b><small>${voice.provider}${voice.category ? ` · ${voice.category}` : ""}</small></span>
          <em>${voice.active ? "ativa" : (data.can_change ? "usar" : "bloqueada")}</em>
        </button>`).join("");
      list.querySelectorAll("[data-voice-id]").forEach((button) => button.addEventListener("click", () => {
        selectVoice(button.dataset.voiceId, button.dataset.voiceName);
      }));
    } catch {
      list.innerHTML = '<p class="voice-empty">Não consegui listar as vozes agora.</p>';
    }
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
