(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const stage = byId("stage");
  const feed = byId("conversationFeed");
  const input = byId("commandInput");
  const sendButton = byId("sendButton");
  const voiceButton = byId("voiceButton");
  const muteButton = byId("muteButton");
  const pulseButton = byId("pulseButton");
  const attachmentButton = byId("attachmentButton");
  const attachmentInput = byId("attachmentInput");
  const attachmentTray = byId("attachmentTray");
  const dialog = byId("systemDialog");
  const tourDialog = byId("tourDialog");
  const actionHub = byId("actionHub");
  const actionHubButton = byId("actionHubButton");
  const mobileChatToggle = byId("mobileChatToggle");
  const installButton = byId("installButton");
  const installDialog = byId("installDialog");
  const mobileLayout = window.matchMedia("(max-width: 720px)");
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
    workingState: "thinking",
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
    canceledJobs: new Set(),
    attachments: [],
    historyRestored: false,
    currentCommand: "",
    workingStartedAt: 0,
    lastResponseOk: true,
  };
  let currentAudio = null;
  let currentAudioUrl = "";
  let currentSpeechController = null;
  let speechGeneration = 0;
  let voiceFailureNotified = false;
  let currentPulse = null;
  let progressInterval = 0;
  let progressHideTimer = 0;
  let deferredInstallPrompt = null;
  let viewportCeiling = Math.round(window.visualViewport?.height || window.innerHeight);
  let viewportWidth = window.innerWidth;

  function ownerToken() {
    try {
      return localStorage.getItem(OWNER_TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  const ACTION_CATALOG = [
    { id: "search", label: "Pesquisar na web", command: "pesquise na web as notícias mais importantes de inteligência artificial hoje e cite as fontes", keywords: /pesquis|busc|google|internet|not[ií]cia|atual/i },
    { id: "spotify", label: "Abrir Spotify", command: "abra o Spotify", keywords: /m[uú]sica|spotify/i },
    { id: "steam", label: "Abrir Steam", command: "abra a Steam", keywords: /jogo|steam/i },
    { id: "record", label: "Gravar a tela", command: "abra o gravador de tela", keywords: /grav|tela|v[ií]deo/i },
    { id: "github", label: "Ver meu GitHub", command: "mostre meus repositórios do GitHub", keywords: /github|repo|c[oó]digo|pull/i },
    { id: "n8n", label: "Projetar fluxo n8n", command: "crie um blueprint n8n para a automação que eu descrever", keywords: /n\s*8\s*n|workflow|automa/i },
    { id: "memory", label: "Abrir memória", command: "mostre minhas memórias", keywords: /mem[oó]ria|lembr/i },
    { id: "agenda", label: "Ver agenda", command: "mostre minha agenda", keywords: /agenda|tarefa|lembrete/i },
    { id: "computer", label: "Analisar o Mac", command: "meu computador está travando, analise a memória", keywords: /mac|computador|trav|ram|mem[oó]ria/i },
  ];

  const CAPABILITIES = [
    "Conversar com OpenRouter sem expor instruções internas",
    "Pesquisar a web ao vivo e mostrar fontes clicáveis",
    "Ouvir pelo microfone e falar com ElevenLabs",
    "Abrir e fechar aplicativos pelo worker do Mac",
    "Tirar print, abrir o gravador e analisar arquivos",
    "Consultar GitHub autenticado sem mostrar credenciais",
    "Ler agenda, criar tarefas e usar n8n quando conectado",
    "Guardar memória confirmada e restaurar conversa privada",
    "Editar o próprio projeto; deploy só com pedido explícito",
  ];

  const STARTER_ACTIONS = {
    guest: [
      ["Pesquisar agora", "pesquise na web as notícias mais importantes de inteligência artificial hoje e cite as fontes"],
      ["O que você faz?", "me diga em poucas frases as melhores coisas que você consegue fazer"],
      ["Testar sua voz", "fale uma frase curta para mim"],
    ],
    owner: [
      ["Pesquisar agora", "pesquise na web as notícias mais importantes de inteligência artificial hoje e cite as fontes"],
      ["Analisar meu Mac", "meu computador está travando, analise a memória"],
      ["Abrir Spotify", "abra o Spotify"],
    ],
  };

  function renderStarterActions() {
    const target = byId("starterActions");
    if (!target) return;
    const actions = session.paired ? STARTER_ACTIONS.owner : STARTER_ACTIONS.guest;
    target.innerHTML = actions.map(([label, command]) => (
      `<button type="button" data-starter-command="${escapeHtml(command)}">${escapeHtml(label)}</button>`
    )).join("");
  }

  function setActionHub(open) {
    actionHub.hidden = !open;
    actionHubButton.setAttribute("aria-expanded", String(open));
    if (open && mobileLayout.matches) input.blur();
  }

  function setMobileChatExpanded(expanded) {
    const active = Boolean(expanded && mobileLayout.matches);
    stage.classList.toggle("mobile-chat-expanded", active);
    mobileChatToggle?.setAttribute("aria-expanded", String(active));
    mobileChatToggle?.setAttribute("aria-label", active ? "Reduzir conversa" : "Expandir conversa");
    const label = mobileChatToggle?.querySelector("span");
    if (label) label.textContent = active ? "Reduzir" : "Expandir";
  }

  function syncMobileViewport() {
    const height = Math.round(window.visualViewport?.height || window.innerHeight);
    if (Math.abs(window.innerWidth - viewportWidth) > 80) {
      viewportWidth = window.innerWidth;
      viewportCeiling = height;
    }
    viewportCeiling = Math.max(viewportCeiling, height);
    document.documentElement.style.setProperty("--jarvis-viewport-height", `${height}px`);
    input.placeholder = mobileLayout.matches ? "Fale ou escreva…" : "Escreva ou fale comigo…";
    const composerFocused = document.activeElement === input || byId("commandForm")?.contains(document.activeElement);
    const keyboardOpen = mobileLayout.matches && composerFocused && viewportCeiling - height > 120;
    stage.classList.toggle("mobile-keyboard-open", keyboardOpen);
    if (keyboardOpen) setMobileChatExpanded(true);
    if (!mobileLayout.matches) setMobileChatExpanded(false);
  }

  function standaloneMode() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  function renderInstallAvailability() {
    if (!installButton) return;
    installButton.hidden = !mobileLayout.matches || standaloneMode();
  }

  async function requestInstall() {
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice.catch(() => null);
      deferredInstallPrompt = null;
      renderInstallAvailability();
      return;
    }
    installDialog?.showModal();
  }

  function registerMobileShell() {
    const localSecure = ["localhost", "127.0.0.1"].includes(window.location.hostname);
    if (!("serviceWorker" in navigator) || (window.location.protocol !== "https:" && !localSecure)) return;
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/jarvis-sw.js", { scope: "/" }).catch(() => null);
    }, { once: true });
  }

  function updateActionHub(command = session.currentCommand, data = {}) {
    const context = `${command || ""} ${data.intent || ""}`;
    const ranked = [...ACTION_CATALOG].sort((left, right) => Number(right.keywords.test(context)) - Number(left.keywords.test(context)));
    byId("actionHubGrid").innerHTML = ranked.map((item, index) => (
      `<button type="button" data-hub-command="${escapeHtml(item.command)}" class="${index < 2 ? "recommended" : ""}"><i>${index < 2 ? "SUGESTÃO" : "AÇÃO"}</i><span>${escapeHtml(item.label)}</span><b>→</b></button>`
    )).join("");
    byId("capabilityList").innerHTML = CAPABILITIES.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    byId("hubWorkerValue").textContent = session.deviceOnline ? "conectado" : session.deviceBridge ? "offline" : "não configurado";
    byId("actionHubHint").textContent = data.job?.id
      ? "A ação foi enviada ao Mac. Aqui ficam os próximos comandos úteis."
      : data.agentic || data.executed_locally
        ? "O JARVIS escolheu uma ferramenta real. Você pode encadear outra ação."
        : "Escolha uma ação ou continue conversando. Nada é executado só por abrir este painel.";
    if (data.job?.id || data.agentic || data.executed_locally) setActionHub(true);
  }

  async function restoreConversationHistory() {
    if (!session.paired || session.historyRestored) return;
    try {
      const data = await request("/conversation-history");
      if (data.ok && Array.isArray(data.messages)) {
        session.history = data.messages.slice(-24);
        session.historyRestored = true;
        if (session.history.length && byId("welcomeMessage")) {
          session.history.forEach((message) => {
            const role = message.role === "user" ? "user" : "jarvis";
            addMessage(message.content, role);
          });
          feed.scrollTop = feed.scrollHeight;
        }
        byId("conversationMemoryValue").textContent = data.persistent
          ? `${Math.ceil(session.history.length / 2)} turnos no Supabase`
          : "sessão local";
        byId("contextCount").textContent = `${Math.ceil(session.history.length / 2)} turnos`;
      }
    } catch {
      byId("conversationMemoryValue").textContent = "sincronização indisponível";
    }
  }

  async function syncConversationHistory() {
    if (!session.paired || !session.history.length) return;
    try {
      const data = await request("/conversation-sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: session.history.slice(-24) }),
      });
      if (data.ok) byId("conversationMemoryValue").textContent = `${Math.ceil(data.count / 2)} turnos no Supabase`;
    } catch {
      byId("conversationMemoryValue").textContent = "sessão local · sync pendente";
    }
  }

  const stateLabels = {
    idle: ["PRESENÇA", "aguardando você"],
    listening: ["ESCUTA", "ouvindo sua voz"],
    thinking: ["NÚCLEO", "raciocinando com o contexto"],
    voice: ["VOZ", "preparando uma resposta natural"],
    planning: ["NÚCLEO", "organizando possibilidades"],
    forge: ["FORJA", "construindo e verificando"],
    speaking: ["RESPOSTA", "falando com você"],
    response: ["RESPOSTA", "resultado disponível"],
    memory: ["MEMÓRIA", "gravando conhecimento confirmado"],
    local: ["FORJA", "executando pelo worker local"],
    success: ["CONCLUÍDO", "ação finalizada"],
    error: ["ATENÇÃO", "a ação encontrou um problema"],
    offline: ["OFFLINE", "runtime indisponível"],
  };

  const statePresentation = {
    idle: ["●", "PRESENÇA", "JARVIS", "ambiente em espera"],
    listening: ["◌", "ESCUTA", "CANAL ABERTO", "captando sua voz"],
    thinking: ["◉", "NÚCLEO", "RACIOCÍNIO", "conectando contexto"],
    planning: ["◉", "NÚCLEO", "PLANEJAMENTO", "organizando possibilidades"],
    forge: ["◆", "FORJA", "CONSTRUÇÃO", "montando e verificando"],
    local: ["◆", "FORJA", "EXECUÇÃO", "worker local em atividade"],
    memory: ["◇", "MEMÓRIA", "ARQUIVO", "gravando contexto confirmado"],
    speaking: ["≈", "VOZ", "TRANSMISSÃO", "falando com você"],
    voice: ["≈", "VOZ", "SÍNTESE", "preparando áudio"],
    response: ["✓", "RESULTADO", "CONCLUÍDO", "resposta disponível"],
    success: ["✓", "RESULTADO", "CONCLUÍDO", "ação confirmada"],
    error: ["!", "SISTEMA", "ATENÇÃO", "algo precisa ser revisto"],
    offline: ["×", "SISTEMA", "OFFLINE", "runtime indisponível"],
  };

  function setVisualState(state) {
    const normalized = state || "idle";
    const [mode, label] = stateLabels[normalized] || stateLabels.idle;
    stage.dataset.state = normalized;
    byId("modeLabel").textContent = mode;
    byId("stateLabel").textContent = label;
    byId("conversationState").textContent = label;
    const [symbol, phase, name, description] = statePresentation[normalized] || statePresentation.idle;
    byId("stateSymbol").textContent = symbol;
    byId("statePhase").textContent = phase;
    byId("stateName").textContent = name;
    byId("stateDescription").textContent = description;
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
    if (session.working) return setVisualState(session.workingState || "thinking");
    setVisualState(session.responseState || "idle");
  }

  function setWorking(value, state = "thinking") {
    session.working = value;
    if (value) session.workingState = state;
    sendButton.disabled = value;
    voiceButton.disabled = value || !voiceSupport.input;
    attachmentButton.disabled = value;
    sendButton.textContent = value ? (state === "forge" ? "Construindo…" : state === "memory" ? "Gravando…" : "Pensando…") : "Enviar";
    settleState();
  }

  function setProgressStep(name, status) {
    const step = byId("requestProgress")?.querySelector(`[data-run-step="${name}"]`);
    if (step) step.dataset.status = status;
  }

  function updateProgressClock() {
    const elapsed = Math.max(0, performance.now() - session.workingStartedAt);
    const target = byId("requestElapsed");
    if (!target) return;
    target.textContent = `${(elapsed / 1000).toFixed(1).replace(".", ",")} s`;
    target.dateTime = `PT${(elapsed / 1000).toFixed(1)}S`;
  }

  function beginRequestProgress(state) {
    window.clearTimeout(progressHideTimer);
    window.clearInterval(progressInterval);
    session.workingStartedAt = performance.now();
    const target = byId("requestProgress");
    target.hidden = false;
    target.setAttribute("aria-busy", "true");
    byId("requestCoreLabel").textContent = state === "forge" ? "Forja" : state === "memory" ? "Memória" : "Núcleo";
    setProgressStep("request", "completed");
    setProgressStep("core", "running");
    setProgressStep("result", "pending");
    updateProgressClock();
    progressInterval = window.setInterval(updateProgressClock, 200);
  }

  function finishRequestProgress(ok) {
    window.clearInterval(progressInterval);
    progressInterval = 0;
    updateProgressClock();
    setProgressStep("core", "completed");
    setProgressStep("result", ok ? "completed" : "failed");
    const target = byId("requestProgress");
    target.setAttribute("aria-busy", "false");
    progressHideTimer = window.setTimeout(() => {
      if (!session.working) target.hidden = true;
    }, 4200);
  }

  function workingStateFor(command) {
    const text = String(command || "");
    if (/\b(?:guard(?:a|e|ar)|salv(?:a|e|ar)|memor(?:ize|izar)|lembre)\b.{0,80}\bmem[oó]ria\b|\bmem[oó]ria\b.{0,80}\b(?:guard(?:a|e|ar)|salv(?:a|e|ar))\b/i.test(text)) return "memory";
    if (/\b(?:cri(?:a|e|ar)|constru(?:a|ir)|implement(?:a|e|ar)|edit(?:a|e|ar)|corrig(?:e|ir)|arrum(?:a|e|ar)|deploy|public(?:a|ar)|sub(?:a|ir)|automatiz(?:a|e|ar))\b/i.test(text)) return "forge";
    return "thinking";
  }

  function responseVisualState(data) {
    const state = data?.visual_state || (data?.executed_locally ? "success" : "response");
    if (state === "local" || (data?.job && ["pending", "running"].includes(data.job.status))) return "forge";
    if (state === "planning") return "response";
    return state;
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

  function speechChunks(value, maxLength = 260) {
    const clean = speechText(value);
    if (!clean) return [];
    const sentences = clean.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [clean];
    const pieces = [];
    sentences.forEach((sentence) => {
      let remaining = sentence.trim();
      while (remaining.length > maxLength) {
        const windowText = remaining.slice(0, maxLength + 1);
        const comma = Math.max(windowText.lastIndexOf(", "), windowText.lastIndexOf("; "), windowText.lastIndexOf(": "));
        const space = windowText.lastIndexOf(" ");
        const cut = comma > maxLength * 0.55 ? comma + 1 : space > 0 ? space : maxLength;
        pieces.push(remaining.slice(0, cut).trim());
        remaining = remaining.slice(cut).trim();
      }
      if (remaining) pieces.push(remaining);
    });
    const chunks = [];
    pieces.forEach((piece) => {
      const previous = chunks.at(-1);
      if (previous && `${previous} ${piece}`.length <= maxLength) chunks[chunks.length - 1] = `${previous} ${piece}`;
      else chunks.push(piece);
    });
    return chunks.slice(0, 6);
  }

  function messageHtml(value) {
    return escapeHtml(value)
      .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a class="message-link" href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`\n]+)`/g, "<code class=\"inline-code\">$1</code>");
  }

  function addMessage(text, type = "jarvis", extraHtml = "") {
    byId("welcomeMessage")?.remove();
    stage.classList.add("has-conversation");
    if (mobileLayout.matches) setMobileChatExpanded(true);
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

  function renderAttachmentTray() {
    attachmentTray.hidden = session.attachments.length === 0;
    attachmentTray.innerHTML = session.attachments.map((item, index) => (
      `<span><b>${escapeHtml(item.name)}</b><small>${Math.ceil(item.size / 1024)} KB</small><button type="button" data-remove-attachment="${index}" aria-label="Remover ${escapeHtml(item.name)}">×</button></span>`
    )).join("");
    attachmentTray.querySelectorAll("[data-remove-attachment]").forEach((button) => {
      button.addEventListener("click", () => {
        session.attachments.splice(Number(button.dataset.removeAttachment), 1);
        renderAttachmentTray();
      });
    });
  }

  function fileDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("file_read_failed"));
      reader.readAsDataURL(file);
    });
  }

  async function addAttachments(files) {
    const selected = Array.from(files || []);
    for (const file of selected) {
      if (session.attachments.length >= 2) {
        addMessage("Posso analisar até dois anexos por mensagem.", "error");
        break;
      }
      const total = session.attachments.reduce((sum, item) => sum + item.size, 0) + file.size;
      if (!file.size || total > 2500000) {
        addMessage("Os anexos juntos precisam ter no máximo 2,5 MB.", "error");
        continue;
      }
      try {
        session.attachments.push({
          name: file.name,
          type: file.type || "text/plain",
          size: file.size,
          data_url: await fileDataUrl(file),
        });
      } catch {
        addMessage(`Não consegui ler ${file.name}.`, "error");
      }
    }
    attachmentInput.value = "";
    renderAttachmentTray();
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

  function renderEventStream(stream) {
    if (!stream || stream.protocol !== "jarvis-events/1" || !Array.isArray(stream.events)) return "";
    const rows = stream.events.slice(-5).map((event) => {
      const status = ["running", "succeeded", "failed"].includes(event.status) ? event.status : "unknown";
      const detail = event.detail ? `<small>${escapeHtml(event.detail)}</small>` : "";
      return `<div class="event-row" data-status="${status}"><i></i><span><b>${escapeHtml(event.label || event.type)}</b>${detail}</span></div>`;
    }).join("");
    return `<div class="event-stream"><div class="event-head"><span>EXECUÇÃO REAL</span><small>${Number(stream.elapsed_ms) || 0} ms</small></div>${rows}</div>`;
  }

  function renderUICards(cards) {
    if (!Array.isArray(cards) || !cards.length) return "";
    return `<div class="ui-card-stack">${cards.slice(0, 3).map((card) => {
      const items = Array.isArray(card.items) ? card.items.slice(0, 6) : [];
      const artifact = card.artifact_url
        ? `<a class="artifact-link" href="${escapeHtml(card.artifact_url)}" target="_blank" rel="noopener noreferrer"><img class="artifact-preview" src="${escapeHtml(card.artifact_url)}" alt="Evidência criada pelo worker do Mac"></a>`
        : "";
      return `<article class="ui-card" data-type="${escapeHtml(card.type || "result")}" data-status="${escapeHtml(card.status || "unknown")}"><header><span>${escapeHtml(card.title || "Resultado")}</span><small>${escapeHtml(card.status || "")}</small></header>${card.subtitle ? `<p>${escapeHtml(card.subtitle)}</p>` : ""}${items.length ? `<ol>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>` : ""}${artifact}</article>`;
    }).join("")}</div>`;
  }

  function renderSourceLinks(sources, compact = false) {
    if (!Array.isArray(sources) || !sources.length) return "";
    const links = sources.slice(0, compact ? 5 : 8).map((source, index) => {
      const url = String(source?.url || "");
      if (!/^https?:\/\//i.test(url)) return "";
      const label = source?.title || source?.domain || `Fonte ${index + 1}`;
      const domain = source?.domain ? `<small>${escapeHtml(source.domain)}</small>` : "";
      return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"><i>${index + 1}</i><span>${escapeHtml(label)}${domain}</span></a>`;
    }).filter(Boolean).join("");
    return links ? `<nav class="source-links" aria-label="Fontes da pesquisa"><b>FONTES AO VIVO</b>${links}</nav>` : "";
  }

  function renderMessageContext(data) {
    let html = "";
    html += renderSourceLinks(data.sources, true);
    if (Array.isArray(data.ui_cards) && data.ui_cards.length) {
      html += data.ui_cards.slice(0, 2).map((card) => {
        const items = Array.isArray(card.items) ? card.items.slice(0, 6) : [];
        return `<details class="message-card"><summary>${escapeHtml(card.title || "Resultado")}<small>${escapeHtml(card.status || "")}</small></summary>${card.subtitle ? `<p>${escapeHtml(card.subtitle)}</p>` : ""}${items.length ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}</details>`;
      }).join("");
    }
    const stream = data.event_stream;
    if (stream?.protocol === "jarvis-events/1" && Array.isArray(stream.events)) {
      html += `<details class="message-events"><summary>Execução real<small>${Number(stream.elapsed_ms) || 0} ms</small></summary>${stream.events.slice(-5).map((event) => `<div><i data-status="${escapeHtml(event.status || "unknown")}"></i><span>${escapeHtml(event.label || event.type)}</span></div>`).join("")}</details>`;
    }
    return html;
  }

  function renderLiveCanvas(data) {
    const empty = byId("canvasEmpty");
    const content = byId("canvasContent");
    let html = renderSourceLinks(data.sources) + renderUICards(data.ui_cards) + renderEventStream(data.event_stream);
    if (data.memory_suggestion) {
      html += `<div class="canvas-row"><i>◇</i><span>Memória sugerida</span></div><div class="canvas-result">${escapeHtml(data.memory_suggestion)}</div>`;
    }
    else if (data.job?.id) {
      const target = data.job.target ? ` · ${data.job.target}` : "";
      html += `<div class="canvas-row"><i>↗</i><span>Ação ${escapeHtml(data.job.id)} · ${escapeHtml(data.job.status || "pending")}${escapeHtml(target)}</span></div>`;
      if (data.job.artifact_url) {
        html += `<a class="artifact-link" href="${escapeHtml(data.job.artifact_url)}" target="_blank" rel="noopener noreferrer"><img class="artifact-preview" src="${escapeHtml(data.job.artifact_url)}" alt="Captura privada criada pelo worker do Mac"></a>`;
      }
      if (data.job.result) html += `<div class="canvas-result">${escapeHtml(data.job.result).slice(0, 1800)}</div>`;
    }
    else if (Array.isArray(data.agenda) && data.agenda.length) {
      html += data.agenda.slice(0, 8).map((item) => {
        const scheduled = agendaDate(item.scheduled_for);
        const label = scheduled ? `${item.title || "item da agenda"} · ${scheduled}` : item.title || "item da agenda";
        return `<div class="canvas-row"><i>${escapeHtml(item.id || "·")}</i><span>${escapeHtml(label)}</span></div>`;
      }).join("");
    }
    else if (Array.isArray(data.contacts) && data.contacts.length) {
      html += data.contacts.slice(0, 8).map((item, index) => (
        `<div class="canvas-row"><i>${index + 1}</i><span>${escapeHtml(item.display_name || item.alias)} · ${escapeHtml(item.phone || "")}</span></div>`
      )).join("");
    }
    else if (Array.isArray(data.steps) && data.steps.length) html += canvasRows(data.steps);
    else if (Array.isArray(data.sources) && data.sources.length && !data.web_search?.used) html += canvasRows(data.sources);
    else if (data.result) html += `<div class="canvas-result">${escapeHtml(data.result).slice(0, 1800)}</div>`;
    else if (data.local_command) html += `<div class="canvas-row"><i>→</i><span>Worker local preparado</span></div><div class="canvas-result">${escapeHtml(data.local_command)}</div>`;
    else if (data.provider === "openrouter") html += `<div class="canvas-row"><i>✓</i><span>Resposta pronta para você</span></div>`;
    else if (data.message && !html) html = `<div class="canvas-result">${escapeHtml(data.message).slice(0, 320)}</div>`;
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

  async function refreshPulse() {
    if (document.hidden) return;
    try {
      const data = await request("/pulse");
      const suggestion = data?.suggestion;
      const dismissed = suggestion?.id && localStorage.getItem("jarvis-last-pulse") === suggestion.id;
      currentPulse = suggestion && !dismissed ? suggestion : null;
      pulseButton.hidden = !currentPulse;
      if (currentPulse) {
        pulseButton.textContent = currentPulse.overdue ? "1 pendência" : "1 lembrete";
        pulseButton.title = currentPulse.message;
      }
    } catch {
      currentPulse = null;
      pulseButton.hidden = true;
    }
  }

  async function refreshWorkerStatus(target) {
    try {
      const worker = await request("/device-worker-status");
      session.deviceOnline = Boolean(worker.online);
      target.textContent = worker.online
        ? `Mac conectado · ${worker.hostname || "worker local"}`
        : "Mac offline · abra ou instale o worker local";
      byId("hubWorkerValue").textContent = worker.online ? "conectado" : "offline";
      await refreshActionHistory({ revealLatest: true });
    } catch {
      session.deviceOnline = false;
      target.textContent = "Mac offline · verificação indisponível";
      byId("hubWorkerValue").textContent = "offline";
    }
  }

  async function request(path, options) {
    const requestOptions = { ...(options || {}) };
    const headers = new Headers(requestOptions.headers || {});
    const token = ownerToken();
    if (token) headers.set("X-Jarvis-Owner-Token", token);
    requestOptions.headers = headers;
    if (!requestOptions.signal && typeof window.AbortSignal?.timeout === "function") {
      requestOptions.signal = window.AbortSignal.timeout(path === "/command" ? 45000 : 20000);
    }
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
    currentAudio?.__jarvisFinish?.(false);
    currentAudio?.pause();
    currentAudio = null;
    if (currentAudioUrl) URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = "";
    if (session.speaking) finishSpeaking();
  }

  async function fetchSpeechChunk(text, generation) {
    const controller = new AbortController();
    currentSpeechController = controller;
    const response = await fetch("/speech", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: controller.signal,
    });
    if (generation !== speechGeneration) throw new DOMException("Speech stopped", "AbortError");
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      throw new Error(failure.error_code || "elevenlabs_unavailable");
    }
    return response.blob();
  }

  function playSpeechChunk(blob, text, generation) {
    return new Promise((resolve, reject) => {
      if (generation !== speechGeneration) return resolve(false);
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      let settled = false;
      const finish = (played) => {
        if (settled) return;
        settled = true;
        URL.revokeObjectURL(audioUrl);
        if (currentAudio === audio) {
          currentAudio = null;
          currentAudioUrl = "";
        }
        resolve(played);
      };
      audio.__jarvisFinish = finish;
      currentAudioUrl = audioUrl;
      currentAudio = audio;
      audio.onplay = () => {
        if (generation === speechGeneration) beginSpeaking(text);
      };
      audio.onended = () => finish(true);
      audio.onerror = () => finish(false);
      audio.play().catch((error) => {
        finish(false);
        reject(error);
      });
    });
  }

  function renderMuteState() {
    const desktopLabel = session.muted ? "Fala muda" : "Fala ligada";
    const mobileLabel = session.muted ? "Mudo" : "Voz";
    muteButton.innerHTML = `<span class="desktop-label">${desktopLabel}</span><span class="mobile-label">${mobileLabel}</span>`;
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
    const chunks = speechChunks(text);
    if (!chunks.length) return false;
    stopSpeechOutput();
    if (session.muted) return false;
    const generation = speechGeneration;
    if (!session.elevenlabs) return false;
    session.voicePending = true;
    byId("spokenCaption").textContent = "Preparando voz…";
    settleState();
    let played = false;
    try {
      let prepared = fetchSpeechChunk(chunks[0], generation)
        .then((blob) => ({ blob }))
        .catch((error) => ({ error }));
      for (let index = 0; index < chunks.length; index += 1) {
        const result = await prepared;
        if (result.error) throw result.error;
        if (generation !== speechGeneration) return false;
        prepared = index + 1 < chunks.length
          ? fetchSpeechChunk(chunks[index + 1], generation).then((blob) => ({ blob })).catch((error) => ({ error }))
          : null;
        const chunkPlayed = await playSpeechChunk(result.blob, chunks[index], generation);
        if (generation !== speechGeneration) return false;
        played = played || chunkPlayed;
      }
      session.voiceError = "";
      voiceFailureNotified = false;
      if (generation === speechGeneration) finishSpeaking();
      return played;
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
      if (generation === speechGeneration) currentSpeechController = null;
    }
  }

  async function monitorDeviceCommand(jobId, message) {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      if (session.canceledJobs.has(String(jobId))) return;
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
      if (["succeeded", "failed", "canceled"].includes(data.job.status)) {
        const text = data.job.result ? `${data.message}\n${data.job.result}` : data.message;
        message.querySelector("span").textContent = text;
        message.classList.toggle("error", data.job.status === "failed");
        session.responseState = data.visual_state || (data.job.status === "succeeded" ? "success" : "error");
        byId("requestTitle").textContent = data.job.status === "succeeded" ? "Ação concluída" : data.job.status === "canceled" ? "Ação cancelada" : "Ação falhou";
        refreshActionHistory();
        settleState();
        return;
      }
      message.querySelector("span").textContent = data.message;
      session.responseState = "forge";
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
        window.setTimeout(() => byId("adminPassword").focus(), 30);
      }
      return;
    }

    session.responseState = responseVisualState(data);
    const answer = data.message || data.summary || data.next_action || data.status_real || "Pronto.";
    let extra = "";
    extra += renderMessageContext(data);
    if (data.memory_suggestion) {
      extra += `<button class="memory-command" type="button">${session.paired ? "Guardar na memória" : "Memória privada"}</button>`;
    }
    if (data.local_command) {
      extra += `<button class="copy-command" type="button">Copiar comando local</button><details><summary>ver comando</summary><code>${escapeHtml(data.local_command)}</code></details>`;
    }
    if (data.result) {
      extra += `<details><summary>ver resultado completo</summary><code>${escapeHtml(data.result)}</code></details>`;
    }
    if (data.job?.id && data.job.status === "pending") {
      extra += `<button class="cancel-job" type="button">Cancelar ação</button>`;
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
      if (!session.paired) {
        dialog.showModal();
        byId("ownerTokenInput").focus();
        return;
      }
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
    const cancelJob = message.querySelector(".cancel-job");
    if (cancelJob) cancelJob.addEventListener("click", async () => {
      cancelJob.disabled = true;
      cancelJob.textContent = "Cancelando…";
      try {
        const canceled = await request("/device-cancel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: data.job.id }),
        });
        session.canceledJobs.add(String(data.job.id));
        message.querySelector("span").textContent = canceled.message || "Ação cancelada.";
        cancelJob.remove();
        renderLiveCanvas(canceled);
        refreshActionHistory();
      } catch (error) {
        cancelJob.disabled = false;
        cancelJob.textContent = "Tentar cancelar novamente";
      }
    });
    byId("activityValue").textContent = data.executed_locally ? `Executado localmente · ${data.intent || "ação"}` : answer;
    byId("requestTitle").textContent = data.memory_suggestion ? "Memória sugerida" : data.job?.id ? "Ação enviada ao Mac" : data.executed_locally ? "Ação local" : data.provider === "n8n" ? "Automação concluída" : "Resposta pronta";
    renderLiveCanvas(data);
    updateActionHub(session.currentCommand, data);
    if (data.job?.id && ["pending", "running"].includes(data.job.status)) {
      monitorDeviceCommand(data.job.id, message);
    }
    if (session.responseState === "memory") window.dispatchEvent(new CustomEvent("jarvis-memory-refresh"));
    settleState();
    speak(answer);
  }

  async function sendCommand(rawValue, options = {}) {
    if (session.working) {
      input.focus();
      return;
    }
    const attachments = options.includeAttachments ? session.attachments.slice() : [];
    const command = String(rawValue || "").trim() || (attachments.length ? "Analise estes anexos." : "");
    if (!command) return;
    session.responseState = "";
    session.currentCommand = command;
    const fileLabel = attachments.length ? `<small class="message-attachments">${attachments.map((item) => escapeHtml(item.name)).join(" · ")}</small>` : "";
    addMessage(command, options.source === "voice" ? "user voice" : "user", fileLabel);
    input.value = "";
    session.history.push({ role: "user", content: command });
    session.history = session.history.slice(-24);
    setRequest(command);
    const workingState = workingStateFor(command);
    beginRequestProgress(workingState);
    setWorking(true, workingState);
    try {
      const data = await request("/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, messages: session.history, input_mode: options.source || "text", attachments }),
      });
      if (attachments.length) {
        session.attachments = [];
        renderAttachmentTray();
      }
      session.lastResponseOk = data?.ok !== false;
      showResponse(data);
      const answer = data.message || data.summary;
      if (answer) {
        session.history.push({ role: "assistant", content: answer });
        session.history = session.history.slice(-24);
        window.setTimeout(syncConversationHistory, 0);
      }
    } catch {
      session.lastResponseOk = false;
      showResponse({ ok: false, error: "A conexão com o núcleo do JARVIS caiu." });
    } finally {
      setWorking(false);
      finishRequestProgress(session.lastResponseOk);
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
        sendCommand(transcript, { source: "voice", includeAttachments: true });
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
      byId("modelValue").textContent = status.ai?.model || "—";
      session.paired = Boolean(status.owner_pairing?.authenticated || !status.owner_pairing?.required);
      const toolCount = session.paired ? Number(status.agent_runtime?.available_tools) || 0 : 0;
      byId("aiValue").textContent = status.ai?.configured
        ? `OpenRouter conectado${status.web_search?.configured ? " · web ao vivo" : ""}${toolCount ? ` · ${toolCount} ferramentas` : ""}`
        : "OpenRouter não configurado";
      const accessMode = session.paired ? "owner" : "guest";
      stage.dataset.access = accessMode;
      byId("accessMode").textContent = session.paired ? "Theo · modo master" : "modo visitante";
      byId("accessValue").textContent = session.paired
        ? "Theo master · memória, GitHub e Mac privados disponíveis"
        : status.access?.public_chat
          ? "Visitante · conversa liberada, memória e Mac privados"
          : "Visitante · conversa aguarda OpenRouter";
      byId("welcomeHint").textContent = session.paired
        ? "Escreva ou fale naturalmente."
        : "Converse livremente. Memória privada e Mac pertencem ao Theo.";
      renderStarterActions();
      session.deviceBridge = Boolean(status.device_bridge?.configured);
      session.elevenlabs = Boolean(status.voice?.configured);
      session.voiceError = "";
      byId("voiceValue").textContent = session.elevenlabs
        ? `ElevenLabs${voiceSupport.input ? " + microfone" : ""}`
        : voiceSupport.input
          ? "microfone ativo · saída aguarda ElevenLabs"
          : "ElevenLabs aguarda chave";
      const ready = [
        status.ai?.configured ? (status.web_search?.configured ? "IA + pesquisa web" : toolCount ? `IA + ${toolCount} ferramentas` : "IA") : "",
        status.voice?.configured ? "ElevenLabs" : voiceSupport.input ? "microfone" : "",
        status.automations?.n8n?.configured ? "n8n" : "",
        session.paired && status.device_bridge?.configured ? "Mac pareado" : "",
        status.runtime === "local_web_preview" ? "worker local" : "",
      ].filter(Boolean);
      byId("integrationValue").textContent = ready.join(" · ") || "sem integrações externas";
      byId("integrationHint").textContent = !status.web_search?.configured
        ? "Pesquisa ao vivo aguarda o OpenRouter; as demais integrações continuam independentes."
        : status.automations?.n8n?.configured
        ? "Pesquisa ao vivo e roteamento contextual ativos; agenda e tarefas estão conectadas ao n8n."
        : status.automations?.agenda?.provider === "supabase"
          ? "Pesquisa ao vivo ativa; memória e agenda ficam no Supabase e ações usam o worker local."
          : "Pesquisa ao vivo ativa; persistência aguarda Supabase ou n8n e o Mac usa o worker local.";
      byId("runtimeLabel").textContent = status.runtime === "local_web_preview" ? "Mac local" : "Vercel";
      const tokenInput = byId("ownerTokenInput");
      tokenInput.value = ownerToken();
      byId("adminUsername").closest(".admin-login").hidden = session.paired;
      document.querySelector(".advanced-pairing").hidden = !status.owner_pairing?.required;
      byId("pairingHint").textContent = session.paired
        ? "Modo master ativo neste navegador. A sessão é temporária e pode ser encerrada em Sair."
        : status.owner_pairing?.required
          ? status.owner_pairing?.admin_login_configured
            ? "Entre como admin para liberar memória, agenda, GitHub e ações no Mac."
            : "Login master ainda não configurado no ambiente; use o pareamento avançado."
          : "Pareamento ainda não foi exigido neste ambiente.";
      const workerValue = byId("workerValue");
      if (session.paired && status.device_bridge?.configured) {
        workerValue.textContent = "verificando o Mac em segundo plano";
        refreshWorkerStatus(workerValue);
      } else {
        session.deviceOnline = status.runtime === "local_web_preview";
        workerValue.textContent = session.paired
          ? "Ponte remota ainda não configurada"
          : "Navegador não pareado";
      }
      setVisualState(status.ok ? "idle" : "offline");
      updateActionHub();
      if (session.paired) await restoreConversationHistory();
      refreshPulse();
    } catch {
      byId("connectionText").textContent = "offline";
      session.responseState = "offline";
      settleState();
    }
  }

  byId("commandForm").addEventListener("submit", (event) => {
    event.preventDefault();
    sendCommand(input.value, { includeAttachments: true });
  });
  input.addEventListener("focus", () => {
    if (mobileLayout.matches) setMobileChatExpanded(true);
    window.setTimeout(syncMobileViewport, 80);
  });
  input.addEventListener("blur", () => window.setTimeout(syncMobileViewport, 80));
  attachmentButton.addEventListener("click", () => attachmentInput.click());
  attachmentInput.addEventListener("change", () => addAttachments(attachmentInput.files));
  feed.addEventListener("click", (event) => {
    const suggestion = event.target.closest("[data-starter-command]");
    if (!suggestion) return;
    input.value = suggestion.dataset.starterCommand || "";
    input.focus();
  });
  pulseButton.addEventListener("click", () => {
    if (!currentPulse) return;
    addMessage(currentPulse.message, "jarvis");
    renderLiveCanvas({
      ui_cards: [{
        id: currentPulse.id,
        type: "agenda",
        status: currentPulse.overdue ? "overdue" : "upcoming",
        title: currentPulse.title,
        subtitle: "Sugestão; nenhuma ação executada",
        items: [currentPulse.message],
      }],
    });
    input.value = currentPulse.command || "";
    input.focus();
    try { localStorage.setItem("jarvis-last-pulse", currentPulse.id); } catch { /* session-only dismissal */ }
    currentPulse = null;
    pulseButton.hidden = true;
  });
  byId("detailsButton").addEventListener("click", () => {
    dialog.showModal();
    refreshActionHistory();
  });
  byId("adminLoginButton").addEventListener("click", async () => {
    const username = byId("adminUsername").value.trim();
    const password = byId("adminPassword").value;
    if (!username || !password) {
      byId("pairingHint").textContent = "Informe login e senha para entrar no modo master.";
      return;
    }
    byId("adminLoginButton").disabled = true;
    byId("pairingHint").textContent = "Validando login master…";
    try {
      const data = await request("/admin-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!data.ok || !data.session_token) {
        byId("pairingHint").textContent = data.error || "Login master recusado.";
        return;
      }
      localStorage.setItem(OWNER_TOKEN_KEY, data.session_token);
      byId("adminPassword").value = "";
      session.historyRestored = false;
      await boot();
      if (session.paired) dialog.close();
    } catch {
      byId("pairingHint").textContent = "Não consegui validar o login agora.";
    } finally {
      byId("adminLoginButton").disabled = false;
    }
  });
  byId("adminPassword").addEventListener("keydown", (event) => {
    if (event.key === "Enter") byId("adminLoginButton").click();
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
    session.history = [];
    session.historyRestored = false;
    byId("conversationMemoryValue").textContent = "sessão local";
    await boot();
  });
  actionHubButton.addEventListener("click", () => setActionHub(actionHub.hidden));
  mobileChatToggle?.addEventListener("click", () => {
    setMobileChatExpanded(mobileChatToggle.getAttribute("aria-expanded") !== "true");
  });
  installButton?.addEventListener("click", requestInstall);
  byId("closeInstallDialog")?.addEventListener("click", () => installDialog.close());
  installDialog?.addEventListener("click", (event) => {
    if (event.target === installDialog) installDialog.close();
  });
  byId("closeActionHub").addEventListener("click", () => setActionHub(false));
  actionHub.addEventListener("click", (event) => {
    const button = event.target.closest("[data-hub-command]");
    if (!button) return;
    input.value = button.dataset.hubCommand || "";
    setActionHub(false);
    input.focus();
  });
  byId("tourButton").addEventListener("click", () => tourDialog.showModal());
  byId("closeTour").addEventListener("click", () => tourDialog.close());
  byId("tourActionButton").addEventListener("click", () => {
    tourDialog.close();
    setActionHub(true);
  });
  tourDialog.addEventListener("click", (event) => {
    if (event.target === tourDialog) tourDialog.close();
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
  window.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      setActionHub(actionHub.hidden);
      if (!actionHub.hidden) actionHub.querySelector("button[data-hub-command]")?.focus();
      return;
    }
    if (event.key === "Escape" && !actionHub.hidden) setActionHub(false);
    else if (event.key === "Escape" && mobileLayout.matches && stage.classList.contains("mobile-chat-expanded")) setMobileChatExpanded(false);
  });
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    renderInstallAvailability();
  });
  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    renderInstallAvailability();
  });
  mobileLayout.addEventListener?.("change", () => {
    renderInstallAvailability();
    syncMobileViewport();
  });
  window.visualViewport?.addEventListener("resize", syncMobileViewport);
  window.visualViewport?.addEventListener("scroll", syncMobileViewport);
  window.addEventListener("resize", syncMobileViewport);
  window.addEventListener("pagehide", () => {
    window.clearInterval(progressInterval);
    window.clearTimeout(progressHideTimer);
    stopSpeechOutput();
  }, { once: true });

  renderMuteState();
  renderStarterActions();
  renderInstallAvailability();
  syncMobileViewport();
  registerMobileShell();
  installVoiceInput();
  boot();
  window.setInterval(refreshPulse, 10 * 60 * 1000);
})();
