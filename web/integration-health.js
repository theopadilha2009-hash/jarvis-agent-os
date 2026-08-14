"use strict";

window.JarvisIntegrationHealth = (() => {
  const byId = (id) => document.getElementById(id);
  const number = (value) => value === null || value === undefined || value === ""
    ? null
    : Number.isFinite(Number(value)) ? Number(value) : null;
  let runtime = null;

  if (!document.querySelector('link[data-jarvis-integration-health]')) {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/ui/integration-health.css?v=20260813-ultronfix1";
    stylesheet.dataset.jarvisIntegrationHealth = "true";
    document.head.appendChild(stylesheet);
  }

  function quotaLabel(health = {}) {
    const remaining = number(health.quota_remaining);
    const limit = number(health.quota_limit);
    const unit = String(health.quota_unit || "unidades").slice(0, 30);
    if (remaining === null && limit === null) return "Cota não informada";
    const compact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
    if (remaining !== null && limit !== null) return `${compact.format(Math.max(0, remaining))} / ${compact.format(limit)} ${unit}`;
    return `${compact.format(Math.max(0, remaining ?? limit))} ${unit}`;
  }

  function render(providers = [], configured = []) {
    const target = byId("integrationHealthGrid");
    if (!target) return;
    const configuredSet = new Set(configured);
    target.replaceChildren(...providers.map(({ id, label }) => {
      const summary = window.JarvisIntegrationHistory?.summary(id) || {};
      const card = document.createElement("article");
      const available = configuredSet.has(id);
      const state = !available ? "missing" : summary.ok === false ? "error" : summary.at ? "ok" : "unknown";
      card.className = "integration-health-card";
      card.dataset.state = state;
      const head = document.createElement("header");
      const name = document.createElement("strong");
      name.textContent = label;
      const status = document.createElement("b");
      status.textContent = { missing: "SEM CHAVE", error: "FALHA", ok: "ONLINE", unknown: "NÃO TESTADA" }[state];
      head.append(name, status);
      const metrics = document.createElement("div");
      const latency = document.createElement("span");
      latency.innerHTML = `<small>LATÊNCIA</small><b>${summary.latency_ms ? `${Math.round(summary.latency_ms)} ms` : "—"}</b>`;
      const quota = document.createElement("span");
      const safeQuota = document.createElement("b");
      quota.innerHTML = "<small>COTA</small>";
      safeQuota.textContent = summary.quota || "Cota não informada";
      quota.appendChild(safeQuota);
      metrics.append(latency, quota);
      const failure = document.createElement("p");
      failure.textContent = summary.last_failure
        ? `Última falha: ${summary.last_failure}`
        : available ? "Nenhuma falha registrada neste dispositivo." : "Configure esta API para medir a conexão.";
      card.append(head, metrics, failure);
      return card;
    }));
  }

  async function refresh() {
    if (!runtime) return;
    const { providers, vault, request, record } = runtime;
    const configured = vault.list().map((item) => item.provider);
    const button = byId("integrationHealthRefresh");
    const feedback = byId("integrationHealthFeedback");
    const ready = providers.filter(({ id }) => configured.includes(id));
    if (!ready.length) {
      feedback.textContent = "Configure ao menos uma API antes de medir.";
      render(providers, configured);
      return;
    }
    button.disabled = true;
    feedback.textContent = `Medindo ${ready.length} conexão(ões), uma por vez…`;
    for (const provider of ready) {
      const started = performance.now();
      let data;
      try {
        const config = await vault.get(provider.id);
        data = await request("/integrations/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: provider.id, config: config || {} }),
        });
      } catch (error) {
        data = { ok: false, error: error?.message || "teste interrompido" };
      }
      const health = data?.health || {};
      record(provider.id, "health_check", {
        ...data,
        latency_ms: Math.max(1, performance.now() - started),
        quota: quotaLabel(health),
      });
      render(providers, configured);
    }
    feedback.textContent = "Medição concluída. Nenhuma chave foi armazenada no histórico.";
    button.disabled = false;
  }

  function mount() {
    const target = byId("integrationHealthMount");
    if (!target || byId("integrationHealthGrid")) return;
    target.innerHTML = `
      <section class="integration-health-panel" aria-labelledby="integrationHealthTitle">
        <header class="integration-health-head">
          <span><small>TELEMETRIA LOCAL</small><strong id="integrationHealthTitle">Saúde das APIs</strong></span>
          <button type="button" id="integrationHealthRefresh">Medir configuradas</button>
        </header>
        <div class="integration-health-grid" id="integrationHealthGrid" aria-live="polite"></div>
        <p class="integration-health-feedback" id="integrationHealthFeedback">Latência, cota disponível e última falha aparecem após uma medição manual.</p>
      </section>`;
  }

  function rerender() {
    if (!runtime) return;
    let configured = [];
    try { configured = runtime.vault.list().map((item) => item.provider); } catch { configured = []; }
    render(runtime.providers, configured);
  }

  function bind() {
    runtime = {
      providers: [...document.querySelectorAll("[data-provider]")].map((item) => ({
        id: item.dataset.provider,
        label: item.querySelector("b")?.textContent || item.dataset.provider,
      })),
      vault: window.JarvisApiVault,
      record: (provider, action, data) => window.JarvisIntegrationHistory?.record(provider, action, data),
      request: async (path, options) => {
        const response = await fetch(path, { ...options, signal: AbortSignal.timeout?.(20_000) });
        const data = await response.json().catch(() => ({ ok: false, error: "resposta inválida" }));
        if (!response.ok && data.ok !== false) data.ok = false;
        return data;
      },
    };
    mount();
    byId("integrationHealthRefresh")?.addEventListener("click", refresh);
    window.addEventListener("jarvis-integration-registry", rerender);
    window.addEventListener("jarvis-integration-activity", rerender);
    rerender();
  }

  bind();
  return Object.freeze({ quotaLabel, render, refresh });
})();
