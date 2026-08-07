(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const stage = byId("stage");
  const feed = byId("conversationFeed");
  const input = byId("commandInput");
  const sendButton = byId("sendButton");
  const voiceButton = byId("voiceButton");
  const muteButton = byId("muteButton");
  const dialog = byId("systemDialog");
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceSupport = {
    input: Boolean(Recognition),
  };

  const session = {
    listening: false,
    speaking: false,
    working: false,
    elevenlabs: false,
    muted: (() => {
      try {
        return localStorage.getItem("jarvis-voice-muted") === "1";
      } catch {
        return false;
      }
    })(),
    responseState: "",
    history: [],
  };
  let currentAudio = null;
  let currentAudioUrl = "";
  let speechGeneration = 0;

  const stateLabels = {
    idle: ["PRESENÇA", "aguardando você"],
    listening: ["ESCUTA", "ouvindo sua voz"],
    thinking: ["RACIOCÍNIO", "conectando contexto e ferramentas"],
    planning: ["PLANO", "organizando a execução"],
    speaking: ["RESPOSTA", "falando com você"],
    response: ["RESPOSTA", "resultado disponível"],
    memory: ["MEMÓRIA", "indexando conhecimento local"],
    local: ["WORKER LOCAL", "ação preparada no Mac"],
    success: ["CONCLUÍDO", "ação finalizada"],
    error: ["ATENÇÃO", "a ação encontrou um problema"],
    offline: ["OFFLINE", "runtime indisponível"],
  };

  function setVisualState(state) {
    const normalized = state || "idle";
    const [mode, label] = stateLabels[normalized] || stateLabels.idle;
    stage.dataset.state = normalized;
    byId("modeLabel").textContent = mode;
    byId("stateLabel").textContent = label;
    byId("voiceLink").textContent = normalized === "listening"
      ? "recebendo voz"
      : normalized === "speaking"
        ? "transmitindo resposta"
        : voiceSupport.input || session.elevenlabs
          ? "link disponível"
          : "indisponível neste navegador";
    window.dispatchEvent(new CustomEvent("jarvis-state", { detail: { state: normalized } }));
  }

  function settleState() {
    if (session.listening) return setVisualState("listening");
    if (session.speaking) return setVisualState("speaking");
    if (session.working) return setVisualState("thinking");
    setVisualState(session.responseState || "idle");
  }

  function setWorking(value) {
    session.working = value;
    sendButton.disabled = value;
    sendButton.textContent = value ? "Pensando…" : "Enviar";
    settleState();
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function addMessage(text, type = "jarvis", extraHtml = "") {
    byId("welcomeMessage")?.remove();
    const message = document.createElement("div");
    message.className = `message ${type}`;
    message.innerHTML = `<span>${escapeHtml(text)}</span>${extraHtml}`;
    feed.appendChild(message);
    feed.scrollTop = feed.scrollHeight;
    return message;
  }

  function setRequest(command) {
    byId("requestTitle").textContent = "Executando pedido";
    byId("requestText").textContent = command;
    byId("spokenCaption").textContent = command;
    byId("contextCount").textContent = `${Math.ceil(session.history.length / 2)} turnos`;
  }

  function canvasRows(items) {
    return items.slice(0, 6).map((item, index) => {
      const text = typeof item === "string" ? item : item.action || item.step || item.name || item.path || "item";
      return `<div class="canvas-row"><i>${index + 1}</i><span>${escapeHtml(text)}</span></div>`;
    }).join("");
  }

  function renderLiveCanvas(data) {
    const empty = byId("canvasEmpty");
    const content = byId("canvasContent");
    let html = "";
    if (Array.isArray(data.steps) && data.steps.length) html = canvasRows(data.steps);
    else if (Array.isArray(data.sources) && data.sources.length) html = canvasRows(data.sources);
    else if (data.result) html = `<div class="canvas-result">${escapeHtml(data.result).slice(0, 1800)}</div>`;
    else if (data.local_command) html = `<div class="canvas-row"><i>→</i><span>Worker local preparado</span></div><div class="canvas-result">${escapeHtml(data.local_command)}</div>`;
    else if (data.message) html = `<div class="canvas-result">${escapeHtml(data.message).slice(0, 900)}</div>`;
    content.innerHTML = html;
    empty.hidden = Boolean(html);
  }

  async function request(path, options) {
    const response = await fetch(path, options);
    let data;
    try {
      data = await response.json();
    } catch {
      data = { ok: false, error: "O runtime respondeu em um formato inválido." };
    }
    if (!response.ok && data.ok !== false) data.ok = false;
    return data;
  }

  function beginSpeaking(clean) {
    session.speaking = true;
    byId("spokenCaption").textContent = clean;
    settleState();
  }

  function finishSpeaking() {
    session.speaking = false;
    settleState();
  }

  function stopSpeechOutput() {
    speechGeneration += 1;
    currentAudio?.pause();
    currentAudio = null;
    if (currentAudioUrl) URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = "";
    if (session.speaking) finishSpeaking();
  }

  function renderMuteState() {
    muteButton.textContent = session.muted ? "Fala muda" : "Fala ligada";
    muteButton.setAttribute("aria-pressed", String(session.muted));
    muteButton.title = session.muted ? "Ativar a voz do JARVIS" : "Mutar a voz do JARVIS";
  }

  async function speak(text) {
    if (!text) return;
    const clean = String(text).replace(/\s+/g, " ").slice(0, 2200);
    stopSpeechOutput();
    if (session.muted) return false;
    const generation = speechGeneration;
    if (!session.elevenlabs) return false;
    try {
      const response = await fetch("/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: clean }),
      });
      if (!response.ok) throw new Error("elevenlabs unavailable");
      currentAudioUrl = URL.createObjectURL(await response.blob());
      currentAudio = new Audio(currentAudioUrl);
      currentAudio.onplay = () => {
        if (generation === speechGeneration) beginSpeaking(clean);
      };
      currentAudio.onended = () => {
        if (generation === speechGeneration) finishSpeaking();
      };
      currentAudio.onerror = () => {
        if (generation === speechGeneration) finishSpeaking();
      };
      await currentAudio.play();
    } catch {
      if (generation === speechGeneration) {
        finishSpeaking();
        byId("voiceValue").textContent = "ElevenLabs indisponível";
      }
    }
    return true;
  }

  function showResponse(data) {
    if (!data || data.ok === false) {
      const error = data?.error || data?.message || "Não consegui completar isso.";
      session.responseState = "error";
      addMessage(error, "error");
      renderLiveCanvas({ message: error });
      settleState();
      speak(error);
      return;
    }

    session.responseState = data.visual_state || (data.executed_locally ? "success" : "response");
    const answer = data.message || data.summary || data.next_action || data.status_real || "Pronto.";
    let extra = "";
    if (data.local_command) {
      extra = `<button class="copy-command" type="button">Copiar comando local</button><details><summary>ver comando</summary><code>${escapeHtml(data.local_command)}</code></details>`;
    }
    if (data.result) {
      extra += `<details><summary>ver resultado completo</summary><code>${escapeHtml(data.result)}</code></details>`;
    }
    const message = addMessage(answer, "jarvis", extra);
    const copy = message.querySelector(".copy-command");
    if (copy) copy.addEventListener("click", async () => {
      await navigator.clipboard.writeText(data.local_command);
      copy.textContent = "Copiado";
    });
    byId("activityValue").textContent = data.executed_locally ? `Executado localmente · ${data.intent || "ação"}` : answer;
    byId("requestTitle").textContent = data.executed_locally ? "Ação local" : data.provider === "n8n" ? "Automação concluída" : "Resposta pronta";
    renderLiveCanvas(data);
    if (session.responseState === "memory") window.dispatchEvent(new CustomEvent("jarvis-memory-refresh"));
    settleState();
    speak(answer);
  }

  async function sendCommand(rawValue) {
    const command = String(rawValue || "").trim();
    if (!command) return;
    session.responseState = "";
    addMessage(command, "user");
    input.value = "";
    session.history.push({ role: "user", content: command });
    session.history = session.history.slice(-12);
    setRequest(command);
    setWorking(true);
    try {
      const data = await request("/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, messages: session.history }),
      });
      showResponse(data);
      const answer = data.message || data.summary;
      if (answer) session.history.push({ role: "assistant", content: answer });
    } catch {
      showResponse({ ok: false, error: "A conexão com o núcleo do JARVIS caiu." });
    } finally {
      setWorking(false);
      input.focus();
    }
  }

  function installVoiceInput() {
    if (!Recognition) {
      voiceButton.disabled = true;
      byId("voiceValue").textContent = "resposta apenas";
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "pt-BR";
    recognition.interimResults = true;
    recognition.continuous = false;
    let submitted = false;
    recognition.onstart = () => {
      submitted = false;
      session.listening = true;
      voiceButton.classList.add("listening");
      byId("spokenCaption").textContent = "Estou ouvindo…";
      settleState();
    };
    recognition.onresult = (event) => {
      const rows = Array.from(event.results);
      const transcript = rows.map((row) => row[0].transcript).join(" ").trim();
      input.value = transcript;
      byId("spokenCaption").textContent = transcript || "Estou ouvindo…";
      if (!submitted && rows.at(-1)?.isFinal && transcript) {
        submitted = true;
        recognition.stop();
        sendCommand(transcript);
      }
    };
    recognition.onerror = (event) => {
      if (!["aborted", "no-speech"].includes(event.error)) {
        const message = event.error === "not-allowed" ? "Libere o microfone para falar comigo." : "Não entendi o áudio. Tente novamente.";
        addMessage(message, "error");
      }
    };
    recognition.onend = () => {
      session.listening = false;
      voiceButton.classList.remove("listening");
      settleState();
    };
    voiceButton.addEventListener("click", () => {
      if (session.listening) {
        recognition.abort();
        return;
      }
      stopSpeechOutput();
      try {
        recognition.start();
      } catch {
        addMessage("O microfone já está iniciando. Aguarde um instante.", "error");
      }
    });
    byId("voiceValue").textContent = "ouvir e responder";
  }

  async function boot() {
    try {
      const status = await request("/status");
      byId("connectionDot").classList.toggle("online", Boolean(status.ok));
      byId("connectionText").textContent = status.ok ? "online" : "offline";
      byId("serviceValue").textContent = status.service || "jarvis-web";
      byId("aiValue").textContent = status.ai?.configured ? "OpenRouter conectado" : "OpenRouter não configurado";
      byId("modelValue").textContent = status.ai?.model || "—";
      session.elevenlabs = Boolean(status.voice?.configured);
      byId("voiceValue").textContent = session.elevenlabs
        ? `ElevenLabs${voiceSupport.input ? " + microfone" : ""}`
        : voiceSupport.input
          ? "microfone ativo · saída aguarda ElevenLabs"
          : "ElevenLabs aguarda chave";
      const ready = [
        status.ai?.configured ? "IA" : "",
        status.voice?.configured ? "ElevenLabs" : voiceSupport.input ? "microfone" : "",
        status.automations?.n8n?.configured ? "n8n" : "",
        status.runtime === "local_web_preview" ? "worker local" : "",
      ].filter(Boolean);
      byId("integrationValue").textContent = ready.join(" · ") || "sem integrações externas";
      byId("integrationHint").textContent = status.automations?.n8n?.configured
        ? "Agenda e tarefas conectadas ao n8n."
        : "Agenda aguarda o webhook n8n; ações do Mac usam o worker local.";
      byId("runtimeLabel").textContent = status.runtime === "local_web_preview" ? "Mac local" : "Vercel";
      setVisualState(status.ok ? "idle" : "offline");
    } catch {
      byId("connectionText").textContent = "offline";
      session.responseState = "offline";
      settleState();
    }
  }

  byId("commandForm").addEventListener("submit", (event) => {
    event.preventDefault();
    sendCommand(input.value);
  });
  byId("detailsButton").addEventListener("click", () => dialog.showModal());
  muteButton.addEventListener("click", () => {
    session.muted = !session.muted;
    try {
      localStorage.setItem("jarvis-voice-muted", session.muted ? "1" : "0");
    } catch {
      // The control still works for this session when storage is unavailable.
    }
    if (session.muted) stopSpeechOutput();
    renderMuteState();
  });
  byId("closeDialog").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  renderMuteState();
  installVoiceInput();
  boot();
})();
