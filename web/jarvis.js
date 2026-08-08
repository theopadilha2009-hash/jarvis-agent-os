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
  const OWNER_TOKEN_KEY = "jarvis-owner-token-v1";
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceSupport = {
    input: Boolean(Recognition),
  };

  const session = {
    listening: false,
    speaking: false,
    voicePending: false,
    working: false,
    elevenlabs: false,
    voiceError: "",
    muted: (() => {
      try {
        return localStorage.getItem("jarvis-voice-muted") === "1";
      } catch {
        return false;
      }
    })(),
    responseState: "",
    history: [],
    paired: false,
    deviceOnline: false,
    deviceBridge: false,
  };
  let currentAudio = null;
  let currentAudioUrl = "";
  let currentSpeechController = null;
  let speechGeneration = 0;
  let voiceFailureNotified = false;

  function ownerToken() {
    try {
      return localStorage.getItem(OWNER_TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  const stateLabels = {
    idle: ["PRESENÇA", "aguardando você"],
    listening: ["ESCUTA", "ouvindo sua voz"],
    thinking: ["RACIOCÍNIO", "conectando contexto e ferramentas"],
    voice: ["VOZ", "preparando uma resposta natural"],
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
    byId("conversationState").textContent = label;
    byId("voiceLink").textContent = normalized === "listening"
      ? "recebendo voz"
      : normalized === "speaking"
        ? "transmitindo resposta"
        : session.voiceError
          ? session.voiceError
        : voiceSupport.input || session.elevenlabs
          ? "link disponível"
          : "indisponível neste navegador";
    window.dispatchEvent(new CustomEvent("jarvis-state", { detail: { state: normalized } }));
  }

  function settleState() {
    if (session.listening) return setVisualState("listening");
    if (session.speaking) return setVisualState("speaking");
    if (session.voicePending) return setVisualState("voice");
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

  function speechText(value) {
    const clean = String(value ?? "")
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1")
      .replace(/[*_#>|~]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (clean.length <= 900) return clean;
    const excerpt = clean.slice(0, 900);
    const naturalEnd = Math.max(excerpt.lastIndexOf(". "), excerpt.lastIndexOf("! "), excerpt.lastIndexOf("? "));
    return `${excerpt.slice(0, naturalEnd > 520 ? naturalEnd + 1 : 900).trim()}…`;
  }

  function compactCaption(value, fallback = "Estou aqui.") {
    const clean = speechText(value);
    if (!clean) return fallback;
    const sentence = clean.match(/^.{1,150}?[.!?](?=\s|$)/)?.[0] || clean.slice(0, 148);
    return clean.length > sentence.length && !/[.!?]$/.test(sentence)
      ? `${sentence.trim()}…`
      : sentence.trim();
  }

  function messageHtml(value) {
    return escapeHtml(value)
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`\n]+)`/g, "<code class=\"inline-code\">$1</code>");
  }

  function addMessage(text, type = "jarvis", extraHtml = "") {
    byId("welcomeMessage")?.remove();
    stage.classList.add("has-conversation");
    const message = document.createElement("div");
    message.className = `message ${type}`;
    message.innerHTML = `<span>${messageHtml(text)}</span>${extraHtml}`;
    feed.appendChild(message);
    feed.scrollTop = feed.scrollHeight;
    return message;
  }

  function setRequest(command) {
    byId("requestTitle").textContent = "Executando pedido";
    byId("requestText").textContent = command;
    byId("spokenCaption").textContent = compactCaption(command, "Entendi. Deixe comigo.");
    byId("contextCount").textContent = `${Math.ceil(session.history.length / 2)} turnos`;
  }

  function canvasRows(items) {
    return items.slice(0, 6).map((item, index) => {
      const text = typeof item === "string" ? item : item.action || item.step || item.name || item.path || "item";
      return `<div class="canvas-row"><i>${index + 1}</i><span>${escapeHtml(text)}</span></div>`;
    }).join("");
  }

  function agendaDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("pt-BR", {
      timeZone: "America/Sao_Paulo",
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function renderLiveCanvas(data) {
    const empty = byId("canvasEmpty");
    const content = byId("canvasContent");
    let html = "";
    if (data.memory_suggestion) {
      html = `<div class="canvas-row"><i>◇</i><span>Memória sugerida</span></div><div class="canvas-result">${escapeHtml(data.memory_suggestion)}</div>`;
    }
    else if (data.job?.id) {
      const target = data.job.target ? ` · ${data.job.target}` : "";
      html = `<div class="canvas-row"><i>↗</i><span>Ação ${escapeHtml(data.job.id)} · ${escapeHtml(data.job.status || "pending")}${escapeHtml(target)}</span></div>`;
      if (data.job.artifact_url) {
        html += `<a class="artifact-link" href="${escapeHtml(data.job.artifact_url)}" target="_blank" rel="noopener noreferrer"><img class="artifact-preview" src="${escapeHtml(data.job.artifact_url)}" alt="Captura privada criada pelo worker do Mac"></a>`;
      }
      if (data.job.result) html += `<div class="canvas-result">${escapeHtml(data.job.result).slice(0, 1800)}</div>`;
    }
    else if (Array.isArray(data.agenda) && data.agenda.length) {
      html = data.agenda.slice(0, 8).map((item) => {
        const scheduled = agendaDate(item.scheduled_for);
        const label = scheduled ? `${item.title || "item da agenda"} · ${scheduled}` : item.title || "item da agenda";
        return `<div class="canvas-row"><i>${escapeHtml(item.id || "·")}</i><span>${escapeHtml(label)}</span></div>`;
      }).join("");
    }
    else if (Array.isArray(data.contacts) && data.contacts.length) {
      html = data.contacts.slice(0, 8).map((item, index) => (
        `<div class="canvas-row"><i>${index + 1}</i><span>${escapeHtml(item.display_name || item.alias)} · ${escapeHtml(item.phone || "")}</span></div>`
      )).join("");
    }
    else if (Array.isArray(data.steps) && data.steps.length) html = canvasRows(data.steps);
    else if (Array.isArray(data.sources) && data.sources.length) html = canvasRows(data.sources);
    else if (data.result) html = `<div class="canvas-result">${escapeHtml(data.result).slice(0, 1800)}</div>`;
    else if (data.local_command) html = `<div class="canvas-row"><i>→</i><span>Worker local preparado</span></div><div class="canvas-result">${escapeHtml(data.local_command)}</div>`;
    else if (data.provider === "openrouter") html = `<div class="canvas-row"><i>✓</i><span>Resposta pronta para você</span></div>`;
    else if (data.message) html = `<div class="canvas-result">${escapeHtml(data.message).slice(0, 320)}</div>`;
    content.innerHTML = html;
    empty.hidden = Boolean(html);
  }

  function renderActionHistory(items) {
    const target = byId("actionHistory");
    if (!target) return;
    if (!Array.isArray(items) || !items.length) {
      target.innerHTML = "<small>Nenhuma ação registrada.</small>";
      return;
    }
    target.innerHTML = items.slice(0, 8).map((item) => {
      const suffix = item.target ? ` · ${escapeHtml(item.target)}` : "";
      return `<div class="history-row" data-status="${escapeHtml(item.status || "unknown")}"><i></i><span><b>${escapeHtml(item.action || "ação")}</b>${suffix}<small>${escapeHtml(item.status || "unknown")}</small></span></div>`;
    }).join("");
  }

  async function refreshActionHistory(options = {}) {
    if (!session.paired || !session.deviceBridge) return renderActionHistory([]);
    try {
      const data = await request("/device-history?limit=8");
      renderActionHistory(data.history || []);
      if (options.revealLatest) {
        const artifact = (data.history || []).find((item) => item.artifact_url);
        if (artifact) renderLiveCanvas({ job: artifact });
      }
    } catch {
      renderActionHistory([]);
    }
  }

  async function request(path, options) {
    const requestOptions = { ...(options || {}) };
    const headers = new Headers(requestOptions.headers || {});
    const token = ownerToken();
    if (token) headers.set("X-Jarvis-Owner-Token", token);
    requestOptions.headers = headers;
    const response = await fetch(path, requestOptions);
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
    session.voicePending = false;
    session.speaking = true;
    byId("spokenCaption").textContent = compactCaption(clean);
    settleState();
  }

  function finishSpeaking() {
    session.speaking = false;
    byId("spokenCaption").textContent = "";
    settleState();
  }

  function stopSpeechOutput() {
    speechGeneration += 1;
    session.voicePending = false;
    currentSpeechController?.abort();
    currentSpeechController = null;
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

  function reportVoiceFailure(status, terminal = false) {
    session.voiceError = status;
    if (terminal) session.elevenlabs = false;
    byId("voiceValue").textContent = status;
    byId("voiceLink").textContent = status.toLowerCase();
    byId("integrationValue").textContent = `IA · ${status}`;
    byId("integrationHint").textContent = "A conversa continua em texto; a saída humana aguarda cota válida da ElevenLabs.";
    if (!voiceFailureNotified) {
      voiceFailureNotified = true;
      addMessage(`Áudio não reproduzido: ${status}. A resposta em texto continua funcionando.`, "voice-status");
    }
  }

  async function speak(text) {
    if (!text) return;
    const clean = speechText(text);
    if (!clean) return false;
    stopSpeechOutput();
    if (session.muted) return false;
    const generation = speechGeneration;
    if (!session.elevenlabs) return false;
    session.voicePending = true;
    byId("spokenCaption").textContent = "Preparando voz…";
    settleState();
    const controller = new AbortController();
    currentSpeechController = controller;
    try {
      const response = await fetch("/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: clean }),
        signal: controller.signal,
      });
      if (generation !== speechGeneration || controller !== currentSpeechController) return false;
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}));
        throw new Error(failure.error_code || "elevenlabs_unavailable");
      }
      const audioBlob = await response.blob();
      if (generation !== speechGeneration || controller !== currentSpeechController) return false;
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      currentAudioUrl = audioUrl;
      currentAudio = audio;
      audio.onplay = () => {
        if (generation === speechGeneration) beginSpeaking(clean);
      };
      audio.onended = () => {
        if (generation === speechGeneration) finishSpeaking();
      };
      audio.onerror = () => {
        if (generation === speechGeneration) finishSpeaking();
      };
      if (generation !== speechGeneration || controller !== currentSpeechController) {
        URL.revokeObjectURL(audioUrl);
        return false;
      }
      await audio.play();
      session.voiceError = "";
      voiceFailureNotified = false;
      return true;
    } catch (error) {
      if (error?.name === "AbortError") return false;
      if (generation === speechGeneration) {
        finishSpeaking();
        const errorCode = error?.message;
        const status = {
          elevenlabs_quota: "ElevenLabs sem créditos",
          elevenlabs_authorization: "ElevenLabs sem autorização",
          elevenlabs_rate_limit: "ElevenLabs no limite",
        }[errorCode] || "ElevenLabs indisponível";
        reportVoiceFailure(status, ["elevenlabs_quota", "elevenlabs_authorization"].includes(errorCode));
      }
      return false;
    } finally {
      if (generation === speechGeneration) {
        session.voicePending = false;
        settleState();
      }
      if (controller === currentSpeechController) currentSpeechController = null;
    }
  }

  async function monitorDeviceCommand(jobId, message) {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
      let data;
      try {
        data = await request(`/device-command?id=${encodeURIComponent(jobId)}`);
      } catch {
        continue;
      }
      if (data?.pairing_required) return;
      if (!data?.job) continue;
      renderLiveCanvas(data);
      byId("activityValue").textContent = `${data.message} · ação ${jobId}`;
      if (["succeeded", "failed"].includes(data.job.status)) {
        const text = data.job.result ? `${data.message}\n${data.job.result}` : data.message;
        message.querySelector("span").textContent = text;
        message.classList.toggle("error", data.job.status === "failed");
        session.responseState = data.visual_state || (data.job.status === "succeeded" ? "success" : "error");
        byId("requestTitle").textContent = data.job.status === "succeeded" ? "Ação concluída" : "Ação falhou";
        refreshActionHistory();
        settleState();
        return;
      }
      message.querySelector("span").textContent = data.message;
      session.responseState = "local";
      settleState();
    }
    message.querySelector("span").textContent = "O pedido continua na fila; o worker do Mac não confirmou dentro de um minuto.";
  }

  function showResponse(data) {
    if (!data || data.ok === false) {
      const error = data?.error || data?.message || "Não consegui completar isso.";
      session.responseState = "error";
      addMessage(error, "error");
      renderLiveCanvas({ message: error });
      settleState();
      speak(error);
      if (data?.pairing_required) {
        dialog.showModal();
        window.setTimeout(() => byId("ownerTokenInput").focus(), 30);
      }
      return;
    }

    session.responseState = data.visual_state || (data.executed_locally ? "success" : "response");
    const answer = data.message || data.summary || data.next_action || data.status_real || "Pronto.";
    let extra = "";
    if (data.memory_suggestion) {
      extra = `<button class="memory-command" type="button">Guardar na memória</button>`;
    }
    if (data.local_command) {
      extra += `<button class="copy-command" type="button">Copiar comando local</button><details><summary>ver comando</summary><code>${escapeHtml(data.local_command)}</code></details>`;
    }
    if (data.result) {
      extra += `<details><summary>ver resultado completo</summary><code>${escapeHtml(data.result)}</code></details>`;
    }
    if (session.elevenlabs) {
      extra += `<button class="speak-command" type="button">Ouvir</button>`;
    }
    const message = addMessage(answer, "jarvis", extra);
    const copy = message.querySelector(".copy-command");
    if (copy) copy.addEventListener("click", async () => {
      await navigator.clipboard.writeText(data.local_command);
      copy.textContent = "Copiado";
    });
    const memory = message.querySelector(".memory-command");
    if (memory) memory.addEventListener("click", () => {
      memory.disabled = true;
      memory.textContent = "Preparando memória…";
      sendCommand(`guarde na memória como preferência: ${data.memory_suggestion}`);
    });
    const replay = message.querySelector(".speak-command");
    if (replay) replay.addEventListener("click", async () => {
      replay.disabled = true;
      replay.textContent = "Gerando áudio…";
      const played = await speak(answer);
      replay.disabled = false;
      replay.textContent = played ? "Reproduzir novamente" : "Tentar voz novamente";
    });
    byId("activityValue").textContent = data.executed_locally ? `Executado localmente · ${data.intent || "ação"}` : answer;
    byId("requestTitle").textContent = data.memory_suggestion ? "Memória sugerida" : data.job?.id ? "Ação enviada ao Mac" : data.executed_locally ? "Ação local" : data.provider === "n8n" ? "Automação concluída" : "Resposta pronta";
    renderLiveCanvas(data);
    if (data.job?.id && ["pending", "running"].includes(data.job.status)) {
      monitorDeviceCommand(data.job.id, message);
    }
    if (session.responseState === "memory") window.dispatchEvent(new CustomEvent("jarvis-memory-refresh"));
    settleState();
    speak(answer);
  }

  async function sendCommand(rawValue, options = {}) {
    const command = String(rawValue || "").trim();
    if (!command) return;
    session.responseState = "";
    addMessage(command, options.source === "voice" ? "user voice" : "user");
    input.value = "";
    session.history.push({ role: "user", content: command });
    session.history = session.history.slice(-12);
    setRequest(command);
    setWorking(true);
    try {
      const data = await request("/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, messages: session.history, input_mode: options.source || "text" }),
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
        sendCommand(transcript, { source: "voice" });
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
    voiceButton.title = "Clique, fale normalmente e o comando será enviado quando você terminar.";
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
      session.paired = Boolean(status.owner_pairing?.authenticated || !status.owner_pairing?.required);
      session.deviceBridge = Boolean(status.device_bridge?.configured);
      session.elevenlabs = Boolean(status.voice?.configured);
      session.voiceError = "";
      byId("voiceValue").textContent = session.elevenlabs
        ? `ElevenLabs${voiceSupport.input ? " + microfone" : ""}`
        : voiceSupport.input
          ? "microfone ativo · saída aguarda ElevenLabs"
          : "ElevenLabs aguarda chave";
      const ready = [
        status.ai?.configured ? "IA" : "",
        status.voice?.configured ? "ElevenLabs" : voiceSupport.input ? "microfone" : "",
        status.automations?.n8n?.configured ? "n8n" : "",
        session.paired && status.device_bridge?.configured ? "Mac pareado" : "",
        status.runtime === "local_web_preview" ? "worker local" : "",
      ].filter(Boolean);
      byId("integrationValue").textContent = ready.join(" · ") || "sem integrações externas";
      byId("integrationHint").textContent = status.automations?.n8n?.configured
        ? "Agenda e tarefas conectadas ao n8n."
        : status.automations?.agenda?.provider === "supabase"
          ? "Agenda privada no Supabase; n8n continua opcional. Ações do Mac usam o worker local."
          : "Agenda aguarda o webhook n8n; ações do Mac usam o worker local.";
      byId("runtimeLabel").textContent = status.runtime === "local_web_preview" ? "Mac local" : "Vercel";
      const tokenInput = byId("ownerTokenInput");
      tokenInput.value = ownerToken();
      byId("pairingHint").textContent = session.paired
        ? "Navegador pareado. O token permanece somente neste navegador."
        : status.owner_pairing?.required
          ? "Informe o token privado do Theo para memória, agenda e ações no Mac."
          : "Pareamento ainda não foi exigido neste ambiente.";
      const workerValue = byId("workerValue");
      if (session.paired && status.device_bridge?.configured) {
        const worker = await request("/device-worker-status");
        session.deviceOnline = Boolean(worker.online);
        workerValue.textContent = worker.online
          ? `Mac conectado · ${worker.hostname || "worker local"}`
          : "Mac offline · abra ou instale o worker local";
        await refreshActionHistory({ revealLatest: true });
      } else {
        session.deviceOnline = status.runtime === "local_web_preview";
        workerValue.textContent = session.paired
          ? "Ponte remota ainda não configurada"
          : "Navegador não pareado";
      }
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
  byId("detailsButton").addEventListener("click", () => {
    dialog.showModal();
    refreshActionHistory();
  });
  byId("saveOwnerToken").addEventListener("click", async () => {
    const token = byId("ownerTokenInput").value.trim();
    if (!token) {
      byId("pairingHint").textContent = "Cole o token privado antes de conectar.";
      return;
    }
    try {
      localStorage.setItem(OWNER_TOKEN_KEY, token);
    } catch {
      byId("pairingHint").textContent = "Este navegador bloqueou o armazenamento local.";
      return;
    }
    byId("pairingHint").textContent = "Validando pareamento…";
    await boot();
    if (session.paired) dialog.close();
  });
  byId("clearOwnerToken").addEventListener("click", async () => {
    try {
      localStorage.removeItem(OWNER_TOKEN_KEY);
    } catch {
      // A sessão ainda será atualizada mesmo se o navegador bloquear storage.
    }
    byId("ownerTokenInput").value = "";
    session.paired = false;
    await boot();
  });
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
