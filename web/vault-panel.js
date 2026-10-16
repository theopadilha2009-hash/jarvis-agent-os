(() => {
  "use strict";

  // Painel BYOK do visitante: uma chave por provedor, guardada no navegador.
  // O segredo é selado pelo JarvisApiVault (AES-GCM, chave no IndexedDB);
  // o índice "jarvis-vault-v1" guarda só estado (conectado, data, máscara).
  const VAULT_STATE_KEY = "jarvis-vault-v1";
  const VAULT_PANEL_VERSION = "20261016-byok1";
  const CHAT_PROVIDER_IDS = ["openrouter", "anthropic", "openai"];
  const CHAT_PROVIDER_NAMES = { openrouter: "OpenRouter", anthropic: "Claude", openai: "OpenAI" };
  const VAULT_PROVIDERS = [
    {
      id: "openrouter",
      name: "OpenRouter",
      role: "CONVERSA",
      status: "active",
      placeholder: "sk-or-v1-…",
      hint: "Ativo: sua chave entra no corpo do pedido (client_integrations.openrouter) e é usada antes das chaves do servidor.",
    },
    {
      id: "elevenlabs",
      name: "ElevenLabs",
      role: "VOZ",
      status: "active",
      placeholder: "Chave da ElevenLabs",
      hint: "Ativo: sua chave vai em client_integrations.elevenlabs e alimenta a voz antes das chaves do servidor.",
    },
    {
      id: "anthropic",
      name: "Anthropic Claude",
      role: "CONVERSA",
      status: "pending",
      placeholder: "sk-ant-…",
      hint: "Guardada no seu navegador, mas o gateway ainda não aceita chave do navegador para Anthropic — reportado ao Theo.",
    },
    {
      id: "openai",
      name: "OpenAI",
      role: "VOZ RESERVA",
      status: "pending",
      placeholder: "sk-…",
      hint: "Guardada no seu navegador. Já vale para a voz reserva (OpenAI speech); para o chat, o gateway ainda usa OpenRouter.",
    },
  ];

  function readVaultState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(VAULT_STATE_KEY) || "{}");
      return parsed && parsed.version === 1 && parsed.providers && typeof parsed.providers === "object"
        ? parsed
        : { version: 1, providers: {} };
    } catch {
      return { version: 1, providers: {} };
    }
  }

  function writeVaultState(state) {
    try {
      localStorage.setItem(VAULT_STATE_KEY, JSON.stringify(state));
    } catch {
      // Sem localStorage (modo privado), o cofre segue funcionando em memória.
    }
  }

  function maskKey(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    return text.length > 12 ? `${text.slice(0, 5)}…${text.slice(-4)}` : "salva";
  }

  function markVaultProvider(id, config) {
    const state = readVaultState();
    if (config) {
      state.providers[id] = {
        connected: true,
        updatedAt: new Date().toISOString(),
        hint: maskKey(config.api_key),
      };
    } else {
      delete state.providers[id];
    }
    writeVaultState(state);
  }

  function vaultConfigured(id) {
    try {
      return Boolean(window.JarvisApiVault?.configured(id));
    } catch {
      return Boolean(readVaultState().providers[id]);
    }
  }

  function vaultFeedback(panel, message, state = "") {
    const target = panel.querySelector("[data-vault-feedback]");
    if (!target) return;
    target.textContent = message;
    target.dataset.state = state;
  }

  function renderVaultProviderCard(panel, definition) {
    const saved = vaultConfigured(definition.id);
    const pending = definition.status === "pending";
    const card = document.createElement("form");
    card.className = "vault-provider-card";
    card.dataset.provider = definition.id;
    card.dataset.status = pending ? "pending" : saved ? "connected" : "empty";
    card.setAttribute("aria-label", `${definition.name} · ${pending ? "aguardando gateway" : saved ? "conectado" : "não conectado"}`);

    const head = document.createElement("div");
    head.className = "vault-provider-head";
    const eyebrow = document.createElement("small");
    eyebrow.className = "vault-provider-role";
    eyebrow.textContent = definition.role;
    const title = document.createElement("b");
    title.textContent = definition.name;
    const badge = document.createElement("span");
    badge.className = "vault-badge";
    badge.dataset.state = pending ? "pending" : saved ? "connected" : "empty";
    badge.textContent = pending ? "inativo no gateway" : saved ? "conectado" : "não conectado";
    if (pending) badge.setAttribute("aria-disabled", "true");
    head.append(eyebrow, title, badge);

    const label = document.createElement("label");
    label.className = "vault-provider-field";
    label.htmlFor = `vault-key-${definition.id}`;
    label.textContent = pending ? "Chave (guardada para quando o gateway aceitar)" : "Chave do provedor";
    const input = document.createElement("input");
    input.id = `vault-key-${definition.id}`;
    input.name = "api_key";
    input.type = "password";
    input.autocomplete = "new-password";
    input.placeholder = definition.placeholder;
    input.setAttribute("aria-describedby", `vault-hint-${definition.id}`);
    label.appendChild(input);

    const hint = document.createElement("small");
    hint.className = "vault-provider-hint";
    hint.id = `vault-hint-${definition.id}`;
    hint.textContent = definition.hint;

    const actions = document.createElement("div");
    actions.className = "vault-provider-actions";
    const saveButton = document.createElement("button");
    saveButton.type = "submit";
    saveButton.className = "vault-button";
    saveButton.textContent = saved ? "Atualizar chave" : "Salvar chave";
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "vault-button vault-button-quiet";
    removeButton.textContent = "Remover";
    removeButton.disabled = !saved;
    removeButton.setAttribute("aria-label", `Remover chave ${definition.name}`);
    removeButton.addEventListener("click", () => {
      try {
        window.JarvisApiVault.remove(definition.id);
      } catch {
        // O estado local some mesmo se o cofre criptografado falhar.
      }
      markVaultProvider(definition.id, null);
      input.value = "";
      card.dataset.status = "empty";
      badge.dataset.state = "empty";
      badge.textContent = "não conectado";
      saveButton.textContent = "Salvar chave";
      removeButton.disabled = true;
      const testButton = actions.querySelector("button[data-vault-test]");
      if (testButton) testButton.disabled = true;
      vaultFeedback(panel, `${definition.name}: chave removida deste navegador.`);
      renderVaultHeaderButton();
    });
    actions.append(saveButton, removeButton);

    if (definition.status === "active") {
      const testButton = document.createElement("button");
      testButton.type = "button";
      testButton.className = "vault-button vault-button-quiet";
      testButton.setAttribute("data-vault-test", "");
      testButton.textContent = "Testar agora";
      testButton.disabled = !saved;
      testButton.setAttribute("aria-label", `Testar chave ${definition.name} no provedor`);
      testButton.addEventListener("click", async () => {
        let config = null;
        try {
          config = await window.JarvisApiVault.get(definition.id);
        } catch {
          config = null;
        }
        if (!config?.api_key) {
          vaultFeedback(panel, `${definition.name}: salve a chave antes de testar.`, "error");
          return;
        }
        testButton.disabled = true;
        vaultFeedback(panel, `Testando ${definition.name} direto no provedor…`);
        try {
          const response = await fetch("/integrations/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider: definition.id, config }),
          });
          const data = await response.json().catch(() => ({}));
          vaultFeedback(panel, data.message || data.error || "Teste concluído.", data.ok ? "success" : "error");
        } catch {
          vaultFeedback(panel, `O núcleo não respondeu ao testar ${definition.name}.`, "error");
        } finally {
          testButton.disabled = false;
        }
      });
      actions.appendChild(testButton);
    }

    card.append(head, label, hint, actions);
    card.addEventListener("submit", async (event) => {
      event.preventDefault();
      const apiKey = input.value.trim();
      if (apiKey.length < 8) {
        vaultFeedback(panel, `${definition.name}: cole a chave completa antes de salvar.`, "error");
        return;
      }
      saveButton.disabled = true;
      try {
        await window.JarvisApiVault.save(definition.id, { api_key: apiKey });
        markVaultProvider(definition.id, { api_key: apiKey });
        input.value = "";
        card.dataset.status = "connected";
        badge.dataset.state = "connected";
        badge.textContent = "conectado";
        saveButton.textContent = "Atualizar chave";
        removeButton.disabled = false;
        const testButton = actions.querySelector("button[data-vault-test]");
        if (testButton) testButton.disabled = false;
        vaultFeedback(
          panel,
          pending
            ? `${definition.name}: chave guardada neste navegador. Ela NÃO vai nos pedidos ainda — o gateway precisa aceitar o provedor.`
            : `${definition.name}: chave guardada neste navegador e ativa nos pedidos.`,
          pending ? "error" : "success",
        );
        renderVaultHeaderButton();
      } catch (error) {
        vaultFeedback(panel, error.message || `Não foi possível guardar a chave ${definition.name}.`, "error");
      } finally {
        saveButton.disabled = false;
      }
    });
    return card;
  }

  function ensureVaultStylesheet() {
    if (document.querySelector('link[href*="/ui/api-vault.css"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `/ui/api-vault.css?v=${VAULT_PANEL_VERSION}`;
    document.head.appendChild(link);
  }

  function buildVaultPanel() {
    const panel = document.createElement("dialog");
    panel.id = "jarvisVaultPanel";
    panel.className = "vault-panel-dialog";
    panel.setAttribute("aria-labelledby", "jarvisVaultPanelTitle");

    const head = document.createElement("div");
    head.className = "vault-panel-head";
    const title = document.createElement("b");
    title.id = "jarvisVaultPanelTitle";
    title.textContent = "MINHA IA · COFRE DE CHAVES";
    const subtitle = document.createElement("small");
    subtitle.textContent = "cada chave fica criptografada neste navegador; nada é gravado no servidor";
    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "vault-button vault-button-quiet";
    closeButton.textContent = "Fechar";
    closeButton.setAttribute("aria-label", "Fechar cofre de chaves");
    closeButton.addEventListener("click", () => panel.close());
    head.append(title, subtitle, closeButton);

    const grid = document.createElement("div");
    grid.className = "vault-provider-grid";
    VAULT_PROVIDERS.forEach((definition) => grid.appendChild(renderVaultProviderCard(panel, definition)));

    const foot = document.createElement("div");
    foot.className = "vault-panel-foot";
    const feedback = document.createElement("p");
    feedback.className = "vault-feedback";
    feedback.setAttribute("data-vault-feedback", "");
    feedback.setAttribute("aria-live", "polite");
    feedback.textContent = "Sem chave, a conversa usa as chaves livres do servidor e pode esbarrar em limite.";
    const advanced = document.createElement("button");
    advanced.type = "button";
    advanced.className = "vault-button vault-button-quiet";
    advanced.textContent = "Central completa (n8n, GitHub, Supabase)";
    advanced.setAttribute("aria-label", "Abrir central completa de integrações");
    advanced.addEventListener("click", () => {
      panel.close();
      document.getElementById("integrationsDialog")?.showModal();
    });
    foot.append(feedback, advanced);

    panel.append(head, grid, foot);
    panel.addEventListener("click", (event) => {
      if (event.target === panel) panel.close();
    });
    document.body.appendChild(panel);
    return panel;
  }

  function openVaultPanel() {
    ensureVaultStylesheet();
    const panel = document.getElementById("jarvisVaultPanel") || buildVaultPanel();
    if (!panel.open) panel.showModal();
  }

  function renderVaultHeaderButton() {
    const button = document.getElementById("integrationsButton");
    if (!button) return;
    const chatProvider = CHAT_PROVIDER_IDS.find((id) => vaultConfigured(id)) || "";
    let chip = button.querySelector(".vault-provider-chip");
    if (chatProvider && !chip) {
      chip = document.createElement("span");
      chip.className = "vault-provider-chip";
      button.prepend(chip);
    } else if (!chatProvider && chip) {
      chip.remove();
      chip = null;
    }
    if (chip) chip.textContent = `IA: ${CHAT_PROVIDER_NAMES[chatProvider] || chatProvider} · `;
    button.classList.toggle("vault-connected", Boolean(chatProvider));
    button.title = chatProvider
      ? `Sua chave de IA (${CHAT_PROVIDER_NAMES[chatProvider] || chatProvider}) está ativa · abrir cofre de APIs`
      : "Conectar minha IA · abrir cofre de APIs";
  }

  function mountVaultErrorShortcut(message) {
    if (!message || message.querySelector(".vault-error-cta")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "vault-error-cta";
    button.textContent = vaultConfigured("openrouter")
      ? "Revisar minha chave de IA no cofre"
      : "Conecte sua própria chave para continuar";
    button.setAttribute("aria-label", "Abrir cofre de chaves de IA");
    button.addEventListener("click", () => openVaultPanel());
    message.appendChild(button);
  }

  function watchVaultErrors() {
    const feed = document.getElementById("conversationFeed");
    if (!feed) return;
    const matches = (node) => node instanceof Element
      && node.classList.contains("message")
      && node.classList.contains("error")
      && /IA online ainda não está conectada|IA está ocupada com outro pedido|OpenRouter recusou a requisição|IA ainda não está conectada/i.test(node.textContent || "");
    feed.querySelectorAll(".message.error").forEach((message) => {
      if (matches(message)) mountVaultErrorShortcut(message);
    });
    new MutationObserver((records) => {
      records.forEach((record) => record.addedNodes.forEach((node) => {
        if (matches(node)) mountVaultErrorShortcut(node);
      }));
    }).observe(feed, { childList: true });
  }

  ensureVaultStylesheet();
  renderVaultHeaderButton();
  watchVaultErrors();
  window.JarvisVaultPanel = Object.freeze({ open: openVaultPanel });
})();
