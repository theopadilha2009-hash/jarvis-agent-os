(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const stage = byId("stage");
  const feed = byId("conversationFeed");
  const input = byId("commandInput");
  const sendButton = byId("sendButton");
  const voiceButton = byId("voiceButton");
  const dialog = byId("systemDialog");

  const session = {
    listening: false,
    speaking: false,
    working: false,
    responseState: "",
    history: [],
  };

  const stateLabels = {
    idle: ["PRESENÇA", "aguardando você"],
    listening: ["ESCUTA", "ouvindo sua voz"],
    thinking: ["RACIOCÍNIO", "conectando contexto e ferramentas"],
    planning: ["PLANO", "organizando a execução"],
    speaking: ["RESPOSTA", "falando com você"],
    response: ["RESPOSTA", "resultado disponível"],
    forge: ["FORJA", "construindo uma nova capacidade"],
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
    byId("voiceLink").textContent = normalized === "listening" ? "recebendo voz" : normalized === "speaking" ? "transmitindo resposta" : "link disponível";
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
    byId("requestTitle").textContent = command.toLowerCase().startsWith("forja") ? "Nova construção" : "Entendendo intenção";
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

  function chooseVoice() {
    const voices = speechSynthesis.getVoices();
    return voices.find((voice) => voice.lang === "pt-BR" && /felipe|daniel|thiago|antonio|antônio|google/i.test(voice.name))
      || voices.find((voice) => voice.lang === "pt-BR")
      || voices.find((voice) => voice.lang?.startsWith("pt"));
  }

  function speak(text) {
    if (!("speechSynthesis" in window) || !text) return;
    const clean = String(text).replace(/\s+/g, " ").slice(0, 2200);
    const utterance = new SpeechSynthesisUtterance(clean);
    const voice = chooseVoice();
    if (voice) utterance.voice = voice;
    utterance.lang = "pt-BR";
    utterance.rate = 1.02;
    utterance.pitch = 0.87;
    utterance.onstart = () => {
      session.speaking = true;
      byId("spokenCaption").textContent = clean;
      settleState();
    };
    utterance.onend = utterance.onerror = () => {
      session.speaking = false;
      settleState();
    };
    speechSynthesis.cancel();
    speechSynthesis.speak(utterance);
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
    byId("requestTitle").textContent = data.mode === "forge" ? "Forja em andamento" : data.executed_locally ? "Ação local" : "Resposta pronta";
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
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      voiceButton.disabled = true;
      byId("voiceValue").textContent = "resposta apenas";
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "pt-BR";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => {
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
      if (rows.at(-1)?.isFinal && transcript) sendCommand(transcript);
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
    voiceButton.addEventListener("click", () => session.listening ? recognition.abort() : recognition.start());
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
  byId("closeDialog").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  installVoiceInput();
  boot();
})();
