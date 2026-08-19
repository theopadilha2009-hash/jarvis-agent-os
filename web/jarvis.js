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
  const dialog = byId("systemDialog");
  const tourDialog = byId("tourDialog");
  const actionHub = byId("actionHub");
  const actionHubButton = byId("actionHubButton");
  const mobileChatToggle = byId("mobileChatToggle");
  const newConversationButton = byId("newConversationButton");
  const qualityButton = byId("qualityButton");
  const strengthButton = byId("strengthButton");
  const integrationsButton = byId("integrationsButton");
  const integrationsDialog = byId("integrationsDialog");
  const installButton = byId("installButton");
  const installDialog = byId("installDialog");
  const mobileLayout = window.matchMedia("(max-width: 720px)");
  const CREATOR_MARK = "VGhlbyBMb3JlbnR6IFBhZGlsaGE=";
  const creatorName = () => {
    if (window.JarvisCreator?.name) {
      try { return window.JarvisCreator.name(); } catch { /* selo ausente */ }
    }
    try { return window.atob(CREATOR_MARK); } catch { return "Theo Lorentz Padilha"; }
  };
  const OWNER_TOKEN_KEY = "jarvis-owner-token-v1";
  const OWNER_IDLE_KEY = "jarvis-owner-last-active";
  const LAST_LOGIN_KEY = "jarvis-last-login";
  const REMEMBER_KEY = "jarvis-remember-login-v1";
  const OWNER_IDLE_MS = 12 * 60 * 60 * 1000;
  const CONVERSATION_SESSION_KEY = "jarvis-conversation-session";
  const LOCAL_HISTORY_KEY = "jarvis-conversation-local";
  // v3: a janela nasce como painel à direita. Trocar a chave descarta as
  // geometrias salvas antes disso (achatadas, ou centradas no rodapé).
  const CHAT_RECT_KEY = "jarvis-chat-rect-v4";
  const MAX_VISIBLE_MESSAGES = 24;
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceSupport = {
    input: Boolean(Recognition),
  };
  const RESPONSE_STRENGTH = ["auto", "strong", "maximum"];
  const RESPONSE_STRENGTH_LABELS = {
    auto: ["Auto", "Automática"],
    strong: ["Forte", "Forte"],
    maximum: ["Máxima", "Máxima"],
  };
  const API_PROVIDERS = {
    n8n: {
      label: "n8n",
      eyebrow: "AUTOMAÇÃO",
      tools: [
        { name: "list_workflows", label: "Ler workflows", description: "Lista workflows sem alterar nada.", effect: "read", fields: [] },
        { name: "list_executions", label: "Ler execuções", description: "Lista execuções recentes sem trazer os payloads.", effect: "read", fields: [] },
      ],
      fields: [
        { name: "base_url", label: "URL da instância", placeholder: "https://sua-instancia.app.n8n.cloud", secret: false },
        { name: "api_key", label: "API key", placeholder: "Chave criada em Settings > n8n API", secret: true },
      ],
    },
    openrouter: {
      label: "OpenRouter",
      eyebrow: "INTELIGÊNCIA",
      tools: [
        { name: "inspect_account", label: "Ver uso da chave", description: "Consulta saldo e uso atual.", effect: "read", fields: [] },
        { name: "list_models", label: "Listar modelos", description: "Mostra modelos e janelas de contexto disponíveis.", effect: "read", fields: [] },
      ],
      fields: [{ name: "api_key", label: "API key", placeholder: "sk-or-v1-…", secret: true }],
    },
    elevenlabs: {
      label: "ElevenLabs",
      eyebrow: "VOZ",
      tools: [
        { name: "list_voices", label: "Listar vozes", description: "Mostra as vozes disponíveis.", effect: "read", fields: [] },
        { name: "inspect_subscription", label: "Ver assinatura", description: "Mostra plano, caracteres e slots de voz.", effect: "read", fields: [] },
      ],
      fields: [{ name: "api_key", label: "API key", placeholder: "Chave da ElevenLabs", secret: true }],
    },
    openai: {
      label: "OpenAI",
      eyebrow: "VOZ RESERVA",
      tools: [],
      fields: [{ name: "api_key", label: "API key", placeholder: "sk-…  (voz neural quando a ElevenLabs cair)", secret: true }],
    },
    github: {
      label: "GitHub",
      eyebrow: "CÓDIGO",
      tools: [
        { name: "list_repositories", label: "Ler repositórios", description: "Lista os repositórios acessíveis.", effect: "read", fields: [] },
        ...["issues", "pull requests", "commits", "deploys"].map((label, index) => ({
          name: ["list_issues", "list_pull_requests", "list_commits", "list_deployments"][index],
          label: `Ler ${label}`,
          description: `Lista ${label} recentes sem alterar o repositório.`,
          effect: "read",
          fields: [{ name: "repository", label: "Repositório", placeholder: "owner/nome", type: "text" }],
        })),
      ],
      fields: [{ name: "api_key", label: "Fine-grained token", placeholder: "github_pat_…", secret: true }],
    },
    supabase: {
      label: "Supabase",
      eyebrow: "DADOS",
      tools: [{
        name: "read_rows",
        label: "Ler tabela",
        description: "Lê até 20 linhas sem fazer insert, update ou delete.",
        effect: "read",
        fields: [
          { name: "table", label: "Tabela", placeholder: "jarvis_memories", type: "text" },
          { name: "limit", label: "Limite", placeholder: "10", type: "number", value: "10" },
        ],
      }],
      fields: [
        { name: "base_url", label: "Project URL", placeholder: "https://projeto.supabase.co", secret: false },
        { name: "api_key", label: "Publishable / secret key", placeholder: "sb_publishable_…", secret: true },
      ],
    },
    webhook: {
      label: "Webhook",
      eyebrow: "API PERSONALIZADA",
      tools: [{
        name: "send_event",
        label: "Enviar evento",
        description: "Envia um JSON real. Exige modo Ultron e uma confirmação explícita.",
        effect: "external_write",
        fields: [{ name: "payload", label: "Evento JSON", placeholder: '{\n  "event": "jarvis.test"\n}', type: "textarea" }],
      }],
      fields: [
        { name: "base_url", label: "Endpoint HTTPS", placeholder: "https://api.exemplo.com/health", secret: false },
        { name: "api_key", label: "Bearer token opcional", placeholder: "Token", secret: true },
      ],
    },
  };
  let activeIntegrationProvider = "n8n";
  let integrationSecretVisible = false;

  const session = {
    listening: false,
    speaking: false,
    voicePending: false,
    working: false,
    workingState: "thinking",
    elevenlabs: false,
    localVoice: false,
    voiceError: "",
    voiceFirstAudioMs: 0,
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
    codeMode: false,
    accountName: "",
    canManageAccounts: false,
    deviceOnline: false,
    deviceBridge: false,
    canceledJobs: new Set(),
    attachments: [],
    historyRestored: false,
    currentCommand: "",
    mission: null,
    memoryViewing: false,
    overview: null,
    workingStartedAt: 0,
    lastResponseOk: true,
    lastError: "",
    filePreviewing: false,
    strength: (() => {
      try {
        const saved = localStorage.getItem("jarvis-response-strength");
        return RESPONSE_STRENGTH.includes(saved) ? saved : "auto";
      } catch {
        return "auto";
      }
    })(),
  };

  const GRAPHICS_QUALITY = ["excellent", "medium", "low"];
  const GRAPHICS_LABELS = { excellent: "Excelente", medium: "Média", low: "Baixa" };
  let graphicsQuality = (() => {
    try {
      const saved = localStorage.getItem("jarvis-graphics-quality");
      return GRAPHICS_QUALITY.includes(saved) ? saved : "excellent";
    } catch {
      return "excellent";
    }
  })();

  function applyGraphicsQuality() {
    if (qualityButton) {
      qualityButton.textContent = GRAPHICS_LABELS[graphicsQuality];
      qualityButton.dataset.quality = graphicsQuality;
      qualityButton.setAttribute("aria-label", `Qualidade gráfica: ${GRAPHICS_LABELS[graphicsQuality]}. Clique para mudar.`);
    }
    stage.dataset.graphicsQuality = graphicsQuality;
    window.dispatchEvent(new CustomEvent("jarvis-graphics-quality", { detail: { quality: graphicsQuality } }));
  }
  let currentAudio = null;
  let currentAudioUrl = "";
  let currentSpeechController = null;
  let speechGeneration = 0;
  let voiceFailureNotified = false;
  let currentPulse = null;
  let progressInterval = 0;
  let progressHideTimer = 0;
  let filePreviewTimer = 0;
  let deferredInstallPrompt = null;
  let viewportCeiling = Math.round(window.visualViewport?.height || window.innerHeight);
  let viewportWidth = window.innerWidth;
  let voiceLevel = 0;
  let voiceAudioContext = null;
  let ultronSignalTimer = 0;

  function conversationSessionId() {
    try {
      let id = localStorage.getItem(CONVERSATION_SESSION_KEY) || "";
      if (!/^[A-Za-z0-9_-]{8,80}$/.test(id)) {
        id = (window.crypto?.randomUUID?.() || `c-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`).replace(/[^A-Za-z0-9_-]/g, "");
        localStorage.setItem(CONVERSATION_SESSION_KEY, id);
      }
      return id;
    } catch {
      return "";
    }
  }

  function localHistoryKey() {
    return `${LOCAL_HISTORY_KEY}:${conversationSessionId()}`;
  }

  function readLocalHistory() {
    try {
      const rows = JSON.parse(localStorage.getItem(localHistoryKey()) || "[]");
      if (!Array.isArray(rows)) return [];
      return rows.filter((row) => row && (row.role === "user" || row.role === "assistant") && typeof row.content === "string").slice(-24);
    } catch {
      return [];
    }
  }

  function writeLocalHistory() {
    try {
      localStorage.setItem(localHistoryKey(), JSON.stringify(session.history.slice(-24)));
    } catch { /* quota / private mode */ }
  }

  function renderOccupancy(data) {
    const target = byId("conversationOccupancy");
    if (!target) return;
    const online = Math.max(1, Number(data?.online) || 1);
    const waiting = Number(data?.waiting) || 0;
    target.textContent = waiting
      ? `${online} aqui · ${waiting} na fila`
      : online === 1
        ? "1 neste computador"
        : `${online} computadores agora`;
    target.title = "Cada computador tem o próprio chat. Memória permanente só se você pedir.";
  }

  function copyBugReport() {
    const lastUser = [...session.history].reverse().find((row) => row.role === "user");
    const lastAssistant = [...session.history].reverse().find((row) => row.role === "assistant");
    const report = [
      "BUG JARVIS (visitante)",
      `quando: ${new Date().toISOString()}`,
      `url: ${window.location.origin}${window.location.pathname}`,
      `modo: ${session.paired ? "ULTRON (não deveria estar assim num amigo)" : "visitante"}`,
      `pedido: ${lastUser?.content || session.currentCommand || "—"}`,
      `resposta: ${(lastAssistant?.content || "").slice(0, 280) || "—"}`,
      `erro: ${session.lastError || "nenhum erro gravado"}`,
      "como reportar: manda isso pro Theo no WhatsApp",
    ].join("\n");
    const done = (ok) => {
      const hint = byId("welcomeHint");
      if (hint) hint.textContent = ok ? "Relatório copiado. Manda pro Theo no WhatsApp." : "Não deu pra copiar. Seleciona o texto e manda no WhatsApp.";
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(report).then(() => done(true)).catch(() => done(false));
      return;
    }
    done(false);
  }

  function assistantName() {
    return session.paired ? "ULTRON" : "JARVIS";
  }

  function identityText(value) {
    const text = String(value || "");
    if (!session.paired) return text;
    return text
      .replace(/\bJARVIS\b/gi, "ULTRON");
  }

  function renderStrength() {
    if (!strengthButton) return;
    const [shortLabel, fullLabel] = RESPONSE_STRENGTH_LABELS[session.strength] || RESPONSE_STRENGTH_LABELS.auto;
    strengthButton.querySelector("b").textContent = shortLabel;
    strengthButton.dataset.strength = session.strength;
    strengthButton.setAttribute("aria-label", `Força da resposta: ${fullLabel}`);
    strengthButton.title = {
      auto: "Auto adapta velocidade e profundidade ao pedido",
      strong: "Forte prioriza modelos e respostas de maior qualidade",
      maximum: "Máxima usa a rota mais profunda disponível",
    }[session.strength];
  }

  function apiVault() {
    if (!window.JarvisApiVault) throw new Error("O cofre local ainda não terminou de carregar.");
    return window.JarvisApiVault;
  }

  function renderApiPower() {
    const badge = byId("apiPowerBadge");
    if (badge) badge.textContent = session.paired ? "ULTRON · 3×" : "JARVIS · 1×";
    if (byId("integrationsDialogTitle")) {
      byId("integrationsDialogTitle").textContent = session.paired ? "ARSENAL DE APIs · ULTRON" : "CENTRAL DE APIs · JARVIS";
    }
  }

  function renderIntegrationRegistry() {
    let configured = [];
    try { configured = apiVault().list().map((item) => item.provider); } catch { configured = []; }
    document.querySelectorAll("[data-provider]").forEach((button) => {
      const active = button.dataset.provider === activeIntegrationProvider;
      const connected = configured.includes(button.dataset.provider);
      button.classList.toggle("active", active);
      button.classList.toggle("configured", connected);
      const status = button.querySelector("em");
      if (status) status.textContent = connected ? "salva" : "—";
    });
    if (byId("integrationsCount")) byId("integrationsCount").textContent = String(configured.length);
    renderApiPower();
    window.dispatchEvent(new Event("jarvis-integration-registry"));
    return configured;
  }

  function setIntegrationFeedback(message, state = "") {
    const target = byId("integrationFeedback");
    if (!target) return;
    target.textContent = message;
    target.dataset.state = state;
    if (state) byId("integrationConnectionState").dataset.state = state;
  }

  function renderIntegrationHistory() {
    window.JarvisIntegrationHistory?.render();
  }

  function recordIntegrationActivity(provider, action, data) {
    window.JarvisIntegrationHistory?.record(provider, action, data);
  }

  function renderIntegrationFields(config = {}) {
    const definition = API_PROVIDERS[activeIntegrationProvider];
    if (!definition) return;
    byId("integrationEditorEyebrow").textContent = definition.eyebrow;
    byId("integrationEditorTitle").textContent = definition.label;
    integrationSecretVisible = false;
    byId("integrationRevealButton").textContent = "Mostrar";
    byId("integrationFields").innerHTML = definition.fields.map((field) => (
      `<label>${escapeHtml(field.label)}`
      + `<input data-integration-field="${field.name}" ${field.secret ? 'data-secret="true" type="password" autocomplete="new-password"' : 'type="url" autocomplete="url"'} `
      + `value="${escapeHtml(config[field.name] || "")}" placeholder="${escapeHtml(field.placeholder)}"></label>`
    )).join("");
    const configured = Boolean(config && Object.keys(config).length);
    const connectionState = byId("integrationConnectionState");
    connectionState.textContent = configured ? "configurada" : "não configurada";
    connectionState.dataset.state = configured ? "configured" : "idle";
    byId("integrationRemoveButton").disabled = !configured;
    byId("integrationCopyButton").disabled = !config.api_key;
    byId("n8nStudio").hidden = activeIntegrationProvider !== "n8n";
    window.JarvisIntegrationTabs?.provider(activeIntegrationProvider);
    renderIntegrationTool();
  }

  function renderIntegrationTool() {
    const definition = API_PROVIDERS[activeIntegrationProvider];
    const tools = definition?.tools || [];
    const selector = byId("integrationToolSelect");
    const previous = selector.value;
    selector.replaceChildren(...tools.map((item) => {
      const option = document.createElement("option");
      option.value = item.name;
      option.textContent = item.label;
      return option;
    }));
    if (tools.some((item) => item.name === previous)) selector.value = previous;
    const tool = tools.find((item) => item.name === selector.value) || tools[0];
    if (!tool) return;
    byId("integrationToolTitle").textContent = tool.label;
    byId("integrationToolDescription").textContent = tool.description;
    byId("integrationToolEffect").textContent = tool.effect === "external_write" ? "AÇÃO EXTERNA" : "SOMENTE LEITURA";
    byId("integrationToolEffect").dataset.effect = tool.effect;
    byId("integrationToolRunButton").textContent = tool.effect === "external_write" ? "Confirmar e enviar" : "Executar agora";
    byId("integrationToolFields").innerHTML = (tool.fields || []).map((field) => {
      const value = escapeHtml(field.value || "");
      if (field.type === "textarea") {
        return `<label>${escapeHtml(field.label)}<textarea data-tool-field="${field.name}" rows="4" placeholder="${escapeHtml(field.placeholder)}">${value}</textarea></label>`;
      }
      return `<label>${escapeHtml(field.label)}<input data-tool-field="${field.name}" type="${field.type || "text"}" value="${value}" placeholder="${escapeHtml(field.placeholder)}"></label>`;
    }).join("");
    byId("integrationToolResult").textContent = "Nenhuma execução nesta sessão.";
    renderIntegrationHistory();
  }

  function currentIntegrationTool() {
    const tools = API_PROVIDERS[activeIntegrationProvider]?.tools || [];
    return tools.find((item) => item.name === byId("integrationToolSelect")?.value) || tools[0];
  }

  function integrationToolParameters() {
    const parameters = {};
    byId("integrationToolFields").querySelectorAll("[data-tool-field]").forEach((field) => {
      const value = String(field.value || "").trim();
      if (!value) return;
      if (field.dataset.toolField === "payload") {
        parameters.payload = JSON.parse(value);
      } else if (field.type === "number") {
        parameters[field.dataset.toolField] = Number(value);
      } else {
        parameters[field.dataset.toolField] = value;
      }
    });
    return parameters;
  }

  async function runActiveIntegrationTool() {
    const definition = API_PROVIDERS[activeIntegrationProvider];
    const tool = currentIntegrationTool();
    if (!tool) return;
    let parameters;
    try {
      parameters = integrationToolParameters();
    } catch {
      setIntegrationFeedback("O evento precisa ser um JSON válido.", "error");
      byId("integrationToolResult").textContent = "Execução recusada antes de chamar a API.";
      return;
    }
    if (tool.effect === "external_write") {
      if (!session.paired) {
        setIntegrationFeedback("Entre no modo Ultron para autorizar um envio externo.", "error");
        return;
      }
      if (!await window.JarvisFeatureLoader?.authorize("outbound", `Enviar evento para ${definition.label}`)) {
        setIntegrationFeedback("Envio externo cancelado.", "error");
        return;
      }
    }
    const button = byId("integrationToolRunButton");
    button.disabled = true;
    byId("integrationToolResult").textContent = "Executando pelo adaptador verificado…";
    try {
      const config = integrationConfigFromFields();
      const data = await request("/integrations/tools", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: activeIntegrationProvider,
          tool: tool.name,
          parameters,
          confirmed: tool.effect === "external_write",
          config,
        }),
      });
      byId("integrationToolResult").textContent = data.ok
        ? `${data.message || "Ferramenta concluída."}\n\n${JSON.stringify(data.result, null, 2)}`
        : data.error || "A ferramenta não confirmou a execução.";
      setIntegrationFeedback(data.message || data.error || "Ferramenta concluída.", data.ok ? "success" : "error");
      recordIntegrationActivity(activeIntegrationProvider, tool.name, data);
    } catch {
      byId("integrationToolResult").textContent = "O núcleo não respondeu durante a execução.";
      setIntegrationFeedback("A ferramenta perdeu a conexão com o núcleo.", "error");
      recordIntegrationActivity(activeIntegrationProvider, tool.name, { ok: false, error: "conexão com o núcleo interrompida" });
    } finally {
      button.disabled = false;
    }
  }

  function integrationConfigFromFields() {
    const config = {};
    byId("integrationFields").querySelectorAll("[data-integration-field]").forEach((field) => {
      const value = String(field.value || "").trim();
      if (value) config[field.dataset.integrationField] = value;
    });
    return config;
  }

  async function selectIntegrationProvider(provider) {
    if (!API_PROVIDERS[provider]) return;
    activeIntegrationProvider = provider;
    renderIntegrationRegistry();
    setIntegrationFeedback("Abrindo o cofre local…");
    try {
      const config = await apiVault().get(provider) || {};
      renderIntegrationFields(config);
      setIntegrationFeedback(
        Object.keys(config).length
          ? "Configuração aberta somente neste dispositivo. Você pode testar, copiar, substituir ou remover."
          : "Cole os dados da API e salve. Nada será gravado no servidor.",
      );
    } catch (error) {
      renderIntegrationFields({});
      setIntegrationFeedback(error.message || "Não foi possível abrir o cofre.", "error");
    }
  }

  async function runtimeClientIntegrations(command = "") {
    const providers = ["openrouter", "elevenlabs"];
    if (/\b(?:n8n|workflow|fluxo|automa[cç][aã]o)\b/i.test(command)) providers.push("n8n");
    const integrations = {};
    await Promise.all(providers.map(async (provider) => {
      try {
        const config = await apiVault().get(provider);
        if (config) integrations[provider] = config;
      } catch {
        // A falha de um segredo local não derruba conversa nem voz.
      }
    }));
    return integrations;
  }

  async function saveActiveIntegration() {
    const config = integrationConfigFromFields();
    const definition = API_PROVIDERS[activeIntegrationProvider];
    const needsUrl = definition.fields.some((field) => field.name === "base_url");
    if ((needsUrl && !config.base_url) || (activeIntegrationProvider !== "webhook" && !config.api_key)) {
      setIntegrationFeedback("Preencha os campos obrigatórios antes de salvar.", "error");
      return;
    }
    byId("integrationSaveButton").disabled = true;
    setIntegrationFeedback("Criptografando neste dispositivo…");
    try {
      await apiVault().save(activeIntegrationProvider, config);
      renderIntegrationRegistry();
      renderIntegrationFields(config);
      setIntegrationFeedback(`${definition.label} salva e disponível para o runtime.`, "success");
    } catch (error) {
      setIntegrationFeedback(error.message || "Não foi possível proteger esta configuração.", "error");
    } finally {
      byId("integrationSaveButton").disabled = false;
    }
  }

  async function testActiveIntegration() {
    const config = integrationConfigFromFields();
    byId("integrationTestButton").disabled = true;
    setIntegrationFeedback("Testando diretamente no provedor…");
    try {
      const data = await request("/integrations/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: activeIntegrationProvider, config }),
      });
      setIntegrationFeedback(data.message || data.error || "Teste concluído.", data.ok ? "success" : "error");
      recordIntegrationActivity(activeIntegrationProvider, "test_connection", data);
    } catch {
      setIntegrationFeedback("A conexão com o núcleo caiu durante o teste.", "error");
      recordIntegrationActivity(activeIntegrationProvider, "test_connection", { ok: false, error: "conexão com o núcleo interrompida" });
    } finally {
      byId("integrationTestButton").disabled = false;
    }
  }

  async function copyActiveIntegrationSecret() {
    try {
      const config = await apiVault().get(activeIntegrationProvider);
      if (!config?.api_key) throw new Error("Nenhuma chave salva para copiar.");
      await navigator.clipboard.writeText(config.api_key);
      setIntegrationFeedback("Chave copiada. Evite colá-la em conversas ou arquivos.", "success");
    } catch (error) {
      setIntegrationFeedback(error.message || "O navegador bloqueou a cópia.", "error");
    }
  }

  async function removeActiveIntegration() {
    const definition = API_PROVIDERS[activeIntegrationProvider];
    if (!window.confirm(`Remover ${definition.label} deste dispositivo?`)) return;
    apiVault().remove(activeIntegrationProvider);
    renderIntegrationRegistry();
    renderIntegrationFields({});
    setIntegrationFeedback(`${definition.label} removida do cofre local.`, "success");
  }

  function toggleIntegrationSecret() {
    integrationSecretVisible = !integrationSecretVisible;
    byId("integrationFields").querySelectorAll("[data-secret='true']").forEach((field) => {
      field.type = integrationSecretVisible ? "text" : "password";
    });
    byId("integrationRevealButton").textContent = integrationSecretVisible ? "Ocultar" : "Mostrar";
  }

  function renderN8nWorkflowResult(data) {
    const map = byId("n8nWorkflowMap");
    const list = byId("n8nWorkflowList");
    const summary = byId("n8nWorkflowSummary");
    const clearMap = () => map?.replaceChildren();
    const clearList = () => list?.replaceChildren();
    const renderMap = (plan, workflow) => {
      clearMap();
      clearList();
      const stages = Array.isArray(plan?.stages)
        ? plan.stages
        : Array.isArray(workflow?.nodes)
          ? workflow.nodes.map((node) => ({ label: node.name, kind: "node", description: node.type, status: node.disabled ? "needs_setup" : "ready" }))
          : [];
      stages.forEach((stage, index) => {
        const node = document.createElement("article");
        node.className = "n8n-map-node";
        node.dataset.status = stage.status || "ready";
        const order = document.createElement("small");
        order.textContent = String(index + 1).padStart(2, "0");
        const name = document.createElement("strong");
        name.textContent = stage.label || "Etapa";
        const description = document.createElement("span");
        description.textContent = stage.description || stage.kind || "etapa do workflow";
        const state = document.createElement("em");
        state.textContent = stage.requires_setup || stage.disabled ? "configurar" : stage.status === "review" ? "revisar" : "pronto";
        node.append(order, name, description, state);
        map?.appendChild(node);
        if (index < stages.length - 1) {
          const connector = document.createElement("i");
          connector.className = "n8n-map-connector";
          connector.setAttribute("aria-hidden", "true");
          map?.appendChild(connector);
        }
      });
    };
    const planSummary = (plan, prefix = "PREVIEW") => {
      if (!plan) return prefix;
      const setup = Array.isArray(plan.required_setup) && plan.required_setup.length
        ? `Configurar antes de ativar: ${plan.required_setup.map((item) => `${item.label} (${item.fields?.join(", ") || "campos indicados"})`).join("; ")}.`
        : "Nenhuma credencial externa exigida neste rascunho.";
      const omitted = Array.isArray(plan.omitted_actions) && plan.omitted_actions.length
        ? ` Limite ${plan.source}: ficaram para outro fluxo: ${plan.omitted_actions.join(", ")}.`
        : "";
      return `${prefix} · ${plan.node_count} nós · gatilho ${plan.trigger}.\n${setup}${omitted}\nAtivação bloqueada até revisão e teste manual.`;
    };
    if (!data?.ok) {
      clearMap();
      clearList();
      summary.textContent = data?.error || "O n8n não confirmou a operação.";
      return;
    }
    if (data.inspection && data.status_real === "n8n_workflow_inspected") {
      clearMap();
      const inspection = data.inspection;
      summary.textContent = [
        `INSPEÇÃO · ${inspection.name}`,
        `${inspection.active ? "ATIVO" : "INATIVO"} · ${inspection.node_count} nós · ${inspection.trigger_nodes.length} gatilho(s)`,
        inspection.disabled_nodes.length ? `Desativados: ${inspection.disabled_nodes.join(", ")}.` : "Nenhuma etapa desativada.",
        inspection.external_nodes.length ? `Ações externas: ${inspection.external_nodes.join(", ")}.` : "Sem ação externa detectada.",
        inspection.review_nodes.length ? `Revisão forte: ${inspection.review_nodes.join(", ")}.` : "Nenhum nó de código/comando detectado.",
        "Ativação continua manual depois da revisão e do teste no n8n.",
      ].join("\n");
      return;
    }
    if (Array.isArray(data.workflow_previews)) {
      const primary = data.workflow_previews[0];
      renderMap(primary?.plan, primary);
      summary.textContent = data.workflow_previews.map((item, index) => (
        `${index + 1}. ${item.name}\n${planSummary(item.plan)}`
      )).join("\n\n");
      return;
    }
    if (data.provider === "n8n" && data.status_real?.includes("created_inactive") && Array.isArray(data.workflows)) {
      renderMap(data.workflow?.plan || data.plan, data.workflow);
      summary.textContent = data.workflows.map((item, index) => (
        `${index + 1}. INATIVO · ${item.name}${item.editor_url ? `\n${item.editor_url}` : ""}\n${planSummary(item.plan, "CRIADO")}`
      )).join("\n\n");
      return;
    }
    if (Array.isArray(data.workflows)) {
      clearMap();
      clearList();
      data.workflows.forEach((item) => {
        const row = document.createElement("article");
        row.className = "n8n-workflow-row";
        const copy = document.createElement("span");
        const name = document.createElement("strong");
        name.textContent = item.name || "Workflow";
        const meta = document.createElement("small");
        meta.textContent = `${item.active ? "ATIVO" : "INATIVO"} · ${item.id || "sem id"}`;
        copy.append(name, meta);
        const actions = document.createElement("div");
        if (item.id) {
          const inspect = document.createElement("button");
          inspect.type = "button";
          inspect.dataset.n8nWorkflowAction = "inspect";
          inspect.dataset.workflowId = item.id;
          inspect.textContent = "Inspecionar";
          const duplicate = document.createElement("button");
          duplicate.type = "button";
          duplicate.dataset.n8nWorkflowAction = "duplicate";
          duplicate.dataset.workflowId = item.id;
          duplicate.textContent = "Duplicar inativo";
          actions.append(inspect, duplicate);
        }
        row.append(copy, actions);
        list?.appendChild(row);
      });
      summary.textContent = data.workflows.length ? `${data.workflows.length} workflow(s). Inspecione sem executar ou duplique como inativo.` : "Nenhum workflow encontrado.";
      return;
    }
    if (data.workflow?.nodes && Array.isArray(data.workflow.nodes)) {
      renderMap(data.plan, data.workflow);
      summary.textContent = `${data.workflow.name}\n${planSummary(data.plan)}\nNada foi enviado ao n8n.`;
      return;
    }
    clearMap();
    summary.textContent = `${data.message || "Workflow criado."}${data.workflow?.editor_url ? `\n${data.workflow.editor_url}` : ""}`;
  }

  async function runN8nWorkflowAction(action, workflowId = "") {
    const goal = byId("n8nWorkflowGoal").value.trim();
    const goals = goal.split("||").map((item) => item.trim()).filter(Boolean).slice(0, session.paired ? 3 : 1);
    if (["preview", "create"].includes(action) && !goal) {
      setIntegrationFeedback("Descreva o objetivo do workflow primeiro.", "error");
      byId("n8nWorkflowGoal").focus();
      return;
    }
    if (session.paired && ["create", "duplicate"].includes(action)
      && !await window.JarvisFeatureLoader?.authorize("automation", action === "create" ? "Criar workflow inativo no n8n" : "Duplicar workflow inativo no n8n")) {
      setIntegrationFeedback("Operação n8n cancelada.", "error");
      return;
    }
    const config = await apiVault().get("n8n") || {};
    const button = byId(action === "preview" ? "n8nPreviewButton" : action === "create" ? "n8nCreateButton" : "n8nListButton");
    button.disabled = true;
    byId("n8nWorkflowMap")?.replaceChildren();
    byId("n8nWorkflowSummary").textContent = action === "create" || action === "duplicate" ? "Criando workflow inativo…" : "Consultando n8n…";
    try {
      const data = await request("/integrations/n8n/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          goal: goals[0] || goal,
          goals,
          workflow_id: workflowId,
          confirmed: ["create", "duplicate"].includes(action),
          template: byId("n8nWorkflowTemplate").value,
          config,
        }),
      });
      renderN8nWorkflowResult(data);
      setIntegrationFeedback(data.message || data.error || "Operação n8n concluída.", data.ok ? "success" : "error");
      recordIntegrationActivity("n8n", action, data);
    } catch {
      setIntegrationFeedback("A conexão com o núcleo caiu durante a operação n8n.", "error");
      recordIntegrationActivity("n8n", action, { ok: false, error: "conexão com o núcleo interrompida" });
    } finally {
      button.disabled = false;
    }
  }

  function signalUltron(reason = "response") {
    if (!session.paired) return;
    window.clearTimeout(ultronSignalTimer);
    stage.dataset.ultronSignal = reason;
    stage.classList.remove("ultron-signal");
    window.requestAnimationFrame(() => stage.classList.add("ultron-signal"));
    ultronSignalTimer = window.setTimeout(() => {
      stage.classList.remove("ultron-signal");
      delete stage.dataset.ultronSignal;
    }, 900);
  }

  function applyIdentityMode() {
    const name = assistantName();
    const ultron = session.paired;
    document.documentElement.dataset.persona = ultron ? "ultron" : "jarvis";
    document.title = `${name} · ${creatorName()}`;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", ultron ? "#190305" : "#130824");
    document.querySelector('meta[name="description"]')?.setAttribute("content", `${name}, criado por ${creatorName()}. Central pessoal de memória, automação e controle.`);
    document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute("content", name);
    byId("identityAssistantName").textContent = name;
    const identityRole = byId("identityCreator") || document.querySelector(".identity-name small");
    if (identityRole) identityRole.textContent = ultron ? `para ${creatorName()}` : `por ${creatorName()}`;
    window.JarvisCreator?.lock?.();
    byId("conversationAssistantName").textContent = name;
    byId("systemDialogTitle").textContent = `SISTEMA ${name}`;
    byId("installDialogTitle").textContent = `${name} NO CELULAR`;
    byId("tourIdentityDescription").textContent = `Escreva, fale ou anexe arquivos. O ${name} decide se responde, pesquisa, salva ou executa.`;
    byId("presence").setAttribute("aria-label", `Presença visual do ${name}`);
    document.querySelector(".conversation")?.setAttribute("aria-label", `Conversa com ${name}`);
    document.querySelector(".scene-modes")?.setAttribute("aria-label", `Modos do ${name}`);
    byId("actionHub")?.setAttribute("aria-label", `Ações contextuais do ${name}`);
    input.setAttribute("aria-label", `Pedido para ${name}`);
    byId("ownerTokenInput")?.setAttribute("aria-label", `Token privado do ${name}`);
    if (!session.currentCommand) {
      byId("requestText").textContent = ultron
        ? "Dê a ordem. ULTRON escolhe a rota mais forte disponível."
        : "Fale naturalmente. O JARVIS escolhe as ferramentas por trás.";
    }
    renderMuteState();
    renderApiPower();
    renderIntegrationRegistry();
    window.dispatchEvent(new CustomEvent("jarvis-persona", { detail: { persona: ultron ? "ultron" : "jarvis" } }));
  }

  function formatSeen(value) {
    const stamp = Date.parse(value || "");
    if (!stamp) return "";
    const delta = Math.max(0, Date.now() - stamp);
    if (delta < 60_000) return "agora";
    if (delta < 3_600_000) return `${Math.floor(delta / 60_000)} min`;
    if (delta < 86_400_000) return `${Math.floor(delta / 3_600_000)} h`;
    return `${Math.floor(delta / 86_400_000)} d`;
  }

  function ownerToken() {
    try {
      return localStorage.getItem(OWNER_TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  function rememberLoginEnabled() {
    try { return localStorage.getItem(REMEMBER_KEY) !== "0"; } catch { return true; }
  }

  function setRememberLogin(on) {
    try { localStorage.setItem(REMEMBER_KEY, on ? "1" : "0"); } catch { /* ignore */ }
    const box = byId("rememberLogin");
    if (box) box.checked = Boolean(on);
  }

  function touchOwnerActivity() {
    try { localStorage.setItem(OWNER_IDLE_KEY, String(Date.now())); } catch { /* ignore */ }
  }

  function expireIdleOwnerSession() {
    if (!ownerToken()) return false;
    if (rememberLoginEnabled()) {
      touchOwnerActivity();
      return false;
    }
    let last = 0;
    try { last = Number(localStorage.getItem(OWNER_IDLE_KEY) || 0); } catch { last = 0; }
    if (!last || Date.now() - last < OWNER_IDLE_MS) {
      if (!last) touchOwnerActivity();
      return false;
    }
    try {
      localStorage.removeItem(OWNER_TOKEN_KEY);
      localStorage.removeItem(OWNER_IDLE_KEY);
    } catch { /* ignore */ }
    return true;
  }

  async function exitOwnerMode(trigger = null) {
    const control = trigger || byId("leaveOwnerMode");
    if (control) control.disabled = true;
    stopSpeechOutput();
    try {
      localStorage.removeItem(OWNER_TOKEN_KEY);
      localStorage.removeItem(OWNER_IDLE_KEY);
    } catch {
      byId("pairingHint").textContent = "Este navegador não permitiu encerrar a sessão local.";
      if (control) control.disabled = false;
      return;
    }
    byId("ownerTokenInput").value = "";
    session.paired = false;
    session.codeMode = false;
    session.accountName = "";
    session.canManageAccounts = false;
    applyIdentityMode();
    session.history = [];
    session.historyRestored = false;
    session.currentCommand = "";
    session.mission = null;
    session.responseState = "";
    session.attachments = [];
    byId("conversationMemoryValue").textContent = "sessão local";
    byId("contextCount").textContent = "0 turnos";
    setActionHub(false);
    renderAttachmentTray();
    clearAttachmentPreview();
    renderLiveCanvas({});
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
    { id: "n8n", label: "Criar workflow n8n", description: "Gerar e importar inativo pela API", command: "crie um workflow n8n para receber leads por webhook e preparar os dados", executor: "n8n", keywords: /n8n|workflow|fluxo|automa[cç]/i },
    { id: "github", label: "Inspecionar GitHub", description: "Conta autenticada no Mac", command: "mostre meus repositórios do GitHub", executor: "mac", keywords: /github|repo|c[oó]digo|pull/i },
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
    "Criar, listar e revisar workflows n8n inativos pela API oficial",
    "Usar chaves OpenRouter e ElevenLabs do cofre criptografado deste dispositivo",
    "Guardar memória confirmada e restaurar conversa privada",
    "Editar o próprio projeto; deploy só com pedido explícito",
  ];

  const STARTER_ACTIONS = {
    guest: [
      ["Pesquisar agora", "pesquise na web as notícias mais importantes de inteligência artificial hoje e cite as fontes"],
      ["Quem te criou?", "quem criou você"],
      ["Copiar relatório", "__copy_bug_report__"],
    ],
    code: [
      ["Abrir modo code", "abre o modo code"],
      ["Explicar este pedido", "explique como você construiria isso passo a passo, sem editar o Mac"],
      ["Limpar o chat", "limpa o chat"],
    ],
    owner: [
      ["Melhorar você", "melhore a interface e o modo visitante do jarvis e corrija o que estiver confuso"],
      ["Deploy e merge", "faça deploy e merge do que você melhorou no jarvis"],
      ["Resumo do meu dia", "me dê um resumo operacional do meu dia"],
    ],
  };

  function renderStarterActions() {
    const target = byId("starterActions");
    if (!target) return;
    const actions = session.paired ? STARTER_ACTIONS.owner : session.codeMode ? STARTER_ACTIONS.code : STARTER_ACTIONS.guest;
    target.innerHTML = actions.map(([label, command]) => (
      `<button type="button" data-starter-command="${escapeHtml(command)}">${escapeHtml(label)}</button>`
    )).join("");
    target.querySelectorAll("[data-starter-command]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.starterCommand === "__copy_bug_report__") {
          copyBugReport();
          return;
        }
        sendCommand(button.dataset.starterCommand || "");
      });
    });
  }

  function renderWelcomeState(note = "") {
    const defaultHint = session.paired
      ? "Dê a ordem. Eu escolho a rota mais forte disponível."
      : session.codeMode
        ? "Modo code ativo. Peça para construir; o Mac do Theo continua fechado."
        : "Visitante: converse e pesquise. Sem Mac e sem memória do Theo. Achou um bug? use Copiar relatório.";
    feed.innerHTML = (
      `<div class="welcome" id="welcomeMessage">`
      + `<strong>${session.paired ? "Diga. Eu assumo daqui." : "Estou aqui."}</strong>`
      + `<span id="welcomeHint">${escapeHtml(note || defaultHint)}</span>`
      + `<div class="starter-actions" id="starterActions" aria-label="Sugestões para começar"></div>`
      + `</div>`
    );
    stage.classList.remove("has-conversation");
    stage.classList.remove("spatial-result");
    setMobileChatExpanded(false);
    renderStarterActions();
  }

  async function startNewConversation(options = {}) {
    if (!options.force && (session.working || newConversationButton?.disabled)) return;
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
    writeLocalHistory();
    session.currentCommand = "";
    session.mission = null;
    session.responseState = "";
    session.attachments = [];
    renderAttachmentTray();
    clearAttachmentPreview();
    actionHubButton.classList.remove("has-context");
    byId("conversationMemoryValue").textContent = session.paired ? "0 turnos" : "sessão local";
    byId("contextCount").textContent = "0 turnos";
    byId("requestTitle").textContent = "Pronto para você";
    byId("requestText").textContent = session.paired
      ? "Dê a ordem. ULTRON escolhe a rota mais forte disponível."
      : "Fale naturalmente. O JARVIS escolhe as ferramentas por trás.";
    byId("sceneEyebrow").textContent = "SISTEMA ONLINE";
    byId("sceneMission").textContent = "Aguardando comando";
    byId("sceneDetail").textContent = "Núcleo pronto para conversar ou agir.";
    renderLiveCanvas({});
    renderWelcomeState(note);
    settleState();
    if (newConversationButton) {
      newConversationButton.disabled = false;
      newConversationButton.textContent = "Nova";
    }
    input.focus();
  }

  function setActionHub(open) {
    actionHub.hidden = !open;
    actionHubButton.setAttribute("aria-expanded", String(open));
    if (open) {
      actionHubButton.classList.remove("has-context");
      refreshPersonalOverview();
      if (mobileLayout.matches) input.blur();
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
    if (Array.isArray(data.actions) || Array.isArray(data.domains)) session.overview = data;
    const context = `${command || ""} ${data.intent || ""}`;
    const catalog = session.paired
      ? ACTION_CATALOG
      : ACTION_CATALOG.filter((item) => item.executor === "web" || item.executor === "jarvis");
    const source = session.paired && Array.isArray(session.overview?.actions) && session.overview.actions.length
      ? session.overview.actions.map((item) => ({
          ...item,
          keywords: ACTION_CATALOG.find((fallback) => fallback.id === item.id)?.keywords || /$^/,
        }))
      : catalog;
    const ranked = [...source].sort((left, right) => Number(right.keywords.test(context)) - Number(left.keywords.test(context)));
    const grid = byId("actionHubGrid");
    grid.innerHTML = ranked.map((item, index) => (
      `<button type="button" data-hub-command="${escapeHtml(item.command)}" class="${index < 2 ? "recommended" : ""}" ${item.available === false ? "data-locked=\"true\"" : ""}>`
      + `<i>${escapeHtml(index < 2 ? "SUGESTÃO" : item.executor || "AÇÃO")}</i>`
      + `<span>${escapeHtml(item.label)}<small>${escapeHtml(item.description || item.reason || "")}</small></span>`
      + `<b>${item.available === false ? "•" : "→"}</b></button>`
    )).join("");
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
        sendCommand(nextCommand);
      });
    });
    const domainCapabilities = Array.isArray(session.overview?.domains)
      ? session.overview.domains.map((item) => `${item.label}: ${item.status} · ${item.detail}`)
      : [];
    const guestCapabilities = [
      "Conversar e pesquisar na internet com fontes",
      "Falar e ouvir neste navegador",
      "Cada computador tem o próprio chat",
      "Sem Mac, sem memória do Theo, sem n8n",
      "Achou um bug: Copiar relatório e mandar pro Theo",
    ];
    byId("capabilityList").innerHTML = (session.paired && domainCapabilities.length ? domainCapabilities : session.paired ? CAPABILITIES : guestCapabilities)
      .map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    byId("hubWorkerValue").textContent = session.deviceOnline ? "conectado" : session.deviceBridge ? "offline" : "não configurado";
    byId("actionHubHint").textContent = data.job?.id
      ? "A ação foi enviada ao Mac. Aqui ficam os próximos comandos úteis."
      : data.agentic || data.executed_locally
        ? `${assistantName()} escolheu uma ferramenta real. Você pode encadear outra ação.`
        : session.paired
          ? "Escolha uma ação real ou continue conversando normalmente."
          : "Conversa e pesquisa são públicas; ações pessoais exigem o modo Ultron.";
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
    if (data.job?.id || data.agentic || data.executed_locally) setActionHub(true);
  }

  async function refreshPersonalOverview() {
    try {
      const data = await request("/personal-overview");
      session.overview = data;
      const summary = data.summary || {};
      session.deviceOnline = Boolean(summary.worker_online);
      byId("hubWorkerValue").textContent = session.paired
        ? session.deviceOnline ? "online" : "offline · aceita fila"
        : "modo Ultron necessário";
      byId("hubMemoryValue").textContent = summary.memory_count == null ? "privada" : `${summary.memory_count} registros`;
      byId("hubAgendaValue").textContent = summary.agenda_count == null ? "privada" : `${summary.agenda_count} pendentes`;
      byId("hubLastActionValue").textContent = summary.latest_action || "nenhuma execução registrada";
      byId("hubReadyValue").textContent = summary.ready_actions == null
        ? "entre no modo Ultron"
        : `${summary.ready_actions} disponíveis`;
      byId("actionHubOverview").textContent = identityText(data.message || "Central pessoal carregada.");
      updateActionHub(session.currentCommand, data);
      return data;
    } catch {
      byId("actionHubOverview").textContent = "O estado das conexões não respondeu agora; a conversa continua disponível.";
      return null;
    }
  }

  function restoreLocalConversation() {
    if (session.historyRestored && session.history.length) return;
    const rows = readLocalHistory();
    if (!rows.length) {
      session.historyRestored = true;
      return;
    }
    session.history = rows;
    session.historyRestored = true;
    if (byId("welcomeMessage")) {
      session.history.forEach((message) => {
        addMessage(message.content, message.role === "user" ? "user" : "jarvis");
      });
      feed.scrollTop = feed.scrollHeight;
    }
    byId("conversationMemoryValue").textContent = `${Math.ceil(session.history.length / 2)} turnos neste computador`;
    byId("contextCount").textContent = `${Math.ceil(session.history.length / 2)} turnos`;
  }

  async function restoreConversationHistory() {
    if (!session.paired || session.historyRestored) return;
    try {
      const data = await request("/conversation-history");
      if (data.ok && Array.isArray(data.messages) && data.messages.length) {
        session.history = data.messages.slice(-24);
        session.historyRestored = true;
        if (byId("welcomeMessage")) {
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
        writeLocalHistory();
      } else {
        restoreLocalConversation();
      }
    } catch {
      byId("conversationMemoryValue").textContent = "sincronização indisponível";
      restoreLocalConversation();
    }
  }

  async function syncConversationHistory() {
    writeLocalHistory();
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
    research: ["PESQUISA", "consultando fontes reais"],
    voice: ["VOZ", "preparando uma resposta natural"],
    planning: ["NÚCLEO", "organizando possibilidades"],
    forge: ["FORJA", "construindo e verificando"],
    speaking: ["RESPOSTA", "falando com você"],
    preview: ["ARQUIVO", "abrindo uma prévia"],
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
    research: ["⌕", "PESQUISA", "FONTES AO VIVO", "coletando evidências"],
    planning: ["◉", "NÚCLEO", "PLANEJAMENTO", "organizando possibilidades"],
    forge: ["◆", "FORJA", "CONSTRUÇÃO", "montando e verificando"],
    local: ["◆", "FORJA", "EXECUÇÃO", "worker local em atividade"],
    memory: ["◇", "MEMÓRIA", "ARQUIVO", "gravando contexto confirmado"],
    speaking: ["≈", "VOZ", "TRANSMISSÃO", "falando com você"],
    voice: ["≈", "VOZ", "SÍNTESE", "preparando áudio"],
    preview: ["▧", "ARQUIVO", "PRÉVIA", "preparando leitura"],
    response: ["✓", "RESULTADO", "CONCLUÍDO", "resposta disponível"],
    success: ["✓", "RESULTADO", "CONCLUÍDO", "ação confirmada"],
    error: ["!", "SISTEMA", "ATENÇÃO", "algo precisa ser revisto"],
    offline: ["×", "SISTEMA", "OFFLINE", "runtime indisponível"],
  };

  function setVisualState(state) {
    const normalized = state || "idle";
    const labels = normalized === "memory" && session.memoryViewing
      ? ["MEMÓRIA", "consultando conhecimento salvo"]
      : stateLabels[normalized] || stateLabels.idle;
    const [mode, label] = labels;
    stage.dataset.state = normalized;
    byId("modeLabel").textContent = mode;
    byId("stateLabel").textContent = label;
    byId("conversationState").textContent = label;
    const presentation = normalized === "memory" && session.memoryViewing
      ? ["◇", "MEMÓRIA", "NÚCLEO", "lendo contexto persistente"]
      : statePresentation[normalized] || statePresentation.idle;
    const [symbol, phase, presentedName, description] = presentation;
    const name = normalized === "idle" ? assistantName() : presentedName;
    byId("stateSymbol").textContent = symbol;
    byId("statePhase").textContent = phase;
    byId("stateName").textContent = name;
    byId("stateDescription").textContent = description;
    const activeMode = ["thinking", "planning", "research"].includes(normalized)
      ? "core"
      : ["forge", "local"].includes(normalized)
        ? "forge"
        : normalized === "memory" ? "memory" : "";
    document.querySelectorAll("[data-scene-mode]").forEach((item) => {
      item.classList.toggle("active", item.dataset.sceneMode === activeMode);
    });
    byId("sceneEyebrow").textContent = phase;
    byId("sceneDetail").textContent = description;
    byId("voiceLink").textContent = normalized === "listening"
      ? "recebendo voz"
      : normalized === "speaking"
        ? "transmitindo resposta"
        : session.voiceError
          ? session.voiceError
        : voiceSupport.input || session.elevenlabs
          ? "link disponível"
          : "indisponível neste navegador";
    const voiceLabel = voiceButton?.querySelector("b");
    const interrupting = session.speaking || session.voicePending;
    voiceButton?.classList.toggle("speaking", interrupting);
    if (voiceLabel) voiceLabel.textContent = session.listening ? "Parar" : interrupting ? "Interromper" : "Falar";
    if (voiceButton) {
      voiceButton.setAttribute("aria-label", session.listening ? "Parar escuta" : interrupting ? `Interromper ${assistantName()} e falar` : `Falar com ${assistantName()}`);
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

  function syncComposerAction() {
    const form = byId("commandForm");
    if (!form) return;
    const hasPayload = !!(input.value.trim() || session.attachments.length);
    form.dataset.hasPayload = String(hasPayload);
    sendButton.tabIndex = hasPayload ? 0 : -1;
    voiceButton.tabIndex = hasPayload ? -1 : 0;
    sendButton.setAttribute("aria-hidden", !hasPayload);
    voiceButton.setAttribute("aria-hidden", hasPayload);
  }

  function setWorking(value, state = "thinking") {
    session.working = value;
    if (value) session.workingState = state;
    sendButton.disabled = value;
    voiceButton.disabled = value || !voiceSupport.input;
    attachmentButton.disabled = value;
    const busyLabel = state === "forge" ? "Construindo" : state === "memory" ? "Gravando" : state === "research" ? "Pesquisando" : "Pensando";
    sendButton.textContent = "Enviar";
    sendButton.toggleAttribute("aria-busy", value);
    sendButton.setAttribute("aria-label", value ? `${busyLabel}. Aguarde.` : "Enviar pedido");
    syncComposerAction();
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
    updateShimmerLoader(elapsed);
  }

  const SHIMMER_STATES = {
    thinking: { labels: ["Analisando…", "Pensando…", "Revisando…"], icons: ["✦", "◆", "✶", "❋", "✸"], duration: 3000, tokenTarget: 0.16 },
    research: { labels: ["Pesquisando…", "Verificando…", "Sintetizando…"], icons: ["◈", "◉", "⬡", "⬢", "◍"], duration: 5200, tokenTarget: 0.8 },
    forge: { labels: ["Preparando…", "Construindo…", "Validando…"], icons: ["✦", "◆", "✶", "❋", "✸"], duration: 4400, tokenTarget: 0.92 },
    memory: { labels: ["Lendo…", "Organizando…", "Gravando…"], icons: ["◈", "◉", "⬡", "⬢", "◍"], duration: 3600, tokenTarget: 0.4 },
  };

  function updateShimmerLoader(elapsed, complete = false) {
    const config = SHIMMER_STATES[session.workingState] || SHIMMER_STATES.thinking;
    const progress = complete ? 1 : Math.min(0.96, elapsed / config.duration);
    const frame = Math.floor(elapsed / 850);
    byId("shimmerIcon").textContent = config.icons[frame % config.icons.length];
    byId("shimmerLabel").textContent = complete ? "Concluído" : config.labels[frame % config.labels.length];
    byId("shimmerPercent").textContent = `${Math.round(progress * 100)}%`;
    byId("shimmerTokens").textContent = `${(config.tokenTarget * progress).toFixed(1)}k`;
    byId("shimmerLoader")?.style.setProperty("--shimmer-progress", `${Math.round(progress * 100)}%`);
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
    updateShimmerLoader(0);
    updateProgressClock();
    updateShimmerLoader(performance.now() - session.workingStartedAt, true);
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

  function pulseForWorkingState(state) {
    if (state === "forge") return pulseNucleus("forge", "trabalho iniciado");
    if (state === "memory") return pulseNucleus("memory", "gravando");
    return pulseNucleus("core", "pensando");
  }

  function workingStateFor(command) {
    const text = String(command || "");
    if (/\b(?:guard(?:a|e|ar)|salv(?:a|e|ar)|memor(?:ize|izar)|lembre)\b.{0,80}\bmem[oó]ria\b|\bmem[oó]ria\b.{0,80}\b(?:guard(?:a|e|ar)|salv(?:a|e|ar))\b/i.test(text)) return "memory";
    if (/\b(?:pesquis\w*|busc\w*|procur\w*|investig\w*|not[ií]cias?|cota[cç][aã]o|mais recente)\b/i.test(text)) return "research";
    if (/\b(?:cri(?:a|e|ar)|constru(?:a|ir)|implement(?:a|e|ar)|edit(?:a|e|ar)|corrig(?:e|ir)|arrum(?:a|e|ar)|deploy|public(?:a|ar)|sub(?:a|ir)|automatiz(?:a|e|ar))\b/i.test(text)) return "forge";
    return "thinking";
  }

  // A coluna de núcleos é telemetria: cada um acende quando o evento dele
  // acontece de verdade — gravou memória, começou um deploy, está pensando.
  function pulseNucleus(nucleus, reason) {
    window.dispatchEvent(new CustomEvent("jarvis-nucleus-pulse", { detail: { nucleus, reason } }));
  }

  function nucleusForResult(data) {
    if (data?.intent === "memory_save" || data?.intent === "memory_view" || data?.mode === "memory") return "memory";
    if (data?.job?.id || data?.run?.id || data?.executed_locally || data?.provider === "n8n") return "forge";
    return "";
  }

  function responseVisualState(data) {
    const state = data?.visual_state || (data?.executed_locally ? "success" : "response");
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
      .replace(/(?:…|\.{3,})/g, ".")
      .replace(/\s+/g, " ")
      .trim();
    if (clean.length <= 520) return clean;
    const excerpt = clean.slice(0, 520);
    const naturalEnd = Math.max(excerpt.lastIndexOf(". "), excerpt.lastIndexOf("! "), excerpt.lastIndexOf("? "));
    return `${excerpt.slice(0, naturalEnd > 280 ? naturalEnd + 1 : 520).trim().replace(/[,:;\s]+$/, "")}.`;
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

  function speechChunks(value) {
    const clean = speechText(value);
    if (!clean) return [];
    return window.JarvisVoicePacing?.chunks?.(clean) || [clean];
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
    message.innerHTML = `<span>${messageHtml(identityText(text))}</span>${extraHtml}`;
    feed.appendChild(message);
    const visibleMessages = feed.querySelectorAll(".message");
    if (visibleMessages.length > MAX_VISIBLE_MESSAGES) {
      Array.from(visibleMessages).slice(0, visibleMessages.length - MAX_VISIBLE_MESSAGES).forEach((item) => item.remove());
    }
    feed.scrollTop = feed.scrollHeight;
    return message;
  }

  function setRequest(command) {
    byId("requestTitle").textContent = "Executando pedido";
    byId("requestText").textContent = command;
    byId("spokenCaption").textContent = compactCaption(command, "Entendi. Deixe comigo.");
    byId("sceneEyebrow").textContent = "MISSÃO ATIVA";
    byId("sceneMission").textContent = compactHudText(command, "Executando pedido");
    byId("sceneDetail").textContent = "Selecionando a melhor rota e acompanhando o resultado real.";
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
        if (session.attachments.length) renderFilePreview(session.attachments);
        else clearAttachmentPreview();
      });
    });
    syncComposerAction();
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

  async function addAttachments(files) {
    const selected = Array.from(files || []);
    const added = [];
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
    const selectedMemories = Number(data.memory_selection?.selected) || 0;
    if (selectedMemories) badges.push(`${selectedMemories} memórias relevantes`);
    if (data.mission?.protocol === "jarvis-mission/2") {
      const completed = data.mission.steps?.filter((step) => step.status === "succeeded").length || 0;
      const total = data.mission.steps?.length || 0;
      badges.push(`${completed}/${total} etapas`);
      details += `<section class="message-card mission-card"><strong>Missão</strong><p>${escapeHtml(data.mission.objective || "")}</p>${total ? `<ul>${data.mission.steps.map((step) => `<li data-status="${escapeHtml(step.status || "pending")}">${escapeHtml(step.label || step.id)}</li>`).join("")}</ul>` : ""}</section>`;
    }
    if (Array.isArray(data.sources) && data.sources.length) badges.push(`${data.sources.length} fontes`);
    details += renderSourceLinks(data.sources, true);
    if (Array.isArray(data.ui_cards) && data.ui_cards.length) {
      badges.push(`${data.ui_cards.length} resultado${data.ui_cards.length === 1 ? "" : "s"}`);
      details += data.ui_cards.slice(0, 2).map((card) => {
        const items = Array.isArray(card.items) ? card.items.slice(0, 6) : [];
        return `<section class="message-card"><strong>${escapeHtml(card.title || "Resultado")}</strong>${card.status ? `<small>${escapeHtml(card.status)}</small>` : ""}${card.subtitle ? `<p>${escapeHtml(card.subtitle)}</p>` : ""}${items.length ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}</section>`;
      }).join("");
    }
    const stream = data.event_stream;
    if (stream?.protocol === "jarvis-events/1" && Array.isArray(stream.events)) {
      badges.push(`${Number(stream.elapsed_ms) || 0} ms`);
      details += `<section class="message-events"><strong>Execução real</strong>${stream.events.slice(-5).map((event) => `<div><i data-status="${escapeHtml(event.status || "unknown")}"></i><span>${escapeHtml(event.label || event.type)}</span></div>`).join("")}</section>`;
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
    });
    if (context) message.insertAdjacentHTML("beforeend", context);
  }

  function renderLiveCanvas(data) {
    const empty = byId("canvasEmpty");
    const content = byId("canvasContent");
    let html = "";
    if (data.mission?.protocol === "jarvis-mission/2") {
      const evidence = data.mission.evidence || {};
      html += `<div class="canvas-mission"><div class="canvas-run-head"><b>MISSÃO · ${escapeHtml(data.mission.route || "núcleo")}</b><span>${escapeHtml(evidence.confidence || "pending")}</span></div><strong>${escapeHtml(data.mission.objective || "")}</strong>${(data.mission.steps || []).map((step, index) => `<div class="canvas-row" data-status="${escapeHtml(step.status || "pending")}"><i>${index + 1}</i><span>${escapeHtml(step.label || step.id)}<small>${escapeHtml(step.executor || "brain")}</small></span></div>`).join("")}</div>`;
    }
    html += renderSourceLinks(data.sources) + renderUICards(data.ui_cards) + renderEventStream(data.event_stream);
    if (data.memory_candidate || data.memory_suggestion) {
      const candidate = data.memory_candidate || { content: data.memory_suggestion };
      html += `<div class="canvas-row"><i>◇</i><span>Memória sugerida<small>${escapeHtml(candidate.kind || "learning")} · ainda não salva</small></span></div><div class="canvas-result">${escapeHtml(candidate.content || data.memory_suggestion)}${candidate.reason ? `<small>${escapeHtml(candidate.reason)}</small>` : ""}</div>`;
    }
    else if (Array.isArray(data.jobs) && data.jobs.length > 1) {
      const completed = Number(data.run?.completed) || 0;
      html += `<div class="canvas-run-head"><b>EXECUÇÃO NO MAC</b><span>${completed}/${data.jobs.length} confirmadas</span></div>`;
      html += data.jobs.slice(0, 6).map((job, index) => {
        const target = job.target ? ` · ${job.target}` : "";
        return `<div class="canvas-row" data-status="${escapeHtml(job.status || "pending")}"><i>${index + 1}</i><span>${escapeHtml(job.action || "ação")}${escapeHtml(target)}<small>${escapeHtml(job.status || "pending")}</small></span></div>`;
      }).join("");
      const artifact = data.jobs.find((job) => job?.artifact_url);
      if (artifact) {
        html += `<a class="artifact-link" href="${escapeHtml(artifact.artifact_url)}" target="_blank" rel="noopener noreferrer"><img class="artifact-preview" src="${escapeHtml(artifact.artifact_url)}" alt="Evidência criada durante a execução no Mac"></a>`;
      }
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
      byId("sceneMac").textContent = worker.online ? "Mac conectado" : "Mac offline";
      await refreshActionHistory({ revealLatest: true });
    } catch {
      session.deviceOnline = false;
      target.textContent = "Mac offline · verificação indisponível";
      byId("hubWorkerValue").textContent = "offline";
      byId("sceneMac").textContent = "Mac offline";
    }
  }

  async function request(path, options) {
    const requestOptions = { ...(options || {}) };
    const headers = new Headers(requestOptions.headers || {});
    const token = ownerToken();
    if (token) headers.set("X-Jarvis-Owner-Token", token);
    const conversationId = conversationSessionId();
    if (conversationId) headers.set("X-Jarvis-Conversation-Id", conversationId);
    requestOptions.headers = headers;
    if (!requestOptions.signal && typeof window.AbortSignal?.timeout === "function") {
      requestOptions.signal = window.AbortSignal.timeout(path === "/command" ? 45000 : 20000);
    }
    let last = { ok: false, error: "Sem rede. Tente de novo.", retryable: true };
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const response = await fetch(path, requestOptions);
        let data;
        try {
          data = await response.json();
        } catch {
          data = { ok: false, error: "O runtime respondeu em um formato inválido." };
        }
        if (!response.ok && data.ok !== false) data.ok = false;
        if (response.status >= 500 && attempt === 0) {
          last = data;
          await new Promise((resolve) => window.setTimeout(resolve, 400));
          continue;
        }
        return data;
      } catch {
        if (attempt === 0) {
          await new Promise((resolve) => window.setTimeout(resolve, 400));
          continue;
        }
      }
    }
    return last;
  }

  function beginSpeaking(clean) {
    session.voicePending = false;
    session.speaking = true;
    byId("spokenCaption").textContent = compactCaption(clean);
    settleState();
  }

  function finishSpeaking() {
    session.speaking = false;
    voiceLevel = 0;
    window.dispatchEvent(new CustomEvent("jarvis-voice-level", { detail: { level: 0 } }));
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

  async function fetchSpeechChunk(text, generation, previousText = "", nextText = "") {
    const controller = new AbortController();
    currentSpeechController = controller;
    const persona = document.documentElement.dataset.persona || "jarvis";
    const localBlob = await window.JarvisLocalVoice?.speakBlob(text, { persona });
    if (generation !== speechGeneration) throw new DOMException("Speech stopped", "AbortError");
    if (localBlob) {
      session.localVoice = true;
      return localBlob;
    }
    const clientIntegrations = await runtimeClientIntegrations();
    const headers = { "Content-Type": "application/json" };
    const token = ownerToken();
    if (token) headers["X-Jarvis-Owner-Token"] = token;
    const response = await fetch("/speech", {
      method: "POST",
      headers,
      body: JSON.stringify({
        text,
        previous_text: previousText,
        next_text: nextText,
        voice_profile: window.JarvisVoiceCalibrator?.profile(),
        persona: document.documentElement.dataset.persona || "jarvis",
        client_integrations: clientIntegrations,
      }),
      signal: controller.signal,
    });
    if (generation !== speechGeneration) throw new DOMException("Speech stopped", "AbortError");
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      throw new Error(failure.error_code || "elevenlabs_unavailable");
    }
    return response.blob();
  }

  function playSpeechChunk(blob, text, generation, onPlay = null) {
    return new Promise((resolve, reject) => {
      if (generation !== speechGeneration) return resolve(false);
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      let stopMeter = () => {};
      try {
        voiceAudioContext ||= new (window.AudioContext || window.webkitAudioContext)();
        const analyser = voiceAudioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.82;
        const source = voiceAudioContext.createMediaElementSource(audio);
        source.connect(analyser);
        analyser.connect(voiceAudioContext.destination);
        const samples = new Uint8Array(analyser.fftSize);
        let meterFrame = 0;
        const meter = () => {
          analyser.getByteTimeDomainData(samples);
          let sum = 0;
          samples.forEach((sample) => { const value = (sample - 128) / 128; sum += value * value; });
          voiceLevel += (Math.min(1, Math.sqrt(sum / samples.length) * 5.2) - voiceLevel) * 0.28;
          window.dispatchEvent(new CustomEvent("jarvis-voice-level", { detail: { level: voiceLevel } }));
          meterFrame = window.requestAnimationFrame(meter);
        };
        meterFrame = window.requestAnimationFrame(meter);
        stopMeter = () => window.cancelAnimationFrame(meterFrame);
      } catch {
        // Mantém a presença sincronizada com a reprodução mesmo sem Web Audio.
        let meterFrame = 0;
        const fallbackMeter = (time) => {
          if (generation !== speechGeneration || audio.paused || audio.ended) return;
          const pulse = 0.24 + (0.5 + 0.5 * Math.sin(time * 0.013)) * 0.3;
          voiceLevel += (pulse - voiceLevel) * 0.22;
          window.dispatchEvent(new CustomEvent("jarvis-voice-level", { detail: { level: voiceLevel } }));
          meterFrame = window.requestAnimationFrame(fallbackMeter);
        };
        audio.addEventListener("play", () => {
          meterFrame = window.requestAnimationFrame(fallbackMeter);
        }, { once: true });
        stopMeter = () => window.cancelAnimationFrame(meterFrame);
      }
      let settled = false;
      const finish = (played) => {
        if (settled) return;
        settled = true;
        stopMeter();
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
        voiceAudioContext?.resume?.().catch(() => {});
        onPlay?.();
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
    muteButton.title = session.muted ? `Ativar a voz do ${assistantName()}` : `Mutar a voz do ${assistantName()}`;
  }

  // Voz degradada é um problema visível, não um detalhe silencioso.
  let voiceDowngradeShown = false;
  async function announceVoiceDowngrade() {
    if (voiceDowngradeShown) return;
    voiceDowngradeShown = true;
    let note = "A voz neural caiu; estou falando pelo navegador.";
    try {
      const status = await request("/voice-status");
      if (status?.message) {
        const resets = status.resets_at ? new Date(status.resets_at) : null;
        const when = resets && !Number.isNaN(resets.valueOf())
          ? ` Volta em ${resets.toLocaleDateString("pt-BR")}.`
          : "";
        note = `${status.message}${when}`;
      }
    } catch { /* sem diagnóstico, fica o aviso genérico */ }
    addMessage(note, "jarvis");
  }

  function reportVoiceFailure(status, terminal = false) {
    session.voiceError = status;
    if (terminal) session.elevenlabs = false;
    byId("voiceValue").textContent = status;
    byId("voiceLink").textContent = status.toLowerCase();
    byId("integrationValue").textContent = `IA · ${status}`;
    byId("integrationHint").textContent = "ElevenLabs falhou; a voz do navegador cobre enquanto isso.";
    announceVoiceDowngrade();
  }

  function speakBrowser(text, generation) {
    const synth = window.speechSynthesis;
    if (!synth || !text) return false;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "pt-BR";
    utterance.rate = 0.95;
    utterance.pitch = 0.72;
    utterance.onstart = () => {
      if (generation === speechGeneration) beginSpeaking(text);
    };
    utterance.onend = () => {
      if (generation === speechGeneration) finishSpeaking();
    };
    utterance.onerror = () => {
      if (generation === speechGeneration) finishSpeaking();
    };
    // O JARVIS é voz masculina, grave e firme: nada de voz feminina por acaso.
    const FEMALE_VOICES = /luciana|joana|maria|fernanda|catarina|helena|francisca|sandy|shelley|flo|grandma|karen|paulina|m[oó]nica|female|mulher/i;
    const MALE_VOICES = /reed|rocko|eddy|grandpa|felix|daniel|ricardo|felipe|jo[aã]o|carlos|thiago|male|homem/i;
    const pickVoice = () => {
      const voices = (synth.getVoices() || []).filter((voice) => /pt.?BR|portuguese/i.test(`${voice.lang} ${voice.name}`));
      const rank = (voice) => {
        const name = voice.name || "";
        const female = FEMALE_VOICES.test(name);
        const male = MALE_VOICES.test(name);
        let score = 0;
        if (male) score += 10;
        if (female) score -= 12;
        if (/premium|enhanced|siri|neural/i.test(name)) score += 4;
        if (/google/i.test(name)) score += 2;
        if (!voice.localService) score += 1;
        return score;
      };
      const best = voices.sort((a, b) => rank(b) - rank(a))[0];
      if (best) utterance.voice = best;
      synth.speak(utterance);
    };
    if (synth.getVoices().length) pickVoice();
    else synth.addEventListener("voiceschanged", pickVoice, { once: true });
    byId("voiceValue").textContent = "Voz do navegador";
    return true;
  }

  async function speak(text) {
    if (!text) return;
    const chunks = speechChunks(text);
    if (!chunks.length) return false;
    stopSpeechOutput();
    if (session.muted) return false;
    const generation = speechGeneration;
    session.voicePending = true;
    const voiceRequestedAt = performance.now();
    byId("spokenCaption").textContent = "Preparando voz…";
    settleState();
    let played = false;
    try {
      let prepared = fetchSpeechChunk(chunks[0], generation, "", chunks[1] || "")
        .then((blob) => ({ blob }))
        .catch((error) => ({ error }));
      for (let index = 0; index < chunks.length; index += 1) {
        const result = await prepared;
        if (result.error) throw result.error;
        if (generation !== speechGeneration) return false;
        prepared = index + 1 < chunks.length
          ? fetchSpeechChunk(
            chunks[index + 1],
            generation,
            chunks[index],
            chunks[index + 2] || "",
          ).then((blob) => ({ blob })).catch((error) => ({ error }))
          : null;
        const chunkPlayed = await playSpeechChunk(result.blob, chunks[index], generation, index === 0 ? () => {
          session.voiceFirstAudioMs = Math.max(1, Math.round(performance.now() - voiceRequestedAt));
          byId("voiceValue").textContent = session.localVoice
            ? `Pocket TTS · voz em ${session.voiceFirstAudioMs} ms`
            : `ElevenLabs · voz em ${session.voiceFirstAudioMs} ms`;
        } : null);
        if (generation !== speechGeneration) return false;
        played = played || chunkPlayed;
      }
      session.voiceError = "";
      voiceFailureNotified = false;
      if (generation === speechGeneration) finishSpeaking();
      if (played) return true;
      return speakBrowser(chunks.join(" "), generation);
    } catch (error) {
      if (error?.name === "AbortError") return false;
      if (generation === speechGeneration) {
        const errorCode = error?.message;
        const status = {
          elevenlabs_quota: "ElevenLabs sem créditos",
          elevenlabs_authorization: "ElevenLabs sem autorização",
          elevenlabs_rate_limit: "ElevenLabs no limite",
        }[errorCode] || "ElevenLabs indisponível";
        reportVoiceFailure(status, ["elevenlabs_quota", "elevenlabs_authorization"].includes(errorCode));
        return speakBrowser(chunks.join(" "), generation);
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

  window.JarvisVoicePreview = () => speak("Certo, Theo. Estou aqui e vou cuidar disso com calma.");

  const devicePollDelay = window.JarvisDeviceFeedback?.pollDelay || ((attempt) => Math.min(1200, 250 + (attempt * 190)));

  async function monitorDeviceCommand(jobId, message) {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      if (session.canceledJobs.has(String(jobId))) return;
      await new Promise((resolve) => window.setTimeout(resolve, devicePollDelay(attempt)));
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
      renderLiveCanvas(data);
      refreshMessageExecutionContext(message, data);
      byId("activityValue").textContent = `${data.message} · ação ${jobId}`;
      if (["succeeded", "failed", "canceled"].includes(data.job.status)) {
        const text = data.job.result ? `${data.message}\n${data.job.result}` : data.message;
        message.querySelector("span").textContent = text;
        message.classList.toggle("error", data.job.status === "failed");
        message.querySelector(".cancel-job")?.remove();
        session.responseState = data.visual_state || (data.job.status === "succeeded" ? "success" : "error");
        byId("requestTitle").textContent = data.job.status === "succeeded" ? "Ação concluída" : data.job.status === "canceled" ? "Ação cancelada" : "Ação falhou";
        refreshActionHistory();
        refreshPersonalOverview();
        settleState();
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
      await new Promise((resolve) => window.setTimeout(resolve, devicePollDelay(attempt)));
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
      renderLiveCanvas(data);
      refreshMessageExecutionContext(message, data);
      byId("activityValue").textContent = data.message;
      message.querySelector("span").textContent = data.message;
      if (data.run.terminal) {
        const failed = data.jobs.find((job) => job.status === "failed");
        if (failed?.result) message.querySelector("span").textContent = `${data.message}\n${failed.result}`;
        message.classList.toggle("error", data.run.status === "failed");
        message.querySelector(".cancel-run")?.remove();
        session.responseState = data.visual_state || (data.run.status === "succeeded" ? "success" : "error");
        byId("requestTitle").textContent = data.run.status === "succeeded" ? "Execução concluída" : data.run.status === "canceled" ? "Execução cancelada" : "Execução interrompida";
        refreshActionHistory();
        refreshPersonalOverview();
        settleState();
        if (data.run.status === "succeeded") speak(data.message);
        return;
      }
      session.responseState = "forge";
      settleState();
    }
    message.querySelector("span").textContent = "A execução continua registrada, mas o Mac não confirmou todas as etapas dentro do tempo de acompanhamento.";
  }

  function showResponse(data) {
    if (!data || data.ok === false) {
      stage.classList.remove("spatial-result");
      const error = data?.error || data?.message || "Não consegui completar isso.";
      session.lastError = error;
      session.responseState = "error";
      byId("sceneEyebrow").textContent = "ATENÇÃO";
      byId("sceneMission").textContent = compactHudText(error, "Execução interrompida");
      byId("sceneDetail").textContent = "O erro foi preservado sem inventar um resultado.";
      const message = addMessage(error, "error");
      if (data?.worker_offline) {
        window.JarvisDeviceFeedback?.mountOfflineActions({
          message,
          dialog,
          refresh: async () => {
            await refreshWorkerStatus(byId("workerValue"));
            return session.deviceOnline;
          },
          onConnected: () => {
            byId("sceneDetail").textContent = "Worker local reconectado e pronto para receber a ação.";
          },
        });
      }
      renderLiveCanvas({ message: error });
      settleState();
      if (!data?.worker_offline) speak(error);
      if (data?.pairing_required) {
        dialog.showModal();
        window.setTimeout(() => byId("adminPassword").focus(), 30);
      }
      return;
    }

    if (data.client_action === "clear_chat") {
      startNewConversation({ force: true }).catch(() => {
        renderWelcomeState("Nova conversa nesta tela; a limpeza remota não confirmou.");
      });
      return;
    }
    if (data.client_action === "open_voice_panel") {
      import("/ui/voice-calibrator.js?v=20260815-vozes2").catch(() => null);
    }
    if (data.client_action === "open_persona_panel") {
      openPersonaPanel();
    }
    if (data.client_action === "open_code_mode") {
      session.responseState = "forge";
      stage.classList.add("spatial-result");
    }
    if (data.client_action === "open_url" && data.open_url && !data.already_opened) {
      data.already_opened = Boolean(window.open(data.open_url, "_blank", "noopener,noreferrer"));
    }
    session.memoryViewing = data.intent === "memory_view" || data.mode === "memory";
    session.responseState = responseVisualState(data);
    stage.classList.add("spatial-result");
    session.mission = data.mission || null;
    const answer = identityText(data.message || data.summary || data.next_action || data.status_real || "Pronto.");
    const card = data.author_card;
    const authorHtml = card && card.photo
      ? `<a class="author-card" href="${escapeHtml(card.url)}" target="_blank" rel="noopener noreferrer">`
        + `<img src="${escapeHtml(card.photo)}" alt="Foto de ${escapeHtml(card.name)}" width="64" height="64">`
        + `<span><b>${escapeHtml(card.name)}</b><small>${escapeHtml(card.headline)}</small>`
        + `<em>${escapeHtml(card.city)} · LinkedIn</em></span></a>`
      : "";
    byId("sceneEyebrow").textContent = data.job?.id || data.executed_locally ? "AÇÃO CONFIRMADA" : "RESULTADO";
    byId("sceneMission").textContent = compactHudText(answer, "Resultado disponível");
    byId("sceneDetail").textContent = data.web_search?.used
      ? `${Number(data.web_search.source_count) || 0} fontes verificadas ao vivo.`
      : data.response_strength === "maximum"
        ? "Resposta processada com força máxima."
        : data.model_routing?.quality_tier === "quality_first"
        ? "Resposta processada pela rota de qualidade."
        : "Resposta pronta no canal principal.";
    let extra = "";
    let messageActions = `<button class="copy-response" type="button">Copiar</button>`;
    if (data.client_action === "open_url" && data.open_url) {
      messageActions += `<a class="open-link" href="${escapeHtml(data.open_url)}" target="_blank" rel="noopener noreferrer">Abrir</a>`;
    }
    if (data.status_real === "free_web_search_unavailable" && session.currentCommand) {
      messageActions += `<a class="open-link" href="https://www.google.com/search?q=${encodeURIComponent(session.currentCommand)}" target="_blank" rel="noopener noreferrer">Buscar no Google</a>`;
    }
    extra += renderMessageContext(data);
    if (data.memory_suggestion) {
      messageActions += `<button class="memory-command" type="button">${session.paired ? "Guardar na memória" : "Memória privada"}</button>`;
    }
    if (data.local_command) {
      messageActions += `<button class="copy-command" type="button">Copiar comando</button>`;
      extra += `<details><summary>ver comando local</summary><code>${escapeHtml(data.local_command)}</code></details>`;
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
    const message = addMessage(answer, "jarvis", authorHtml + extra);
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
        renderLiveCanvas(canceled);
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
    byId("requestTitle").textContent = data.memory_suggestion ? "Memória sugerida" : data.jobs?.length > 1 ? "Execução enviada ao Mac" : data.job?.id ? "Ação enviada ao Mac" : data.executed_locally ? "Ação local" : data.provider === "n8n" ? "Automação concluída" : "Resposta pronta";
    renderLiveCanvas(data);
    updateActionHub(session.currentCommand, data);
    const ultronMoment = data.persona?.id === "ultron_private"
      && (data.response_strength === "maximum" || data.executed_locally || data.external_processing || data.provider === "n8n");
    if (ultronMoment) signalUltron(data.executed_locally || data.provider === "n8n" ? "victory" : "response");
    if (Array.isArray(data.jobs) && data.jobs.length > 1 && !data.run?.terminal) {
      monitorDeviceRun(data.jobs.map((job) => job.id), message);
    } else if (data.job?.id && ["pending", "running"].includes(data.job.status)) {
      monitorDeviceCommand(data.job.id, message);
    }
    if (session.responseState === "memory") window.dispatchEvent(new CustomEvent("jarvis-memory-refresh"));
    const pulsed = nucleusForResult(data);
    if (pulsed) pulseNucleus(pulsed, data.intent || data.status_real || "resultado");
    settleState();
    speak(answer);
  }

  // Ele te vê chegar: se o cockpit ficou parado enquanto o Mac estava
  // bloqueado ou em outra aba, ele abre a conversa sozinho quando você volta.
  const ARRIVAL_AWAY_MS = 25 * 60 * 1000;
  const ARRIVAL_COOLDOWN_MS = 60 * 60 * 1000;
  const ARRIVAL_KEY = "jarvis-last-arrival";
  let awaySince = 0;

  function arrivalAllowed() {
    try {
      const last = Number(localStorage.getItem(ARRIVAL_KEY) || 0);
      return !last || Date.now() - last > ARRIVAL_COOLDOWN_MS;
    } catch {
      return true;
    }
  }

  function markArrival() {
    try {
      localStorage.setItem(ARRIVAL_KEY, String(Date.now()));
    } catch { /* sem storage, o cooldown vale só nesta aba */ }
  }

  async function greetOnArrival({ requested = false, reason = "", silent = false } = {}) {
    if (session.working || session.listening) return;
    if (!requested && !arrivalAllowed()) return;
    markArrival();
    pulseNucleus("core", reason || "chegada");
    if (reason === "boot") {
      const welcome = "Bem-vindo, Theo. Sistemas no ar. O que vamos fazer hoje?";
      addMessage(welcome, "jarvis");
      if (!silent) speak(welcome);
      if (session.paired) await sendCommand("me dê um resumo operacional do meu dia", { source: "arrival" });
      return;
    }
    if (session.paired) {
      await sendCommand("me dê um resumo operacional do meu dia", { source: "arrival" });
      return;
    }
    const hour = new Date().getHours();
    const greeting = hour < 5 ? "Boa madrugada" : hour < 12 ? "Bom dia" : hour < 19 ? "Boa tarde" : "Boa noite";
    const line = `${greeting}, Theo. Estava aqui. Diga o que precisa.`;
    addMessage(line, "jarvis");
    if (!silent) speak(line);
  }

  function watchArrival() {
    // O worker abre o cockpit com ?arrival=worker quando você desbloqueia o Mac.
    try {
      const params = new URLSearchParams(window.location.search);
      const arrival = params.get("arrival");
      if (arrival) {
        // O worker já falou pelo alto-falante do Mac: aqui só o texto.
        const silent = params.get("spoken") === "1";
        history.replaceState(null, "", window.location.pathname);
        window.setTimeout(() => greetOnArrival({ requested: true, reason: arrival, silent }), 900);
      }
    } catch { /* sem query string, segue o fluxo normal */ }
    const leaving = () => {
      if (!awaySince) awaySince = Date.now();
    };
    const returning = () => {
      const away = awaySince ? Date.now() - awaySince : 0;
      awaySince = 0;
      if (away >= ARRIVAL_AWAY_MS) greetOnArrival();
    };
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") leaving();
      else returning();
    });
    window.addEventListener("blur", leaving);
    window.addEventListener("focus", returning);
    // Máquina que dormiu com a aba visível: o relógio parado denuncia a ausência.
    let lastTick = Date.now();
    window.setInterval(() => {
      const now = Date.now();
      if (now - lastTick >= ARRIVAL_AWAY_MS && document.visibilityState === "visible") greetOnArrival();
      lastTick = now;
    }, 30_000);
  }

  function browserOpenFor(command) {
    const value = String(command || "").toLocaleLowerCase("pt-BR");
    if (session.paired && /\bspotify\b/.test(value)) return null;
    const google = value.match(/^(?:google|pesquisa no google|busca no google)\s+(.+)/);
    if (google) {
      return { url: `https://www.google.com/search?q=${encodeURIComponent(google[1])}`, label: "Google" };
    }
    if (!/\b(?:abre|abrir|abra|inici(?:a|e|ar))\b/.test(value)) return null;
    const targets = [
      [/\bwhatsapp\b/, "https://web.whatsapp.com", "WhatsApp"],
      [/\byoutube\b/, "https://www.youtube.com", "YouTube"],
      [/\bspotify\b/, "https://open.spotify.com", "Spotify"],
      [/\b(?:mapa|maps|como chegar)\b/, "https://maps.google.com", "Google Maps"],
      [/\bcalend[aá]rio|agenda\b/, "https://calendar.google.com", "Agenda"],
      [/\bgmail\b/, "https://mail.google.com", "Gmail"],
      [/\bgithub\b/, "https://github.com", "GitHub"],
      [/\bgoogle\b/, "https://www.google.com", "Google"],
    ];
    for (const [pattern, url, label] of targets) {
      if (pattern.test(value)) return { url, label };
    }
    return null;
  }

  async function sendCommand(rawValue, options = {}) {
    if (session.working) {
      input.focus();
      return;
    }
    const attachments = options.includeAttachments ? session.attachments.slice() : [];
    const command = String(rawValue || "").trim() || (attachments.length ? "Analise estes anexos." : "");
    if (!command) return;
    const localOpen = !attachments.length ? browserOpenFor(command) : null;
    if (localOpen && options.source !== "voice") {
      const popup = window.open(localOpen.url, "_blank", "noopener,noreferrer");
      addMessage(command, "user");
      input.value = "";
      syncComposerAction();
      syncComposerHeight();
      showResponse({
        ok: true,
        message: popup ? `Abrindo ${localOpen.label}.` : `O navegador bloqueou o popup. Toque em Abrir.`,
        client_action: "open_url",
        open_url: localOpen.url,
        already_opened: Boolean(popup),
      });
      return;
    }
    if (session.paired && window.JarvisFeatureLoader?.screenUnavailable(command, session.deviceOnline)) {
      addMessage(command, options.source === "voice" ? "user voice" : "user");
      input.value = "";
      syncComposerAction();
      syncComposerHeight();
      showResponse({ ok: false, worker_offline: true, error: "O Mac está offline. A captura não entrou na fila; ligue o worker e tente de novo." });
      return;
    }
    const permissionCategory = session.paired ? window.JarvisFeatureLoader?.categoryForCommand(command) : "";
    if (permissionCategory && !await window.JarvisFeatureLoader?.authorize(permissionCategory, command)) {
      addMessage("Ação cancelada pela política de permissões do Ultron.", "error");
      return;
    }
    session.responseState = "";
    stage.classList.remove("spatial-result");
    session.memoryViewing = false;
    session.currentCommand = command;
    const fileLabel = attachments.length ? `<small class="message-attachments">${attachments.map((item) => escapeHtml(item.name)).join(" · ")}</small>` : "";
    addMessage(command, options.source === "voice" ? "user voice" : "user", fileLabel);
    input.value = "";
    syncComposerAction();
    syncComposerHeight();
    session.history.push({ role: "user", content: command });
    session.history = session.history.slice(-24);
    writeLocalHistory();
    setRequest(command);
    if (session.paired && session.strength === "maximum") signalUltron("order");
    const workingState = workingStateFor(command);
    const reflectionStartedAt = performance.now();
    beginRequestProgress(workingState);
    pulseForWorkingState(workingState);
    setWorking(true, workingState);
    try {
      const clientIntegrations = await runtimeClientIntegrations(command);
      const commandBody = {
        command,
        messages: session.history,
        input_mode: options.source || "text",
        attachments,
        strength: session.paired && session.strength === "auto" ? "strong" : session.strength,
        persona_style: window.JarvisPersonaPanel?.current() || personaStyleFallback(),
        client_integrations: clientIntegrations,
      };
      let data = await request("/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(commandBody),
      });
      if (data?.retryable && /ocupad|fila/i.test(String(data.error || ""))) {
        renderOccupancy(data.occupancy);
        byId("conversationState").textContent = "na fila";
        await new Promise((resolve) => window.setTimeout(resolve, Math.max(2000, Number(data.queue?.retry_after || 3) * 1000)));
        data = await request("/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...commandBody, attachments: [] }),
        });
      }
      const minimumReflectionMs = data.mode === "memory" || data.intent === "memory_view_close"
        ? 100
        : ["research", "planning"].includes(workingState) ? 600 : 280;
      const remainingReflectionMs = minimumReflectionMs - (performance.now() - reflectionStartedAt);
      if (remainingReflectionMs > 0) {
        byId("conversationState").textContent = "revisando resposta";
        byId("stateDescription").textContent = "conferindo antes de entregar";
        await new Promise((resolve) => window.setTimeout(resolve, remainingReflectionMs));
      }
      if (attachments.length) {
        session.attachments = [];
        renderAttachmentTray();
        clearAttachmentPreview();
      }
      session.lastResponseOk = data?.ok !== false;
      renderOccupancy(data.occupancy);
      showResponse(data);
      if (data?.client_action === "clear_chat") return;
      const answer = data.message || data.summary;
      if (answer) {
        session.history.push({ role: "assistant", content: answer });
        session.history = session.history.slice(-24);
        window.setTimeout(syncConversationHistory, 0);
      }
    } catch {
      session.lastResponseOk = false;
      showResponse({ ok: false, error: `A conexão com o núcleo do ${assistantName()} caiu.` });
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
      syncComposerAction();
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
    installWakeWord();
  }

  // Personalidade: o painel é carregado sob demanda, mas o estilo escolhido
  // precisa viajar em todo pedido mesmo antes de alguém abrir o painel.
  function personaStyleFallback() {
    try {
      return localStorage.getItem("jarvis-persona-style-v1") || "padrao";
    } catch {
      return "padrao";
    }
  }

  function openPersonaPanel() {
    import("/ui/persona-panel.js?v=20260815-persona1")
      .then(() => window.JarvisPersonaPanel?.open())
      .catch(() => null);
  }

  // Chamar pelo nome, como a Siri: "oi jarvis", "bom dia jarvis", "fala ultron".
  const WAKE_CALL = "ei|ai|a[ií]|oi|ol[aá]|al[oô]|fala|falae|opa|psiu|escuta|escute|acorda|acorde|desperta|desperte|bom\\s*dia|boa\\s*tarde|boa\\s*noite|beleza|qual\\s*foi|e\\s*a[eií]|eae";
  const WAKE_NAME = "jarvis|j[aá]rvis|jarves|jarvi[sz]|javis|jarbis|ultron|ultr[oó]n|jar\\s*is";
  const WAKE_WORD = new RegExp(
    `\\b(?:${WAKE_CALL})\\s*[,!.]*\\s*(?:${WAKE_NAME})\\b`
    + `|^\\s*(?:${WAKE_NAME})\\b(?=[\\s,!?]|$)`
    + `|\\b(?:${WAKE_NAME})\\b[^.?!]{0,20}?\\b(?:t[aá]\\s+a[ií]|est[aá]\\s+a[ií]|acordado|escutando|me\\s+ouve|me\\s+escuta)`,
    "i",
  );
  // v2: a chave antiga ficou envenenada com "0" na primeira negativa do microfone.
  const WAKE_KEY = "jarvis-wake-word-v2";

  function wakeWordEnabled() {
    try {
      return localStorage.getItem(WAKE_KEY) !== "0";
    } catch {
      return true;
    }
  }

  function setWakeWord(enabled) {
    try {
      localStorage.setItem(WAKE_KEY, enabled ? "1" : "0");
    } catch { /* vale só nesta aba */ }
  }

  async function microphoneGranted() {
    try {
      const status = await navigator.permissions.query({ name: "microphone" });
      return status.state === "granted";
    } catch {
      return false;
    }
  }

  async function askMicrophone() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      return true;
    } catch {
      return false;
    }
  }

  function installWakeWord() {
    if (!Recognition) return;
    const badge = byId("wakeIndicator");
    const listener = new Recognition();
    listener.lang = "pt-BR";
    listener.interimResults = true;
    listener.continuous = true;
    let running = false;
    let blocked = false;
    let restartTimer = 0;
    let afterEnd = null;
    let commandUntil = 0;

    const paint = () => {
      if (!badge) return;
      const listening = commandUntil && Date.now() < commandUntil;
      const state = !wakeWordEnabled() ? "off" : blocked ? "blocked" : listening ? "command" : running ? "on" : "arming";
      badge.hidden = false;
      badge.dataset.state = state;
      badge.title = {
        on: "Escutando pelo nome. Diga \"oi Jarvis\" sem clicar em nada.",
        command: "Te ouvindo. Fale o pedido.",
        arming: "Preparando a escuta pelo nome…",
        blocked: "Microfone bloqueado. Clique para liberar e atender pelo nome.",
        off: "Escuta pelo nome desligada. Clique para ligar.",
      }[state];
    };

    // Nunca devolve sem reagendar: um ciclo ocupado não pode matar a escuta.
    const arm = (delay = 900) => {
      window.clearTimeout(restartTimer);
      restartTimer = window.setTimeout(async () => {
        if (!wakeWordEnabled()) return paint();
        if (running || session.listening || session.working) return arm(600);
        if (!(await microphoneGranted())) {
          blocked = true;
          return paint();
        }
        blocked = false;
        try {
          listener.start();
        } catch {
          arm(600);
        }
        paint();
      }, delay);
    };

    listener.onstart = () => { running = true; paint(); };
    listener.onend = () => {
      running = false;
      const pending = afterEnd;
      afterEnd = null;
      if (pending) pending();
      else if (wakeWordEnabled()) arm(250);
      paint();
    };
    listener.onerror = (event) => {
      // Negativa do microfone não desliga o recurso: ela só pede um clique.
      if (event.error === "not-allowed" || event.error === "service-not-allowed") blocked = true;
      paint();
    };
    // Depois de acordar, a próxima frase já é comando: nada de parar e
    // reabrir o microfone, que é o que fazia a chamada demorar.
    let lastFired = "";
    let lastFiredAt = 0;

    const fire = (text) => {
      const key = text.toLowerCase();
      // Resultados parciais repetem o mesmo trecho várias vezes.
      if (key === lastFired && Date.now() - lastFiredAt < 4_000) return;
      lastFired = key;
      lastFiredAt = Date.now();
      commandUntil = 0;
      paint();
      sendCommand(text, { source: "voice" });
    };

    listener.onresult = (event) => {
      const rows = Array.from(event.results).slice(event.resultIndex);
      const heard = rows.map((row) => row[0].transcript).join(" ").trim();
      const settled = rows.some((row) => row.isFinal);
      const strip = (text) => text.replace(WAKE_WORD, " ").replace(/\s+/g, " ").trim();

      if (commandUntil && Date.now() < commandUntil) {
        const order = strip(heard);
        if (settled && order.length > 2) fire(order);
        return;
      }
      if (!WAKE_WORD.test(heard)) return;
      pulseNucleus("core", "chamado");
      const rest = strip(heard);
      // "oi jarvis, abre o chrome" vai direto, sem esperar o microfone reabrir.
      if (rest.length > 3) return fire(rest);

      const reply = session.paired ? "Diga, Theo." : "Estou aqui.";
      addMessage(reply, "jarvis");
      speak(reply);
      commandUntil = Date.now() + 9_000;
      lastFired = heard.toLowerCase();
      lastFiredAt = Date.now();
      paint();
    };

    badge?.addEventListener("click", async () => {
      if (!wakeWordEnabled()) {
        setWakeWord(true);
        blocked = false;
        paint();
        arm(200);
        return;
      }
      if (blocked) {
        blocked = !(await askMicrophone());
        paint();
        if (!blocked) arm(200);
        return;
      }
      setWakeWord(false);
      if (running) listener.stop();
      paint();
    });

    window.addEventListener("jarvis-wake-word", (event) => {
      setWakeWord(Boolean(event.detail?.enabled));
      if (event.detail?.enabled) arm(300);
      else if (running) listener.stop();
      paint();
    });

    (async () => {
      paint();
      if (!wakeWordEnabled()) return;
      if (await microphoneGranted()) return arm(500);
      // Sem permissão ainda: o primeiro gesto na página serve de autorização.
      blocked = true;
      paint();
      const onGesture = async () => {
        if (await askMicrophone()) {
          blocked = false;
          arm(300);
        }
        paint();
      };
      window.addEventListener("pointerdown", onGesture, { once: true });
    })();

    window.JarvisWakeWord = Object.freeze({
      enabled: wakeWordEnabled,
      test: (phrase) => WAKE_WORD.test(String(phrase || "")),
      set: (value) => window.dispatchEvent(new CustomEvent("jarvis-wake-word", { detail: { enabled: value } })),
    });
  }

  async function boot() {
    try {
      expireIdleOwnerSession();
      const status = await request("/status");
      renderOccupancy(status.occupancy);
      byId("connectionDot").classList.toggle("online", Boolean(status.ok));
      byId("connectionText").textContent = status.ok ? "online" : "offline";
      byId("serviceValue").textContent = status.service || "jarvis-web";
      byId("modelValue").textContent = status.ai?.model || "—";
      session.paired = Boolean(status.owner_pairing?.authenticated || !status.owner_pairing?.required);
      session.codeMode = Boolean(status.access?.code || session.paired);
      session.accountName = status.access?.username || "";
      session.canManageAccounts = Boolean(status.access?.can_manage_accounts);
      if (session.paired) touchOwnerActivity();
      const crown = byId("crownButton");
      if (crown) {
        crown.hidden = !session.canManageAccounts;
        const pending = Number(status.access?.pending_accounts || 0);
        crown.dataset.count = pending > 0 ? String(pending) : "";
        crown.title = pending > 0 ? `${pending} conta(s) esperando aprovação` : "Contas do JARVIS";
      }
      const browserProviders = renderIntegrationRegistry();
      const browserOpenRouter = browserProviders.includes("openrouter");
      const browserN8n = browserProviders.includes("n8n");
      const toolCount = session.paired ? Number(status.agent_runtime?.available_tools) || 0 : 0;
      byId("aiValue").textContent = status.ai?.configured || browserOpenRouter
        ? `OpenRouter conectado${browserOpenRouter ? " · cofre local" : ""}${status.web_search?.configured ? " · web ao vivo" : ""}${toolCount ? ` · ${toolCount} ferramentas` : ""}`
        : "OpenRouter não configurado";
      byId("sceneBrain").textContent = status.ai?.configured || browserOpenRouter
        ? status.ai?.deep_model ? "IA adaptativa online" : "IA online"
        : "IA offline";
      const accessMode = session.paired ? "owner" : session.codeMode ? "member" : "guest";
      stage.dataset.access = accessMode;
      applyIdentityMode();
      const canLeaveOwnerMode = Boolean((session.paired || session.codeMode) && status.owner_pairing?.required);
      byId("accessModeLabel").textContent = canLeaveOwnerMode
        ? (session.paired ? "Sair do Ultron" : "Sair da conta")
        : session.paired
          ? "Theo · modo Ultron"
          : session.codeMode
            ? `${session.accountName || "conta"} · code`
            : "Entrar";
      byId("accessMode").dataset.action = canLeaveOwnerMode ? "logout" : "details";
      byId("accessMode").title = canLeaveOwnerMode
        ? "Voltar ao modo visitante"
        : session.paired ? "Ver detalhes do modo Ultron" : session.codeMode ? "Conta JARVIS · modo code" : "Entrar no modo Ultron";
      byId("leaveOwnerMode").hidden = !canLeaveOwnerMode;
      byId("leaveOwnerMode").textContent = session.paired ? "Sair do modo Ultron" : "Sair da conta";
      byId("accessValue").textContent = session.paired
        ? "Modo Ultron · memória, GitHub e Mac privados disponíveis"
        : session.codeMode
          ? "Conta JARVIS · modo code ativo. Mac e memória do Theo bloqueados."
          : status.access?.public_chat
            ? "Visitante · conversa liberada, memória e Mac privados"
            : "Visitante · conversa aguarda OpenRouter";
      const welcomeLogin = byId("welcomeLogin");
      if (welcomeLogin) welcomeLogin.hidden = Boolean(session.paired || session.codeMode);
      const welcomeHint = byId("welcomeHint");
      if (welcomeHint) {
        welcomeHint.textContent = session.paired
          ? "Dê a ordem. Eu escolho a rota mais forte disponível."
          : session.codeMode
            ? "Modo code ativo. Peça para construir; o Mac do Theo continua fechado."
            : "Visitante: converse e pesquise. Sem Mac e sem memória do Theo.";
      }
      renderStarterActions();
      session.deviceBridge = Boolean(status.device_bridge?.configured);
      session.elevenlabs = Boolean(status.voice?.configured || browserProviders.includes("elevenlabs"));
      session.localVoice = status.voice?.provider === "pocket_tts" || status.voice?.source === "self_hosted" || status.voice?.fallback === "self_hosted";
      session.voiceError = "";
      byId("voiceValue").textContent = status.voice?.provider === "elevenlabs"
        ? `ElevenLabs${voiceSupport.input ? " + microfone" : ""}`
        : session.localVoice
          ? `Pocket TTS · ${status.voice?.name || "rafael"}`
          : voiceSupport.input
            ? "microfone ativo · saída aguarda voz"
            : "voz aguarda motor local ou ElevenLabs";
      window.JarvisLocalVoice?.probe().then((base) => {
        if (!base) return;
        const info = window.JarvisLocalVoice.info();
        session.localVoice = true;
        const persona = document.documentElement.dataset.persona || "jarvis";
        const label = persona === "ultron" ? (info.ultronVoice || "javert") : (info.voice || "rafael");
        byId("voiceValue").textContent = `Pocket TTS · ${label}`;
      }).catch(() => {});
      const ready = [
        status.ai?.configured || browserOpenRouter ? (status.web_search?.configured ? "IA + pesquisa web" : toolCount ? `IA + ${toolCount} ferramentas` : "IA") : "",
        session.elevenlabs ? "ElevenLabs" : voiceSupport.input ? "microfone" : "",
        status.automations?.n8n?.configured || browserN8n ? "n8n" : "",
        browserProviders.length ? `${browserProviders.length} API(s) no cofre` : "",
        session.paired && status.device_bridge?.configured ? "Mac pareado" : "",
        status.runtime === "local_web_preview" ? "worker local" : "",
      ].filter(Boolean);
      byId("integrationValue").textContent = ready.join(" · ") || "sem integrações externas";
      byId("integrationHint").textContent = browserProviders.length
        ? `${browserProviders.length} integração(ões) protegida(s) neste dispositivo. ${session.paired ? "Ultron opera com orçamento 3×." : "JARVIS opera em 1×; ações externas protegidas pedem Ultron."}`
        : !status.web_search?.configured
        ? "Pesquisa ao vivo aguarda o OpenRouter; as demais integrações continuam independentes."
        : status.automations?.n8n?.configured || browserN8n
        ? "Pesquisa ao vivo e roteamento contextual ativos; agenda e tarefas estão conectadas ao n8n."
        : status.automations?.agenda?.provider === "supabase"
          ? "Pesquisa ao vivo ativa; memória e agenda ficam no Supabase e ações usam o worker local."
          : "Pesquisa ao vivo ativa; persistência aguarda Supabase ou n8n e o Mac usa o worker local.";
      byId("runtimeLabel").textContent = status.runtime === "local_web_preview" ? "Mac local" : "Vercel";
      const tokenInput = byId("ownerTokenInput");
      tokenInput.value = ownerToken();
      try {
        const remembered = localStorage.getItem(LAST_LOGIN_KEY);
        if (remembered && byId("adminUsername") && !session.paired && !session.codeMode) {
          byId("adminUsername").value = remembered;
        }
        setRememberLogin(rememberLoginEnabled());
      } catch { /* ignore */ }
      byId("adminUsername").closest(".admin-login").hidden = session.paired || session.codeMode;
      const rememberLabel = byId("rememberLoginLabel");
      if (rememberLabel) rememberLabel.hidden = session.paired || session.codeMode;
      const signupBox = byId("accountSignup");
      if (signupBox) signupBox.hidden = session.paired || session.codeMode;
      document.querySelector(".advanced-pairing").hidden = !status.owner_pairing?.required;
      byId("pairingHint").textContent = session.paired
        ? (rememberLoginEnabled()
          ? "Modo Ultron ativo neste aparelho. Fica conectado até você tocar em Sair."
          : "Modo Ultron ativo neste navegador. Sem “manter conectado”, a sessão cai após 12h parado.")
        : status.owner_pairing?.required
          ? status.owner_pairing?.admin_login_configured
            ? "Entre como admin para liberar memória, agenda, GitHub e ações no Mac."
            : "Login do modo Ultron ainda não configurado; use o pareamento avançado."
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
        byId("sceneMac").textContent = status.runtime === "local_web_preview"
          ? "Mac local"
          : session.paired ? "Mac não pareado" : "Mac privado";
      }
      setVisualState(status.ok ? "idle" : "offline");
      updateActionHub();
      if (session.paired) {
        await Promise.all([restoreConversationHistory(), refreshPersonalOverview()]);
      } else {
        restoreLocalConversation();
        refreshPersonalOverview();
      }
      refreshPulse();
      window.setInterval(() => {
        request("/presence").then((data) => renderOccupancy(data)).catch(() => null);
      }, 20000);
    } catch {
      byId("connectionText").textContent = "offline";
      session.responseState = "offline";
      settleState();
    }
  }

  function syncComposerHeight() {
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(120, Math.max(50, input.scrollHeight))}px`;
  }

  function clamp(value, min, max) {
    return Math.round(Math.min(max, Math.max(min, value)));
  }

  function applyConversationRect(rect, persist = true) {
    const panel = document.querySelector(".conversation");
    if (!panel || !rect) return;
    const minW = 320;
    const minH = 340;
    const topbar = 60;
    const width = clamp(rect.width, minW, window.innerWidth - 16);
    const height = clamp(rect.height, minH, window.innerHeight - topbar - 16);
    const left = clamp(rect.left, 8, Math.max(8, window.innerWidth - width - 8));
    const top = clamp(rect.top, topbar, Math.max(topbar, window.innerHeight - height - 8));
    panel.dataset.placed = "1";
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
    panel.style.width = `${width}px`;
    panel.style.height = `${height}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    panel.style.transform = "none";
    panel.style.setProperty("--conversation-left", `${left}px`);
    panel.style.setProperty("--conversation-top", `${top}px`);
    panel.style.setProperty("--conversation-width", `${width}px`);
    panel.style.setProperty("--conversation-height", `${height}px`);
    panel.style.setProperty("--conversation-transform", "none");
    panel.style.setProperty("--conversation-bottom", "auto");
    if (persist) {
      try {
        localStorage.setItem(CHAT_RECT_KEY, JSON.stringify({ left, top, width, height }));
      } catch { /* ignore */ }
    }
  }

  function defaultConversationRect() {
    // Painel à direita: o busto e os núcleos ficam livres à esquerda.
    const width = Math.min(Math.max(360, Math.round(window.innerWidth * 0.26)), 480, window.innerWidth - 32);
    const height = Math.min(Math.max(440, Math.round(window.innerHeight * 0.66)), 700, window.innerHeight - 96);
    return {
      width,
      height,
      left: Math.max(16, window.innerWidth - width - 28),
      top: Math.max(64, Math.round(window.innerHeight * 0.13)),
    };
  }

  function bindConversationResize() {
    const panel = document.querySelector(".conversation");
    if (!panel) return;
    let startX = 0;
    let startY = 0;
    let start = {};
    let edge = "";
    const pointOf = (event) => event.touches ? event.touches[0] : event;
    const onMove = (event) => {
      const point = pointOf(event);
      const dx = point.clientX - startX;
      const dy = point.clientY - startY;
      const next = { ...start };
      if (edge === "move") {
        next.left = start.left + dx;
        next.top = start.top + dy;
      } else {
        if (edge.includes("e")) next.width = start.width + dx;
        if (edge.includes("s")) next.height = start.height + dy;
        if (edge.includes("w")) {
          next.width = start.width - dx;
          next.left = start.left + dx;
        }
        if (edge.includes("n")) {
          next.height = start.height - dy;
          next.top = start.top + dy;
        }
      }
      applyConversationRect(next);
      event.preventDefault();
    };
    const onEnd = (event) => {
      panel.classList.remove("is-dragging");
      if (event?.pointerId != null) {
        try { event.target?.releasePointerCapture?.(event.pointerId); } catch { /* already released */ }
      }
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onEnd);
      window.removeEventListener("touchmove", onMove);
      window.removeEventListener("touchend", onEnd);
    };
    const begin = (nextEdge, event) => {
      if (event.button != null && event.button !== 0) return;
      const point = pointOf(event);
      const box = panel.getBoundingClientRect();
      edge = nextEdge;
      startX = point.clientX;
      startY = point.clientY;
      start = { left: box.left, top: box.top, width: box.width, height: box.height };
      panel.classList.add("is-dragging");
      if (event.pointerId != null) {
        try { event.currentTarget?.setPointerCapture?.(event.pointerId); } catch { /* Safari */ }
      }
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onEnd);
      window.addEventListener("touchmove", onMove, { passive: false });
      window.addEventListener("touchend", onEnd);
      event.preventDefault();
    };
    const startMove = (event) => {
      if (event.target.closest("a, input, textarea, .new-conversation-button, .mobile-chat-toggle")) return;
      begin("move", event);
    };
    panel.querySelector(".conversation-head")?.addEventListener("pointerdown", startMove);
    panel.querySelector(".conversation-head")?.addEventListener("touchstart", startMove, { passive: false });
    byId("conversationMove")?.addEventListener("pointerdown", (event) => begin("move", event));
    byId("conversationMove")?.addEventListener("touchstart", (event) => begin("move", event), { passive: false });
    panel.querySelectorAll(".conversation-edges [data-edge]").forEach((handle) => {
      handle.addEventListener("pointerdown", (event) => begin(handle.dataset.edge, event));
      handle.addEventListener("touchstart", (event) => begin(handle.dataset.edge, event), { passive: false });
    });
    window.addEventListener("resize", () => {
      const box = panel.getBoundingClientRect();
      applyConversationRect({ left: box.left, top: box.top, width: box.width, height: box.height }, false);
    });
    try {
      const saved = JSON.parse(localStorage.getItem(CHAT_RECT_KEY) || "null");
      if (saved && saved.width && saved.height) {
        applyConversationRect(saved, false);
        return;
      }
      applyConversationRect(defaultConversationRect(), false);
    } catch {
      applyConversationRect(defaultConversationRect(), false);
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
  input.addEventListener("input", () => {
    syncComposerAction();
    syncComposerHeight();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      byId("commandForm").requestSubmit();
    }
  });
  input.addEventListener("blur", () => window.setTimeout(syncMobileViewport, 80));
  bindConversationResize();
  watchArrival();
  syncComposerHeight();
  attachmentButton.addEventListener("click", () => attachmentInput.click());
  attachmentInput.addEventListener("change", () => addAttachments(attachmentInput.files));
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
    syncComposerAction();
    input.focus();
    try { localStorage.setItem("jarvis-last-pulse", currentPulse.id); } catch {}
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
    window.setTimeout(() => byId("adminPassword")?.focus(), 30);
    refreshActionHistory();
  });
  byId("welcomeLogin")?.addEventListener("click", () => {
    dialog.showModal();
    window.setTimeout(() => byId("adminPassword")?.focus(), 30);
  });
  integrationsButton?.addEventListener("click", async () => {
    renderIntegrationRegistry();
    integrationsDialog.showModal();
    await selectIntegrationProvider(activeIntegrationProvider);
  });
  byId("closeIntegrationsDialog")?.addEventListener("click", () => integrationsDialog.close());
  integrationsDialog?.addEventListener("click", (event) => {
    if (event.target === integrationsDialog) integrationsDialog.close();
  });
  integrationsDialog?.addEventListener("close", () => {
    integrationSecretVisible = false;
    byId("integrationFields")?.replaceChildren();
  });
  byId("integrationProviderList")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-provider]");
    if (button) selectIntegrationProvider(button.dataset.provider);
  });
  byId("integrationSaveButton")?.addEventListener("click", saveActiveIntegration);
  byId("integrationTestButton")?.addEventListener("click", testActiveIntegration);
  byId("integrationCopyButton")?.addEventListener("click", copyActiveIntegrationSecret);
  byId("integrationRemoveButton")?.addEventListener("click", removeActiveIntegration);
  byId("integrationRevealButton")?.addEventListener("click", toggleIntegrationSecret);
  byId("integrationToolSelect")?.addEventListener("change", renderIntegrationTool);
  byId("integrationToolRunButton")?.addEventListener("click", runActiveIntegrationTool);
  byId("integrationHistoryClear")?.addEventListener("click", () => {
    window.JarvisIntegrationHistory?.clear();
  });
  byId("n8nPreviewButton")?.addEventListener("click", () => runN8nWorkflowAction("preview"));
  byId("n8nCreateButton")?.addEventListener("click", () => runN8nWorkflowAction("create"));
  byId("n8nListButton")?.addEventListener("click", () => runN8nWorkflowAction("list"));
  byId("n8nWorkflowList")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-n8n-workflow-action]");
    if (!button) return;
    runN8nWorkflowAction(button.dataset.n8nWorkflowAction, button.dataset.workflowId || "");
  });
  qualityButton?.addEventListener("click", () => {
    const current = GRAPHICS_QUALITY.indexOf(graphicsQuality);
    graphicsQuality = GRAPHICS_QUALITY[(current + 1) % GRAPHICS_QUALITY.length];
    try { localStorage.setItem("jarvis-graphics-quality", graphicsQuality); } catch { /* session only */ }
    applyGraphicsQuality();
  });
  applyGraphicsQuality();
  strengthButton?.addEventListener("click", () => {
    const current = RESPONSE_STRENGTH.indexOf(session.strength);
    session.strength = RESPONSE_STRENGTH[(current + 1) % RESPONSE_STRENGTH.length];
    try { localStorage.setItem("jarvis-response-strength", session.strength); } catch { /* session only */ }
    renderStrength();
  });
  renderStrength();
  byId("adminLoginButton").addEventListener("click", async () => {
    const username = byId("adminUsername").value.trim();
    const password = byId("adminPassword").value;
    if (!username || !password) {
      byId("pairingHint").textContent = "Informe login e senha.";
      return;
    }
    byId("adminLoginButton").disabled = true;
    byId("pairingHint").textContent = "Validando login…";
    try {
      const data = await request("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!data.ok || !data.session_token) {
        byId("pairingHint").textContent = identityText(data.error || "Login recusado.");
        return;
      }
      localStorage.setItem(OWNER_TOKEN_KEY, data.session_token);
      try { localStorage.setItem(LAST_LOGIN_KEY, username); } catch { /* ignore */ }
      setRememberLogin(Boolean(byId("rememberLogin")?.checked));
      touchOwnerActivity();
      byId("adminPassword").value = "";
      session.historyRestored = false;
      await boot();
      if (session.paired || session.codeMode) dialog.close();
    } catch {
      byId("pairingHint").textContent = "Não consegui validar o login agora.";
    } finally {
      byId("adminLoginButton").disabled = false;
    }
  });
  byId("signupButton")?.addEventListener("click", async () => {
    const username = byId("signupUsername")?.value.trim();
    const password = byId("signupPassword")?.value;
    const email = byId("signupEmail")?.value.trim();
    const accepted = Boolean(byId("signupTerms")?.checked);
    if (!username || !password) {
      byId("pairingHint").textContent = "Crie um login e uma senha com pelo menos 8 caracteres.";
      return;
    }
    if (!accepted) {
      byId("pairingHint").textContent = "Aceite os termos de uso para criar a conta.";
      return;
    }
    byId("signupButton").disabled = true;
    byId("pairingHint").textContent = "Criando conta…";
    try {
      const data = await request("/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, email, accepted_terms: accepted }),
      });
      byId("pairingHint").textContent = identityText(data.error || data.message || "Conta enviada.");
      if (data.ok) {
        byId("signupPassword").value = "";
        byId("adminUsername").value = username;
      }
    } catch {
      byId("pairingHint").textContent = "Não consegui criar a conta agora.";
    } finally {
      byId("signupButton").disabled = false;
    }
  });

  async function refreshAccountsPanel() {
    const list = byId("accountsList");
    if (!list) return;
    const data = await request("/accounts");
    if (!data.ok) {
      list.innerHTML = `<small>${escapeHtml(data.error || "Não consegui ler as contas.")}</small>`;
      return;
    }
    list.innerHTML = (data.users || []).map((user) => {
      const actions = user.role === "owner"
        ? ""
        : `${user.role === "pending" ? `<button type="button" data-account-action="approve" data-username="${escapeHtml(user.username)}">Aprovar code</button>` : ""}`
          + `<button type="button" data-account-action="${user.disabled ? "enable" : "disable"}" data-username="${escapeHtml(user.username)}">${user.disabled ? "Ativar" : "Pausar"}</button>`
          + `<button type="button" data-account-action="delete" data-username="${escapeHtml(user.username)}">Apagar</button>`;
      return `<article class="account-row"><div><b>${escapeHtml(user.username)}</b><small>${escapeHtml(user.role)} · ${(user.access || []).join(", ") || "sem acesso"}${user.disabled ? " · pausada" : ""}${user.last_seen_at ? ` · visto ${escapeHtml(formatSeen(user.last_seen_at))}` : ""}</small></div><menu>${actions}</menu></article>`;
    }).join("") || "<small>Nenhuma conta ainda.</small>";
  }

  byId("crownButton")?.addEventListener("click", async () => {
    const panel = byId("accountsDialog");
    if (!panel) return;
    panel.showModal();
    await refreshAccountsPanel();
  });
  byId("closeAccountsDialog")?.addEventListener("click", () => byId("accountsDialog")?.close());
  byId("accountsList")?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-account-action]");
    if (!button) return;
    const data = await request("/accounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: button.dataset.accountAction, username: button.dataset.username }),
    });
    byId("accountsHint").textContent = identityText(data.error || data.status_real || "Conta atualizada.");
    await refreshAccountsPanel();
  });
  byId("adminPassword").addEventListener("keydown", (event) => {
    if (event.key === "Enter") byId("adminLoginButton").click();
  });
  ["signupUsername", "signupPassword", "signupEmail"].forEach((id) => {
    byId(id)?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") byId("signupButton")?.click();
    });
  });
  byId("saveOwnerToken").addEventListener("click", async () => {
    const token = byId("ownerTokenInput").value.trim();
    if (!token) {
      byId("pairingHint").textContent = "Cole o token privado antes de conectar.";
      return;
    }
    try {
      localStorage.setItem(OWNER_TOKEN_KEY, token);
      touchOwnerActivity();
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
  newConversationButton?.addEventListener("click", startNewConversation);
  document.querySelectorAll("[data-scene-mode]").forEach((item) => {
    item.setAttribute("role", "button");
    item.tabIndex = 0;
    const openScene = () => {
      const mode = item.dataset.sceneMode;
      if (mode === "forge" && !session.paired && !session.codeMode) {
        byId("pairingHint").textContent = "Entre com o login do Ultron ou crie conta para o modo code.";
        dialog.showModal();
        window.setTimeout(() => byId("adminPassword").focus(), 30);
        return;
      }
      if (mode === "memory" && !session.paired) {
        byId("pairingHint").textContent = "A memória privada pede o modo Ultron.";
        dialog.showModal();
        window.setTimeout(() => byId("adminPassword").focus(), 30);
        return;
      }
      const command = mode === "forge" ? "abre a forja" : mode === "memory" ? "abre a memória" : "abre o núcleo";
      sendCommand(command);
    };
    item.addEventListener("click", openScene);
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openScene();
      }
    });
  });
  byId("sceneCommandButton")?.addEventListener("click", () => setActionHub(true));
  mobileChatToggle?.addEventListener("click", () => {
    setMobileChatExpanded(mobileChatToggle.getAttribute("aria-expanded") !== "true");
  });
  installButton?.addEventListener("click", requestInstall);
  byId("closeInstallDialog")?.addEventListener("click", () => installDialog.close());
  installDialog?.addEventListener("click", (event) => {
    if (event.target === installDialog) installDialog.close();
  });
  byId("closeActionHub").addEventListener("click", () => setActionHub(false));
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
    window.clearTimeout(filePreviewTimer);
    byId("integrationFields")?.replaceChildren();
    stopSpeechOutput();
  }, { once: true });

  renderMuteState();
  syncComposerAction();
  applyIdentityMode();
  renderStarterActions();
  renderInstallAvailability();
  syncMobileViewport();
  registerMobileShell();
  installVoiceInput();
  boot();
  window.setInterval(refreshPulse, 10 * 60 * 1000);
  if (/[?&]debug=1(?:&|$)/.test(location.search)) {
    const box = document.createElement("pre");
    box.id = "jarvisDebug";
    box.style.cssText = "position:fixed;left:8px;bottom:8px;z-index:80;max-width:92vw;margin:0;font:11px/1.35 ui-monospace,monospace;background:#000c;color:#c4b5fd;padding:8px;border-radius:8px;white-space:pre-wrap";
    const paint = () => {
      const tts = window.JarvisLocalVoice?.info?.() || {};
      box.textContent = [
        "debug cockpit",
        `token ${ownerToken() ? "sim" : "não"}`,
        `remember ${rememberLoginEnabled() ? "sim" : "não"}`,
        `paired ${session.paired ? "ultron" : session.codeMode ? "code" : "visitante"}`,
        `tts ${tts.ok ? `${tts.engine || "ok"} ${tts.voice || ""}`.trim() : "offline"}`,
        `lastError ${session.lastError || "—"}`,
      ].join("\n");
    };
    document.body.appendChild(box);
    paint();
    window.setInterval(paint, 2000);
  }
})();
