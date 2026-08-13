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
  const filePreview = byId("filePreview");
  const conversation = document.querySelector(".conversation");
  const dialog = byId("systemDialog");
  const tourDialog = byId("tourDialog");
  const memoryDialog = byId("memoryDialog");
  const taskDialog = byId("taskDialog");
  const fileWorkspaceDialog = byId("fileWorkspaceDialog");
  const actionHub = byId("actionHub");
  const actionHubBackdrop = byId("actionHubBackdrop");
  const actionHubButton = byId("actionHubButton");
  const actionHubSearch = byId("actionHubSearch");
  const mobileChatToggle = byId("mobileChatToggle");
  const newConversationButton = byId("newConversationButton");
  const installButton = byId("installButton");
  const installDialog = byId("installDialog");
  const mobileLayout = window.matchMedia("(max-width: 720px)");
  const OWNER_TOKEN_KEY = "jarvis-owner-token-v1";
  const MAX_VISIBLE_MESSAGES = 24;
  const FILE_WORKSPACE_DB = "jarvis-file-workspace-v1";
  const FILE_WORKSPACE_LIMIT = 12;
  const FILE_WORKSPACE_BYTES = 12_000_000;
  const ALLOWED_ATTACHMENT_TYPES = new Set([
    "image/jpeg", "image/png", "image/webp", "application/pdf",
    "text/plain", "text/markdown", "text/csv", "application/json",
  ]);
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
    mission: null,
    overview: null,
    workingStartedAt: 0,
    lastResponseOk: true,
    filePreviewing: false,
    notifications: (() => {
      try {
        return localStorage.getItem("jarvis-notifications-enabled") === "1";
      } catch {
        return false;
      }
    })(),
  };
  let currentAudio = null;
  let currentAudioUrl = "";
  let currentSpeechController = null;
  let currentCommandController = null;
  const interruptedCommandControllers = new WeakSet();
  let speechGeneration = 0;
  let voiceFailureNotified = false;
  let currentPulse = null;
  let progressInterval = 0;
  let progressHideTimer = 0;
  let filePreviewTimer = 0;
  let deferredInstallPrompt = null;
  let viewportCeiling = Math.round(window.visualViewport?.height || window.innerHeight);
  let viewportWidth = window.innerWidth;
  const memoryManager = { nodes: [], writable: false, provider: "" };
  const notifiedRuns = new Set();

  function ownerToken() {
    try {
      return localStorage.getItem(OWNER_TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  async function exitOwnerMode(trigger = null) {
    const control = trigger || byId("leaveOwnerMode");
    if (control) control.disabled = true;
    stopSpeechOutput();
    try {
      localStorage.removeItem(OWNER_TOKEN_KEY);
    } catch {
      byId("pairingHint").textContent = "Este navegador não permitiu encerrar a sessão local.";
      if (control) control.disabled = false;
      return;
    }
    byId("ownerTokenInput").value = "";
    session.paired = false;
    session.history = [];
    session.historyRestored = false;
    session.currentCommand = "";
    session.mission = null;
    session.responseState = "";
    session.attachments = [];
    byId("conversationMemoryValue").textContent = "sessão local";
    setActionHub(false);
    renderAttachmentTray();
    clearAttachmentPreview();
    renderWelcomeState("Modo visitante ativo. A memória privada e o Mac continuam protegidos.");
    await boot();
    if (!session.paired && dialog.open) dialog.close();
    if (control) control.disabled = false;
  }

  const ACTION_CATALOG = [
    { id: "daily", label: "Resumo do meu dia", description: "Agenda, memória e atividade recente", command: "me dê um resumo operacional do meu dia", executor: "jarvis", keywords: /dia|hoje|agenda|resumo/i },
    { id: "spotify", label: "Abrir Spotify", description: "Executar no Mac", command: "abra o Spotify", executor: "mac", keywords: /m[uú]sica|spotify/i },
    { id: "mac-run", label: "Executar sequência", description: "Várias ações com confirmação por etapa", command: "abra o Spotify e depois tire um print da tela", executor: "mac", keywords: /sequ[eê]ncia|etapa|depois|execut/i },
    { id: "screen", label: "Capturar minha tela", description: "Executar no Mac e devolver evidência", command: "tire um print da tela", executor: "mac", keywords: /print|captur|tela|imagem/i },
    { id: "computer", label: "Diagnosticar o Mac", description: "Memória e processos", command: "meu computador está travando, analise a memória", executor: "mac", keywords: /mac|computador|trav|ram/i },
    { id: "memory", label: "Abrir memória", description: "Persistente ou local", command: "mostre minhas memórias", executor: "memory", keywords: /mem[oó]ria|lembr/i },
    { id: "agenda", label: "Ver agenda", description: "Tarefas e lembretes", command: "mostre minha agenda", executor: "agenda", keywords: /agenda|tarefa|lembrete/i },
    { id: "task", label: "Criar tarefa", description: "Adicionar tarefa com data", command: "crie uma tarefa para amanhã: revisar minhas prioridades", executor: "agenda", interaction: "draft", keywords: /cri(?:ar|e).*tarefa|agenda|amanh[aã]|prioridade/i },
    { id: "github", label: "Inspecionar GitHub", description: "Conta autenticada no Mac", command: "mostre meus repositórios do GitHub", executor: "mac", keywords: /github|repo|c[oó]digo|pull/i },
    { id: "screen-record", label: "Gravar minha tela", description: "Gravador nativo do Mac", command: "grave a tela do meu Mac", executor: "mac", keywords: /grav(?:ar|e)|v[ií]deo|tela/i },
    { id: "system", label: "Verificar sistema", description: "JARVIS, integrações e Mac", command: "verifique o estado do JARVIS e do meu Mac", executor: "jarvis", keywords: /sistema|status|estado|integra[cç][aã]o|mac/i },
    { id: "plan", label: "Criar plano executável", description: "Etapas, riscos e próximo passo", command: "crie um plano curto e executável para a minha próxima prioridade", executor: "jarvis", keywords: /plano|planej|prioridade|etapa/i },
    { id: "research", label: "Pesquisar com fontes", description: "Web e READMEs reais", command: "pesquise projetos públicos de assistente pessoal no GitHub e compare as funções comprovadas", executor: "web", keywords: /pesquis|busc|github|internet/i },
  ];

  const CAPABILITIES = [
    "Conversar com OpenRouter sem expor instruções internas",
    "Pesquisar a web ao vivo e mostrar fontes clicáveis",
    "Ouvir pelo microfone e falar com ElevenLabs",
    "Abrir e fechar aplicativos pelo worker do Mac",
    "Encadear até seis ações no Mac e interromper as seguintes se uma falhar",
    "Tirar print, abrir o gravador e analisar arquivos",
    "Consultar GitHub autenticado sem mostrar credenciais",
    "Ler agenda, criar tarefas e usar n8n quando conectado",
    "Guardar memória confirmada e restaurar conversa privada",
    "Editar o próprio projeto; deploy só com pedido explícito",
  ];

  const STARTER_ACTIONS = {
    guest: [
      ["Pesquisar com fontes", "pesquise na web as notícias mais importantes de inteligência artificial hoje e cite as fontes"],
      ["Conhecer o JARVIS", "me mostre objetivamente o que você consegue fazer e quais ações exigem confirmação"],
      ["Criar um plano", "crie um plano curto e executável para a minha próxima ideia"],
    ],
    owner: [
      ["Começar meu dia", "me dê um resumo operacional do meu dia e o próximo foco"],
      ["Buscar na memória", "busque na memória por decisões e aprendizados recentes"],
      ["Investigar com fontes", "pesquise com fontes atuais algo importante para meus projetos"],
    ],
  };

  function renderStarterActions() {
    const target = byId("starterActions");
    if (!target) return;
    const actions = session.paired ? STARTER_ACTIONS.owner : STARTER_ACTIONS.guest;
    target.innerHTML = actions.map(([label, command]) => (
      `<button type="button" data-starter-command="${escapeHtml(command)}">${escapeHtml(label)}</button>`
    )).join("");
    target.querySelectorAll("[data-starter-command]").forEach((button) => {
      button.addEventListener("click", () => sendCommand(button.dataset.starterCommand || ""));
    });
  }

  function renderWelcomeState(note = "") {
    const defaultHint = session.paired
      ? "Peça o resultado. Eu planejo, confirmo riscos e mostro a evidência."
      : "Conversa e pesquisa estão disponíveis. Memória e Mac exigem acesso do Theo.";
    feed.innerHTML = (
      `<div class="welcome" id="welcomeMessage">`
      + `<strong>${session.paired ? "Pronto, Theo." : "Como posso ajudar?"}</strong>`
      + `<span id="welcomeHint">${escapeHtml(note || defaultHint)}</span>`
      + `<div class="starter-actions" id="starterActions" aria-label="Sugestões para começar"></div>`
      + `</div>`
    );
    stage.classList.remove("has-conversation");
    setMobileChatExpanded(false);
    renderStarterActions();
  }

  async function startNewConversation() {
    if (session.working || newConversationButton?.disabled) return;
    stopSpeechOutput();
    if (newConversationButton) {
      newConversationButton.disabled = true;
      newConversationButton.textContent = "Limpando…";
    }
    let note = "Nova conversa iniciada.";
    if (session.paired) {
      try {
        const data = await request("/conversation-clear", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        note = data.ok
          ? "Nova conversa. Suas memórias confirmadas continuam guardadas."
          : "Nova conversa nesta tela; o histórico privado não confirmou a limpeza.";
      } catch {
        note = "Nova conversa nesta tela; o histórico privado não respondeu.";
      }
    }
    session.history = [];
    session.historyRestored = true;
    session.currentCommand = "";
    session.mission = null;
    session.responseState = "";
    session.attachments = [];
    renderAttachmentTray();
    clearAttachmentPreview();
    actionHubButton.classList.remove("has-context");
    byId("conversationMemoryValue").textContent = session.paired ? "0 turnos" : "sessão local";
    byId("sceneEyebrow").textContent = "PRONTO";
    byId("sceneMission").textContent = "O que vamos fazer?";
    byId("sceneDetail").textContent = "Conversa, pesquisa, memória e execução em um só lugar.";
    renderWelcomeState(note);
    settleState();
    if (newConversationButton) {
      newConversationButton.disabled = false;
      newConversationButton.textContent = "Nova";
    }
    input.focus();
  }

  function setActionHub(open) {
    const wasOpen = !actionHub.hidden;
    actionHub.hidden = !open;
    actionHubBackdrop.hidden = !open;
    document.body.classList.toggle("action-hub-open", open);
    actionHubButton.setAttribute("aria-expanded", String(open));
    if (open) {
      actionHubButton.classList.remove("has-context");
      actionHubSearch.value = "";
      updateActionHub(session.currentCommand);
      refreshPersonalOverview();
      if (mobileLayout.matches) input.blur();
      window.setTimeout(() => actionHubSearch.focus(), 30);
    } else if (wasOpen) {
      actionHubButton.focus();
    }
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
    input.placeholder = mobileLayout.matches ? "O que você quer fazer?" : "Descreva o resultado que você quer…";
    const composerFocused = document.activeElement === input || byId("commandForm")?.contains(document.activeElement);
    const keyboardOpen = mobileLayout.matches && composerFocused && viewportCeiling - height > 120;
    stage.classList.toggle("mobile-keyboard-open", keyboardOpen);
    if (keyboardOpen) setMobileChatExpanded(true);
    if (!mobileLayout.matches) setMobileChatExpanded(false);
  }

  function resizeComposerInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 144)}px`;
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

  function renderNotificationState() {
    const button = byId("notificationButton");
    if (!button) return;
    const supported = "Notification" in window;
    if (!supported) {
      button.disabled = true;
      button.textContent = "Notificações indisponíveis";
      return;
    }
    if (Notification.permission === "denied") {
      session.notifications = false;
      button.disabled = true;
      button.textContent = "Notificações bloqueadas";
      button.setAttribute("aria-pressed", "false");
      return;
    }
    const active = session.notifications && Notification.permission === "granted";
    button.disabled = false;
    button.textContent = active ? "Notificações ligadas" : "Ativar notificações";
    button.setAttribute("aria-pressed", String(active));
  }

  async function toggleNotifications() {
    if (!("Notification" in window)) return;
    if (session.notifications && Notification.permission === "granted") {
      session.notifications = false;
    } else {
      const permission = Notification.permission === "granted"
        ? "granted"
        : await Notification.requestPermission();
      session.notifications = permission === "granted";
    }
    try {
      localStorage.setItem("jarvis-notifications-enabled", session.notifications ? "1" : "0");
    } catch {
      // Permission still works for the current tab when storage is unavailable.
    }
    renderNotificationState();
  }

  async function notifyBackgroundCompletion(id, title, body) {
    const notificationId = String(id || "jarvis-completion");
    if (!document.hidden || !session.notifications || !("Notification" in window) || Notification.permission !== "granted" || notifiedRuns.has(notificationId)) return false;
    notifiedRuns.add(notificationId);
    const options = {
      body: speechText(body).slice(0, 180),
      tag: notificationId,
      renotify: false,
      icon: "/ui/jarvis-icon-192.png",
      badge: "/ui/jarvis-icon-192.png",
      data: { url: "/" },
    };
    try {
      const registration = await navigator.serviceWorker?.getRegistration?.();
      if (registration) await registration.showNotification(title, options);
      else {
        const notification = new Notification(title, options);
        notification.onclick = () => window.focus();
      }
      return true;
    } catch {
      notifiedRuns.delete(notificationId);
      return false;
    }
  }

  function searchableActionText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function updateActionHub(command = session.currentCommand, data = {}) {
    if (Array.isArray(data.actions) || Array.isArray(data.domains)) session.overview = data;
    const context = `${command || ""} ${data.intent || ""}`;
    const source = Array.isArray(session.overview?.actions) && session.overview.actions.length
      ? session.overview.actions.map((item) => ({
          ...item,
          keywords: ACTION_CATALOG.find((fallback) => fallback.id === item.id)?.keywords || /$^/,
        }))
      : ACTION_CATALOG;
    const query = searchableActionText(actionHubSearch?.value);
    const terms = query.split(/\s+/).filter(Boolean);
    const ranked = source
      .map((item) => {
        const haystack = searchableActionText([item.id, item.label, item.description, item.reason, item.executor, item.command].join(" "));
        if (terms.some((term) => !haystack.includes(term))) return null;
        const label = searchableActionText(item.label);
        const queryScore = !query ? 0 : label === query ? 6 : label.startsWith(query) ? 4 : label.includes(query) ? 3 : 1;
        const contextScore = item.keywords.test(context) ? 2 : 0;
        return { item, score: queryScore + contextScore };
      })
      .filter(Boolean)
      .sort((left, right) => right.score - left.score)
      .map((row) => row.item);
    const grid = byId("actionHubGrid");
    grid.innerHTML = ranked.length ? ranked.map((item, index) => (
      `<button type="button" data-hub-command="${escapeHtml(item.command)}" data-hub-interaction="${escapeHtml(item.interaction || "send")}" class="${index < 2 ? "recommended" : ""}" ${item.available === false ? "data-locked=\"true\"" : ""}>`
      + `<i>${escapeHtml(query && index === 0 ? "MELHOR" : index < 2 ? "SUGESTÃO" : item.executor || "AÇÃO")}</i>`
      + `<span>${escapeHtml(item.label)}<small>${escapeHtml(item.description || item.reason || "")}</small></span>`
      + `<b>${item.available === false ? "•" : item.interaction === "draft" ? "✎" : "→"}</b></button>`
    )).join("") : `<p class="action-hub-empty">Nenhuma ação corresponde a “${escapeHtml(actionHubSearch.value)}”. Tente buscar por memória, tela, agenda, GitHub ou pesquisa.</p>`;
    grid.querySelectorAll("[data-hub-command]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.locked === "true") {
          setActionHub(false);
          dialog.showModal();
          window.setTimeout(() => byId("adminPassword").focus(), 30);
          return;
        }
        const nextCommand = button.dataset.hubCommand || "";
        setActionHub(false);
        if (button.dataset.hubInteraction === "draft") {
          input.value = nextCommand;
          resizeComposerInput();
          input.focus();
          input.setSelectionRange(input.value.length, input.value.length);
          return;
        }
        sendCommand(nextCommand);
      });
    });
    const domainCapabilities = Array.isArray(session.overview?.domains)
      ? session.overview.domains.map((item) => `${item.label}: ${item.status} · ${item.detail}`)
      : [];
    byId("capabilityList").innerHTML = (domainCapabilities.length ? domainCapabilities : CAPABILITIES)
      .map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    byId("hubWorkerValue").textContent = session.deviceOnline ? "conectado" : session.deviceBridge ? "offline" : "não configurado";
    if (query) byId("hubReadyValue").textContent = `${ranked.length} encontrado${ranked.length === 1 ? "" : "s"}`;
    byId("actionHubHint").textContent = data.job?.id
      ? "A ação foi enviada ao Mac. Aqui ficam os próximos comandos úteis."
      : data.agentic || data.executed_locally
        ? "O JARVIS escolheu uma ferramenta real. Você pode encadear outra ação."
        : session.paired
          ? "Escolha uma ação real ou continue conversando normalmente."
          : "Conversa e pesquisa são públicas; ações pessoais exigem o modo master.";
    const hasContext = Boolean(
      data.job?.id
      || data.agentic
      || data.executed_locally
      || data.memory_suggestion
      || data.memory_candidate
      || (Array.isArray(data.sources) && data.sources.length)
      || (Array.isArray(data.ui_cards) && data.ui_cards.length)
    );
    actionHubButton.classList.toggle("has-context", hasContext && actionHub.hidden);
    // A central nunca se abre sozinha; o resultado apenas sinaliza contexto no botão.
  }

  async function refreshPersonalOverview() {
    try {
      const data = await request("/personal-overview");
      session.overview = data;
      const summary = data.summary || {};
      session.deviceOnline = Boolean(summary.worker_online);
      byId("hubWorkerValue").textContent = session.paired
        ? session.deviceOnline ? "online" : "offline · aceita fila"
        : "modo master necessário";
      byId("hubMemoryValue").textContent = summary.memory_count == null ? "privada" : `${summary.memory_count} registros`;
      byId("hubAgendaValue").textContent = summary.agenda_count == null ? "privada" : `${summary.agenda_count} pendentes`;
      byId("hubLastActionValue").textContent = summary.latest_action || "nenhuma execução registrada";
      byId("hubReadyValue").textContent = summary.ready_actions == null
        ? "entre no modo master"
        : `${summary.ready_actions} disponíveis`;
      byId("actionHubOverview").textContent = data.message || "Central pessoal carregada.";
      updateActionHub(session.currentCommand, data);
      return data;
    } catch {
      byId("actionHubOverview").textContent = "O estado das conexões não respondeu agora; a conversa continua disponível.";
      return null;
    }
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

  const statePresentation = {
    idle: ["aguardando você", "PRONTO", "ambiente em espera"],
    listening: ["ouvindo sua voz", "ESCUTA", "captando sua voz"],
    thinking: ["raciocinando com o contexto", "NÚCLEO", "conectando contexto"],
    research: ["consultando fontes reais", "PESQUISA", "coletando evidências"],
    planning: ["organizando possibilidades", "PLANO", "estruturando a execução"],
    forge: ["construindo e verificando", "EXECUÇÃO", "montando e verificando"],
    local: ["executando pelo worker local", "MAC", "worker local em atividade"],
    memory: ["gravando conhecimento confirmado", "MEMÓRIA", "registrando contexto confirmado"],
    speaking: ["falando com você", "VOZ", "transmitindo a resposta"],
    preview: ["abrindo prévia", "ARQUIVO", "preparando o material para análise"],
    voice: ["preparando áudio", "VOZ", "gerando uma resposta natural"],
    response: ["resultado disponível", "CONCLUÍDO", "resposta disponível no canal principal"],
    success: ["ação finalizada", "CONCLUÍDO", "resultado e evidência confirmados"],
    error: ["ação interrompida", "ATENÇÃO", "algo precisa ser revisto"],
    offline: ["runtime indisponível", "OFFLINE", "verifique a conexão do serviço"],
  };

  function setVisualState(state) {
    const normalized = state || "idle";
    const [label, phase, description] = statePresentation[normalized] || statePresentation.idle;
    stage.dataset.state = normalized;
    byId("conversationState").textContent = label;
    byId("sceneEyebrow").textContent = phase;
    byId("sceneDetail").textContent = description;
    const voiceLabel = voiceButton?.querySelector("b");
    const interrupting = session.speaking || session.voicePending || session.working;
    voiceButton?.classList.toggle("speaking", interrupting);
    if (voiceLabel) voiceLabel.textContent = session.listening ? "Parar" : interrupting ? "Interromper" : "Falar";
    if (voiceButton) {
      voiceButton.setAttribute("aria-label", session.listening ? "Parar escuta" : interrupting ? "Interromper JARVIS e falar" : "Falar com JARVIS");
      voiceButton.title = interrupting ? "Interromper a resposta e falar agora" : "Clique, fale normalmente e o comando será enviado quando você terminar.";
    }
    window.dispatchEvent(new CustomEvent("jarvis-state", { detail: { state: normalized } }));
  }

  function settleState() {
    if (session.listening) return setVisualState("listening");
    if (session.speaking) return setVisualState("speaking");
    if (session.voicePending) return setVisualState("voice");
    if (session.working) return setVisualState(session.workingState || "thinking");
    if (session.filePreviewing) return setVisualState("preview");
    setVisualState(session.responseState || "idle");
  }

  function setWorking(value, state = "thinking") {
    session.working = value;
    if (value) session.workingState = state;
    sendButton.disabled = value;
    voiceButton.disabled = !voiceSupport.input;
    attachmentButton.disabled = value;
    sendButton.textContent = value ? (state === "forge" ? "Construindo…" : state === "memory" ? "Gravando…" : state === "research" ? "Pesquisando…" : "Pensando…") : "Enviar";
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
    byId("requestCoreLabel").textContent = state === "forge" ? "Forja" : state === "memory" ? "Memória" : state === "research" ? "Pesquisa" : "Núcleo";
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
    if (/\b(?:pesquis\w*|busc\w*|procur\w*|investig\w*|not[ií]cias?|cota[cç][aã]o|mais recente)\b/i.test(text)) return "research";
    if (/\b(?:cri(?:a|e|ar)|constru(?:a|ir)|implement(?:a|e|ar)|edit(?:a|e|ar)|corrig(?:e|ir)|arrum(?:a|e|ar)|deploy|public(?:a|ar)|sub(?:a|ir)|automatiz(?:a|e|ar))\b/i.test(text)) return "forge";
    return "thinking";
  }

  function responseVisualState(data) {
    const state = data?.visual_state || (data?.executed_locally ? "success" : "response");
    if (data?.state === "waiting_confirmation") return "planning";
    if (data?.state === "running") return "forge";
    if (data?.run && ["pending", "running"].includes(data.run.status)) return "forge";
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
    if (clean.length <= 520) return clean;
    const excerpt = clean.slice(0, 520);
    const naturalEnd = Math.max(excerpt.lastIndexOf(". "), excerpt.lastIndexOf("! "), excerpt.lastIndexOf("? "));
    return `${excerpt.slice(0, naturalEnd > 280 ? naturalEnd + 1 : 520).trim()}…`;
  }

  function compactCaption(value, fallback = "Estou aqui.") {
    const clean = speechText(value);
    if (!clean) return fallback;
    const sentence = clean.match(/^.{1,150}?[.!?](?=\s|$)/)?.[0] || clean.slice(0, 148);
    return clean.length > sentence.length && !/[.!?]$/.test(sentence)
      ? `${sentence.trim()}…`
      : sentence.trim();
  }

  function compactHudText(value, fallback, limit = 76) {
    const clean = speechText(value);
    if (!clean) return fallback;
    if (clean.length <= limit) return clean;
    return `${clean.slice(0, limit).replace(/\s+\S*$/, "").trim()}…`;
  }

  function speechChunks(value, maxLength = 230) {
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
    if (chunks.length > 1 && chunks[0].length > 165) {
      const first = chunks[0];
      const windowText = first.slice(0, 166);
      const cut = Math.max(windowText.lastIndexOf(". "), windowText.lastIndexOf(", "), windowText.lastIndexOf(" "));
      if (cut > 90) chunks.splice(0, 1, first.slice(0, cut + 1).trim(), first.slice(cut + 1).trim());
    }
    return chunks.filter(Boolean).slice(0, 3);
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
    const visibleMessages = feed.querySelectorAll(".message");
    if (visibleMessages.length > MAX_VISIBLE_MESSAGES) {
      Array.from(visibleMessages).slice(0, visibleMessages.length - MAX_VISIBLE_MESSAGES).forEach((item) => item.remove());
    }
    feed.scrollTop = feed.scrollHeight;
    return message;
  }

  function setRequest(command) {
    byId("spokenCaption").textContent = compactCaption(command, "Entendi. Deixe comigo.");
    byId("sceneEyebrow").textContent = "MISSÃO ATIVA";
    byId("sceneMission").textContent = compactHudText(command, "Executando pedido");
    byId("sceneDetail").textContent = "Selecionando a melhor rota e acompanhando o resultado real.";
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
        if (session.attachments.length) renderFilePreview(session.attachments);
        else clearAttachmentPreview();
      });
    });
  }

  function attachmentKind(item) {
    const type = String(item?.type || "").toLowerCase();
    if (type.startsWith("image/")) return "image";
    if (type === "application/pdf") return "pdf";
    if (type.includes("json")) return "json";
    if (type.includes("csv")) return "csv";
    return "text";
  }

  function renderFilePreview(items) {
    const rows = Array.from(items || []).filter(Boolean);
    const item = rows.at(-1);
    if (!filePreview || !item) return clearAttachmentPreview();
    const kind = attachmentKind(item);
    const labels = { image: "IMAGEM", pdf: "PDF", json: "JSON", csv: "CSV", text: "TEXTO" };
    filePreview.hidden = false;
    filePreview.dataset.kind = kind;
    byId("filePreviewKind").textContent = labels[kind] || "ARQUIVO";
    byId("filePreviewName").textContent = item.name || "arquivo";
    byId("filePreviewMeta").textContent = rows.length > 1
      ? `${rows.length} arquivos preparados · ${Math.ceil(rows.reduce((sum, row) => sum + row.size, 0) / 1024)} KB`
      : `${labels[kind] || "ARQUIVO"} · ${Math.ceil(item.size / 1024)} KB · leitura local`;
    const image = byId("filePreviewImage");
    image.src = kind === "image" ? item.data_url : "";
    stage.dataset.filePreview = "open";
  }

  function clearAttachmentPreview() {
    window.clearTimeout(filePreviewTimer);
    session.filePreviewing = false;
    delete stage.dataset.filePreview;
    if (filePreview) {
      window.setTimeout(() => {
        if (!stage.dataset.filePreview) filePreview.hidden = true;
      }, 640);
    }
    settleState();
  }

  function showAttachmentPreview(items) {
    const rows = Array.from(items || []).filter(Boolean);
    if (!rows.length) return;
    window.clearTimeout(filePreviewTimer);
    renderFilePreview(rows);
    byId("filePreviewEyebrow").textContent = rows.length > 1 ? "PRÉVIAS ABERTAS" : "PRÉVIA ABERTA";
    const phrase = rows.length > 1
      ? "Estas são prévias dos arquivos que estou analisando."
      : "Esta é uma prévia do arquivo que estou analisando.";
    session.filePreviewing = true;
    byId("spokenCaption").textContent = phrase;
    settleState();
    filePreviewTimer = window.setTimeout(() => {
      session.filePreviewing = false;
      settleState();
    }, 6200);
    speak(phrase);
  }

  function fileDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("file_read_failed"));
      reader.readAsDataURL(file);
    });
  }

  function supportedAttachment(file) {
    if (ALLOWED_ATTACHMENT_TYPES.has(String(file?.type || "").toLowerCase())) return true;
    return /\.(?:jpe?g|png|webp|pdf|txt|md|csv|json)$/i.test(String(file?.name || ""));
  }

  async function addAttachments(files) {
    const selected = Array.from(files || []);
    const added = [];
    for (const file of selected) {
      if (!supportedAttachment(file)) {
        addMessage(`${file.name || "Este arquivo"} não é compatível. Use imagem, PDF, texto, Markdown, CSV ou JSON.`, "error");
        continue;
      }
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
        const attachment = {
          name: file.name,
          type: file.type || "text/plain",
          size: file.size,
          data_url: await fileDataUrl(file),
        };
        session.attachments.push(attachment);
        added.push(attachment);
      } catch {
        addMessage(`Não consegui ler ${file.name}.`, "error");
      }
    }
    attachmentInput.value = "";
    renderAttachmentTray();
    if (added.length) showAttachmentPreview(session.attachments);
  }

  function openFileWorkspaceDatabase() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) return reject(new Error("indexeddb_unavailable"));
      const request = indexedDB.open(FILE_WORKSPACE_DB, 2);
      request.onupgradeneeded = () => {
        const database = request.result;
        if (!database.objectStoreNames.contains("files")) database.createObjectStore("files", { keyPath: "id" });
        if (!database.objectStoreNames.contains("outbox")) database.createObjectStore("outbox", { keyPath: "id" });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("indexeddb_failed"));
    });
  }

  async function readWorkspaceFiles() {
    const database = await openFileWorkspaceDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction("files", "readonly");
      const request = transaction.objectStore("files").getAll();
      request.onsuccess = () => resolve((request.result || []).sort((left, right) => String(right.updated_at).localeCompare(String(left.updated_at))));
      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => database.close();
    });
  }

  async function writeWorkspaceFiles(records) {
    const database = await openFileWorkspaceDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction("files", "readwrite");
      const store = transaction.objectStore("files");
      records.forEach((record) => store.put(record));
      transaction.oncomplete = () => { database.close(); resolve(); };
      transaction.onerror = () => { database.close(); reject(transaction.error); };
    });
  }

  async function deleteWorkspaceFile(id = "") {
    const database = await openFileWorkspaceDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction("files", "readwrite");
      const store = transaction.objectStore("files");
      if (id) store.delete(id);
      else store.clear();
      transaction.oncomplete = () => { database.close(); resolve(); };
      transaction.onerror = () => { database.close(); reject(transaction.error); };
    });
  }

  async function readOfflineOutbox() {
    const database = await openFileWorkspaceDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction("outbox", "readonly");
      const request = transaction.objectStore("outbox").getAll();
      request.onsuccess = () => resolve((request.result || []).sort((left, right) => String(left.created_at).localeCompare(String(right.created_at))));
      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => database.close();
    });
  }

  async function saveOfflineCommand(command, attachments = []) {
    const database = await openFileWorkspaceDatabase();
    const record = {
      id: window.crypto?.randomUUID?.() || `offline-${Date.now()}`,
      command: String(command || "").slice(0, 8000),
      attachment_names: attachments.map((item) => String(item.name || "arquivo").slice(0, 200)),
      created_at: new Date().toISOString(),
    };
    return new Promise((resolve, reject) => {
      const transaction = database.transaction("outbox", "readwrite");
      transaction.objectStore("outbox").put(record);
      transaction.oncomplete = () => { database.close(); resolve(record); };
      transaction.onerror = () => { database.close(); reject(transaction.error); };
    });
  }

  async function deleteOfflineCommand(id = "") {
    const database = await openFileWorkspaceDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction("outbox", "readwrite");
      const store = transaction.objectStore("outbox");
      if (id) store.delete(id);
      else store.clear();
      transaction.oncomplete = () => { database.close(); resolve(); };
      transaction.onerror = () => { database.close(); reject(transaction.error); };
    });
  }

  async function renderOfflineOutbox() {
    const panel = byId("offlineOutbox");
    try {
      const rows = await readOfflineOutbox();
      panel.hidden = rows.length === 0;
      if (!rows.length) return;
      const first = rows[0];
      byId("offlineOutboxTitle").textContent = `${rows.length} ${rows.length === 1 ? "pedido guardado" : "pedidos guardados"} offline`;
      byId("offlineOutboxDetail").textContent = first.attachment_names?.length
        ? `${first.command} · reanexe: ${first.attachment_names.join(", ")}`
        : first.command;
    } catch {
      panel.hidden = true;
    }
  }

  function updateConnectivity() {
    const online = navigator.onLine !== false;
    byId("connectionDot").classList.toggle("online", online);
    byId("connectionText").textContent = online ? "online" : "offline";
    if (!online && !session.working) {
      session.responseState = "offline";
      settleState();
    }
    renderOfflineOutbox();
  }

  function workspaceFileKind(item) {
    const kind = attachmentKind(item);
    return ({ image: "IMG", pdf: "PDF", json: "JSON", csv: "CSV", text: "TXT" })[kind] || "FILE";
  }

  async function renderFileWorkspace() {
    const target = byId("fileWorkspaceList");
    try {
      const files = await readWorkspaceFiles();
      const total = files.reduce((sum, item) => sum + Number(item.size || 0), 0);
      byId("fileWorkspaceStatus").textContent = `${files.length}/${FILE_WORKSPACE_LIMIT} arquivos · ${(total / 1000000).toFixed(1).replace(".", ",")} MB · só neste navegador`;
      target.innerHTML = files.length ? files.map((item) => (
        `<article class="workspace-file" data-workspace-id="${escapeHtml(item.id)}"><i>${workspaceFileKind(item)}</i><span><b title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</b><small>${Math.ceil(item.size / 1024)} KB · ${escapeHtml(item.type || "arquivo")}</small><footer><button type="button" data-workspace-use>Usar</button><button type="button" data-workspace-delete>Remover</button></footer></span></article>`
      )).join("") : '<p class="memory-empty">Guarde PDFs, imagens e textos para reutilizar em outras conversas.</p>';
      target.querySelectorAll("[data-workspace-use]").forEach((button) => button.addEventListener("click", () => {
        const item = files.find((row) => row.id === button.closest(".workspace-file").dataset.workspaceId);
        if (!item) return;
        const totalSize = session.attachments.reduce((sum, row) => sum + row.size, 0) + item.size;
        if (session.attachments.length >= 2 || totalSize > 2500000) {
          byId("fileWorkspaceStatus").textContent = "O pedido aceita no máximo dois arquivos e 2,5 MB no total.";
          return;
        }
        session.attachments.push({ name: item.name, type: item.type, size: item.size, data_url: item.data_url });
        renderAttachmentTray();
        showAttachmentPreview(session.attachments);
        byId("fileWorkspaceStatus").textContent = `${item.name} anexado ao próximo pedido.`;
      }));
      target.querySelectorAll("[data-workspace-delete]").forEach((button) => button.addEventListener("click", async () => {
        if (!window.confirm("Remover este arquivo do espaço local do JARVIS?")) return;
        await deleteWorkspaceFile(button.closest(".workspace-file").dataset.workspaceId);
        renderFileWorkspace();
      }));
    } catch {
      byId("fileWorkspaceStatus").textContent = "Este navegador não liberou armazenamento local de arquivos.";
      target.innerHTML = "";
    }
  }

  async function storeFilesInWorkspace(files) {
    const selected = Array.from(files || []).filter(supportedAttachment);
    try {
      const existing = await readWorkspaceFiles();
      let total = existing.reduce((sum, item) => sum + Number(item.size || 0), 0);
      const available = Math.max(0, FILE_WORKSPACE_LIMIT - existing.length);
      const records = [];
      for (const file of selected.slice(0, available)) {
        if (!file.size || file.size > 2500000 || total + file.size > FILE_WORKSPACE_BYTES) continue;
        records.push({
          id: window.crypto?.randomUUID?.() || `file-${Date.now()}-${records.length}`,
          name: file.name,
          type: file.type || "text/plain",
          size: file.size,
          data_url: await fileDataUrl(file),
          updated_at: new Date().toISOString(),
        });
        total += file.size;
      }
      if (records.length) await writeWorkspaceFiles(records);
      byId("workspaceFileInput").value = "";
      await renderFileWorkspace();
      if (!records.length) byId("fileWorkspaceStatus").textContent = "Nada salvo: confira formato, limite de 12 arquivos e 12 MB.";
    } catch {
      byId("fileWorkspaceStatus").textContent = "Não consegui salvar no espaço local deste navegador.";
    }
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
    const readmeCount = sources.filter((source) => source?.research_depth === "readme").length;
    const links = sources.slice(0, compact ? 5 : 8).map((source, index) => {
      const url = String(source?.url || "");
      if (!/^https?:\/\//i.test(url)) return "";
      const label = source?.title || source?.domain || `Fonte ${index + 1}`;
      const meta = [
        source?.domain,
        source?.license && source.license !== "NOASSERTION" ? source.license : "",
        Number(source?.stars) > 0 ? `★ ${Number(source.stars).toLocaleString("pt-BR")}` : "",
        source?.research_depth === "readme" ? `README · ${Number(source?.evidence_count) || 0} achados` : "",
      ].filter(Boolean).join(" · ");
      const evidence = Array.isArray(source?.feature_evidence) ? source.feature_evidence.slice(0, 2).join(" • ") : "";
      const detailText = evidence || source?.snippet || "";
      const detail = !compact && detailText
        ? `<em>${escapeHtml(String(detailText).slice(0, 360))}</em>`
        : "";
      return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"><i>${index + 1}</i><span><strong>${escapeHtml(label)}</strong>${meta ? `<small>${escapeHtml(meta)}</small>` : ""}${detail}</span></a>`;
    }).filter(Boolean).join("");
    const header = readmeCount ? `PESQUISA PROFUNDA · ${readmeCount} READMES` : "FONTES AO VIVO";
    return links ? `<nav class="source-links" aria-label="Fontes da pesquisa"><b>${header}</b>${links}</nav>` : "";
  }

  function renderMessageContext(data) {
    let details = "";
    const badges = [];
    if (data.mission?.protocol === "jarvis-mission/2") {
      const completed = data.mission.steps?.filter((step) => step.status === "succeeded").length || 0;
      const total = data.mission.steps?.length || 0;
      badges.push(`${completed}/${total} etapas`);
      details += `<section class="message-card mission-card"><strong>Missão</strong><p>${escapeHtml(data.mission.objective || "")}</p>${total ? `<ul>${data.mission.steps.map((step) => `<li data-status="${escapeHtml(step.status || "pending")}">${escapeHtml(step.label || step.id)}</li>`).join("")}</ul>` : ""}</section>`;
    }
    if (Array.isArray(data.sources) && data.sources.length) badges.push(`${data.sources.length} fontes`);
    details += renderSourceLinks(data.sources);
    if (Array.isArray(data.ui_cards) && data.ui_cards.length) {
      badges.push(`${data.ui_cards.length} resultado${data.ui_cards.length === 1 ? "" : "s"}`);
      details += renderUICards(data.ui_cards);
    }
    if (data.memory_candidate || data.memory_suggestion) {
      const candidate = data.memory_candidate || { content: data.memory_suggestion };
      badges.push("memória sugerida");
      details += `<section class="message-card"><strong>Memória sugerida</strong><small>ainda não salva</small><p>${escapeHtml(candidate.content || data.memory_suggestion)}</p>${candidate.reason ? `<p>${escapeHtml(candidate.reason)}</p>` : ""}</section>`;
    }
    const jobs = Array.isArray(data.jobs) ? data.jobs : data.job?.id ? [data.job] : [];
    if (jobs.length) {
      badges.push(`${jobs.length} ${jobs.length === 1 ? "ação" : "ações"}`);
      details += `<section class="message-card execution-card"><strong>Execução no Mac</strong><small>${escapeHtml(data.run?.status || jobs[0]?.status || "pending")}</small><ul>${jobs.slice(0, 6).map((job) => `<li data-status="${escapeHtml(job.status || "pending")}">${escapeHtml(job.action || "ação")}${job.target ? ` · ${escapeHtml(job.target)}` : ""}</li>`).join("")}</ul>${jobs.find((job) => job?.artifact_url)?.artifact_url ? `<a class="artifact-link" href="${escapeHtml(jobs.find((job) => job?.artifact_url).artifact_url)}" target="_blank" rel="noopener noreferrer"><img class="artifact-preview" src="${escapeHtml(jobs.find((job) => job?.artifact_url).artifact_url)}" alt="Evidência criada pelo worker do Mac"></a>` : ""}</section>`;
    }
    const stream = data.event_stream;
    if (stream?.protocol === "jarvis-events/1" && Array.isArray(stream.events)) {
      badges.push(`${Number(stream.elapsed_ms) || 0} ms`);
      details += renderEventStream(stream);
    }
    if (!details) return "";
    const summary = badges.length ? badges.slice(0, 3).join(" · ") : "ver evidências";
    return `<details class="message-context"><summary><span>Detalhes reais</span><small>${escapeHtml(summary)}</small></summary><div>${details}</div></details>`;
  }

  function refreshMessageExecutionContext(message, data) {
    message.querySelectorAll(".message-context").forEach((card) => card.remove());
    const context = renderMessageContext({
      ui_cards: data.ui_cards || [],
      mission: data.mission,
      sources: data.sources || [],
      event_stream: data.event_stream,
      memory_candidate: data.memory_candidate,
      memory_suggestion: data.memory_suggestion,
      jobs: data.jobs,
      job: data.job,
      run: data.run,
    });
    if (context) message.insertAdjacentHTML("beforeend", context);
  }

  function renderActionHistory(items) {
    const target = byId("actionHistory");
    if (!target) return;
    if (!Array.isArray(items) || !items.length) {
      target.innerHTML = "<small>Nenhum run registrado neste filtro.</small>";
      return;
    }
    target.innerHTML = items.slice(0, 30).map((item) => {
      const state = item.state || "unknown";
      const action = item.action?.label || item.action?.name || "Run do JARVIS";
      const timestamp = item.updated_at ? new Date(item.updated_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "horário indisponível";
      const evidence = Array.isArray(item.evidence) ? item.evidence : [];
      const evidenceRows = evidence.map((row) => {
        const value = String(row?.value || "evidência confirmada");
        const content = /^https?:\/\//i.test(value)
          ? `<a href="${escapeHtml(value)}" target="_blank" rel="noopener noreferrer">${escapeHtml(row.type || "fonte")}</a>`
          : `${escapeHtml(row?.type || "evidência")}: ${escapeHtml(value)}`;
        return `<li>${content}</li>`;
      }).join("");
      const retry = item.retryable
        ? `<button type="button" data-retry-run="${escapeHtml(item.run_id)}">Reexecutar</button>`
        : "";
      return `<div class="history-row" data-status="${escapeHtml(state)}"><i></i><span>`
        + `<b title="${escapeHtml(item.command || action)}">${escapeHtml(action)}</b>`
        + `<small>${escapeHtml(state)} · ${escapeHtml(timestamp)}</small>`
        + `<details><summary>Detalhes e evidências</summary><p>${escapeHtml(item.command || "Comando não registrado")}</p>${item.error ? `<p>${escapeHtml(item.error)}</p>` : ""}${evidenceRows ? `<ul>${evidenceRows}</ul>` : "<small>Sem evidência anexada.</small>"}</details>`
        + `${retry}</span></div>`;
    }).join("");
    target.querySelectorAll("[data-retry-run]").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "Reexecutando…";
        const data = await request(`/runs/${encodeURIComponent(button.dataset.retryRun)}/retry`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        if (data.ok === false) addMessage(data.error || "Não consegui reexecutar este run.", "error");
        else addMessage(data.message || "Nova tentativa criada.", "jarvis", renderMessageContext(data));
        refreshActionHistory();
      });
    });
  }

  async function refreshActionHistory() {
    const target = byId("actionHistory");
    if (target) target.innerHTML = "<small>Carregando runs…</small>";
    try {
      const state = byId("runHistoryFilter")?.value || "";
      const data = await request(`/runs?limit=30${state ? `&state=${encodeURIComponent(state)}` : ""}`);
      if (data.ok === false) {
        if (target) target.innerHTML = `<small>${escapeHtml(data.error || "Histórico privado indisponível.")}</small>`;
        return;
      }
      renderActionHistory(data.runs || []);
    } catch {
      renderActionHistory([]);
    }
  }

  function renderMemoryManager() {
    const target = byId("memoryManagerList");
    const search = searchableActionText(byId("memoryManagerSearch")?.value);
    const kind = byId("memoryManagerKind")?.value || "";
    const rows = memoryManager.nodes.filter((item) => {
      const matchesKind = !kind || item.kind === kind;
      const haystack = searchableActionText([item.label, item.content, item.category, item.layer, item.kind, item.path].join(" "));
      return matchesKind && (!search || haystack.includes(search));
    });
    byId("memoryManagerStatus").textContent = `${rows.length} de ${memoryManager.nodes.length} registros · ${memoryManager.provider || "índice local"}${memoryManager.writable ? " · edição ativa" : " · somente leitura"}`;
    if (!rows.length) {
      target.innerHTML = '<p class="memory-empty">Nenhuma memória corresponde a este filtro.</p>';
      return;
    }
    target.innerHTML = rows.map((item) => {
      const memoryId = String(item.id || "").replace(/^supabase:/, "");
      const editable = memoryManager.writable && String(item.id || "").startsWith("supabase:");
      return `<article class="memory-item" data-memory-id="${escapeHtml(memoryId)}">`
        + `<header><i>${escapeHtml(item.category || item.layer || "MEMÓRIA")}</i><small>${escapeHtml(item.kind || "context")}</small></header>`
        + `<p>${escapeHtml(item.content || item.label || item.path)}</p>`
        + (editable ? `<footer><button type="button" data-edit-memory>Editar</button><button class="danger" type="button" data-archive-memory>Excluir</button></footer>` : `<small>${escapeHtml(item.path || "registro local")}</small>`)
        + (editable ? `<div class="memory-editor" hidden><textarea maxlength="4000" aria-label="Conteúdo da memória">${escapeHtml(item.content || "")}</textarea><select aria-label="Tipo da memória"><option value="learning" ${item.kind === "learning" ? "selected" : ""}>Aprendizado</option><option value="decision" ${item.kind === "decision" ? "selected" : ""}>Decisão</option><option value="preference" ${item.kind === "preference" ? "selected" : ""}>Preferência</option><option value="context" ${item.kind === "context" ? "selected" : ""}>Contexto</option></select><footer><button type="button" data-save-memory>Salvar</button><button type="button" data-cancel-memory>Cancelar</button></footer></div>` : "")
        + `</article>`;
    }).join("");
    target.querySelectorAll("[data-edit-memory]").forEach((button) => button.addEventListener("click", () => {
      const card = button.closest(".memory-item");
      card.querySelector(".memory-editor").hidden = false;
      card.querySelector(".memory-editor textarea").focus();
    }));
    target.querySelectorAll("[data-cancel-memory]").forEach((button) => button.addEventListener("click", () => {
      button.closest(".memory-editor").hidden = true;
    }));
    target.querySelectorAll("[data-save-memory]").forEach((button) => button.addEventListener("click", async () => {
      const card = button.closest(".memory-item");
      button.disabled = true;
      const data = await request("/memory-update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: card.dataset.memoryId, content: card.querySelector("textarea").value, kind: card.querySelector("select").value }),
      });
      if (data.ok === false) {
        button.disabled = false;
        byId("memoryManagerStatus").textContent = data.error || "Edição não confirmada.";
        return;
      }
      await loadMemoryManager();
      window.dispatchEvent(new CustomEvent("jarvis-memory-refresh"));
    }));
    target.querySelectorAll("[data-archive-memory]").forEach((button) => button.addEventListener("click", async () => {
      const card = button.closest(".memory-item");
      if (!window.confirm("Excluir esta memória da visão ativa? Ela será arquivada, não destruída.")) return;
      button.disabled = true;
      const data = await request("/memory-archive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: card.dataset.memoryId }),
      });
      if (data.ok === false) {
        button.disabled = false;
        byId("memoryManagerStatus").textContent = data.error || "Exclusão não confirmada.";
        return;
      }
      await loadMemoryManager();
      window.dispatchEvent(new CustomEvent("jarvis-memory-refresh"));
    }));
  }

  async function loadMemoryManager() {
    byId("memoryManagerStatus").textContent = "Sincronizando memória…";
    const data = await request("/memory-tree");
    if (data.ok === false) {
      memoryManager.nodes = [];
      byId("memoryManagerStatus").textContent = data.error || "Memória indisponível.";
      byId("memoryManagerList").innerHTML = '<p class="memory-empty">Entre no modo master para consultar a memória privada.</p>';
      return;
    }
    memoryManager.nodes = Array.isArray(data.nodes) ? data.nodes : [];
    memoryManager.writable = Boolean(data.persistent_write);
    memoryManager.provider = data.provider || "";
    renderMemoryManager();
  }

  function renderTaskBoard(tasks, counts = {}) {
    const labels = { pending: "PENDENTES", blocked: "BLOQUEADAS", done: "CONCLUÍDAS" };
    byId("taskSummary").textContent = `${Number(counts.pending) || 0} pendentes · ${Number(counts.blocked) || 0} bloqueadas · ${Number(counts.done) || 0} concluídas · append-only local`;
    byId("taskBoard").innerHTML = Object.entries(labels).map(([status, label]) => {
      const rows = tasks.filter((item) => item.status === status);
      const cards = rows.map((item) => {
        const actions = status === "pending"
          ? '<button data-task-action="done">Concluir</button><button data-task-action="block">Bloquear</button>'
          : status === "blocked"
            ? '<button data-task-action="reopen">Reabrir</button><button data-task-action="done">Concluir</button>'
            : '<button data-task-action="reopen">Reabrir</button>';
        return `<article class="task-card" data-task-id="${escapeHtml(item.id)}"><p>${escapeHtml(item.text)}</p><small>${escapeHtml(item.project || "sem projeto")} · ${escapeHtml(item.updated_at || "sem data")}${item.reason ? ` · ${escapeHtml(item.reason)}` : ""}</small><footer>${actions}</footer></article>`;
      }).join("") || '<small>Nenhuma tarefa aqui.</small>';
      return `<section class="task-column"><header><b>${label}</b><span>${rows.length}</span></header>${cards}</section>`;
    }).join("");
    byId("taskBoard").querySelectorAll("[data-task-action]").forEach((button) => button.addEventListener("click", async () => {
      const card = button.closest(".task-card");
      const action = button.dataset.taskAction;
      let detail = "";
      if (action === "block") {
        detail = window.prompt("Qual é o motivo do bloqueio?")?.trim() || "";
        if (!detail) return;
      }
      button.disabled = true;
      const data = await request(`/tasks/${encodeURIComponent(card.dataset.taskId)}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ detail }),
      });
      if (data.ok === false) byId("taskSummary").textContent = data.error || "Mudança não confirmada.";
      else loadTaskBoard();
    }));
  }

  async function loadTaskBoard() {
    byId("taskSummary").textContent = "Sincronizando fila local…";
    const data = await request("/tasks?limit=300");
    if (data.ok === false) {
      byId("taskSummary").textContent = data.error || "Fila indisponível.";
      byId("taskBoard").innerHTML = "";
      return;
    }
    renderTaskBoard(data.tasks || [], data.counts || {});
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
      await refreshActionHistory();
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

  async function requestCommandStream(payload, onEvent, signal = null) {
    const headers = new Headers({ "Content-Type": "application/json" });
    const token = ownerToken();
    if (token) headers.set("X-Jarvis-Owner-Token", token);
    const requestSignal = signal || (typeof window.AbortSignal?.timeout === "function"
      ? window.AbortSignal.timeout(60000)
      : undefined);
    const response = await fetch("/command-stream", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: requestSignal,
    });
    const contentType = response.headers.get("Content-Type") || "";
    if (!contentType.includes("application/x-ndjson")) {
      const data = await response.json().catch(() => ({ ok: false, error: "O stream respondeu em um formato inválido." }));
      return data;
    }
    let result = null;
    let buffer = "";
    const acceptLine = (line) => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      onEvent?.(event);
      if (event.type === "stream.result") result = event.payload;
    };
    if (response.body?.getReader) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        lines.forEach(acceptLine);
        if (done) break;
      }
    } else {
      buffer = await response.text();
    }
    if (buffer.trim()) acceptLine(buffer);
    return result || { ok: false, error: "O stream terminou antes do resultado final." };
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

  function interruptActiveResponse() {
    if (!currentCommandController || currentCommandController.signal.aborted) return false;
    interruptedCommandControllers.add(currentCommandController);
    currentCommandController.abort();
    session.working = false;
    session.responseState = "";
    setWorking(false);
    byId("spokenCaption").textContent = "Interrompido. Estou ouvindo.";
    byId("sceneDetail").textContent = "Resposta anterior interrompida por Theo.";
    return true;
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
      if (!data.mission && session.mission) {
        data.mission = { ...session.mission, steps: session.mission.steps.map((step, index) => ({ ...step, status: index < 2 ? data.job.status : data.job.status === "succeeded" ? "succeeded" : "pending" })) };
      }
      refreshMessageExecutionContext(message, data);
      byId("activityValue").textContent = `${data.message} · ação ${jobId}`;
      if (["succeeded", "failed", "canceled"].includes(data.job.status)) {
        const text = data.job.result ? `${data.message}\n${data.job.result}` : data.message;
        message.querySelector("span").textContent = text;
        message.classList.toggle("error", data.job.status === "failed");
        message.querySelector(".cancel-job")?.remove();
        session.responseState = data.visual_state || (data.job.status === "succeeded" ? "success" : "error");
        refreshActionHistory();
        refreshPersonalOverview();
        settleState();
        notifyBackgroundCompletion(`job-${jobId}`, data.job.status === "succeeded" ? "JARVIS concluiu a ação" : "A ação do JARVIS precisa de atenção", text);
        return;
      }
      message.querySelector("span").textContent = data.message;
      session.responseState = "forge";
      settleState();
    }
    message.querySelector("span").textContent = "O pedido continua na fila; o worker do Mac não confirmou dentro de um minuto.";
  }

  async function monitorDeviceRun(jobIds, message) {
    const ids = jobIds.map(String);
    for (let attempt = 0; attempt < 80; attempt += 1) {
      if (ids.every((id) => session.canceledJobs.has(id))) return;
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
      let data;
      try {
        data = await request(`/device-run?ids=${encodeURIComponent(ids.join(","))}`);
      } catch {
        continue;
      }
      if (data?.pairing_required) return;
      if (!data?.run || !Array.isArray(data.jobs)) continue;
      if (!data.mission && session.mission) {
        data.mission = { ...session.mission, steps: session.mission.steps.map((step, index) => ({ ...step, status: data.jobs[index]?.status || step.status })) };
      }
      refreshMessageExecutionContext(message, data);
      byId("activityValue").textContent = data.message;
      message.querySelector("span").textContent = data.message;
      if (data.run.terminal) {
        const failed = data.jobs.find((job) => job.status === "failed");
        if (failed?.result) message.querySelector("span").textContent = `${data.message}\n${failed.result}`;
        message.classList.toggle("error", data.run.status === "failed");
        message.querySelector(".cancel-run")?.remove();
        session.responseState = data.visual_state || (data.run.status === "succeeded" ? "success" : "error");
        refreshActionHistory();
        refreshPersonalOverview();
        settleState();
        if (data.run.status === "succeeded") speak(data.message);
        notifyBackgroundCompletion(`run-${data.run.id || ids.join("-")}`, data.run.status === "succeeded" ? "JARVIS concluiu a sequência" : "A sequência do JARVIS terminou com alerta", data.message);
        return;
      }
      session.responseState = "forge";
      settleState();
    }
    message.querySelector("span").textContent = "A execução continua registrada, mas o Mac não confirmou todas as etapas dentro do tempo de acompanhamento.";
  }

  function showResponse(data, streamedMessage = null) {
    if (!data || data.ok === false) {
      streamedMessage?.remove();
      const error = data?.error || data?.message || "Não consegui completar isso.";
      const failedCommand = session.currentCommand;
      session.responseState = "error";
      byId("sceneEyebrow").textContent = "ATENÇÃO";
      byId("sceneMission").textContent = compactHudText(error, "Execução interrompida");
      byId("sceneDetail").textContent = "O erro foi preservado sem inventar um resultado.";
      const retryHtml = failedCommand && !data?.pairing_required
        ? `<div class="message-actions"><button class="retry-command" type="button">Tentar novamente</button></div>`
        : "";
      const errorMessage = addMessage(error, "error", retryHtml);
      errorMessage.querySelector(".retry-command")?.addEventListener("click", (event) => {
        event.currentTarget.disabled = true;
        event.currentTarget.textContent = "Tentando…";
        sendCommand(failedCommand, { includeAttachments: session.attachments.length > 0 });
      });
      settleState();
      speak(error);
      if (data?.pairing_required) {
        dialog.showModal();
        window.setTimeout(() => byId("adminPassword").focus(), 30);
      }
      return;
    }

    session.responseState = responseVisualState(data);
    session.mission = data.mission || null;
    const answer = data.message || data.summary || data.next_action || data.status_real || "Pronto.";
    byId("sceneEyebrow").textContent = data.job?.id || data.executed_locally ? "AÇÃO CONFIRMADA" : "RESULTADO";
    byId("sceneMission").textContent = compactHudText(answer, "Resultado disponível");
    byId("sceneDetail").textContent = data.web_search?.used
      ? `${Number(data.web_search.source_count) || 0} fontes verificadas ao vivo.`
      : data.model_routing?.quality_tier === "quality_first"
        ? "Resposta processada pela rota de qualidade."
        : "Resposta pronta no canal principal.";
    let extra = "";
    let messageActions = `<button class="copy-response" type="button">Copiar</button>`;
    extra += renderMessageContext(data);
    if (data.memory_suggestion) {
      messageActions += `<button class="memory-command" type="button">${session.paired ? "Guardar na memória" : "Memória privada"}</button>`;
    }
    if (data.local_command) {
      messageActions += `<button class="copy-command" type="button">Copiar comando</button>`;
      extra += `<details><summary>ver comando local</summary><code>${escapeHtml(data.local_command)}</code></details>`;
    }
    if (data.needs_confirmation && data.run_id) {
      messageActions += `<button class="confirm-agent-run" type="button">Confirmar ação</button>`;
      messageActions += `<button class="cancel-agent-run" type="button">Cancelar</button>`;
    }
    if (data.result) {
      extra += `<details><summary>ver resultado completo</summary><code>${escapeHtml(data.result)}</code></details>`;
    }
    if (Array.isArray(data.jobs) && data.jobs.length > 1 && !data.run?.terminal) {
      messageActions += `<button class="cancel-run" type="button">Cancelar etapas</button>`;
    } else if (data.job?.id && data.job.status === "pending") {
      messageActions += `<button class="cancel-job" type="button">Cancelar ação</button>`;
    }
    if (session.elevenlabs) {
      messageActions += `<button class="speak-command" type="button">Ouvir</button>`;
    }
    extra += `<div class="message-actions">${messageActions}</div>`;
    const message = streamedMessage || addMessage(answer, "jarvis", extra);
    if (streamedMessage) {
      message.className = "message jarvis";
      message.innerHTML = `<span>${messageHtml(answer)}</span>${extra}`;
      feed.scrollTop = feed.scrollHeight;
    }
    const copyResponse = message.querySelector(".copy-response");
    if (copyResponse) copyResponse.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(answer);
        copyResponse.textContent = "Copiado";
        window.setTimeout(() => { copyResponse.textContent = "Copiar"; }, 1600);
      } catch {
        copyResponse.textContent = "Não copiou";
      }
    });
    const copy = message.querySelector(".copy-command");
    if (copy) copy.addEventListener("click", async () => {
      await navigator.clipboard.writeText(data.local_command);
      copy.textContent = "Copiado";
    });
    const confirmAgentRun = message.querySelector(".confirm-agent-run");
    if (confirmAgentRun) confirmAgentRun.addEventListener("click", async () => {
      confirmAgentRun.disabled = true;
      confirmAgentRun.textContent = "Executando…";
      message.querySelector(".cancel-agent-run")?.setAttribute("disabled", "");
      try {
        const confirmed = await request(`/runs/${encodeURIComponent(data.run_id)}/confirm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        message.querySelector(".message-actions")?.remove();
        showResponse(confirmed);
      } catch {
        confirmAgentRun.disabled = false;
        confirmAgentRun.textContent = "Tentar confirmar novamente";
        message.querySelector(".cancel-agent-run")?.removeAttribute("disabled");
      }
    });
    const cancelAgentRun = message.querySelector(".cancel-agent-run");
    if (cancelAgentRun) cancelAgentRun.addEventListener("click", async () => {
      cancelAgentRun.disabled = true;
      cancelAgentRun.textContent = "Cancelando…";
      try {
        const canceled = await request(`/runs/${encodeURIComponent(data.run_id)}/cancel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        message.querySelector("span").textContent = canceled.message || "Ação cancelada.";
        message.querySelector(".message-actions")?.remove();
        refreshMessageExecutionContext(message, canceled);
      } catch {
        cancelAgentRun.disabled = false;
        cancelAgentRun.textContent = "Tentar cancelar novamente";
      }
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
      const kind = data.memory_candidate?.kind === "decision" ? "decisão" : data.memory_candidate?.kind === "preference" ? "preferência" : "aprendizado";
      sendCommand(`guarde na memória como ${kind}: ${data.memory_suggestion}`);
    });
    const replay = message.querySelector(".speak-command");
    if (replay) replay.addEventListener("click", async () => {
      if (session.speaking || session.voicePending) {
        stopSpeechOutput();
        replay.textContent = "Ouvir";
        return;
      }
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
        refreshMessageExecutionContext(message, canceled);
        refreshActionHistory();
      } catch (error) {
        cancelJob.disabled = false;
        cancelJob.textContent = "Tentar cancelar novamente";
      }
    });
    const cancelRun = message.querySelector(".cancel-run");
    if (cancelRun) cancelRun.addEventListener("click", async () => {
      cancelRun.disabled = true;
      cancelRun.textContent = "Cancelando pendentes…";
      const ids = data.jobs.map((job) => String(job.id));
      const results = await Promise.all(ids.map((id) => request("/device-cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      }).catch(() => ({ ok: false }))));
      results.forEach((result, index) => {
        if (result?.ok) session.canceledJobs.add(ids[index]);
      });
      cancelRun.textContent = "Cancelamento solicitado";
      refreshActionHistory();
    });
    byId("activityValue").textContent = data.executed_locally ? `Executado localmente · ${data.intent || "ação"}` : answer;
    updateActionHub(session.currentCommand, data);
    if (Array.isArray(data.jobs) && data.jobs.length > 1 && !data.run?.terminal) {
      monitorDeviceRun(data.jobs.map((job) => job.id), message);
    } else if (data.job?.id && ["pending", "running"].includes(data.job.status)) {
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
    resizeComposerInput();
    session.history.push({ role: "user", content: command });
    session.history = session.history.slice(-24);
    setRequest(command);
    const workingState = workingStateFor(command);
    beginRequestProgress(workingState);
    setWorking(true, workingState);
    let streamedMessage = null;
    let streamedText = "";
    const commandController = new AbortController();
    currentCommandController = commandController;
    const commandTimeout = window.setTimeout(() => commandController.abort(), 60000);
    try {
      const data = await requestCommandStream({
        command,
        messages: session.history,
        input_mode: options.source || "text",
        attachments,
      }, (event) => {
        if (event.type === "stream.phase") {
          byId("sceneDetail").textContent = event.label || "Processando pedido";
        }
        if (event.type === "stream.delta") {
          if (!streamedMessage) {
            streamedMessage = addMessage("", "jarvis streaming");
            streamedMessage.setAttribute("aria-live", "polite");
            streamedMessage.setAttribute("aria-busy", "true");
          }
          streamedText += event.delta || "";
          streamedMessage.querySelector("span").innerHTML = messageHtml(streamedText);
          feed.scrollTop = feed.scrollHeight;
        }
      }, commandController.signal);
      if (attachments.length) {
        session.attachments = [];
        renderAttachmentTray();
        clearAttachmentPreview();
      }
      session.lastResponseOk = data?.ok !== false;
      streamedMessage?.setAttribute("aria-busy", "false");
      showResponse(data, streamedMessage);
      if (Number(data?.event_stream?.elapsed_ms) >= 10000) {
        notifyBackgroundCompletion(data.event_stream.run_id, data.ok === false ? "JARVIS encontrou um problema" : "JARVIS terminou", data.message || data.error || data.summary || "Resultado disponível.");
      }
      const answer = data.message || data.summary;
      if (answer) {
        session.history.push({ role: "assistant", content: answer });
        session.history = session.history.slice(-24);
        window.setTimeout(syncConversationHistory, 0);
      }
    } catch (error) {
      streamedMessage?.remove();
      if (interruptedCommandControllers.has(commandController)) {
        return;
      }
      session.lastResponseOk = false;
      const offlineFailure = navigator.onLine === false || error instanceof TypeError;
      if (offlineFailure) {
        try {
          await saveOfflineCommand(command, attachments);
          await renderOfflineOutbox();
          showResponse({ ok: false, error: "Sem conexão. Guardei o pedido neste navegador; ele só será reenviado quando você confirmar." });
        } catch {
          showResponse({ ok: false, error: "Sem conexão e sem acesso ao armazenamento local. O pedido continua no histórico da conversa." });
        }
      } else {
        showResponse({ ok: false, error: "A conexão com o núcleo do JARVIS caiu." });
      }
    } finally {
      window.clearTimeout(commandTimeout);
      const ownsRequestState = currentCommandController === commandController;
      if (ownsRequestState) currentCommandController = null;
      if (ownsRequestState || !currentCommandController) {
        setWorking(false);
        finishRequestProgress(session.lastResponseOk);
        input.focus();
      }
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
    recognition.maxAlternatives = 1;
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
      resizeComposerInput();
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
      interruptActiveResponse();
      stopSpeechOutput();
      try {
        recognition.start();
      } catch {
        addMessage("O microfone já está iniciando. Aguarde um instante.", "error");
      }
    });
    voiceButton.title = "Clique para interromper qualquer resposta e falar imediatamente.";
    byId("voiceValue").textContent = "ouvir e responder";
  }

  async function boot() {
    renderNotificationState();
    updateConnectivity();
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
      const canLeaveOwnerMode = Boolean(session.paired && status.owner_pairing?.required);
      byId("accessMode").dataset.action = canLeaveOwnerMode ? "logout" : "details";
      byId("accessMode").title = canLeaveOwnerMode
        ? "Voltar ao modo visitante"
        : session.paired ? "Ver detalhes do acesso master" : "Entrar no modo master";
      byId("leaveOwnerMode").hidden = !canLeaveOwnerMode;
      byId("accessValue").textContent = session.paired
        ? "Theo master · memória, GitHub e Mac privados disponíveis"
        : status.access?.public_chat
          ? "Visitante · conversa liberada, memória e Mac privados"
          : "Visitante · conversa aguarda OpenRouter";
      const welcomeHint = byId("welcomeHint");
      if (welcomeHint) {
        welcomeHint.textContent = session.paired
          ? "Peça o resultado. Eu planejo, confirmo riscos e mostro a evidência."
          : "Conversa e pesquisa estão disponíveis. Memória e Mac exigem acesso do Theo.";
      }
      renderStarterActions();
      session.deviceBridge = Boolean(status.device_bridge?.configured);
      session.elevenlabs = Boolean(status.voice?.configured);
      session.voiceError = "";
      byId("voiceValue").textContent = session.elevenlabs
        ? `ElevenLabs${voiceSupport.input ? " + microfone" : ""}`
        : voiceSupport.input
          ? "microfone ativo · saída aguarda ElevenLabs"
          : "ElevenLabs aguarda chave";
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
      if (session.paired) {
        await Promise.all([restoreConversationHistory(), refreshPersonalOverview()]);
      } else {
        refreshPersonalOverview();
      }
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
  input.addEventListener("input", resizeComposerInput);
  input.addEventListener("paste", (event) => {
    const files = Array.from(event.clipboardData?.files || []);
    if (!files.length) return;
    event.preventDefault();
    addAttachments(files);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    byId("commandForm").requestSubmit();
  });
  input.addEventListener("blur", () => window.setTimeout(syncMobileViewport, 80));
  attachmentButton.addEventListener("click", () => attachmentInput.click());
  attachmentInput.addEventListener("change", () => addAttachments(attachmentInput.files));
  conversation.addEventListener("dragenter", (event) => {
    if (!Array.from(event.dataTransfer?.types || []).includes("Files")) return;
    event.preventDefault();
    conversation.classList.add("is-dragging");
  });
  conversation.addEventListener("dragover", (event) => {
    if (!Array.from(event.dataTransfer?.types || []).includes("Files")) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  });
  conversation.addEventListener("dragleave", (event) => {
    if (!conversation.contains(event.relatedTarget)) conversation.classList.remove("is-dragging");
  });
  conversation.addEventListener("drop", (event) => {
    const files = Array.from(event.dataTransfer?.files || []);
    conversation.classList.remove("is-dragging");
    if (!files.length) return;
    event.preventDefault();
    addAttachments(files);
  });
  pulseButton.addEventListener("click", () => {
    if (!currentPulse) return;
    const pulseData = {
      ui_cards: [{
        id: currentPulse.id,
        type: "agenda",
        status: currentPulse.overdue ? "overdue" : "upcoming",
        title: currentPulse.title,
        subtitle: "Sugestão; nenhuma ação executada",
        items: [currentPulse.message],
      }],
    };
    addMessage(currentPulse.message, "jarvis", renderMessageContext(pulseData));
    input.value = currentPulse.command || "";
    resizeComposerInput();
    input.focus();
    try { localStorage.setItem("jarvis-last-pulse", currentPulse.id); } catch { /* session-only dismissal */ }
    currentPulse = null;
    pulseButton.hidden = true;
  });
  byId("detailsButton").addEventListener("click", () => {
    dialog.showModal();
    refreshActionHistory();
  });
  byId("accessMode").addEventListener("click", () => {
    if (byId("accessMode").dataset.action === "logout") {
      exitOwnerMode(byId("accessMode"));
      return;
    }
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
  byId("clearOwnerToken").addEventListener("click", () => exitOwnerMode(byId("clearOwnerToken")));
  byId("leaveOwnerMode").addEventListener("click", () => exitOwnerMode(byId("leaveOwnerMode")));
  actionHubButton.addEventListener("click", () => setActionHub(actionHub.hidden));
  actionHubBackdrop.addEventListener("click", () => setActionHub(false));
  actionHubSearch.addEventListener("input", () => updateActionHub(session.currentCommand));
  actionHubSearch.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown") return;
    event.preventDefault();
    actionHub.querySelector("button[data-hub-command]")?.focus();
  });
  actionHub.addEventListener("keydown", (event) => {
    if (!event.target.matches("button[data-hub-command]") || !["ArrowDown", "ArrowUp"].includes(event.key)) return;
    const actions = Array.from(actionHub.querySelectorAll("button[data-hub-command]"));
    const index = actions.indexOf(event.target);
    event.preventDefault();
    if (event.key === "ArrowUp" && index <= 0) actionHubSearch.focus();
    else actions[Math.max(0, Math.min(actions.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)))]?.focus();
  });
  newConversationButton?.addEventListener("click", startNewConversation);
  mobileChatToggle?.addEventListener("click", () => {
    setMobileChatExpanded(mobileChatToggle.getAttribute("aria-expanded") !== "true");
  });
  installButton?.addEventListener("click", requestInstall);
  byId("closeInstallDialog")?.addEventListener("click", () => installDialog.close());
  installDialog?.addEventListener("click", (event) => {
    if (event.target === installDialog) installDialog.close();
  });
  byId("closeActionHub").addEventListener("click", () => setActionHub(false));
  byId("tourButton").addEventListener("click", () => {
    if (dialog.open) dialog.close();
    tourDialog.showModal();
  });
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
  byId("memoryManagerButton")?.addEventListener("click", () => {
    dialog.close();
    memoryDialog.showModal();
    loadMemoryManager();
  });
  byId("closeMemoryDialog")?.addEventListener("click", () => memoryDialog.close());
  memoryDialog?.addEventListener("click", (event) => {
    if (event.target === memoryDialog) memoryDialog.close();
  });
  byId("memoryManagerSearch")?.addEventListener("input", renderMemoryManager);
  byId("memoryManagerKind")?.addEventListener("change", renderMemoryManager);
  byId("taskQueueButton")?.addEventListener("click", () => {
    dialog.close();
    taskDialog.showModal();
    loadTaskBoard();
  });
  byId("closeTaskDialog")?.addEventListener("click", () => taskDialog.close());
  taskDialog?.addEventListener("click", (event) => {
    if (event.target === taskDialog) taskDialog.close();
  });
  byId("taskQuickAdd")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = byId("taskQuickText").value.trim();
    if (!text) return;
    const data = await request("/tasks/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, project: byId("taskQuickProject").value.trim() }),
    });
    if (data.ok === false) {
      byId("taskSummary").textContent = data.error || "Tarefa não criada.";
      return;
    }
    byId("taskQuickText").value = "";
    loadTaskBoard();
  });
  byId("fileWorkspaceButton")?.addEventListener("click", () => {
    dialog.close();
    fileWorkspaceDialog.showModal();
    renderFileWorkspace();
  });
  byId("closeFileWorkspace")?.addEventListener("click", () => fileWorkspaceDialog.close());
  fileWorkspaceDialog?.addEventListener("click", (event) => {
    if (event.target === fileWorkspaceDialog) fileWorkspaceDialog.close();
  });
  byId("workspaceFileInput")?.addEventListener("change", (event) => storeFilesInWorkspace(event.target.files));
  byId("clearFileWorkspace")?.addEventListener("click", async () => {
    if (!window.confirm("Remover todos os arquivos guardados neste navegador?")) return;
    await deleteWorkspaceFile();
    renderFileWorkspace();
  });
  byId("notificationButton")?.addEventListener("click", toggleNotifications);
  byId("retryOfflineOutbox")?.addEventListener("click", async () => {
    const rows = await readOfflineOutbox().catch(() => []);
    const next = rows[0];
    if (!next) return renderOfflineOutbox();
    await deleteOfflineCommand(next.id);
    await renderOfflineOutbox();
    sendCommand(next.command, { source: "offline-outbox" });
  });
  byId("discardOfflineOutbox")?.addEventListener("click", async () => {
    if (!window.confirm("Descartar todos os pedidos guardados offline?")) return;
    await deleteOfflineCommand();
    renderOfflineOutbox();
  });
  window.addEventListener("online", () => {
    updateConnectivity();
    boot();
  });
  window.addEventListener("offline", updateConnectivity);
  byId("refreshRunHistory")?.addEventListener("click", refreshActionHistory);
  byId("runHistoryFilter")?.addEventListener("change", refreshActionHistory);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  window.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      setActionHub(actionHub.hidden);
      if (!actionHub.hidden) actionHubSearch.focus();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "n") {
      event.preventDefault();
      if (!actionHub.hidden) setActionHub(false);
      startNewConversation();
      return;
    }
    if (event.key === "Tab" && !actionHub.hidden) {
      const controls = Array.from(actionHub.querySelectorAll("button:not([disabled]), a[href], summary, input:not([disabled])"))
        .filter((control) => control.getClientRects().length > 0);
      const first = controls[0];
      const last = controls.at(-1);
      if (first && event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (last && !event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
      return;
    }
    if (event.key === "Escape" && !actionHub.hidden) setActionHub(false);
    else if (event.key === "Escape" && (session.working || session.speaking || session.voicePending)) {
      interruptActiveResponse();
      stopSpeechOutput();
    } else if (event.key === "Escape" && mobileLayout.matches && stage.classList.contains("mobile-chat-expanded")) setMobileChatExpanded(false);
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
  resizeComposerInput();
  registerMobileShell();
  installVoiceInput();
  boot();
  window.setInterval(refreshPulse, 10 * 60 * 1000);
})();
